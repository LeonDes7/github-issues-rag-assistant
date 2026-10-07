"""Collect read-only evidence for baseline misses without OpenAI requests."""

import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from rag_assistant import api, evaluate


ROOT = Path(__file__).resolve().parents[1]


def main():
    cases = {c["case_id"]: c for c in evaluate.load_cases(ROOT / "evaluation_cases.generated.jsonl")}
    baseline = json.loads((ROOT / "retrieval_comparison_results.json").read_text())
    misses = [r for r in baseline["case_results"]["vector"] if r["retrieval_metrics"]["applicable"] and not r["retrieval_metrics"]["hit_at_k"]]
    output = []
    with psycopg.connect(**evaluate.database_options(api.get_settings()), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        for result in misses:
            case = cases[result["case_id"]]
            gold = case["expected_issues"][0]
            queries = conn.execute(
                "SELECT plainto_tsquery('english', %s)::text AS strict, "
                "websearch_to_tsquery('english', %s)::text AS websearch, "
                "(SELECT string_agg(quote_literal(term), ' | ' ORDER BY term) "
                "FROM unnest(tsvector_to_array(to_tsvector('english', %s))) AS terms(term)) AS loose",
                (case["question"],) * 3,
            ).fetchone()
            lexical = {}
            for mode, query in queries.items():
                ranked = conn.execute(
                    "SELECT chunk_id, repository, issue_number, chunk_type, source_url, "
                    "ts_rank_cd(search_vector, %s::tsquery) AS score "
                    "FROM public.github_issue_chunks WHERE search_vector @@ %s::tsquery "
                    "ORDER BY score DESC, chunk_id", (query or "",) * 2,
                ).fetchall()
                gold_matches = [(rank, chunk) for rank, chunk in enumerate(ranked, 1)
                                if chunk["repository"] == gold["repository"] and chunk["issue_number"] == gold["issue_number"]]
                lexical[mode] = {"query": query, "candidate_count": len(ranked), "top5": ranked[:5],
                                 "gold_best_chunk_rank": gold_matches[0][0] if gold_matches else None,
                                 "gold_best_chunk": gold_matches[0][1] if gold_matches else None}
            sources = []
            keys = {(gold["repository"], gold["issue_number"])} | {
                (r["repository"], r["issue_number"]) for r in result["retrieved_issues"]}
            for repo, number in sorted(keys):
                issue = conn.execute("SELECT repository, issue_number, title, body, github_url, comment_count FROM public.github_issues_clean WHERE repository=%s AND issue_number=%s", (repo, number)).fetchone()
                chunks = conn.execute("SELECT chunk_id, chunk_type, source_url, chunk_text FROM public.github_issue_chunks WHERE repository=%s AND issue_number=%s ORDER BY chunk_id", (repo, number)).fetchall()
                sources.append({"issue": issue, "chunks": chunks})
            output.append({"case_id": case["case_id"], "question": case["question"], "gold": gold,
                           "baseline_top5": result["retrieved_issues"], "lexical": lexical, "sources": sources})
            print(json.dumps({"case_id": case["case_id"], "question": case["question"], "gold": gold,
                              "top5": result["retrieved_issues"],
                              "lexical": {m: {k: v for k, v in r.items() if k in {"candidate_count", "gold_best_chunk_rank", "gold_best_chunk"}} for m, r in lexical.items()}}, default=str))
    (ROOT / "retrieval_miss_evidence.json").write_text(json.dumps(output, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
