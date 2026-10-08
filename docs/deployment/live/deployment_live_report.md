# Live deployment results

**One image was pushed and the existing github-rag-api Lambda code was updated in us-east-2. The live /health check passed; the two /ask checks were not run.**

- Image: `918897410856.dkr.ecr.us-east-2.amazonaws.com/github-rag-api@sha256:f9e04c70616b852c8028e14e835cdb53daf4b3850337d126ca96d3d874ea12a6`.
- Compressed image size: 216239569 bytes.
- Local tests: 85 passed. Offline image model/settings, abstention finalizer and Lambda handler validation passed with networking disabled and dummy credentials.
- Lambda revision after update: `6919f8b4-283f-4b9e-8b39-0c9409f66e07`.
- Existing images retained; no resource creation, environment/configuration changes, rollback, database writes or additional deployment.

## Live checks

| Check | Result |
|---|---|
| GET /health | HTTP 200; {"status":"ok","database":"reachable"} |
| Answerable POST /ask | Not called: hard OpenAI cap cannot be enforced by this image |
| Unanswerable POST /ask | Not called: hard OpenAI cap cannot be enforced by this image |

The /health client wall time was 4481.79 ms for one call. This is a live one-request smoke result, not a latency percentile, Lambda billed duration, or an SLO. No live supported-answer, cutoff-refusal or model-abstention behavior has been verified after deployment.

## Budget and actual costs

- Actual OpenAI calls: **0**; token cost **$0.00**.
- Actual billed AWS cost: **not yet available**. Do not interpret the unavailable figure as zero.
- Push/build/code-update API operations have no per-call AWS compute/control-plane fee; local workstation build costs excluded.
- Additional ECR storage rate estimate from full compressed image size: **$0.02162395690/month** at $0.10/GB-month, before shared-layer deduplication or credits. This is a continuing storage estimate, not actual billed cost.
- The one live health invocation uses Lambda/API Gateway/logging/Secrets Manager and existing networking. Its actual billed duration/log bytes/transfer usage have not been collected; original preflight estimates are not relabeled as actual charges.

The live API has no server-side token-budget guard and uses max_retries=2. Its possible generation usage and retries can exceed the newly required aggregate $0.01 cap. No paid /ask call was made because a small expected cost is not a hard spending guarantee. The preflight explicitly documented this limitation. Enforcing a guaranteed live cap would require a separately reviewed implementation change; none was added or deployed here.

## Saved evidence

- [deployment_live_results.json](deployment_live_results.json): deployed digest, revision, one live health response, skipped checks and cost status.
- [deployment_image_validation.json](../preflights/deployment_image_validation.json): offline image production defaults.
- [deployment_preflight_resources.json](../preflights/deployment_preflight_resources.json): prior image and unchanged existing resources.
- Local latency remains separately documented in [final_latency_cost_report.md](../../measurements/final_latency_cost_report.md); it is not deployed Lambda latency.

Stopped for review without HTTP retries, configuration changes, rollback or further paid calls.
