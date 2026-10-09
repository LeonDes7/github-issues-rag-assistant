# Final live deployment verification

**The existing github-rag-api Lambda was updated in us-east-2. Exactly three live smoke requests completed with HTTP 200.** No retries, rollback, configuration changes, infrastructure creation or database writes were performed. Existing images were retained.

## Image and controls

- Deployed image: `<ACCOUNT_ID>.dkr.ecr.us-east-2.amazonaws.com/github-rag-api@sha256:1e08220c4cbff6fbd46ea5f9d191532e7c2cd6c24f09731e556123340e2832e4`.
- Compressed ECR image size: **216247900 bytes** (216.2479 MB, decimal).
- Lambda revision: `29648095-57d4-45db-b004-7a07c6fd3faa`.
- Effective settings were validated in the built image using the existing Lambda environment and dummy secrets, with networking disabled. Source SHA-256 matched local source. Existing environment, role, VPC, memory, timeout and architecture were checked unchanged after update.
- Verified limits: RAG_MAX_GENERATION_INPUT_TOKENS=12000; OPENAI_GENERATION_MAX_OUTPUT_TOKENS=512; OPENAI_MAX_RETRIES=0.
- Retrieval preserved: vector, ef_search=100, fetch 30, collapse to five distinct issues, three configured repositories, cutoff 0.5370554072220923.
- 93 local tests passed before deployment.

## Exact live checks

| Request | Result | Client wall time | Standard-rate token cost USD |
|---|---|---:|---:|
| /health | HTTP 200; PostgreSQL reachable | 4622.12 ms | $0 |
| What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets? | HTTP 200; answered | 6074.88 ms | $0.00025435 |
| What is the latest stable Python release today? | HTTP 200; cutoff_refused | 911.71 ms | $1.8E-7 |

The answerable response passed the smoke checks for a non-abstaining answer, nonempty structured sources, and inline citation indices within that source list. The unanswerable response returned the API cutoff-refusal text and reported zero generation tokens. Thus this live run verifies the cutoff-refusal path; it does not exercise the model-selected abstention path live. That latter path remains covered by local unit tests and the prior frozen-response local API regression.

These are single-request live smoke wall times, not p50/p95 latency measurements, billed Lambda durations, or performance guarantees. The sixty-request local p50/p95 results remain separately labeled local current-code latency and predate the new token controls.

## Token accounting and hard cap

- API-reported embedding tokens: **29** (20 answerable + 9 cutoff-refused).
- API-reported generation input: **1213 tokens**; output: **120 tokens**.
- Usage-based cost at standard uncached rates: **$0.00025453** = 29 ? $0.02/M + 1213 ? $0.15/M + 120 ? $0.60/M.
- Approved hard cap: **$0.005**. Before any live request, the verified two-call maximum was **$0.00421498**, conservatively assuming both requests generate at the full input/output limits with no retries. Recorded usage stayed below those limits.
- Cached-input breakdown is not exposed by the current API. Standard-rate accounting conservatively ignores any cache discount; actual discounted invoice cost cannot be reconciled from these responses. No failed-call usage is unknown in this completed run.

## AWS cost status

Actual billed AWS charges are not yet available. Control-plane image push/code update has no per-call fee, but image storage and the three live invocations/logging/network/secret reads incur usage. Applying $0.10/GB-month to the full compressed image gives a conservative additional storage-rate estimate of **$0.021624790/month**, before layer sharing/free credits. Existing NAT/IPv4/RDS costs continue independently. This storage rate is an estimate, not actual billed cost.

## Answer review limitation

The answerable smoke is plumbing/citation-index verification, not a paid or exhaustive factual judge. Its sample code returns dict(settings.config), and the response itself warns that this exposes secrets and requires additional filtering or masking. Do not treat that illustrative snippet as a verified safe secret-redaction implementation. Full answer text and returned sources are saved for user review; no follow-up generation or repair was performed.

## Artifacts

- [final_deployment_live_results.json](final_deployment_live_results.json): full live responses, token usage/performance, costs, digest, image size and effective settings.
- `scripts/deploy_final_smoke.py`: exclusive-result deployment and exactly-three-check runner; HTTP/SDK retries disabled for this run.
- [deployment_input_budget_preflight.md](../preflights/deployment_input_budget_preflight.md): approved token bound and fixed questions.
- README separates completed live smoke verification from local latency metrics. Streamlit UI code changes were not separately deployed by this Lambda-only task.

Stopped for review. No additional live request, configuration change, rollback or deployment followed these checks.
