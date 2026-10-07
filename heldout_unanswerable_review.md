# Harder unanswerable evaluation: awaiting cost approval

Fifteen new candidate unanswerables, five per repository. Labels are hypotheses based on the required detail and read-only lexical preflight, not human verification or exhaustive proof of corpus-wide absence. The saved lexical evidence contains nearby topics, including noisy traceback matches. After approved vector retrieval, review the actual evidence and report any label ambiguity instead of forcing a false-accept designation. Do not rewrite questions after seeing cutoff scores.

Fixed evaluation cutoff: **0.537**, exactly as requested. No retuning. Retrieval stays vector, ef_search=100, configured three-repository scope, fetch 30 chunks and keep up to five distinct issues. No settings file or live configuration was changed.

## Frozen questions

1. **heldout-tiangolo-oauth-revocation**: How can a FastAPI OAuth2 dependency revoke an already authenticated WebSocket connection across four Uvicorn workers within 30 seconds, and what indexed issue demonstrates that guarantee?

2. **heldout-tiangolo-yield-cancellation**: Which FastAPI dependency-with-yield pattern guarantees exactly-once transaction rollback when a streaming response is cancelled after headers are sent, including process termination?

3. **heldout-tiangolo-upload-benchmark**: What measured p95 latency and peak RSS does the indexed FastAPI corpus report for 100 concurrent 1 GiB multipart uploads using UploadFile on a 2-vCPU host?

4. **heldout-tiangolo-openapi-tenant-signing**: How do the indexed FastAPI issues implement tenant-specific OpenAPI schemas whose OAuth scopes are cryptographically signed and refreshed without restarting workers?

5. **heldout-tiangolo-background-durable**: Which FastAPI BackgroundTasks configuration provides durable exactly-once execution after a worker crash, and where is the failure-recovery protocol specified in the indexed issues?

6. **heldout-encode-middleware-benchmark**: What measured throughput improvement does pure ASGI middleware give over BaseHTTPMiddleware with 64 concurrent streaming clients, 256 KiB responses, and TLS on a 2-vCPU host?

7. **heldout-encode-websocket-replay**: Which Starlette WebSocket reconnection recipe in the indexed issues guarantees ordered exactly-once delivery with persisted replay across a server restart?

8. **heldout-encode-lifespan-failover**: How does Starlette lifespan coordinate atomic failover of a shared PostgreSQL connection pool across multiple workers without losing any in-flight transaction?

9. **heldout-encode-multipart-integrity**: Which Starlette multipart upload design verifies a client-provided SHA-256 incrementally, resumes an interrupted upload at a byte offset, and guarantees no duplicate bytes in the stored file?

10. **heldout-encode-cors-policy-proof**: What indexed Starlette issue proves a dynamically reloaded per-tenant CORS policy cannot leak one tenant's allowed origins to another during concurrent configuration updates?

11. **heldout-pydantic-validator-benchmark**: What measured speedup do the indexed Pydantic issues report for a 50-field discriminated union with three nested model levels over 10 million records on an ARM64 2-vCPU host?

12. **heldout-pydantic-migration-proof**: Which indexed Pydantic migration procedure proves byte-for-byte identical JSON serialization between v1 and v2 for recursive generics, custom encoders, aliases, and timezone-aware datetimes together?

13. **heldout-pydantic-settings-secret-rotation**: How do indexed Pydantic settings issues rotate encrypted secrets across multiple running processes atomically while preserving rollback to the previous key after a failed deployment?

14. **heldout-pydantic-schema-lossless-roundtrip**: Which Pydantic implementation in the indexed issues provides lossless JSON Schema to model to JSON Schema round-tripping, including recursive references, custom validators, and field ordering?

15. **heldout-pydantic-validator-sandbox**: Which Pydantic validator configuration safely executes tenant-supplied Python validation code with enforced CPU and memory limits and a documented sandbox escape analysis?

## Proposed paid run

- Embed the 15 questions once with text-embedding-3-small: 474 estimated tokens, **$0.00000948** at the recorded $0.02/million rate. Cache them locally.
- Apply the fixed cutoff read-only. Refused cases skip generation.
- For any cases passing the cutoff, generate an answer with GPT-5 nano and the existing grounding prompt, minimal reasoning, and at most 1,200 completion tokens. This is an evaluation-only model selection; the production model and retrieval settings remain unchanged.
- Up to 15 generation calls. Using the previous comparison's measured mean of 1,542.5 prompt tokens and the full output cap for every case, estimated total **$0.008366355** if all 15 pass; **$0.00000948** if all are refused. These are estimates, not measured metrics.
- Proposed hard budget **$0.02**. Actual contexts are unknown before embedding/retrieval. A deliberately loose corpus-wide serialization bound is $0.22090698; it is not permission to spend that amount. Locally count each prepared prompt and check remaining budget before each call. Stop if the approved budget is insufficient; no retries or automatic budget increase. The existing $1 cumulative cap also applies.

## Results pending approval

Save results separately from the original 60-case calibration file. Report cutoff refusals, cutoff passes, completed generated answers, model abstentions despite passing the cutoff, unsupported factual answers, and ambiguous labels separately. Include per-case scores, evidence, citations, generated text where applicable, and review notes. A cutoff pass is a gate false accept under the candidate label, not automatically a hallucinated answer. No held-out metrics are available yet.

No OpenAI calls, deployments, database writes, deletes, or latency testing were performed. All 77 local tests pass. Stop for approval.
