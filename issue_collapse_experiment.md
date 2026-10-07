# Experiment B: issue-level collapse

API top_k=5 currently selects five chunks, not five distinct issues; evaluation Hit@5 also scores five chunk positions. Collapse is experimental only.

Fixed experiment: ef_search=100, retrieve 30 chunks, retain the highest-ranked chunk per (repository, issue_number), select up to five issues. No reranking, alias normalization, embedding calls, generation calls, or cutoff changes. Issue collapse has not been applied to the API.

## Cumulative retrieval metrics

| Scope | Stage | Hit@5 | Recall@5 | MRR |
|---|---|---:|---:|---:|
| overall | Original: HNSW40, five chunks | 0.8000 | 0.8000 | 0.7526 |
| overall | A: HNSW100, five chunks | 0.8667 | 0.8667 | 0.8193 |
| overall | B: HNSW100, 30 chunks collapsed to five issues | 0.9333 | 0.9333 | 0.8389 |
| encode/starlette | Original: HNSW40, five chunks | 0.9333 | 0.9333 | 0.9333 |
| encode/starlette | A: HNSW100, five chunks | 0.9333 | 0.9333 | 0.9333 |
| encode/starlette | B: HNSW100, 30 chunks collapsed to five issues | 0.9333 | 0.9333 | 0.9333 |
| pydantic/pydantic | Original: HNSW40, five chunks | 0.6667 | 0.6667 | 0.6667 |
| pydantic/pydantic | A: HNSW100, five chunks | 0.8000 | 0.8000 | 0.8000 |
| pydantic/pydantic | B: HNSW100, 30 chunks collapsed to five issues | 0.9333 | 0.9333 | 0.8333 |
| tiangolo/fastapi | Original: HNSW40, five chunks | 0.8000 | 0.8000 | 0.6578 |
| tiangolo/fastapi | A: HNSW100, five chunks | 0.8667 | 0.8667 | 0.7244 |
| tiangolo/fastapi | B: HNSW100, 30 chunks collapsed to five issues | 0.9333 | 0.9333 | 0.7500 |

The original baseline comes from A's measured ef_search=40 run. A and B above were rerun together on a shared read-only snapshot with 63,634 embedded chunks; A reproduces its accepted metrics.

## Context diversity and fixed-cutoff replay

Cutoff remains 0.5370554072220923; no optimization was run. The 15 unanswerable questions are the original calibration cases, not a held-out check.

| Stage | Mean unique issues | Contexts with five issues / 45 | Mean context characters | Unanswerables refused / 15 | Wrongly refused / 45 |
|---|---:|---:|---:|---:|---:|
| A: HNSW100, five chunks | 2.3778 | 3 | 3704.18 | 15 | 2 |
| B: HNSW100, 30 chunks collapsed to five issues | 4.9778 | 44 | 4056.18 | 15 | 2 |

Gained retrieval hits: generated-tiangolo-fastapi-5108, generated-pydantic-pydantic-4999, generated-pydantic-pydantic-4108. Lost hits: none.

All 60 top similarity scores are identical before and after collapse, so refusal decisions are unchanged. Remaining misses: Starlette #1119, Pydantic #4598, FastAPI #14502. Wrong refusals: FastAPI #5988 and Starlette #1295. Context diversity is measured on the proposed chunk lists; answer correctness and generated-answer quality were not evaluated.

## Corpus count reconciliation

The 63,002 snapshot counted tiangolo/fastapi (28,255 chunks), encode/starlette (4,450), and pydantic/pydantic (30,297). The unfiltered retrieval table also contains 632 chunks under fastapi/fastapi from 76 issues loaded on October 5, before the three-repository full load. All 76 have matching title and body under tiangolo/fastapi, and all 632 chunk identities (issue number, type, index) overlap. Their context prefixes/embeddings can still differ. This is repository-alias duplication, not 632 newly added canonical chunks. Previous commentary saying the corpus had grown was incorrect.

Selected repositories: 9,555 Silver issue identities, 43,535 comments, 9,541 Gold issues with chunks, 63,002 embedded chunks. Unfiltered database: 9,631 Silver issue identities, 43,955 comments, 9,617 Gold issue identities, 63,634 embedded chunks. Unfiltered counts include alias duplicates and are not canonical unique-issue counts. The scope audit found zero missing embeddings, wrong dimensions, or Gold orphans across the entire database. No records were deleted or normalized.

A reporting-only alias-equivalence check found 0 answerable contexts whose unique-issue count was inflated by the alias. Retrieval and evaluation matching were not changed.

## Full data-quality rerun

```json
{
  "passed": true,
  "layers": [
    {
      "layer": "bronze",
      "passed": true,
      "counts": {
        "source_records": 9831,
        "parsed_records": 9831,
        "valid_unique_issues": 9555,
        "rejected_records": 276,
        "duplicate_records": 276,
        "expected_deduplicated_or_rejected": 276
      },
      "hard_failures": [],
      "warnings": [
        "276 Bronze row(s) were rejected, including 276 duplicate issue keys"
      ],
      "valid_issue_count": 9555,
      "repositories": [
        "encode/starlette",
        "pydantic/pydantic",
        "tiangolo/fastapi"
      ]
    },
    {
      "layer": "silver",
      "passed": true,
      "counts": {
        "bronze_valid_unique_issues": 9555,
        "silver_rows": 9555,
        "silver_comments": 43535,
        "null_or_blank_key_rows": 0,
        "duplicate_issue_keys": 0,
        "malformed_comment_arrays": 0,
        "comments_are_nested_under_existing_issue_rows": true
      },
      "hard_failures": [],
      "warnings": [],
      "silver_issue_count": 9555,
      "repositories": [
        "encode/starlette",
        "pydantic/pydantic",
        "tiangolo/fastapi"
      ]
    },
    {
      "layer": "gold",
      "passed": true,
      "counts": {
        "silver_rows": 9555,
        "silver_chunkable_issues": 9541,
        "expected_no_content_drops": 14,
        "gold_issues_with_chunks": 9541,
        "gold_chunks": 63002,
        "chunks_without_embeddings": 0,
        "embeddings_with_wrong_dimensions": 0,
        "orphan_chunks": 0,
        "embedding_dimensions": 1536
      },
      "hard_failures": [],
      "warnings": [
        "14 Silver issue(s) have no chunkable body, comment, or resolution and are expected not to appear in Gold"
      ]
    }
  ],
  "read_method": "Existing quality checks, eight-worker read-only S3 prefetch; unchanged validation and source order"
}
```

## Optional index rebuild

Not run. The existing index remains untouched. No candidate index or additional storage was created; build time and m=32/ef_construction=128 recall are unmeasured.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/experiment_issue_collapse.py
.\.venv\Scripts\python.exe scripts/run_quality_report.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Configure RAG_HNSW_EF_SEARCH=40 to compare the old API default; omit it or set 100 for the accepted setting. The benchmark explicitly fixes 100 and uses the existing ignored embedding cache. SET LOCAL is transaction-scoped; a live autocommit check confirmed the session returns to 40 after both default-100 and override-40 queries. The deployed Lambda has not been updated.
