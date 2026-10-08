"""Read-only lexical candidate check; makes no OpenAI calls or database writes."""

import json
from pathlib import Path

import psycopg

from rag_assistant import api, evaluate


def main():
    root = Path(__file__).resolve().parents[1]
    cases = evaluate.load_cases(root / "evaluation/evaluation_cases.generated.jsonl")
    with psycopg.connect(**evaluate.database_options(api.get_settings())) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        for case in cases:
            count = connection.execute(
                "SELECT count(*) FROM public.github_issue_chunks "
                "WHERE search_vector @@ plainto_tsquery('english', %s)",
                (case["question"],),
            ).fetchone()[0]
            print(json.dumps({"case_id": case["case_id"], "fts_matches": count}))
        for case in cases[:3]:
            print("FTS execution plan:", case["case_id"])
            plan = connection.execute(
                "EXPLAIN (ANALYZE, BUFFERS) SELECT chunk_id "
                "FROM public.github_issue_chunks "
                "WHERE search_vector @@ plainto_tsquery('english', %s) "
                "ORDER BY ts_rank_cd(search_vector, "
                "plainto_tsquery('english', %s)) DESC, chunk_id LIMIT 5",
                (case["question"], case["question"]),
            ).fetchall()
            print("\n".join(row[0] for row in plan))


if __name__ == "__main__":
    main()
