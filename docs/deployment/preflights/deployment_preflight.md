# Deployment preflight ? awaiting approval

**No image build, push, deployment, paid OpenAI call or live endpoint test has been made.**

## Existing resources to update

- `<PROJECT_ARN>`: Push one uniquely tagged amd64 image; no deletion or repository setting change.
- `<PROJECT_ARN>`: UpdateFunctionCode to resolved new ECR digest using expected RevisionId; Publish=false. Preserve existing configuration/environment, IAM and VPC. New code defaults implement approved clean-scope settings.

## Resources reused without changes

- api_id: `"w3qqwb25w0"`.
- integration: `"dgaicxp"`.
- role: `"<PROJECT_ARN>"`.
- secret_arn: `"<PROJECT_ARN>"`.
- rds: `"<PROJECT_ARN>"`.
- nat: `[{"id": "nat-097cf07818b8577a9", "state": "available", "subnet": "subnet-0769c27ce21678466"}]`.
- vpc: `{"SubnetIds": ["subnet-02970a3628abe0a1e", "subnet-08624d3bb13fc2619"], "SecurityGroupIds": ["sg-09328f537d896d8b4"], "VpcId": "vpc-005161e9ccd247f58", "Ipv6AllowedForDualStack": false}`.
- log_group: `"/aws/lambda/github-rag-api"`.

**No new NAT gateway, VPC endpoint, EC2 instance, Glue resource, Multi-AZ RDS resource or other infrastructure will be created.** The existing single-AZ database stays single-AZ. Only ECR image content and Lambda code reference change; logs will append to the existing group. Registry scanning is BASIC and repository lifecycle policy is absent, so this push does not schedule image cleanup.

## Proposed sequence

1. Run local tests and inspect build context; .env is excluded by .dockerignore and Dockerfile copies only pyproject/README/src.
2. Build locally and validate target image API defaults, prompt/finalizer, dependency imports and Lambda handler. Abort for mismatched configuration or oversized image; do not repair AWS networking by creating resources.
3. Authenticate to existing ECR and push one unique tag; resolve digest; retain existing images. Basic scan-on-push currently enabled; no enhanced scan.
4. Re-read Lambda revision and compare to snapshot; update code by digest only, preserving config; wait for update completion. No alias/version publication or configuration mutations.
5. Call GET /health once, then POST /ask once for each exact question below; no HTTP retry. Save sanitized responses, usage/performance and Lambda logs locally; do not log bearer/API keys.
6. Stop after report; failed checks do not authorize additional tests or automated rollback.

Local Docker Desktop buildx --platform linux/amd64 --provenance=false --sbom=false; use Dockerfile; no AWS build service, no secret build arguments. Base and dependency versions are unpinned: build tests and import check required before push. No build performed in preflight.

Current deployed digest retained: `<ACCOUNT_ID>.dkr.ecr.us-east-2.amazonaws.com/github-rag-api@sha256:ec8bf244716b7cf4f8e3300f6edccd5682138bd48f7a000411ae752e701849b5`. Existing revision: `e34152f6-6add-49ac-aed5-ea7773d75454`. No automatic rollback or deletion.

## Exact live checks

Endpoint: `https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com`.

- GET /health. 200, PostgreSQL reachable; no OpenAI call
- POST /ask: {"question": "What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?", "top_k": 5}. 200, supported answer with matching inline/structured citations; generation likely
- POST /ask: {"question": "What is the latest stable Python release today?", "top_k": 5}. 200, cutoff refusal with no generation; if model abstains instead, fixed API text without inline citations/prose, separate sources. Record observed outcome without assuming refusal.

## Incremental cost estimate

- Local build/push/update control-plane: **$0 AWS compute/control-plane fees**; workstation resources excluded.
- Three smoke checks: estimated **$0.000361087835205078125 AWS**.
- Two `/ask` tests: estimated **$0.00026968 OpenAI**.
- Additional ECR storage: assume 0.25 GB at $0.10/GB-month = **$0.025/month**, or **$0.0008333333333333333333333333333/day**, continuing while the image is retained.
- Expected AWS + OpenAI smoke cost: **$0.000630767835205078125**, plus ECR retention.

AWS component assumptions:

{
  "lambda_15_gb_seconds": "0.0002500005",
  "lambda_3_requests": "0.0000006",
  "http_api_3_requests": "0.000003",
  "logs_100_kib_at_0_50_per_gib": "0.00004768371582031250",
  "nat_processing_1_mib_at_0_045_per_gib": "0.0000439453125",
  "secrets_3_reads": "0.000015",
  "internet_egress_10_kib_at_0_09_per_gib": "8.58306884765625E-7"
}

Local workstation build; no CodeBuild/EC2. Existing Lambda 1024 MB x86_64; 15 aggregate billed seconds across 3 invocations (cold-start/init can exceed this). 100 KiB logs, 1 MiB NAT traffic, 10 KiB endpoint egress, up to 3 Secrets Manager reads; no credits/free-tier assumed. Existing gp2 RDS has no per-read I/O charge. These are estimates, not hard caps.

Current deployed compressed image 216147543 bytes; assume up to 250 MB entirely additional billed storage, no layer-dedup/free-tier credit. Actual new size unknown until approved build. AWS ECR $0.10/GB-month; upload and same-region Lambda transfer $0. No deletion planned, so storage continues.

First measured local instance of each selected question: 20+9 embedding tokens, 1182 generation input tokens and 153 output tokens. Rates $0.02/M embeddings, $0.15/M uncached input, $0.60/M output. No cached discount assumed. Live context/output/cold starts may differ. Health costs no OpenAI tokens.

Existing NAT/IPv4/RDS/storage continue whether deployment happens or not. If this work alone extends runtime by 15 minutes, allocate NAT $0.01125 + one NAT public IPv4 $0.00125 + RDS compute $0.004 = $0.0165; existing storage and any CPU-credit charges additional. No lifecycle start/stop requested.

Smoke HTTP client will not retry. Existing API get_openai_client uses max_retries=2; preserving code means internal retries remain possible. Conservative model-wide ceiling for two generation requests with three attempts each: about $0.1741824 plus <=$0.00048 embeddings at 4000 tokens/attempt; not an expected cost or an enforced cap. No hard live OpenAI cap is implemented in production.

Rates are usage estimates, not invoice predictions or hard limits. Image size, cold-start billed duration and model output cannot be known before execution. No new hourly networking resource cost is introduced.

## Measured readiness and live status

README updates include only the completed original evaluation, held-out and deterministic abstention checks, and the sixty-request local current-code measurement. Latest local checkpoint is 85 passing tests. No new-image live latency, cost, retrieval or abstention success is claimed. API default settings are verified in the approved build before push; the older deployed retrieval defaults were not inspected. UI wording changes in streamlit_app.py are not part of the Lambda image and require a separate UI rollout if requested.

## Pricing references

- [ECR storage/transfer](https://aws.amazon.com/ecr/pricing/)
- [Lambda](https://aws.amazon.com/lambda/pricing/)
- [HTTP API](https://aws.amazon.com/api-gateway/pricing/)
- [NAT and IPv4](https://aws.amazon.com/vpc/pricing/)
- [Secrets Manager](https://aws.amazon.com/secrets-manager/pricing/)
- [CloudWatch](https://aws.amazon.com/cloudwatch/pricing/)
- [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Embeddings](https://developers.openai.com/api/docs/models/text-embedding-3-small)

Approve the concrete build/push/code-update and three-check scope before execution. Preflight does not authorize deployment.
