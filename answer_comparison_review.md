# Answer comparison review checkpoint

The approved twenty GPT-5 nano calls completed, with minimal reasoning and a 1,200-token completion limit each. Recorded usage was 30,850 prompt tokens and 3,329 completion tokens: $0.0028741 at standard rates, below the approved $0.02 cap. This is token-based cost accounting, not an invoice reconciliation; any cached-input discount is not applied. No extra embeddings or ingestion runs were performed. Each answer is saved in `context_comparison_answers.json`; `context_comparison_answers.md` presents ten questions side by side with source links. This is a human review checkpoint, not a measured claim that answer quality improved. Only context selection differs between the two modes; model and prompt are identical. All twenty calls finished normally without truncation and all numeric citations refer to supplied source indices. Pydantic #4108's new context has four distinct issues because the thirty candidates did not contain a fifth.

Production Lambda `github-rag-api` in `us-east-2` explicitly uses `gpt-4o-mini` and embeddings `text-embedding-3-small`. GPT-5 nano was used only for this comparison. The deployed source layer was read from the exact Lambda image digest, verified against its SHA-256, and inspected without deploying or invoking `/ask`. Its prompt template exactly matches the current repository. `production_model_audit.json` records that evidence and the full prompt.

The production system prompt instructs the model to answer only from retrieved issue excerpts; invent no facts, fixes, commands, or citations; clearly state insufficient evidence; treat heuristic resolutions as low-confidence evidence; cite every factual claim with numbered source citations; and keep answers concise and technical. The excerpts are JSON containing citation numbers, repository/issue identities, issue/source URLs, chunk types, similarity scores, and text. The user question is the separate user message. Production generation passes `temperature=0`. Deployment is still the old October 5 image, so the recent retrieval settings and collapse code are not live yet.

## What the idempotency test proves

`tests/test_incremental_pipeline.py::IncrementalPipelineTests.test_second_run_uses_watermark_and_preserves_silver_row_count` exists and passes. It invokes `run_pipeline()` twice and checks that the second ingestion receives the first run's watermark. It also checks equal Silver row counts and chunk counts.

**It does not prove database idempotency.** Ingestion, Silver loading, embedding, and quality checks are mocked. Silver always returns seven rows and embedding always returns nine chunks. The watermark store is an in-memory fake. Those count assertions therefore cannot detect duplicate database inserts. The loader's separate test checks unique-key/upsert SQL and mocked insert/update totals, but is also not a real database replay test. No end-to-end test currently executes two ingestion runs against real S3/Postgres and demonstrates unchanged stored row counts. No such run was performed in this checkpoint.

## Implemented versus deployment scaffolding

| Part | Actual implementation and limits |
|---|---|
| Repository scope | Configured storage names govern ingestion, Bronze loading, embedding, and quality checks. Explicit selections must be a configured subset; both FastAPI aliases cannot be configured together. |
| Watermarks | Real Postgres table creation, per-repository reads, and monotonic `GREATEST` upserts. Advanced after Bronze, Silver, and Gold checks succeed. Earlier layer writes are committed independently; there is no transaction across GitHub, S3, and Postgres. |
| GitHub incremental fetch | Real `since` parameter, pagination, comment fetching, PR exclusion, and retry handling. Incremental runs refresh existing per-issue S3 objects instead of skipping them. Only closed issues are fetched; reopened issues are not reconciled. |
| Bronze persistence | Real stable repository/issue object keys and manifests. Existing configured Bronze records are reread for validation/loading; downstream work is not limited to just the new batch. |
| Silver persistence | Real normalization/deduplication, composite unique keys, content hashes, and `ON CONFLICT` updates conditional on changed values. |
| Gold refresh | Real new/changed-issue selection, pending-embedding recovery, stable chunk identities, and reusable stored embeddings. Changed issues' old chunks are deleted and replaced by existing job code; no such operation was run here. Any future real refresh needs to respect the user's no-delete and paid-run approval rules. |
| Quality gates | Real scoped Bronze/Silver/Gold checks raise on failure before watermarks advance. Missing embeddings are caught by the Gold gate. |
| Execution entry points | Local pipeline CLI and ingestion Lambda handler exist and call the implemented pipeline. |
| Daily scheduling | PowerShell schedule-creation helper exists. A dedicated ingestion Lambda, its deployment/configuration, and daily schedule are not provisioned. Read-only AWS audit found only the API Lambda and no Scheduler or legacy EventBridge schedules in `us-east-2`. |
| Operational guarantees | No real two-run idempotency integration proof, concurrent-run lock, cross-layer atomic transaction, or automated reopened/deleted-issue reconciliation. Configurable scan/record caps also need care: reaching a cap is not a guarantee that every update was processed before advancing the maximum observed watermark. |

Validation: all 77 tests pass, including a separate rerun of the two-run orchestration test. No production code changed in this checkpoint. Stop here for the user's review; do not add held-out questions, remeasure performance, redeploy, or continue other checkpoints yet.
