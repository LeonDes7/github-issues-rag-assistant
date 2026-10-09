# One safe answered-request cost preflight — approval pending

Exactly one POST to `https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com/ask`, against the already deployed remediation Lambda `github-rag-api` in `us-east-2`. No build, push, deployment, configuration change, database write, extra health check, warmup or retry is included. No endpoint/OpenAI/AWS/database request was made to prepare this preflight.

```json
{"question":"What problem did the reporter observe when sending larger base64-encoded video frames over a WebSocket?","top_k":5}
```

This is Codex-checked, not human-verified evaluation case `generated-tiangolo-fastapi-2071`, unrelated to settings or secrets. It returned an answered outcome in all five prior local measurement rounds. The expected supported fact is that larger base64-encoded video frames caused the WebSocket client to disconnect, grounded in FastAPI issue #2071. Those historical local results establish the selection; they do not guarantee a supported answer from the deployed remediation image.

Existing models remain `text-embedding-3-small` and `gpt-4o-mini`; generation input is bounded at 12,000 tokens and output at 512, with zero OpenAI retries. Retrieval and cutoff settings remain unchanged. Local cl100k tokenization of the exact question yields 18 embedding tokens.

| Maximum usage | Standard uncached price | USD |
|---|---|---:|
| Embedding, 18 tokens | $0.02/million | 0.00000036 |
| Generation input, 12,000 tokens | $0.15/million | 0.00180000 |
| Generation output, 512 tokens | $0.60/million | 0.00030720 |
| **Proposed hard OpenAI cap** | **One request, zero retries** | **0.00210756** |

No cache discounts or free credits assumed. Bound uses the existing enforced token controls, unchanged production models and exact question. Record returned token usage and cost at these rates; the API does not expose cached-input invoice breakdown. If usage is unavailable following a failure, report it as unknown rather than zero. Stop without retry or replacement question.

Illustrative added AWS request cost is approximately **$0.00016545**, assuming one 1 GB Lambda invocation with five billed seconds ($0.0000833335), one Lambda request ($0.0000002), one HTTP API request ($0.000001), one secret read ($0.000005), 64 KiB logs ($0.000030517578125), 1 MiB NAT processing ($0.0000439453125) and 5 KiB response transfer ($0.000000429153443). AWS billing is not a hard cap; duration/data volumes can differ. No added image storage or infrastructure cost. Existing ECR storage and RDS/NAT/IPv4 hourly charges continue independently. Combined illustrative execution cost is approximately **$0.00227301** at maximum OpenAI usage.

After approval, require HTTP 200; inspect the returned answer for a supported description of the reported disconnect and a valid inline citation to the matching structured source. Confirm structured source links remain present, no secret-like literal or unsafe recommendation is returned, and token usage stays within limits. If it abstains/withholds, report that outcome and that supported-answer behavior was not verified. Save the response, outcome, usage and actual token cost in a separate live report; stop afterward. One smoke observation is not a general quality metric or latency percentile.

Recorded current image: `sha256:3ee06641a7814eec96ed08c553ab7a15fdb82095e5f0ef983636d2c6f1855330`. Local evidence: [remediation_deployment_live_results.json](../live/remediation_deployment_live_results.json), [evaluation_cases.generated.jsonl](../../../evaluation/evaluation_cases.generated.jsonl), [final_latency_cost_results.json](../../measurements/final_latency_cost_results.json). Machine-readable plan: [safe_answer_live_cost_preflight.json](safe_answer_live_cost_preflight.json).

Pricing references carried forward from the approved deployment preflight: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [embeddings](https://developers.openai.com/api/docs/models/text-embedding-3-small), [Lambda](https://aws.amazon.com/lambda/pricing/), [HTTP API](https://aws.amazon.com/api-gateway/pricing/), [NAT](https://aws.amazon.com/vpc/pricing/).

Awaiting explicit approval before the single live request.
