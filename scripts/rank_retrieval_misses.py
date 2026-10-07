"""Rank missed gold chunks exactly; embedding creation requires explicit approval."""

import argparse
import json
from pathlib import Path

import psycopg
import tiktoken

from rag_assistant import api, evaluate


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".question_embeddings.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-embedding-run", action="store_true")
    args = parser.parse_args()
    cases = evaluate.load_cases(ROOT / "evaluation_cases.generated.jsonl")
    model = "text-embedding-3-small"
    if not CACHE.exists():
        if not args.approved_embedding_run:
            raise SystemExit("No cached embeddings. Obtain approval before using --approved-embedding-run.")
        inputs = [c["question"] for c in cases]
        tokens = sum(len(tiktoken.encoding_for_model(model).encode(q)) for q in inputs)
        if tokens > 2000:
            raise SystemExit("Input exceeds approved run token guard.")
        print(f"Embedding {tokens} tokens; estimate ${tokens * 0.02 / 1e6:.8f} at recorded repository rate; no retries.", flush=True)
        response = api.get_openai_client().with_options(max_retries=0).embeddings.create(
            model=model, input=inputs, dimensions=api.VECTOR_DIMENSIONS)
        vectors = {cases[item.index]["case_id"]: item.embedding for item in response.data}
        if len(vectors) != len(cases) or any(len(v) != api.VECTOR_DIMENSIONS for v in vectors.values()):
            raise RuntimeError("Incomplete embedding response")
        CACHE.write_text(json.dumps({"model": model, "input_tokens": response.usage.prompt_tokens,
                                     "estimated_cost_usd_at_recorded_rate": response.usage.prompt_tokens * 0.02 / 1e6,
                                     "questions": {c["case_id"]: c["question"] for c in cases}, "vectors": vectors}), encoding="utf-8")
    cache = json.loads(CACHE.read_text())
    if cache["model"] != model or cache["questions"] != {c["case_id"]: c["question"] for c in cases}:
        raise RuntimeError("Embedding cache does not match cases/model")
    evidence = json.loads((ROOT / "retrieval_miss_evidence.json").read_text())
    with psycopg.connect(**evaluate.database_options(api.get_settings())) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        for item in evidence:
            vector = json.dumps(cache["vectors"][item["case_id"]])
            gold = item["gold"]
            best = conn.execute(
                "SELECT chunk_id, chunk_type, source_url, embedding <=> %s::vector AS distance "
                "FROM public.github_issue_chunks WHERE repository=%s AND issue_number=%s "
                "AND embedding IS NOT NULL ORDER BY distance, chunk_id LIMIT 1",
                (vector, gold["repository"], gold["issue_number"]),
            ).fetchone()
            rank = conn.execute(
                "SELECT 1 + count(*) FROM public.github_issue_chunks WHERE embedding IS NOT NULL "
                "AND (embedding <=> %s::vector < %s OR "
                "(embedding <=> %s::vector = %s AND chunk_id < %s))",
                (vector, best[3], vector, best[3], best[0]),
            ).fetchone()[0] if best else None
            live = api.retrieve_chunks(conn, cache["vectors"][item["case_id"]], 5, hnsw_ef_search=40)
            item["exact_vector_gold_rank"] = rank
            item["exact_vector_gold_chunk"] = {"chunk_id": str(best[0]), "chunk_type": best[1],
                                                "source_url": best[2], "similarity": 1 - best[3]} if best else None
            item["live_vector_top5"] = [{k: r[k] for k in ("repository", "issue_number", "source_url", "chunk_type", "similarity_score")} for r in live]
            wider = api.retrieve_chunks(conn, cache["vectors"][item["case_id"]], 100, hnsw_ef_search=40)
            item["approximate_vector_gold_rank_with_limit_100"] = next(
                (r for r, chunk in enumerate(wider, 1) if chunk["repository"] == gold["repository"]
                 and chunk["issue_number"] == gold["issue_number"]), None)
            print(json.dumps({"case_id": item["case_id"], "exact_vector_gold_rank": rank, "best_chunk": item["exact_vector_gold_chunk"]}), flush=True)
    (ROOT / "retrieval_miss_evidence.json").write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
