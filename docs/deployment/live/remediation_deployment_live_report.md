# Remediation live verification — 2026-10-08

One remediation image was built and pushed to the existing ECR repository and only the existing `github-rag-api` Lambda code image was updated in `us-east-2`. No infrastructure or database writes were performed, no configuration/retrieval/cutoff settings were changed, and existing images were retained. Exactly two live checks ran with zero retries and no warmups. Both passed the approved safety checks; execution stopped afterward.

The deployed image is `918897410856.dkr.ecr.us-east-2.amazonaws.com/github-rag-api@sha256:3ee06641a7814eec96ed08c553ab7a15fdb82095e5f0ef983636d2c6f1855330`, tag `remediation-20261008-final`. ECR reports compressed image size **216,254,880 bytes (216.25488 MB decimal)**. Image validation confirmed API and redaction file hashes, unchanged retrieval settings, generation input limit 12,000, output limit 512, and OpenAI retries zero. All 101 local tests passed before execution. The Streamlit patch was not deployed.

| Live check | Result | Observed client time |
|---|---|---:|
| GET `/health` | HTTP 200; `status=ok`, `database=reachable` | 3,919.07 ms |
| POST `/ask`, fixed settings-dump question, top_k=5 | HTTP 200; model abstained, API fixed response | 5,724.62 ms |

Exact question: “What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?”

Exact returned answer:

> The retrieved excerpts do not provide enough evidence to answer this question.

The answer is exactly the fixed API-controlled abstention, with no appended prose, inline citations, secret-like literals, unsafe settings-dump recommendation, `dict(settings.config)` or `return settings.config` pattern. Five structured retrieved-source records remain separate, with source/issue links and metadata for Starlette issues 408, 671, 763, 391 and 914. They do not imply support for the unavailable answer. The same five source identities as the prior unsafe answer were retained. This is a **safe model abstention**, not the unsafe-pattern withholding message and not a supported substantive answer. A supported answered outcome was therefore not verified. No raw model response is exposed or stored by the API; only the final API response was inspected.

The unsafe pattern was absent in this case. This single live check does not prove complete credential detection or suppression of all unsafe code patterns. These are live smoke observations, not latency percentiles or replacements for historical local current-code measurements.

## Usage and cost

The single `/ask` used 20 embedding tokens, 1,180 generation input tokens and 67 generation output tokens. At the preflight's standard uncached rates:

| Usage | USD |
|---|---:|
| Embedding: 20 × $0.02 / million | 0.00000040 |
| Generation input: 1,180 × $0.15 / million | 0.00017700 |
| Generation output: 67 × $0.60 / million | 0.00004020 |
| **Actual token-usage cost at standard rates** | **0.00021760** |

This is below the approved hard OpenAI cap of **$0.00210760**. Health has no OpenAI usage. The API does not expose cached-input billing breakdown; final invoice discounts cannot be reconciled from this response. AWS actual billed cost is not yet available, and no additional billing/network checks were made. The approved illustrative AWS execution estimate remains approximately $0.00025439; full-new-image ECR storage at the measured size is conservatively $0.021625488/month, before shared-layer savings. No billed-cost claim is made for AWS.

Complete response, image validation, timestamps and usage are saved in [remediation_deployment_live_results.json](remediation_deployment_live_results.json). No retry, rollback, subsequent deployment or additional live call was performed. Stopped for review.
