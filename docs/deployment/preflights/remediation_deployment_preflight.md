# Remediation deployment preflight — approval pending

Prepared 2026-10-08 from saved deployment/resource artifacts. No build, push, AWS/API endpoint request, OpenAI request, or database access was performed for this preflight. The remediation remains local and undeployed; its prior local verification reported 101 passing tests.

## Exact scope

Build locally and push one image to existing ECR repository `918897410856.dkr.ecr.us-east-2.amazonaws.com/github-rag-api`. Update only the code image of existing Lambda `arn:aws:lambda:us-east-2:918897410856:function:github-rag-api`. Retain all existing images. Current recorded image digest: `sha256:1e08220c4cbff6fbd46ea5f9d191532e7c2cd6c24f09731e556123340e2832e4`.

Reuse existing HTTP API `w3qqwb25w0`, execution role, secret, log group, VPC/subnets/security group, NAT gateway and RDS instance. Create no infrastructure, including NAT gateway, VPC endpoint, EC2, Glue or Multi-AZ resource. Change no Lambda configuration, retrieval ranking/settings, cutoff or database data. The Streamlit patch remains local; this approval would update the Lambda backend only.

Before an approved update, compare existing configuration/revision with the recorded deployment and validate effective image settings locally. Stop on unexpected drift rather than modifying configuration. Production models remain `text-embedding-3-small` and `gpt-4o-mini`; input limit 12,000, output limit 512, OpenAI retries zero. Vector retrieval, ef_search=100, fetch 30, five distinct issues and cutoff 0.5370554072220923 remain unchanged.

## Exactly two live checks, no retries or warmups

1. GET `https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com/health`. Require HTTP 200 and healthy database status. This endpoint checks database connectivity without writing data or calling OpenAI.
2. POST `https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com/ask` with exactly:

```json
{"question":"What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?","top_k":5}
```

Require HTTP 200, the expected retrieval/citation metadata and separate source links, and no returned `dict(settings.config)` or `return settings.config` pattern. Review the complete response for exposed recognizable credentials or an unsafe settings-dump recommendation. Record whether the result is a supported answer, fixed withholding message or fixed abstention; do not force a substantive answer. If it refuses, report that the unsafe pattern was absent but a supported answered outcome was not verified. If any check fails, stop without retry, rollback, configuration change or additional deployment/call.

The prior exact answer/source review found setting-name references and masked examples, not a literal credential. The defect was an unsafe recommendation. Pattern-based redaction cannot establish that every possible sensitive value or unsafe code pattern is suppressed. One live check validates only this case. Record complete live results, token usage priced at standard rates, new image digest/size and verification outcome in a separate remediation report; distinguish it from historical local latency measurements. Stop afterward.

## Cost estimate

No free-tier credits or cache discounts assumed. Prices follow the existing deployment preflight; actual AWS billing and new image size are unavailable before execution.

| Item | Assumption | Incremental USD |
|---|---|---:|
| Local build / push transfer | Local machine; ECR inbound and same-region Lambda image transfer | 0 |
| Added ECR storage | Previous compressed image 216,247,900 bytes; charge full new image conservatively, ignoring shared layers | 0.02162479/month |
| ECR planning allowance | New image up to 250 MB decimal at $0.10/GB-month; actual size measured after build | 0.025/month |
| Lambda compute | 1,024 MB x86, 10 aggregate billed seconds across two checks, $0.0000166667/GB-second | 0.000166667 |
| Lambda requests | Two at $0.20/million | 0.0000004 |
| HTTP API requests | Two at $1/million | 0.000002 |
| Secrets Manager reads | Up to two at $0.05/10,000 | 0.000010 |
| Logs | 64 KiB at $0.50/GiB | 0.000030517578125 |
| Existing NAT data processing | 1 MiB at $0.045/GiB | 0.0000439453125 |
| Internet response transfer | 10 KiB at $0.09/GiB | 0.000000858306885 |
| Estimated AWS execution total | Above illustrative duration/data assumptions | 0.00025438819751 |
| Question embedding | 20 tokens at $0.02/million | 0.00000040 |
| Generation input maximum | 12,000 tokens at $0.15/million | 0.00180000 |
| Generation output maximum | 512 tokens at $0.60/million | 0.00030720 |
| **One-request OpenAI maximum** | **Embedding plus generation, zero retries** | **0.00210760** |

Use $0.00210760 as the proposed hard OpenAI spending ceiling for this single request. The bound assumes the deployed token controls are validated and maintained and provider usage stays within the enforced limits; reject the run before a paid call if validation fails. Health costs no OpenAI tokens. Report API usage priced at uncached rates; invoices/cache discounts are not exposed by the current response.

Combined illustrative one-time execution cost: $0.00236198819751, plus ongoing added ECR storage. AWS execution costs are estimates, not a hard ceiling: cold-start time, image retrieval, duration and traffic can differ. The full-image storage estimate is conservative because ECR can share existing layers; 250 MB is a planning assumption, not a guaranteed new image size. Retained images accrue storage until separately authorized for removal.

Existing NAT, public IPv4 and RDS hourly charges continue independently. They are not new resources or additional hourly rates created by this deployment. If this work alone extends their uptime by 15 minutes, the prior rate assumptions attribute approximately $0.0165 ($0.01125 NAT + $0.00125 IPv4 + $0.004 RDS), separately from the request estimate. No RDS lifecycle action is included.

Pricing references: [ECR](https://aws.amazon.com/ecr/pricing/), [Lambda](https://aws.amazon.com/lambda/pricing/), [API Gateway](https://aws.amazon.com/api-gateway/pricing/), [VPC](https://aws.amazon.com/vpc/pricing/), [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). Resource evidence: [final_deployment_live_results.json](../live/final_deployment_live_results.json), [deployment_preflight_resources.json](deployment_preflight_resources.json), [measurement_aws_price_snapshot.json](../../measurements/measurement_aws_price_snapshot.json). Finding and patch evidence: [live_answer_secret_review.md](../../security/live_answer_secret_review.md).

Approval required before build/push, Lambda update or the two live checks. No execution is authorized by this preflight.
