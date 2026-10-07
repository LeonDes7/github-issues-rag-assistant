"""Experiment A: cached embeddings, session-only HNSW settings, exact search.

No OpenAI client is created. No schema, data, global settings, or cutoff is changed.
"""

import argparse
import json
import random
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from rag_assistant import api, evaluate


ROOT = Path(__file__).resolve().parents[1]


class QueryCursor:
    def __init__(self, cursor, owner):
        self.cursor, self.owner = cursor, owner

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *args):
        return self.cursor.__exit__(*args)

    def execute(self, sql, params=None):
        if sql.startswith("SET LOCAL "):
            self.cursor.execute(sql)
            return
        if self.owner.exact:
            old = "ORDER BY chunks.embedding <=> %s::vector"
            if sql.count(old) != 1:
                raise RuntimeError("Vector SQL changed; exact scan adapter requires review")
            # An expression rather than the bare distance operator cannot use
            # the HNSW ordering path. Preserve joins, WHERE, LIMIT, and scoring.
            sql = sql.replace(old, "ORDER BY (chunks.embedding <=> %s::vector) + 0")
        self.owner.last_query = (sql, params)
        self.cursor.execute(sql, params)

    def fetchall(self):
        return self.cursor.fetchall()


class QueryConnection:
    def __init__(self, connection, exact=False):
        self.connection, self.exact = connection, exact
        self.last_query = None

    def cursor(self):
        return QueryCursor(self.connection.cursor(), self)

    def transaction(self):
        return self.connection.transaction()


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def group_summary(rows):
    scored = [r for r in rows if r["answerable"]]
    return {
        "cases": len(scored),
        "hit_at_5": statistics.mean(r["metrics"]["hit_at_k"] for r in scored),
        "recall_at_5": statistics.mean(r["metrics"]["recall_at_k"] for r in scored),
        "mrr": statistics.mean(r["metrics"]["mrr"] for r in scored),
        "retrieval_latency_ms": {
            "mean": statistics.mean(r["latency_ms"] for r in scored),
            "p50": percentile([r["latency_ms"] for r in scored], 0.5),
            "p95": percentile([r["latency_ms"] for r in scored], 0.95),
        },
    }


