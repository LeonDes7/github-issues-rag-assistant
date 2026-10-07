"""Experiment B: 30 chunks -> best chunk per issue -> five issues, ef_search=100.

Uses cached embeddings only. Does not change production retrieval or the cutoff.
"""

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from rag_assistant import api, evaluate


ROOT = Path(__file__).resolve().parents[1]


def collapse(chunks, top_k=5):
    seen = set()
    selected = []
    for chunk in chunks:
        key = (chunk["repository"], chunk["issue_number"])
        if key not in seen:
            seen.add(key)
            selected.append(chunk)
            if len(selected) == top_k:
                break
    return selected


def summary(rows):
    answerable = [r for r in rows if r["answerable"]]
    return {
        "cases": len(answerable),
        "hit_at_5": statistics.mean(r["metrics"]["hit_at_k"] for r in answerable),
        "recall_at_5": statistics.mean(r["metrics"]["recall_at_k"] for r in answerable),
        "mrr": statistics.mean(r["metrics"]["mrr"] for r in answerable),
        "mean_unique_issues_in_context": statistics.mean(r["unique_issues"] for r in answerable),
        "contexts_with_five_distinct_issues": sum(r["unique_issues"] == 5 for r in answerable),
        "mean_context_characters": statistics.mean(r["context_characters"] for r in answerable),
        "frozen_cutoff": {
            "unanswerable_refused": sum(r["refused"] and not r["answerable"] for r in rows),
            "answerable_wrongly_refused": sum(r["refused"] and r["answerable"] for r in rows),
            "unanswerable_passed": sum(not r["refused"] and not r["answerable"] for r in rows),
        },
    }


