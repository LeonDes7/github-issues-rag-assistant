# Step 1: duplicate audit and retention proposal

This review uses existing measured experiment files. No OpenAI calls, deployments, database writes, or deletions were made. No evaluation was rerun in this checkpoint.

## Effect on retrieval experiments

Historical A and B ran against all 63,634 chunks, including 632 rows stored under the additional `fastapi/fastapi` alias. The original three-repository snapshot has 63,002 chunks. This was a scope difference, not a new embedding run.

The existing `clean_scope_experiment.json` replays the accepted combined configuration (ef_search=100, fetch 30, collapse to five distinct issues) on both scopes using cached embeddings and a shared read-only database snapshot. It reports zero per-case metric changes and zero refusal-decision changes across the original 60 cases. The metrics below use only the 45 answerable cases.

| Scope | All rows Hit@5 / Recall@5 / MRR | Configured repos Hit@5 / Recall@5 / MRR |
|---|---|---|
| Overall | 0.9333 / 0.9333 / 0.8389 | 0.9333 / 0.9333 / 0.8389 |
| FastAPI | 0.9333 / 0.9333 / 0.7500 | 0.9333 / 0.9333 / 0.7500 |
| Starlette | 0.9333 / 0.9333 / 0.9333 | 0.9333 / 0.9333 / 0.9333 |
| Pydantic | 0.9333 / 0.9333 / 0.8333 | 0.9333 / 0.9333 / 0.8333 |

Both scopes refused 15/15 original unanswerable cases and wrongly refused 2/45 answerable cases at the unchanged calibrated cutoff. These are calibration-set results. Hit@5 here is over distinct issues. Context text and similarity scores need not be identical: average answerable context characters changed from 4056.1778 to 4056.2000. Thus the duplicate rows did not alter measured final retrieval or refusal outcomes; the evidence does not establish that they were irrelevant to every historical A-only setting or latency measurement. Those isolated variants were not replayed on the clean scope.

## Production code scope and tests

The repository's production retrieval code already filters vector candidates and both hybrid candidate branches by the configured repository list before their limits. The default/active storage names are `tiangolo/fastapi`, `encode/starlette`, and `pydantic/pydantic`. GitHub's current FastAPI URL redirects do not require adding the extra storage alias. Both old chunk context and distinct-issue context use the scoped retrieval helper. `RAG_REPOSITORIES` can override retrieval scope; it must continue to contain the approved storage names in deployment configuration.

The scope tests verify defaults, configuration, rejection of an empty scope, and parameterized filters on vector and both hybrid branches. The branch test was strengthened in this checkpoint to assert that every candidate branch includes the filter before its LIMIT. Ingestion/loading/embedding/quality scope guards were implemented in the preceding checkpoint. The scoped quality report confirms 9,555 issues, 43,535 comments, and 63,002 embedded chunks.

This is repository production code, not a deployment claim. The Lambda still runs the earlier image. No deployment was performed.

## Cleanup proposal: retain and exclude

Keep the current archive-only arrangement. The approved local archive already exists under the git-ignored `archives/fastapi_alias/20261007T210850Z` directory. `alias_archive_receipt.json` records verified hashes, round-trip checks, credential scanning, and post-export database counts.

| Retained alias table | Rows |
|---|---:|
| github_issues_clean | 76 |
| github_issue_chunks | 632 |
| github_issue_classifications | 76 |
| Total | 784 |

Retain all these rows and the canonical rows; exclude the alias from retrieval and future job configuration. Keep the archive local and ignored. No new archive copy, SQL cleanup, index rebuild, or resource removal is proposed. There is no deletion step or deletion approval request.

## Deferred local database replay integration test

Track a real local PostgreSQL/pgvector integration test as follow-up, not as completed coverage. It should exercise actual schema and Silver/Gold persistence twice against identical local Bronze fixtures; simulate external GitHub/S3 and embeddings without paid calls; assert exact unchanged issue, comment, chunk, classification, and watermark counts/identities; assert no second-run embedding request; and include a changed-content replay separately. Run it against an isolated local test database, never the RDS corpus. The existing mocked orchestration test is insufficient evidence of database idempotency. Provisioning a local test database and implementing this test are deferred, as requested.

Rerun local checks: `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`. Any future paid evaluation requires a cost estimate and explicit approval before execution. Stop at this checkpoint.
