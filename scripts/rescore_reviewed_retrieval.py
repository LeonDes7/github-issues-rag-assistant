"""Author-approved retrieval rescore. Default is offline preflight; --execute makes calls."""

import argparse
import hashlib
import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import tiktoken

from rag_assistant import api, evaluate

ROOT = Path(__file__).resolve().parents[1]
MODEL = "text-embedding-3-small"
RATE = 0.02  # USD / million input tokens; standard embedding price
CONFIG = {
    "RAG_RETRIEVAL_MODE": "vector",
    "RAG_CONTEXT_MODE": "issues",
    "RAG_HNSW_EF_SEARCH": "100",
    "RAG_REPOSITORIES": "tiangolo/fastapi,encode/starlette,pydantic/pydantic",
    "RAG_CONFIDENCE_THRESHOLD": "0.5370554072220923",
    "OPENAI_EMBEDDING_MODEL": MODEL,
    "OPENAI_MAX_RETRIES": "0",
}


def summarize(rows):
    return {
        "cases": len(rows),
        "hit_at_5": statistics.mean(r["metrics"]["hit_at_k"] for r in rows),
        "recall_at_5": statistics.mean(r["metrics"]["recall_at_k"] for r in rows),
        "mrr": statistics.mean(r["metrics"]["mrr"] for r in rows),
        "hits": sum(r["metrics"]["hit_at_k"] for r in rows),
        "answerable_wrongly_refused": sum(r["refused"] for r in rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    path = ROOT / "evaluation/evaluation_cases.generated.jsonl"
    cases = [c for c in evaluate.load_cases(path) if not c["expected_abstain"]]
    if len(cases) != 44 or any(c["verification_status"] != "manually_verified" for c in cases):
        raise RuntimeError("Expected exactly 44 author-approved answerable cases")
    cache = json.loads((ROOT / ".question_embeddings.json").read_text())
    if cache["model"] != MODEL:
        raise RuntimeError("Wrong embedding cache model")
    missing = [c for c in cases if cache["questions"].get(c["case_id"]) != c["question"]
               or c["case_id"] not in cache["vectors"]]
    if [c["case_id"] for c in missing] != ["generated-pydantic-pydantic-11491"]:
        raise RuntimeError("Expected exactly one new embedding for the edited question")
    encoder = tiktoken.encoding_for_model(MODEL)
    tokens = sum(len(encoder.encode(c["question"])) for c in missing)
    if tokens != 13:
        raise RuntimeError("Edited question differs from approved 13-token estimate")
    preflight = {
        "answerable_cases": 44, "cached_embeddings": 43, "embedding_calls": 1,
        "generation_calls": 0, "judge_calls": 0, "estimated_input_tokens": tokens,
        "estimated_openai_cost_usd": tokens * RATE / 1_000_000,
        "production_config": CONFIG, "top_k": 5, "candidate_chunks": 30,
        "generated_cases_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    print(json.dumps(preflight, indent=2), flush=True)
    if not args.execute:
        return
    output = ROOT / "docs/experiments/retrieval/author_reviewed_rescore_results.json"
    if output.exists():
        raise RuntimeError("Results already exist; refusing to overwrite or repeat paid calls")
    os.environ.update(CONFIG)
    api.get_settings.cache_clear()
    settings = api.get_settings()
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "preflight": preflight,
              "cutoff_retuned": False, "database_read_only": True, "case_results": []}
    # Connect before spending; all retrieval uses the actual production context function.
    with psycopg.connect(**evaluate.database_options(settings)) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        from openai import OpenAI
        with OpenAI(api_key=settings["OPENAI_API_KEY"], max_retries=0, timeout=30) as client:
            response = client.embeddings.create(model=MODEL, input=missing[0]["question"])
        report["actual_embedding_usage"] = response.usage.model_dump()
        report["actual_openai_cost_usd"] = response.usage.total_tokens * RATE / 1_000_000
        report["openai_calls"] = 1
        vectors = dict(cache["vectors"])
        vectors[missing[0]["case_id"]] = response.data[0].embedding
        for vector in (vectors[c["case_id"]] for c in cases):
            if len(vector) != 1536:
                raise RuntimeError("Unexpected embedding dimensions")
        # Exclusive checkpoint prevents an accidental second call on rerun after a failure.
        with output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        for case in cases:
            chunks = api.retrieve_context(conn, vectors[case["case_id"]], 5,
                                          retrieval_mode="vector", context_mode="issues")
            report["case_results"].append({
                "case_id": case["case_id"], "question": case["question"],
                "repository": case["expected_issues"][0]["repository"],
                "human_verified": "yes", "metrics": evaluate.retrieval_case_metrics(case, chunks),
                "refused": api.should_refuse(chunks, settings["RAG_CONFIDENCE_THRESHOLD"]),
                "retrieved": [{key: c[key] for key in
                               ("repository", "issue_number", "source_url", "chunk_type", "similarity_score")}
                              for c in chunks],
            })
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    rows = report["case_results"]
    report["overall"] = summarize(rows)
    report["by_repository"] = {repo: summarize([r for r in rows if r["repository"] == repo])
                               for repo in sorted({r["repository"] for r in rows})}
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["overall"], indent=2))


if __name__ == "__main__":
    main()
