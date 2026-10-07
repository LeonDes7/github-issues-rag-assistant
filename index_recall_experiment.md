# Experiment A: index recall

One timed retrieval per question per setting, interleaved in seeded shuffled setting order. Latency includes the production query, joins, chunk payload transfer, and local decoding over the existing RDS connection; excludes embeddings, generation, connection setup, SET commands, and EXPLAIN. All latency summaries use only the 45 answerable cases. Cache effects and current RDS load apply; this is not an end-to-end API benchmark.

The historical baseline is preserved separately; its corpus snapshot had 63,002 chunks. All fresh variants below share a read-only repeatable-read snapshot.

| Scope | Setting | Hit@5 | Recall@5 | MRR | Mean ms | p50 ms | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|
| overall | HNSW ef_search=40 | 0.8000 | 0.8000 | 0.7526 | 207.61 | 71.92 | 551.06 |
| overall | HNSW ef_search=100 | 0.8667 | 0.8667 | 0.8193 | 365.14 | 88.48 | 1029.97 |
| overall | HNSW ef_search=200 | 0.8667 | 0.8667 | 0.8193 | 615.63 | 427.34 | 1775.57 |
| overall | HNSW ef_search=400 | 0.8667 | 0.8667 | 0.8193 | 1849.51 | 1686.02 | 3003.44 |
| overall | Exact scan | 0.8889 | 0.8889 | 0.8267 | 5824.26 | 5562.45 | 7226.48 |
| encode/starlette | HNSW ef_search=40 | 0.9333 | 0.9333 | 0.9333 | 185.59 | 63.93 | 456.41 |
| encode/starlette | HNSW ef_search=100 | 0.9333 | 0.9333 | 0.9333 | 235.50 | 61.99 | 763.68 |
| encode/starlette | HNSW ef_search=200 | 0.9333 | 0.9333 | 0.9333 | 373.41 | 62.17 | 1159.87 |
| encode/starlette | HNSW ef_search=400 | 0.9333 | 0.9333 | 0.9333 | 1806.99 | 1784.49 | 3096.09 |
| encode/starlette | Exact scan | 1.0000 | 1.0000 | 0.9556 | 5910.85 | 5521.51 | 7938.43 |
| pydantic/pydantic | HNSW ef_search=40 | 0.6667 | 0.6667 | 0.6667 | 263.36 | 304.22 | 558.81 |
| pydantic/pydantic | HNSW ef_search=100 | 0.8000 | 0.8000 | 0.8000 | 581.60 | 544.68 | 1172.46 |
| pydantic/pydantic | HNSW ef_search=200 | 0.8000 | 0.8000 | 0.8000 | 639.74 | 427.34 | 1704.68 |
| pydantic/pydantic | HNSW ef_search=400 | 0.8000 | 0.8000 | 0.8000 | 2081.23 | 2151.03 | 2967.99 |
| pydantic/pydantic | Exact scan | 0.8000 | 0.8000 | 0.8000 | 5694.56 | 5544.42 | 6893.35 |
| tiangolo/fastapi | HNSW ef_search=40 | 0.8000 | 0.8000 | 0.6578 | 173.88 | 58.21 | 504.42 |
| tiangolo/fastapi | HNSW ef_search=100 | 0.8667 | 0.8667 | 0.7244 | 278.32 | 61.79 | 705.59 |
| tiangolo/fastapi | HNSW ef_search=200 | 0.8667 | 0.8667 | 0.7244 | 833.74 | 708.48 | 1750.72 |
| tiangolo/fastapi | HNSW ef_search=400 | 0.8667 | 0.8667 | 0.7244 | 1660.31 | 1409.46 | 2948.71 |
| tiangolo/fastapi | Exact scan | 0.8667 | 0.8667 | 0.7244 | 5867.36 | 5663.00 | 7108.34 |

## Frozen-cutoff calibration replay

Cutoff remains 0.5370554072220923; no threshold optimization or retuning was performed. The same 15 original unanswerables are a calibration replay, not held-out evidence.

| Setting | Refused unanswerable / 15 | Wrongly refused answerable / 45 | Unanswerable passed | Total refused / 60 |
|---|---:|---:|---:|---:|
| HNSW ef_search=40 | 15 | 4 | 0 | 19 |
| HNSW ef_search=100 | 15 | 2 | 0 | 17 |
| HNSW ef_search=200 | 15 | 2 | 0 | 17 |
| HNSW ef_search=400 | 15 | 2 | 0 | 17 |
| Exact scan | 15 | 2 | 0 | 17 |

## Four exact-top-three misses

