# Author-approved retrieval rescore: complete

The author personally reviewed and approved the CSV verdicts. The current
generated and reviewed JSONL files contain **44 kept answerable cases** (43 yes,
one edit) and 15 off-topic/unanswerable cases. FastAPI #5108 is excluded;
Pydantic #11491 uses: "What concern about the organization of the serialization
documentation motivated a rewrite?" The CSV retains the rejected row as review
evidence. `evaluation/evaluation_cases.original.jsonl` preserves the original
60-case input for historical reports.

## Completed rescore on October 16, 2026

All 44 kept answerable cases completed. Metrics use the top five distinct retrieved issues before cutoff refusal; false refusals are reported separately.

| Scope | Cases | Hits | Hit@5 | Recall@5 | MRR | False refusals |
|---|---:|---:|---:|---:|---:|---:|
| Overall | 44 | 41 | 0.9318 | 0.9318 | 0.8504 | 2 |
| encode/starlette | 15 | 14 | 0.9333 | 0.9333 | 0.9333 | 1 |
| pydantic/pydantic | 15 | 14 | 0.9333 | 0.9333 | 0.8333 | 0 |
| tiangolo/fastapi | 14 | 13 | 0.9286 | 0.9286 | 0.7798 | 1 |

Retrieval misses: Starlette #1119, Pydantic #4598, FastAPI #14502. False refusals: FastAPI #5988 and Starlette #1295.

The run reused 43 cached embeddings and made exactly one text-embedding-3-small call for the edited Pydantic question. API-reported usage was **13 input / total tokens**, costing **$0.00000026** at $0.02 per million tokens. This is token-based cost, not invoice reconciliation. No generation, judge calls, retries, database writes, or AWS changes occurred.

The 15 off-topic cases were excluded. Results describe retrieval on this small author-approved set; they do not establish general answer accuracy. Historical 45-case development scores and deployed ten-request latency measurements remain separate.

[Raw completed results](author_reviewed_rescore_results.json) include per-case sources, scores, metrics, refusal decisions, configuration, fixture hash, usage, and timestamps.

## Earlier blocked attempt

An earlier attempt on October 16 timed out because RDS was stopped at the time. It scored zero cases and made zero OpenAI calls. No infrastructure changes were made. The [original attempt record](author_reviewed_rescore_attempt.json) is retained as historical evidence.

## Prepared command and scope

```powershell
.\.venv\Scripts\python.exe scripts/rescore_reviewed_retrieval.py --execute
```

Uses actual production `retrieve_context`: vector retrieval, ef_search=100,
30 candidates collapsed to five distinct issues, the three configured repositories,
and unchanged cutoff 0.5370554072220923. The transaction is read-only.
Only the 44 answerable cases are scored; the 15 unanswerables are retained as
fixtures and excluded from this run. No generation, judge, or cutoff tuning.

Offline preflight found 43 matching cached embeddings and one missing embedding
for the edited question: 13 input tokens, estimated $0.00000026 at the standard
text-embedding-3-small rate of $0.02 per million tokens. The runner disables
retries and refuses an unexpected cache miss or changed token estimate.

The completed run is saved in `author_reviewed_rescore_results.json`. The runner
refuses to overwrite that file or repeat the paid call when it exists. This is a
local production-config retrieval evaluation, not a deployed API latency or
answer-quality test. Local verification: **105 tests pass**.
