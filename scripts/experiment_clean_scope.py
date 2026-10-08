"""Recheck accepted A+B with/without alias rows; propose cleanup without writes."""

import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql

from rag_assistant import api, evaluate
from experiment_issue_collapse import collapse, summary


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ["tiangolo/fastapi", "encode/starlette", "pydantic/pydantic"]
ALIAS = "fastapi/fastapi"


def main():
    cases = evaluate.load_cases(ROOT / "evaluation/evaluation_cases.generated.jsonl")
    cache = json.loads((ROOT / ".question_embeddings.json").read_text())
    if cache["questions"] != {c["case_id"]: c["question"] for c in cases} or cache["model"] != "text-embedding-3-small":
        raise RuntimeError("Cache does not match cases")
    settings = api.get_settings()
    if set(settings["RAG_REPOSITORIES"]) != set(CLEAN):
        raise RuntimeError("Configured production repositories differ from approved clean scope")
    cutoff = json.loads((ROOT / "docs/experiments/retrieval/confidence_calibration_results.json").read_text())["threshold_selection"]["recommended_threshold"]
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "ef_search": 100,
              "candidate_chunks": 30, "selected_issues": 5, "cutoff": cutoff,
              "openai_calls": 0, "cutoff_retuned": False, "production_repositories": settings["RAG_REPOSITORIES"],
              "case_results": {"Unfiltered A+B": [], "Clean A+B": []}}
    with psycopg.connect(**evaluate.database_options(settings)) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        report["counts"] = {
            "all_chunks": conn.execute("SELECT count(*) FROM public.github_issue_chunks").fetchone()[0],
            "clean_chunks": conn.execute("SELECT count(*) FROM public.github_issue_chunks WHERE repository=ANY(%s)", (CLEAN,)).fetchone()[0],
            "alias_issue_numbers": [r[0] for r in conn.execute("SELECT issue_number FROM public.github_issues_clean WHERE repository=%s ORDER BY issue_number", (ALIAS,)).fetchall()],
        }
        tables = conn.execute("SELECT table_name FROM information_schema.columns WHERE table_schema='public' AND column_name IN ('repository','issue_number') GROUP BY table_name HAVING count(DISTINCT column_name)=2 ORDER BY table_name").fetchall()
        report["alias_rows_by_issue_table"] = {
            name: conn.execute(sql.SQL("SELECT count(*) FROM public.{} WHERE repository=%s").format(sql.Identifier(name)), (ALIAS,)).fetchone()[0]
            for (name,) in tables
        }
        report["foreign_keys"] = conn.execute("SELECT conrelid::regclass::text, confrelid::regclass::text, pg_get_constraintdef(oid) FROM pg_constraint WHERE contype='f' AND (confrelid='public.github_issues_clean'::regclass OR confrelid='public.github_issue_chunks'::regclass)").fetchall()
        report["matching_canonical_issues"] = conn.execute("SELECT count(*),count(*) FILTER (WHERE a.title=b.title AND a.body=b.body) FROM public.github_issues_clean a JOIN public.github_issues_clean b ON a.issue_number=b.issue_number WHERE a.repository=%s AND b.repository='tiangolo/fastapi'", (ALIAS,)).fetchone()
        for index, case in enumerate(cases, 1):
            for mode, repos in (("Unfiltered A+B", CLEAN + [ALIAS]), ("Clean A+B", CLEAN)):
                candidates = api.retrieve_chunks(conn, cache["vectors"][case["case_id"]], 30,
                                                 hnsw_ef_search=100, repositories=repos)
                assert all(c["repository"] in repos for c in candidates)
                chunks = collapse(candidates)
                metrics = evaluate.retrieval_case_metrics(case, chunks)
                report["case_results"][mode].append({
                    "case_id": case["case_id"], "question": case["question"],
                    "repository": case["expected_issues"][0]["repository"] if case["expected_issues"] else "unanswerable",
                    "answerable": metrics["applicable"], "metrics": metrics,
                    "score": api.retrieval_score(chunks), "refused": api.should_refuse(chunks, cutoff),
                    "unique_issues": len({(c["repository"], c["issue_number"]) for c in chunks}),
                    "context_characters": sum(len(c["chunk_text"]) for c in chunks), "human_verified": "",
                    "retrieved": [{k: c[k] for k in ("repository", "issue_number", "source_url", "chunk_type", "similarity_score")} for c in chunks],
                })
            if index % 10 == 0:
                print(f"Completed {index}/60 questions in both scopes", flush=True)
    report["summaries"] = {mode: {"overall": summary(rows), "by_repository": {
        repo: summary([r for r in rows if r["repository"] == repo]) for repo in CLEAN}}
        for mode, rows in report["case_results"].items()}
    before, after = report["case_results"].values()
    report["metric_changes"] = [{"case_id": a["case_id"], "before": b["metrics"], "after": a["metrics"]}
                                for b, a in zip(before, after) if b["metrics"] != a["metrics"]]
    report["refusal_changes"] = [a["case_id"] for b, a in zip(before, after) if b["refused"] != a["refused"]]
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    (ROOT / "docs/experiments/retrieval/clean_scope_experiment.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("counts", "alias_rows_by_issue_table", "foreign_keys", "summaries", "metric_changes", "refusal_changes")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
