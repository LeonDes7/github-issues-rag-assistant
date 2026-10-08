"""One authorized frozen-evidence replay, without retrieval or automatic retries."""
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from rag_assistant import api

ROOT = Path(__file__).resolve().parents[1]
CAP = Decimal("0.01090985")


def cost(inputs, outputs):
    return (Decimal(inputs) * Decimal("0.05") + Decimal(outputs) * Decimal("0.40")) / Decimal(1000000)


def main():
    preflight_raw = (ROOT / "docs/experiments/abstention/final_abstention_regression_preflight.json").read_bytes()
    prepared = json.loads(preflight_raw)
    baseline_raw = (ROOT / "docs/experiments/abstention/heldout_unanswerable_results.json").read_bytes()
    baseline = json.loads(baseline_raw)
    prior = [c for c in baseline["cases"] if not c["cutoff_refused"]]
    if hashlib.sha256(baseline_raw).hexdigest() != prepared["baseline_sha256"]:
        raise RuntimeError("Baseline changed")
    if hashlib.sha256(api.GROUNDED_ANSWER_PROMPT.encode()).hexdigest() != prepared["prompt_sha256"]:
        raise RuntimeError("Prompt changed")
    if len(prepared["cases"]) != 14 or len(prior) != 14:
        raise RuntimeError("Expected exactly fourteen prior passes")
    if hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest() != prepared["api_source_sha256"]:
        raise RuntimeError("API implementation changed")
    reservations = []
    for case, old in zip(prepared["cases"], prior):
        if case["case_id"] != old["case_id"] or case["evidence"] != old["evidence"] or case["question"] != old["question"]:
            raise RuntimeError("Frozen case changed")
        evidence = [{"citation": f"[{i}]", **{key: c[key] for key in (
            "repository", "issue_number", "issue_url", "source_url", "chunk_type", "similarity_score"
        )}, "excerpt": c["chunk_text"]} for i, c in enumerate(old["evidence"], 1)]
        expected = [{"role": "system", "content": api.GROUNDED_ANSWER_PROMPT.format(retrieved_chunks=json.dumps(evidence, ensure_ascii=False))},
                    {"role": "user", "content": old["question"]}]
        if case["messages"] != expected:
            raise RuntimeError("Frozen request changed")
        bound = sum(len(m["content"].encode("utf-8")) for m in expected) + 512
        reservations.append(cost(bound, 1200))
    if sum(reservations) > CAP:
        raise RuntimeError("Whole run exceeds approved cap")
    output = ROOT / "docs/experiments/abstention/final_abstention_regression_results.json"
    # Exclusive creation records the attempt before any paid call and prevents reruns.
    result = {"status": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "preflight_sha256": hashlib.sha256(preflight_raw).hexdigest(),
              "baseline_sha256": prepared["baseline_sha256"], "prompt_sha256": prepared["prompt_sha256"],
              "model": "gpt-5-nano", "reasoning_effort": "minimal", "completion_token_cap": 1200,
              "hard_budget_usd": str(CAP), "actual_token_cost_usd": "0", "generation_calls_attempted": 0,
              "generation_calls_completed": 0, "embedding_calls": 0, "database_calls": 0,
              "automatic_retries": 0, "cutoff": baseline["cutoff"], "retuned": False,
              "retrieval_settings": baseline["retrieval_settings"], "cases": [],
              "cost_note": "API-reported tokens at $0.05/$0.40 per million input/output; cached discounts ignored; not invoice reconciliation."}
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")
    def save():
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    load_dotenv(ROOT / ".env")
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], max_retries=0, timeout=90)
    spent = Decimal(0)
    try:
        for index, case in enumerate(prepared["cases"]):
            if spent + sum(reservations[index:]) > CAP:
                raise RuntimeError("Remaining reservations exceed approved cap")
            entry = {**case, "review_notes": "Pending citation-support review", "human_verified": ""}
            result["cases"].append(entry)
            result["generation_calls_attempted"] += 1
            save()
            response = client.chat.completions.create(
                model="gpt-5-nano", messages=case["messages"], reasoning_effort="minimal",
                max_completion_tokens=1200,
            )
            choice = response.choices[0]
            entry.update(raw_generated_answer=choice.message.content,
                         generated_answer=api.finalize_generated_answer(choice.message.content or "", [c["chunk_text"] for c in case["evidence"]]),
                         finish_reason=choice.finish_reason, response_model=response.model,
                         generation_usage=response.usage.model_dump(),
                         generation_cost_usd=str(cost(response.usage.prompt_tokens, response.usage.completion_tokens)))
            spent += Decimal(entry["generation_cost_usd"])
            result["actual_token_cost_usd"] = str(spent)
            result["generation_calls_completed"] += 1
            save()
            print(f'{index + 1}/14 {case["case_id"]}: {choice.finish_reason}; cumulative ${spent}', flush=True)
            if spent > CAP or choice.finish_reason != "stop" or not choice.message.content:
                raise RuntimeError("Budget or incomplete-response check failed; no retry")
        result["status"] = "completed_pending_review"
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    except Exception as exc:
        result["status"] = "stopped_no_retry"
        result["error_type"] = type(exc).__name__
        save()
        raise


if __name__ == "__main__":
    main()