| Case | HNSW ef_search=40 | HNSW ef_search=100 | HNSW ef_search=200 | HNSW ef_search=400 | Exact scan |
|---|---:|---:|---:|---:|---:|
| generated-encode-starlette-1119 | miss | miss | miss | miss | 3 |
| generated-tiangolo-fastapi-2071 | miss | 1 | 1 | 1 | 1 |
| generated-pydantic-pydantic-7461 | miss | 1 | 1 | 1 | 1 |
| generated-pydantic-pydantic-11491 | miss | 1 | 1 | 1 | 1 |

## Index interpretation and recommendation

The catalog shows a valid, ready cosine HNSW index with no explicit reloptions. Installed pgvector 0.8.1 defaults therefore apply: m=16 and ef_construction=64. The initial session has ef_search=40 and iterative_scan=off. There is no IVFFlat index, so lists/probes do not apply. See the [version-matched pgvector documentation](https://github.com/pgvector/pgvector/blob/v0.8.1/README.md#hnsw).

Queries exclude NULL embeddings but have no repository WHERE filter; all current chunks have embeddings. The inner issue join remains unchanged. The HNSW plans use github_issue_chunks_embedding_hnsw_idx; the exact plan uses parallel sequential scans and a sort. Recovering gold by increasing search depth and bypassing the index, while keeping the corpus, embeddings, scoring, and joins fixed, isolates an approximate-index recall limitation. This does not establish corruption or the specific internal graph cause.

Recommend ef_search=100 as the lowest measured search setting that recovers three of the four misses: 39/45 retrieval hits versus 36/45 at 40. Settings 200 and 400 achieve the same hit and MRR scores with greater measured latency. Starlette #1119 remains absent at every tested HNSW setting. Exact scan is the only tested method that recovers all four (40/45 hits), but its measured latency makes it a costly default on this instance. If all four must be recovered, exact is the demonstrated option; ef_search=100 is a partial-recovery compromise, not a complete fix. No AWS dollar savings or monthly cost were measured; latency is the observed compute tradeoff. Values between tested settings and values above 400 were not benchmarked.


## Metadata and query plans

```json
{
  "server_version": "PostgreSQL 18.3 on aarch64-unknown-linux-gnu, compiled by aarch64-unknown-linux-gnu-gcc (GCC) 12.4.0, 64-bit",
  "pgvector_version": "0.8.1",
  "indexes": [
    [
      "github_issue_chunks_pkey",
      "CREATE UNIQUE INDEX github_issue_chunks_pkey ON public.github_issue_chunks USING btree (chunk_id)"
    ],
    [
      "github_issue_chunks_identity_unique",
      "CREATE UNIQUE INDEX github_issue_chunks_identity_unique ON public.github_issue_chunks USING btree (repository, issue_number, chunk_type, chunk_index)"
    ],
    [
      "github_issue_chunks_embedding_hnsw_idx",
      "CREATE INDEX github_issue_chunks_embedding_hnsw_idx ON public.github_issue_chunks USING hnsw (embedding vector_cosine_ops)"
    ],
    [
      "github_issue_chunks_search_vector_gin_idx",
      "CREATE INDEX github_issue_chunks_search_vector_gin_idx ON public.github_issue_chunks USING gin (search_vector)"
    ]
  ],
  "vector_index_options": [
    [
      "github_issue_chunks_embedding_hnsw_idx",
      null,
      true,
      true
    ]
  ],
  "initial_search_settings": [
    [
      "hnsw.ef_search",
      "40"
    ],
    [
      "hnsw.iterative_scan",
      "off"
    ],
    [
      "hnsw.max_scan_tuples",
      "20000"
    ],
    [
      "hnsw.scan_mem_multiplier",
      "1"
    ],
    [
      "ivfflat.iterative_scan",
      "off"
    ],
    [
      "ivfflat.max_probes",
      "32768"
    ],
    [
      "ivfflat.probes",
      "1"
    ]
  ],
  "corpus": [
    63634,
    63634,
    9617
  ],
  "filters": "WHERE chunks.embedding IS NOT NULL; INNER JOIN clean issues by repository/issue_number; LEFT JOIN heuristic classifications. No repository WHERE restriction.",
  "corpus_end_same_snapshot": [
    63634,
    63634
  ]
}
```

### HNSW ef_search=40

```text
Limit  (cost=2586.54..2616.97 rows=5 width=741)
  ->  Nested Loop Left Join  (cost=2586.54..383051.63 rows=62508 width=741)
        ->  Nested Loop  (cost=2586.26..378642.75 rows=62508 width=725)
              ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks  (cost=2585.96..374141.60 rows=62508 width=677)
                    Order By: (embedding <=> '<cached question embedding omitted>'::vector)
                    Filter: (embedding IS NOT NULL)
              ->  Memoize  (cost=0.30..0.43 rows=1 width=73)
                    Cache Key: chunks.repository, chunks.issue_number
                    Cache Mode: logical
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
        ->  Memoize  (cost=0.28..0.31 rows=1 width=35)
              Cache Key: chunks.repository, chunks.issue_number
              Cache Mode: logical
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
```

### HNSW ef_search=100

```text
Limit  (cost=5199.27..5229.49 rows=5 width=741)
  ->  Nested Loop Left Join  (cost=5199.27..383051.63 rows=62508 width=741)
        ->  Nested Loop  (cost=5198.99..378642.75 rows=62508 width=725)
              ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks  (cost=5198.69..374141.60 rows=62508 width=677)
                    Order By: (embedding <=> '<cached question embedding omitted>'::vector)
                    Filter: (embedding IS NOT NULL)
              ->  Memoize  (cost=0.30..0.43 rows=1 width=73)
                    Cache Key: chunks.repository, chunks.issue_number
                    Cache Mode: logical
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
        ->  Memoize  (cost=0.28..0.31 rows=1 width=35)
              Cache Key: chunks.repository, chunks.issue_number
              Cache Mode: logical
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
```

### HNSW ef_search=200

```text
Limit  (cost=9104.07..9133.99 rows=5 width=741)
  ->  Nested Loop Left Join  (cost=9104.07..383051.63 rows=62508 width=741)
        ->  Nested Loop  (cost=9103.79..378642.75 rows=62508 width=725)
              ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks  (cost=9103.50..374141.60 rows=62508 width=677)
                    Order By: (embedding <=> '<cached question embedding omitted>'::vector)
                    Filter: (embedding IS NOT NULL)
              ->  Memoize  (cost=0.30..0.43 rows=1 width=73)
                    Cache Key: chunks.repository, chunks.issue_number
                    Cache Mode: logical
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
        ->  Memoize  (cost=0.28..0.31 rows=1 width=35)
              Cache Key: chunks.repository, chunks.issue_number
              Cache Mode: logical
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
```

### HNSW ef_search=400

```text
Limit  (cost=16248.68..16278.02 rows=5 width=741)
  ->  Nested Loop Left Join  (cost=16248.68..383051.63 rows=62508 width=741)
        ->  Nested Loop  (cost=16248.40..378642.75 rows=62508 width=725)
              ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks  (cost=16248.10..374141.60 rows=62508 width=677)
                    Order By: (embedding <=> '<cached question embedding omitted>'::vector)
                    Filter: (embedding IS NOT NULL)
              ->  Memoize  (cost=0.30..0.43 rows=1 width=73)
                    Cache Key: chunks.repository, chunks.issue_number
                    Cache Mode: logical
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
        ->  Memoize  (cost=0.28..0.31 rows=1 width=35)
              Cache Key: chunks.repository, chunks.issue_number
              Cache Mode: logical
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
```

### Exact scan

```text
Limit  (cost=18076.86..18077.44 rows=5 width=741)
  ->  Gather Merge  (cost=18076.86..25356.94 rows=62508 width=741)
        Workers Planned: 2
        ->  Sort  (cost=17076.83..17141.94 rows=26045 width=741)
              Sort Key: (((chunks.embedding <=> '<cached question embedding omitted>'::vector) + '0'::double precision))
              ->  Hash Left Join  (cost=1920.91..16644.23 rows=26045 width=741)
                    Hash Cond: ((chunks.repository = classifications.repository) AND (chunks.issue_number = classifications.issue_number))
                    ->  Parallel Hash Join  (cost=1905.63..16101.53 rows=26045 width=725)
                          Hash Cond: ((chunks.repository = issues.repository) AND (chunks.issue_number = issues.issue_number))
                          ->  Parallel Seq Scan on github_issue_chunks chunks  (cost=0.00..14059.14 rows=26045 width=677)
                                Filter: (embedding IS NOT NULL)
                          ->  Parallel Hash  (cost=1820.65..1820.65 rows=5665 width=73)
                                ->  Parallel Seq Scan on github_issues_clean issues  (cost=0.00..1820.65 rows=5665 width=73)
                    ->  Hash  (cost=11.14..11.14 rows=276 width=35)
                          ->  Seq Scan on github_issue_classifications classifications  (cost=0.00..11.14 rows=276 width=35)
                                Filter: ((classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
```

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/experiment_index_recall.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Requires the existing ignored question embedding cache and database credentials. It makes no OpenAI calls and applies only transaction-local search settings. The exact adapter changes only the ORDER BY distance expression. Production application code and deployed Lambda are unchanged.
