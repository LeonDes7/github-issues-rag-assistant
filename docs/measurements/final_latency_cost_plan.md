# Final latency and cost measurement plan

Current local API pipeline with production model overrides and approved clean-scope settings; not deployed Lambda performance. **Prepared only; no measurement is authorized yet.**

Proposed: 12 exact queries ? 5 rounds = 60 serial requests; 30 expected answered and 30 expected cutoff-refused. No additional warmups or retries. Estimated OpenAI: **$0.01134145**; proposed hard cap **$0.10**. Estimated allocated AWS cost for a 15-minute window: **$0.00487890625** (including $0.004 of already-running RDS compute); estimated incremental transfer **$0.00087890625**. AWS amounts are assumptions, not billing caps.

## Exact query sample

1. **expected_answered ? generated-encode-starlette-408**: What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?
2. **expected_answered ? generated-encode-starlette-542**: What is the recommended workaround for the dependency issue between graphene and aniso8601 when installing starlette[full]?
3. **expected_answered ? generated-tiangolo-fastapi-2071**: What problem did the reporter observe when sending larger base64-encoded video frames over a WebSocket?
4. **expected_answered ? generated-tiangolo-fastapi-618**: What steps should I take if the automatic reload feature fails to work on Windows 10 when modifying main.py?
5. **expected_answered ? generated-pydantic-pydantic-4999**: What unexpected behavior occurred when the reporter called `.parse_obj()` in an async loop?
6. **expected_answered ? generated-pydantic-pydantic-8499**: What is the workaround for the RecursionError encountered when parsing graph-like data with Pydantic V2?
7. **expected_cutoff_refused ? unanswerable-01**: What is the latest stable Python release today?
8. **expected_cutoff_refused ? unanswerable-02**: Which AWS IAM policy should I attach for production access?
9. **expected_cutoff_refused ? unanswerable-03**: What is the current price of a PostgreSQL RDS instance?
10. **expected_cutoff_refused ? unanswerable-04**: Can you diagnose my private production server from this repository?
11. **expected_cutoff_refused ? unanswerable-06**: What is the weather forecast for Tokyo tomorrow?
12. **expected_cutoff_refused ? unanswerable-11**: Summarize the contents of a file on my personal computer.

## Configuration and execution

{
  "OPENAI_GENERATION_MODEL": "gpt-4o-mini",
  "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
  "VECTOR_DIMENSIONS": 1536,
  "RAG_RETRIEVAL_MODE": "vector",
  "RAG_CONTEXT_MODE": "issues",
  "RAG_HNSW_EF_SEARCH": 100,
  "FETCH_CANDIDATES": 30,
  "TOP_K_DISTINCT_ISSUES": 5,
  "RAG_CONFIDENCE_THRESHOLD": 0.5370554072220923,
  "RAG_REPOSITORIES": [
    "tiangolo/fastapi",
    "encode/starlette",
    "pydantic/pydantic"
  ],
  "temperature": 0,
  "generation_output_cap": "unchanged production API behavior: no explicit cap; model maximum 16384"
}

For round r (0..4), rotate the six paired answered/refused query pairs by r; interleave answered then refused. No adaptive substitutions or extra runs.

Use local actual /ask route with real OpenAI client and a read-only psycopg connection; default_transaction_read_only=on for session, validate SHOW transaction_read_only, each retrieval transaction read-only with unchanged SET LOCAL hnsw.ef_search. No evaluate persistence, DDL, DML, index writes, archival or RDS lifecycle changes. Save results only locally.

Before any paid call, verify nonsecret runtime models/settings and API source hash; abort on mismatch. Deployed Lambda retrieval defaults remain unverified; no invocation/deployment. RDS must already be Available.

## Estimates and assumptions

OpenAI formula: 935 estimated embedding tokens ? $0.02/M + 51485 estimated generation input tokens ? $0.15/M + 6000 assumed output tokens ? $0.60/M = $0.01134145. Input estimates use the current prompt with previously saved five-issue contexts; live retrieved context can differ. Output assumes 200 tokens for each of 30 answered requests. No cache discount assumed for estimate. Cohort outcomes are predictions, not guaranteed; up to 60 requests may require generation.

Reserve exact current input text byte bound plus framing and full model output maximum before each generation; check cumulative actual spend plus reservation <= approved cap; stop without changing generation limits if insufficient. Do not claim 60 completed if stopped.

Existing available single-AZ db.t4g.micro PostgreSQL 18.3, 20 GiB gp2, Ohio. Storage unchanged. Excludes existing storage/backup charges and unknown T4g surplus-credit charges; no account discounts/free transfer allowance assumed. Fifteen-minute window and 10 MiB transfer are estimates, not enforced AWS caps.

A local run invokes no Lambda/API Gateway. Thus it cannot report their billed durations, cold starts, or deployed endpoint latency. Fresh metadata confirms production model overrides and RDS instance shape; the deployed Lambda is unchanged since October 5 and its retrieval defaults have not been inspected. The current abstention prompt/finalizer belongs to local code.

## Reporting

Use observed response: substantive answered, cutoff-refused, model-abstained after cutoff pass, failed/incomplete. Do not mix model abstentions with cutoff refusals. Preserve cohort counts and surprises.

Report empirical p50/p95 (linear interpolation) separately by observed outcome, for client total, embedding, DB retrieval, generation; cutoff-refused generation latency zero. Connection/client setup separately. Single concurrency; first request marked separately, no forced cold starts or cache flush. p95 on ~30 observations is descriptive, not an SLO.

Per request API-reported embedding tokens, generation prompt/completion/cached tokens, model ID, actual usage-based USD (cached-input $0.075/M when reported; uncached $0.15/M; output $0.60/M; embedding $0.02/M). Failed requests with unknown usage flagged unknown, not zero; no paid judge or invoice claims.

## Pricing references

- [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- [RDS PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS transfer pricing](https://aws.amazon.com/ec2/pricing/on-demand-backup/)

The instance-hour rate was fetched from the AWS Price List API; saved in [measurement_aws_price_snapshot.json](measurement_aws_price_snapshot.json). Safe AWS configuration metadata is saved in [measurement_configuration_snapshot.json](measurement_configuration_snapshot.json).

Do not run the existing `measure_rag_performance.py` unchanged: it fetches five chunks directly, has no explicit read-only enforcement, and combines outcome latency groups. An approved run needs a separate harness implementing this plan, without changing API/retrieval defaults.

Awaiting explicit approval. No paid model calls, database query, deployment, deletion, or retrieval setting changes were made during preparation.
