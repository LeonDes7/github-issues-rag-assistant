# Local current-code latency and actual token cost

**This is local current-code latency, not deployed Lambda latency.**

Completed 60/60 requests. Hard OpenAI cap: $0.03. Recorded API-token cost: $0.00725905. Status: complete.

| Outcome | n | Total p50 ms | Total p95 ms | Mean OpenAI cost/query USD | Total OpenAI USD |
|---|---:|---:|---:|---:|---:|
| answered | 25 | 2047.3831999115646 | 4815.164500009268 | 0.000257734 | 0.00644335 |
| cutoff_refused | 30 | 398.8562999293208 | 1226.5535849845035 | 2.166666666666666666666666667E-7 | 0.00000650 |
| model_abstained | 5 | 1301.1104001197964 | 1802.5618399959058 | 0.00016184 | 0.00080920 |
| incomplete | 0 | None | None | None | 0 |

Settings: GPT-4o mini; text-embedding-3-small (1536 dimensions); vector retrieval; ef_search=100; fetch 30; collapse to five issues; three configured repositories; cutoff 0.5370554072220923. No generation output limit was added. No retries, warmups, deployment, database writes, or retrieval/cutoff changes.

RDS session default_transaction_read_only=on was verified before queries. Retrieval uses existing read-only transactions and SET LOCAL search depth. A real OpenAI client and read-only RDS connection were injected into the actual local /ask route. Single concurrency; five rotating rounds of the twelve approved queries. Setup is reported separately; the first request is flagged. No cache flush or forced cold-start operation occurred.

Embedding, DB retrieval, generation and client-total p50/p95 are saved per outcome in docs/measurements/final_latency_cost_results.json, with per-request API token usage and cost. Percentiles use linear interpolation; these sample percentiles are descriptive, not an SLO. Costs use reported cached input discounts; no free-tier assumptions or invoice reconciliation. Failed requests with unknown API usage are flagged, not represented as known free calls.

Budget reservations occur before embedding and, after retrieval reveals the exact prompt, before generation using a UTF-8 input bound plus framing and the full 16384-token model output maximum. If that reservation fails, the partial request is retained separately and the run stops without changing output limits. No paid call can start without its reservation.

Stop reason: All sixty requests completed.

No additional work or calls after this measurement report.