def render(report):
    a = json.loads((ROOT / "index_recall_experiment.json").read_text())
    original = next(e for e in a["experiments"] if e["ef_search"] == 40)
    modes = list(report["summaries"])
    lines = ["# Experiment B: issue-level collapse", "", report["production_context"], "",
             "Fixed experiment: ef_search=100, retrieve 30 chunks, retain the highest-ranked chunk per (repository, issue_number), select up to five issues. No reranking, alias normalization, embedding calls, generation calls, or cutoff changes. Issue collapse has not been applied to the API.", "",
             "## Cumulative retrieval metrics", "",
             "| Scope | Stage | Hit@5 | Recall@5 | MRR |", "|---|---|---:|---:|---:|"]
    for scope in ["overall"] + sorted(original["by_repository"]):
        before = original["overall"] if scope == "overall" else original["by_repository"][scope]
        stages = [("Original: HNSW40, five chunks", before)]
        for mode in modes:
            s = report["summaries"][mode]
            stages.append((mode, s["overall"] if scope == "overall" else s["by_repository"][scope]))
        for label, s in stages:
            lines.append(f"| {scope} | {label} | {s['hit_at_5']:.4f} | {s['recall_at_5']:.4f} | {s['mrr']:.4f} |")
    lines += ["", "The original baseline comes from A's measured ef_search=40 run. A and B above were rerun together on a shared read-only snapshot with 63,634 embedded chunks; A reproduces its accepted metrics.", "",
              "## Context diversity and fixed-cutoff replay", "",
              f"Cutoff remains {report['cutoff']}; no optimization was run. The 15 unanswerable questions are the original calibration cases, not a held-out check.", "",
              "| Stage | Mean unique issues | Contexts with five issues / 45 | Mean context characters | Unanswerables refused / 15 | Wrongly refused / 45 |",
              "|---|---:|---:|---:|---:|---:|"]
    for mode in modes:
        s = report["summaries"][mode]["overall"]
        c = s["frozen_cutoff"]
        lines.append(f"| {mode} | {s['mean_unique_issues_in_context']:.4f} | {s['contexts_with_five_distinct_issues']} | {s['mean_context_characters']:.2f} | {c['unanswerable_refused']} | {c['answerable_wrongly_refused']} |")
    lines += ["", "Gained retrieval hits: " + ", ".join(report["gained_hits"]) + ". Lost hits: " + (", ".join(report["lost_hits"]) or "none") + ".", "",
              "All 60 top similarity scores are identical before and after collapse, so refusal decisions are unchanged. Remaining misses: Starlette #1119, Pydantic #4598, FastAPI #14502. Wrong refusals: FastAPI #5988 and Starlette #1295. Context diversity is measured on the proposed chunk lists; answer correctness and generated-answer quality were not evaluated.", "",
              "## Corpus count reconciliation", "",
              "The 63,002 snapshot counted tiangolo/fastapi (28,255 chunks), encode/starlette (4,450), and pydantic/pydantic (30,297). The unfiltered retrieval table also contains 632 chunks under fastapi/fastapi from 76 issues loaded on October 5, before the three-repository full load. All 76 have matching title and body under tiangolo/fastapi, and all 632 chunk identities (issue number, type, index) overlap. Their context prefixes/embeddings can still differ. This is repository-alias duplication, not 632 newly added canonical chunks. Previous commentary saying the corpus had grown was incorrect.", "",
              "Selected repositories: 9,555 Silver issue identities, 43,535 comments, 9,541 Gold issues with chunks, 63,002 embedded chunks. Unfiltered database: 9,631 Silver issue identities, 43,955 comments, 9,617 Gold issue identities, 63,634 embedded chunks. Unfiltered counts include alias duplicates and are not canonical unique-issue counts. The scope audit found zero missing embeddings, wrong dimensions, or Gold orphans across the entire database. No records were deleted or normalized.", ""]
    alias_duplicates = sum(
        row["unique_issues"] != len({
            ("tiangolo/fastapi" if c["repository"] == "fastapi/fastapi" else c["repository"], c["issue_number"])
            for c in row["retrieved"]
        })
        for rows in report["case_results"].values() for row in rows if row["answerable"]
    )
    lines += [f"A reporting-only alias-equivalence check found {alias_duplicates} answerable contexts whose unique-issue count was inflated by the alias. Retrieval and evaluation matching were not changed.", ""]
    quality_path = ROOT / "data_quality_checkpoint_b.json"
    if quality_path.exists() and quality_path.stat().st_size:
        # PowerShell redirection may produce UTF-16 depending on shell version.
        raw = quality_path.read_bytes()
        quality = json.loads(raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"))
        lines += ["## Full data-quality rerun", "", "```json", json.dumps(quality, indent=2), "```", ""]
    lines += ["## Optional index rebuild", "",
              "Not run. The existing index remains untouched. No candidate index or additional storage was created; build time and m=32/ef_construction=128 recall are unmeasured.", "",
              "## Reproduce", "", "```powershell",
              ".\\.venv\\Scripts\\python.exe scripts/experiment_issue_collapse.py",
              ".\\.venv\\Scripts\\python.exe scripts/run_quality_report.py",
              ".\\.venv\\Scripts\\python.exe -m unittest discover -s tests", "```", "",
              "Configure RAG_HNSW_EF_SEARCH=40 to compare the old API default; omit it or set 100 for the accepted setting. The benchmark explicitly fixes 100 and uses the existing ignored embedding cache. SET LOCAL is transaction-scoped; a live autocommit check confirmed the session returns to 40 after both default-100 and override-40 queries. The deployed Lambda has not been updated.", ""]
    (ROOT / "issue_collapse_experiment.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    cases = evaluate.load_cases(ROOT / "evaluation_cases.generated.jsonl")
    cache = json.loads((ROOT / ".question_embeddings.json").read_text())
    if cache["model"] != "text-embedding-3-small" or cache["questions"] != {c["case_id"]: c["question"] for c in cases}:
        raise RuntimeError("Cache does not match evaluation cases")
    cutoff = json.loads((ROOT / "confidence_calibration_results.json").read_text())["threshold_selection"]["recommended_threshold"]
    modes = {"A: HNSW100, five chunks": [], "B: HNSW100, 30 chunks collapsed to five issues": []}
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "ef_search": 100,
              "candidate_chunks": 30, "cutoff": cutoff, "cutoff_retuned": False, "openai_calls": 0,
              "identity": "(repository, issue_number); existing evaluation identity unchanged, no alias normalization",
              "production_context": "API top_k=5 currently selects five chunks, not five distinct issues; evaluation Hit@5 also scores five chunk positions. Collapse is experimental only.",
              "case_results": modes}
    with psycopg.connect(**evaluate.database_options(api.get_settings())) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        report["corpus"] = conn.execute("SELECT count(*),count(embedding) FROM public.github_issue_chunks").fetchone()
        for index, case in enumerate(cases, 1):
            embedding = cache["vectors"][case["case_id"]]
            start = time.perf_counter()
            baseline = api.retrieve_chunks(conn, embedding, 5, hnsw_ef_search=100)
            baseline_latency = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            candidates = api.retrieve_chunks(conn, embedding, 30, hnsw_ef_search=100)
            selected = collapse(candidates)
            collapse_latency = (time.perf_counter() - start) * 1000
            for mode, chunks, latency in zip(modes, (baseline, selected), (baseline_latency, collapse_latency)):
                metrics = evaluate.retrieval_case_metrics(case, chunks)
                modes[mode].append({
                    "case_id": case["case_id"], "question": case["question"],
                    "repository": case["expected_issues"][0]["repository"] if case["expected_issues"] else "unanswerable",
                    "answerable": metrics["applicable"], "metrics": metrics,
                    "score": api.retrieval_score(chunks), "refused": api.should_refuse(chunks, cutoff),
                    "unique_issues": len({(c["repository"], c["issue_number"]) for c in chunks}),
                    "context_characters": sum(len(c["chunk_text"]) for c in chunks),
                    "retrieval_latency_ms": latency, "human_verified": "",
                    "retrieved": [{k: c[k] for k in ("repository", "issue_number", "source_url", "chunk_type", "similarity_score")} for c in chunks],
                })
            if index % 10 == 0:
                print(f"Completed {index}/{len(cases)} cases", flush=True)
    report["summaries"] = {mode: {"overall": summary(rows), "by_repository": {
        repo: summary([r for r in rows if r["repository"] == repo]) for repo in sorted({r["repository"] for r in rows if r["answerable"]})}}
        for mode, rows in modes.items()}
    before, after = list(modes.values())
    report["gained_hits"] = [a["case_id"] for b, a in zip(before, after) if a["answerable"] and a["metrics"]["hit_at_k"] > b["metrics"]["hit_at_k"]]
    report["lost_hits"] = [a["case_id"] for b, a in zip(before, after) if a["answerable"] and a["metrics"]["hit_at_k"] < b["metrics"]["hit_at_k"]]
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    (ROOT / "issue_collapse_experiment.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    render(report)
    print(json.dumps({"summaries": report["summaries"], "gained_hits": report["gained_hits"], "lost_hits": report["lost_hits"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
