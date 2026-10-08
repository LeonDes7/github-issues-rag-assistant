# Final deterministic abstention regression

All fourteen saved model responses were verified through the actual local `/ask` route with external dependencies mocked. Each raw model response contained only `[INSUFFICIENT_EVIDENCE]`. Each API answer was exactly:

> The retrieved excerpts do not provide enough evidence to answer this question.

Every API answer had no inline model citations or appended prose. The separate structured `citations` list exactly matched the frozen retrieved sources in count, order, URLs, scores, chunk types, and classification metadata. No source was promoted into an answer claim.

## Calls and actual token cost

- Exactly 14 network-enabled GPT-5 nano calls, all completed with `stop`; no retries or paid judge calls.
- API-reported input: **19,613 tokens**; output: **252 tokens**.
- Actual usage-based token cost: **$0.00108145 USD**, below the **$0.01090985** hard cap.
- Rates: $0.05/million input and $0.40/million output; cached-input discounts ignored. This is not invoice reconciliation.
- Requested model: `gpt-5-nano`; returned model: `gpt-5-nano-2025-08-07`; reasoning effort `minimal`; completion cap 1,200/call.
- Reported cached input: 0; reasoning output: 0 tokens.

## Per-case API verification

| Frozen case | Fixed answer / no prose / no inline citations | Separate sources matched | Cost (USD) |
|---|---|---:|---:|
| heldout-tiangolo-oauth-revocation | PASS | 5 | $0.0000712 |
| heldout-tiangolo-yield-cancellation | PASS | 5 | $0.0000868 |
| heldout-tiangolo-upload-benchmark | PASS | 5 | $0.0001005 |
| heldout-tiangolo-openapi-tenant-signing | PASS | 5 | $0.00008955 |
| heldout-tiangolo-background-durable | PASS | 5 | $0.00008485 |
| heldout-encode-middleware-benchmark | PASS | 5 | $0.0001282 |
| heldout-encode-websocket-replay | PASS | 5 | $0.0000621 |
| heldout-encode-lifespan-failover | PASS | 5 | $0.0000738 |
| heldout-encode-multipart-integrity | PASS | 5 | $0.0000557 |
| heldout-encode-cors-policy-proof | PASS | 5 | $0.00006865 |
| heldout-pydantic-validator-benchmark | PASS | 5 | $0.00006965 |
| heldout-pydantic-migration-proof | PASS | 5 | $0.0000641 |
| heldout-pydantic-schema-lossless-roundtrip | PASS | 5 | $0.00006485 |
| heldout-pydantic-validator-sandbox | PASS | 5 | $0.0000615 |

## Verification boundaries

Generation used only the fourteen prepared requests and frozen excerpts; the baseline, prompt and API source hashes were checked. API replay made no OpenAI, embedding, RDS, AWS, or real retrieval calls: it supplied a stub embedding vector, frozen retrieval results and saved chat responses. Generation, finalization, response serialization, and citation assembly used the actual API code. Every check and API answer/source snapshot is saved in [final_abstention_regression_results.json](final_abstention_regression_results.json).

Cutoff 0.537 and retrieval settings remain unchanged. No deployment, database writes, deletion, latency testing, or production code changes occurred in this run. The earlier regression reports remain separate.

This verifies the targeted output contract on these fourteen frozen cases; it is not a new headline metric, a general cutoff-robustness result, or live retrieval/UI validation. BackgroundTasks and schema-round-trip ambiguous labels remain unchanged. Human verification remains pending.

## Artifacts

- [final_abstention_regression_preflight.json](final_abstention_regression_preflight.json): frozen requests, settings, source hashes and approved estimate.
- [final_abstention_regression_results.json](final_abstention_regression_results.json): raw model outputs, usage/cost, API snapshots, and individual deterministic checks.
- `scripts/run_final_abstention_regression.py`: exclusive-output, budget-guarded paid runner with no retries.
- `scripts/verify_final_abstention_regression.py`: offline API verification and report generator.

Stopped for user review; no further calls.
