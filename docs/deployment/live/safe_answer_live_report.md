# Single safe-answer live verification

Result: **PASS**, HTTP 200, supported answered outcome. Exactly one approved live POST `/ask` was sent to the existing remediation Lambda in `us-east-2`, with zero retries and hard OpenAI cap $0.00210756. No build/push, deployment, configuration change, additional live check or database write was performed. Stopped after saving results.

Question (`top_k=5`): “What problem did the reporter observe when sending larger base64-encoded video frames over a WebSocket?”

Exact answer:

> The reporter observed that when sending larger base64-encoded video frames over a WebSocket, the client gets disconnected. This issue occurred while trying to transfer video from the client to the server for processing in real-time [1].

Citation [1] maps to FastAPI issue #2071, https://github.com/fastapi/fastapi/issues/2071. The reported disconnect and client/server real-time video context agree with the manually verified case and saved prior source-grounded local responses. Five retrieved-source records remain separate, with source/issue URLs and metadata. The remaining sources are Starlette #407, #1369, FastAPI #2445 and Starlette #940; they are not cited as support for the answer. No abstention/withholding, known unsafe settings-dump pattern or recognizable sensitive literal was returned. This verifies supported-answer behavior for this single case, not a general quality metric.

API-reported tokens: 18 embedding, 1,087 generation input, 45 generation output. Standard uncached token cost: $0.00000036 embedding + $0.00016305 input + $0.00002700 output = **$0.00019041**, below the approved cap. Cache invoice breakdown is not exposed by the API; actual AWS billed cost is unavailable. Token limits were respected.

Observed live client time: 8,784.48 ms; API-reported processing time: 5,632.96 ms. These are single live observations, not p50/p95 or local latency metrics.

Full raw response, all five citation records, token usage, timestamps and pass/fail result: [safe_answer_live_results.json](safe_answer_live_results.json). No retry or follow-up call occurred.
