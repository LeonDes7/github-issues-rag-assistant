# Author-approved retrieval rescore: blocked

The author personally reviewed and approved the CSV verdicts. The current
generated and reviewed JSONL files contain **44 kept answerable cases** (43 yes,
one edit) and 15 off-topic/unanswerable cases. FastAPI #5108 is excluded;
Pydantic #11491 uses: "What concern about the organization of the serialization
documentation motivated a rewrite?" The CSV retains the rejected row as review
evidence. `evaluation/evaluation_cases.original.jsonl` preserves the original
60-case input for historical reports.

## Attempt on October 16, 2026

The author approved the command below. Database connection timed out before
the OpenAI embedding request. A read-only RDS status query confirmed the existing
instance is **stopped**. The user prohibited AWS infrastructure changes, so it
was not started. No database writes or AWS infrastructure changes occurred.

**Zero cases scored; zero OpenAI calls; $0 OpenAI cost. No new retrieval metrics.**
The historical 45-case scores are not scores for the approved 44-case set.
Local verification: **105 tests pass**.

Recorded attempt: [author_reviewed_rescore_attempt.json](author_reviewed_rescore_attempt.json).

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

Once database access is restored, this command will recompute Hit@5, Recall@5,
MRR, retrieval hit counts, and answerable false refusals, overall and per
repository. A completed run will write `author_reviewed_rescore_results.json`;
that file does not exist for this blocked attempt. README headline metrics must
only be updated from a completed run. This is a local production-config retrieval
evaluation, not a deployed API latency or answer-quality test.
