# Deployment preflight for output and retry controls

Prepared only. No OpenAI calls, RDS access, image build/push, AWS changes or deployment in this task. The existing Lambda currently runs the prior image without these new controls.

## Local change and proposed live settings

- `OPENAI_GENERATION_MAX_OUTPUT_TOKENS=512` (valid 1?16384): SDK `max_completion_tokens=512`.
- `OPENAI_MAX_RETRIES=0` (valid 0?10): SDK client `max_retries=0`, covering embeddings and generation.
- Both are defaults in current local code; settings can be overridden through the environment. Validate actual image settings before deployment/smoke.
- Output limiting may truncate supported responses; no supported-answer quality or latency measurement was rerun. Input cost and aggregate budgets are not capped by these two settings.

## Two exact planned live /ask requests

- `POST /ask`, `top_k=5`: What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?
- `POST /ask`, `top_k=5`: What is the latest stable Python release today?

Exactly two HTTP requests, no retries or manual replay. Each embeds its question; either may pass the cutoff and generate. `/health` would add no OpenAI tokens. Retrieval stays vector, ef_search=100, fetch 30, collapse to five issues, cutoff 0.5370554072220923 and the three configured repositories.

## Conservative OpenAI worst case

The two fixed questions use 29 embedding tokens with cl100k_base. Reserve two generations even for the intended unanswerable. Conservatively allow 128,000 input tokens per GPT-4o mini call and 512 output tokens per call, ignoring all cache discounts. The 128,000-input allowance intentionally overestimates the usable combined context window.

Embedding: 29 ? $0.02/M = $5.8E-7. Generation input: 256,000 ? $0.15/M = $0.0384. Output: 1,024 ? $0.60/M = $0.0006144. **Total conservative ceiling: $0.03901498.**

**This exceeds the earlier $0.01 hard cap.** A five-excerpt count limit does not enforce a total prompt-token limit. The 700-token chunking target uses a different tokenizer and excludes JSON/metadata/framing; it is not sufficient proof of a hard bound on the generation request. No database-size assumption is silently used.

For comparison only, using the earlier 1,182-token answerable prompt and assuming the second request is cutoff-refused gives $0.00048508 at the 512-output cap. This is a saved-context estimate, not a worst-case guarantee. If a <=20,000-input-token bound per generation were separately verified/enforced, both generations plus embedding would cost at most $0.00661498. No such input bound is currently implemented.

Before a future run, either approve the conservative ceiling or separately review an input-cost guard that refuses oversized generation requests without truncating retrieved evidence. Changing only output and retries cannot prove the earlier aggregate hard cap for arbitrary retrieved input.

## AWS scope and estimate

A future approved rollout adds one image to the existing Ohio ECR repository and updates the existing github-rag-api Lambda image. New controls can rely on defaults, or be explicitly set while preserving all other environment keys. No new NAT, VPC endpoint, EC2, Glue, Multi-AZ, Lambda, repository, subnet or other infrastructure; retain existing images.

Reuse the deployment_preflight resource inventory. Basic image scanning is enabled. Local Docker build/control-plane update have no per-call AWS compute charge. Existing three-check AWS estimate remains about $0.00036109, assuming 15 aggregate billed GB-seconds, three HTTP requests, 100 KiB logs, 1 MiB NAT traffic and three secret reads. New image retention assumes 0.25 GB entirely incremental: $0.025/month. Actual image size/cold-start duration remains unknown; neither figure is a hard AWS cap. Existing NAT/IPv4/RDS hourly charges continue independently.

## Verification

88 local tests pass, including configured and default output-token forwarding, zero/nonzero client retry forwarding, defaults/overrides and invalid environment validation. Existing API, abstention, source rendering and retrieval tests pass. No live behavior or new performance result is claimed.

## Sources

- [GPT-4o mini context/output limits and prices](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Chat Completions max_completion_tokens](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [SDK retry controls](https://github.com/openai/openai-python)
- [Embedding pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- [ECR](https://aws.amazon.com/ecr/pricing/)
- [Lambda](https://aws.amazon.com/lambda/pricing/)

Stopped for review. No deployment or paid calls authorized by this preflight.