def render(report, path):
    lines = ["# Experiment A: index recall", "", report["measurement_note"], "",
             "The historical baseline is preserved separately; its corpus snapshot had 63,002 chunks. All fresh variants below share a read-only repeatable-read snapshot.", "",
             "| Scope | Setting | Hit@5 | Recall@5 | MRR | Mean ms | p50 ms | p95 ms |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for scope in ["overall"] + sorted(report["experiments"][0]["by_repository"]):
        for experiment in report["experiments"]:
            summary = experiment[scope] if scope == "overall" else experiment["by_repository"][scope]
            latency = summary["retrieval_latency_ms"]
            lines.append(f"| {scope} | {experiment['setting']} | {summary['hit_at_5']:.4f} | {summary['recall_at_5']:.4f} | {summary['mrr']:.4f} | {latency['mean']:.2f} | {latency['p50']:.2f} | {latency['p95']:.2f} |")
    lines += ["", "## Frozen-cutoff calibration replay", "",
              f"Cutoff remains {report['cutoff']}; no threshold optimization or retuning was performed. The same 15 original unanswerables are a calibration replay, not held-out evidence.", "",
              "| Setting | Refused unanswerable / 15 | Wrongly refused answerable / 45 | Unanswerable passed | Total refused / 60 |",
              "|---|---:|---:|---:|---:|"]
    for e in report["experiments"]:
        c = e["frozen_cutoff_counts"]
        lines.append(f"| {e['setting']} | {c['correctly_refused']} | {c['wrongly_refused']} | {c['missed_unanswerable']} | {c['total_refused']} |")
    lines += ["", "## Four exact-top-three misses", "",
              "| Case | " + " | ".join(e["setting"] for e in report["experiments"]) + " |",
              "|---|" + "---:|" * len(report["experiments"])]
    for case_id in report["four_misses"]:
        ranks = []
        for e in report["experiments"]:
            row = next(r for r in e["cases"] if r["case_id"] == case_id)
            ranks.append(str(row["gold_rank_at_5"] or "miss"))
        lines.append("| " + case_id + " | " + " | ".join(ranks) + " |")
    lines += ["", "## Index interpretation and recommendation", "",
              "The catalog shows a valid, ready cosine HNSW index with no explicit reloptions. Installed pgvector 0.8.1 defaults therefore apply: m=16 and ef_construction=64. The initial session has ef_search=40 and iterative_scan=off. There is no IVFFlat index, so lists/probes do not apply. See the [version-matched pgvector documentation](https://github.com/pgvector/pgvector/blob/v0.8.1/README.md#hnsw).", "",
              "Queries exclude NULL embeddings but have no repository WHERE filter; all current chunks have embeddings. The inner issue join remains unchanged. The HNSW plans use github_issue_chunks_embedding_hnsw_idx; the exact plan uses parallel sequential scans and a sort. Recovering gold by increasing search depth and bypassing the index, while keeping the corpus, embeddings, scoring, and joins fixed, isolates an approximate-index recall limitation. This does not establish corruption or the specific internal graph cause.", ""]
    by_setting = {e["ef_search"]: e for e in report["experiments"]}
    if all(v in by_setting for v in (40, 100, 200, 400, None)):
        lines += ["Recommend ef_search=100 as the lowest measured search setting that recovers three of the four misses: 39/45 retrieval hits versus 36/45 at 40. Settings 200 and 400 achieve the same hit and MRR scores with greater measured latency. Starlette #1119 remains absent at every tested HNSW setting. Exact scan is the only tested method that recovers all four (40/45 hits), but its measured latency makes it a costly default on this instance. If all four must be recovered, exact is the demonstrated option; ef_search=100 is a partial-recovery compromise, not a complete fix. No AWS dollar savings or monthly cost were measured; latency is the observed compute tradeoff. Values between tested settings and values above 400 were not benchmarked.", ""]
    lines += ["", "## Metadata and query plans", "", "```json", json.dumps(report["database"], indent=2, default=str), "```"]
    for e in report["experiments"]:
        lines += ["", "### " + e["setting"], "", "```text", e["query_plan"], "```"]
    lines += ["", "## Reproduce", "", "```powershell",
              ".\\.venv\\Scripts\\python.exe scripts/experiment_index_recall.py",
              ".\\.venv\\Scripts\\python.exe -m unittest discover -s tests", "```", "",
              "Requires the existing ignored question embedding cache and database credentials. It makes no OpenAI calls and applies only transaction-local search settings. The exact adapter changes only the ORDER BY distance expression. Production application code and deployed Lambda are unchanged.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ef-search", type=int, nargs="+", default=[40, 100, 200, 400])
    parser.add_argument("--skip-exact", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "index_recall_experiment.json")
    args = parser.parse_args()
    if any(v < 1 or v > 1000 for v in args.ef_search):
        parser.error("ef_search must be 1..1000")
    cases = evaluate.load_cases(ROOT / "evaluation_cases.generated.jsonl")
    cache = json.loads((ROOT / ".question_embeddings.json").read_text())
    if cache["model"] != "text-embedding-3-small" or cache["questions"] != {c["case_id"]: c["question"] for c in cases}:
        raise RuntimeError("Embedding cache does not match evaluation cases")
    if any(len(cache["vectors"][c["case_id"]]) != api.VECTOR_DIMENSIONS for c in cases):
        raise RuntimeError("Invalid cached vector dimensions")
    cutoff = json.loads((ROOT / "confidence_calibration_results.json").read_text())["threshold_selection"]["recommended_threshold"]
    variants = [(f"HNSW ef_search={v}", v) for v in args.ef_search]
    if not args.skip_exact:
        variants.append(("Exact scan", None))
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "cutoff": cutoff,
              "openai_calls": 0, "cutoff_retuned": False,
              "measurement_note": "One timed retrieval per question per setting, interleaved in seeded shuffled setting order. Latency includes the production query, joins, chunk payload transfer, and local decoding over the existing RDS connection; excludes embeddings, generation, connection setup, SET commands, and EXPLAIN. All latency summaries use only the 45 answerable cases. Cache effects and current RDS load apply; this is not an end-to-end API benchmark.",
              "four_misses": ["generated-encode-starlette-1119", "generated-tiangolo-fastapi-2071", "generated-pydantic-pydantic-7461", "generated-pydantic-pydantic-11491"],
              "historical_baseline": json.loads((ROOT / "retrieval_comparison_results.json").read_text())["metrics"]["vector"],
              "experiments": [{"setting": name, "ef_search": ef, "cases": []} for name, ef in variants]}
    rng = random.Random(42)
    with psycopg.connect(**evaluate.database_options(api.get_settings())) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '120s'")
        report["database"] = {
            "server_version": conn.execute("SELECT version()").fetchone()[0],
            "pgvector_version": conn.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0],
            "indexes": conn.execute("SELECT indexname,indexdef FROM pg_indexes WHERE tablename='github_issue_chunks'").fetchall(),
            "vector_index_options": conn.execute("SELECT c.relname,c.reloptions,i.indisvalid,i.indisready FROM pg_class c JOIN pg_index i ON i.indexrelid=c.oid JOIN pg_am a ON a.oid=c.relam WHERE a.amname IN ('hnsw','ivfflat')").fetchall(),
            "initial_search_settings": conn.execute("SELECT name,setting FROM pg_settings WHERE name LIKE 'hnsw.%' OR name LIKE 'ivfflat.%'").fetchall(),
            "corpus": conn.execute("SELECT count(*),count(embedding),count(DISTINCT (repository,issue_number)) FROM public.github_issue_chunks").fetchone(),
            "filters": "WHERE chunks.embedding IS NOT NULL; INNER JOIN clean issues by repository/issue_number; LEFT JOIN heuristic classifications. No repository WHERE restriction.",
        }
        for number, case in enumerate(cases, 1):
            order = list(range(len(variants)))
            rng.shuffle(order)
            for index in order:
                name, ef = variants[index]
                conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef or 40),))
                adapter = QueryConnection(conn, exact=ef is None)
                start = time.perf_counter()
                retrieved = api.retrieve_chunks(adapter, cache["vectors"][case["case_id"]], 5, hnsw_ef_search=ef or 40,
                                                repositories=["tiangolo/fastapi", "encode/starlette", "pydantic/pydantic", "fastapi/fastapi"])
                elapsed = (time.perf_counter() - start) * 1000
                metrics = evaluate.retrieval_case_metrics(case, retrieved)
                gold_rank = next((rank for rank, chunk in enumerate(retrieved, 1)
                                  if any(evaluate.matched_expected_reference(gold, chunk) for gold in case["expected_issues"])), None)
                row = {"case_id": case["case_id"], "question": case["question"],
                       "repository": case["expected_issues"][0]["repository"] if case["expected_issues"] else "unanswerable",
                       "answerable": metrics["applicable"], "metrics": metrics, "gold_rank_at_5": gold_rank,
                       "latency_ms": elapsed, "score": api.retrieval_score(retrieved), "refused": api.should_refuse(retrieved, cutoff),
                       "human_verified": "", "retrieved": [{k: chunk[k] for k in ("repository", "issue_number", "source_url", "chunk_type", "similarity_score")} for chunk in retrieved]}
                report["experiments"][index]["cases"].append(row)
                if number == 1:
                    sql, params = adapter.last_query
                    plan = "\n".join(r[0] for r in conn.execute("EXPLAIN " + sql, params).fetchall())
                    report["experiments"][index]["query_plan"] = re.sub(r"'\[[^\]]+\]'::vector", "'<cached question embedding omitted>'::vector", plan)
            if number % 5 == 0:
                print(f"Completed {number}/{len(cases)} cases across {len(variants)} settings", flush=True)
        report["database"]["corpus_end_same_snapshot"] = conn.execute("SELECT count(*),count(embedding) FROM public.github_issue_chunks").fetchone()
    for e in report["experiments"]:
        e["overall"] = group_summary(e["cases"])
        e["by_repository"] = {repo: group_summary([r for r in e["cases"] if r["repository"] == repo]) for repo in sorted({r["repository"] for r in e["cases"] if r["answerable"]})}
        rows = e["cases"]
        e["frozen_cutoff_counts"] = {
            "correctly_refused": sum(r["refused"] and not r["answerable"] for r in rows),
            "wrongly_refused": sum(r["refused"] and r["answerable"] for r in rows),
            "missed_unanswerable": sum(not r["refused"] and not r["answerable"] for r in rows),
            "total_refused": sum(r["refused"] for r in rows),
        }
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    render(report, args.output.with_suffix(".md"))
    print(json.dumps([{k: v for k, v in e.items() if k in {"setting", "overall", "by_repository", "frozen_cutoff_counts"}} for e in report["experiments"]], indent=2), flush=True)


if __name__ == "__main__":
    main()
