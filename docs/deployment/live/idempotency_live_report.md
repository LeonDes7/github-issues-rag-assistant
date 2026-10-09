# Real-database idempotency replay

Status: **PASS**. OpenAI cost: $0. No deletes, AWS resource changes, pushes or deployment.

| Checkpoint | Issues | Comments | Chunks | Embeddings |
|---|---:|---:|---:|---:|
| baseline | 9555 | 43535 | 63002 | 63002 |
| pass_1 | 9555 | 43535 | 63002 | 63002 |
| pass_2 | 9555 | 43535 | 63002 | 63002 |

Pass 1: inserted 0, updated 0.

Pass 2: inserted 0, updated 0.

Embedding fingerprint comparison: baseline = pass 1 = pass 2

Both production entrypoints completed twice against the real database.

Source bodies downloaded once using pinned ETags, cached for both passes; metadata inventories rechecked. Schema preparation bypassed after validation; production upsert and embedding selection retained. Both passes held in one transaction with write locks; concurrent-writer behavior and crash recovery are not tested. Guards enforce a SQL allowlist in the client, not a server-installed policy. S3/transfer costs are unquantified.
