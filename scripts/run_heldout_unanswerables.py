"""Approved, budget-limited held-out replay; read-only database and fixed settings."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import tiktoken
from openai import OpenAI
from rag_assistant import api, evaluate

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = 0.537
OUTPUT_CAP = 1200


def allowed_call(spent, reserved_cost, budget):
    return spent + reserved_cost <= budget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-budget-usd", type=float, required=True)
    args = parser.parse_args()
    if not 0 < args.approved_budget_usd <= 0.02:
        raise RuntimeError("Budget must be positive and at most $0.02")
    output = ROOT / "heldout_unanswerable_results.json"
    cache_path = ROOT / ".heldout_question_embeddings.json"
    if output.exists() or cache_path.exists():
        raise RuntimeError("Existing output/cache: refusing automatic repeated paid run")
    cases_path = ROOT / "heldout_unanswerable_cases.jsonl"
    raw = cases_path.read_bytes()
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    preflight = json.loads((ROOT / "heldout_unanswerable_preflight.json").read_text(encoding="utf-8"))
    assert len(cases) == 15 and [c["question"] for c in cases] == [c["question"] for c in preflight["cases"]]
    settings = api.get_settings()
    for key, value in preflight["retrieval_settings"].items():
        if settings[key] != value:
            raise RuntimeError(f"Retrieval configuration changed: {key}")
    if settings["OPENAI_EMBEDDING_MODEL"] != "text-embedding-3-small":
        raise RuntimeError("Embedding model changed")
    result = {"started_at_utc": datetime.now(timezone.utc).isoformat(), "cases_sha256": hashlib.sha256(raw).hexdigest(), "cutoff": CUTOFF, "retuned": False, "retrieval_settings": preflight["retrieval_settings"], "budget_usd": args.approved_budget_usd, "generation_model": "gpt-5-nano", "completion_token_cap": OUTPUT_CAP, "embedding_calls": 0, "generation_calls": 0, "token_cost_usd_at_standard_rates": 0.0, "cost_note": "API-reported token usage at recorded standard rates ($0.02 embedding; $0.05 chat input/$0.40 output per million). Cached-input discounts are not applied; this is not invoice reconciliation.", "cases": []}

    def save():
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    client = OpenAI(api_key=settings["OPENAI_API_KEY"], max_retries=0, timeout=90)
    embedding_bound = sum(len(c["question"].encode("utf-8")) for c in cases) * 0.02 / 1e6
    if not allowed_call(0, embedding_bound, args.approved_budget_usd):
        raise RuntimeError("Embedding call would exceed budget")
    response = client.embeddings.create(model="text-embedding-3-small", input=[c["question"] for c in cases], dimensions=api.VECTOR_DIMENSIONS)
    vectors = [r.embedding for r in sorted(response.data, key=lambda r: r.index)]
    result["embedding_calls"] = 1
    result["embedding_usage"] = response.usage.model_dump()
    result["embedding_cost_usd"] = response.usage.total_tokens * 0.02 / 1e6
    question_tokens = [len(tiktoken.get_encoding("cl100k_base").encode(c["question"])) for c in cases]
    if sum(question_tokens) != response.usage.total_tokens:
        raise RuntimeError("Embedding token allocation does not match batch usage; cache/results require review")
    result["token_cost_usd_at_standard_rates"] = result["embedding_cost_usd"]
    cache_path.write_text(json.dumps({"cases_sha256": result["cases_sha256"], "model": "text-embedding-3-small", "vectors": vectors}) + "\n", encoding="utf-8")
    save()
    assert len(vectors) == 15 and all(len(v) == api.VECTOR_DIMENSIONS for v in vectors)
    with psycopg.connect(**evaluate.database_options(settings)) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for case, vector in zip(cases, vectors):
            chunks = api.retrieve_context(conn, vector, 5, retrieval_mode=settings["RAG_RETRIEVAL_MODE"], query_text=case["question"], context_mode=settings["RAG_CONTEXT_MODE"])
            score = api.retrieval_score(chunks)
            refused = api.should_refuse(chunks, CUTOFF)
            entry = {"case_id": case["case_id"], "repository": case["repository"], "question": case["question"], "provisional_expected_abstain": True, "rationale": case["unanswerable_rationale"], "score": score, "cutoff_refused": refused, "cutoff_decision": "refused" if refused else "passed", "evidence": [{"citation": f"[{i}]", **c} for i, c in enumerate(chunks, 1)], "generated_answer": None, "generation_cost_usd": 0.0, "generation_usage": None, "label_ambiguous": None, "model_abstained": None, "unsupported_answer": None, "review_notes": "Pending evidence review", "human_verified": ""}
            result["cases"].append(entry)
            entry["embedding_tokens"] = question_tokens[len(result["cases"]) - 1]
            entry["embedding_cost_allocation_usd"] = entry["embedding_tokens"] * 0.02 / 1e6
            save()
            if not refused:
                capture = MagicMock()
                capture.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content="Capture"))]
                api.generate_grounded_answer_with_usage(capture, "gpt-5-nano", case["question"], chunks)
                messages = capture.chat.completions.create.call_args.kwargs["messages"]
                # UTF-8 bytes conservatively bound text tokens; reserve ample framing overhead.
                input_bound = sum(len(m["content"].encode("utf-8")) for m in messages) + 512
                reserve = (input_bound * 0.05 + OUTPUT_CAP * 0.4) / 1e6
                entry["reserved_max_generation_cost_usd"] = reserve
                if not allowed_call(result["token_cost_usd_at_standard_rates"], reserve, args.approved_budget_usd):
                    result["stopped_reason"] = "Budget insufficient before generation; no call made"
                    save()
                    raise RuntimeError(result["stopped_reason"])
                chat = client.chat.completions.create(model="gpt-5-nano", messages=messages, reasoning_effort="minimal", max_completion_tokens=OUTPUT_CAP)
                result["generation_calls"] += 1
                choice = chat.choices[0]
                entry["raw_generated_answer"] = choice.message.content
                entry["generated_answer"] = api.clean_generated_answer(choice.message.content or "", [c["chunk_text"] for c in chunks])
                entry["finish_reason"] = choice.finish_reason
                entry["generation_usage"] = chat.usage.model_dump()
                entry["generation_cost_usd"] = (chat.usage.prompt_tokens * 0.05 + chat.usage.completion_tokens * 0.4) / 1e6
                result["token_cost_usd_at_standard_rates"] += entry["generation_cost_usd"]
                save()
                if choice.finish_reason != "stop" or not choice.message.content:
                    raise RuntimeError("Incomplete answer saved; no automatic retry")
            print(case["case_id"], round(score, 6), entry["cutoff_decision"], flush=True)
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["cutoff_summary"] = {"refused": sum(c["cutoff_refused"] for c in result["cases"]), "passes": sum(not c["cutoff_refused"] for c in result["cases"])}
    save()
    print(json.dumps({k: result[k] for k in ("cutoff_summary", "embedding_calls", "generation_calls", "token_cost_usd_at_standard_rates")}, indent=2))


if __name__ == "__main__":
    main()
