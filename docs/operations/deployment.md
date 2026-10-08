# Deployment reference

This reference preserves the original README chronology. Statements such as
?not yet verified? and old image digests describe earlier checkpoints, not current
status. Model-selected abstention and supported answers are now live-verified;
the current image is documented in [the root README](../../README.md).

Historical commands below can call paid services, write data or change infrastructure.
They are documentation, not authorization to execute. Historical checkpoints are dated;
see the root README and live reports for current verification.

# Trustworthy RAG Assistant for GitHub Issues

An evidence-grounded assistant for questions about closed FastAPI, Starlette,
and Pydantic issues. It retrieves embedded issue discussions from PostgreSQL,
generates answers from the retrieved evidence, and returns clickable GitHub
citations. The Streamlit demo calls the authenticated API from server-side
code; credentials belong in deployment secrets, never in this repository.

## Demo

The Community Cloud UI uses the deployed API endpoint
`https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com`. After deployment,
ask a question to see the answer, the top retrieved issue's predicted
bug/feature/usage category and confidence, source links, and retrieval
diagnostics. The category prediction describes the retrieved issue, not the
question, and heuristic confidence is not ground truth.

## Project layout

- `streamlit_app.py` — Community Cloud-compatible question and citation UI.
- `src/rag_assistant/` — ingestion, cleaning, embeddings, API, evaluation,
  and issue classification modules.
- `tests/` — focused unit tests for data handling and application behavior.
- [evaluation_cases.jsonl](../../evaluation/evaluation_cases.jsonl) and [classification_cases.jsonl](../../evaluation/classification_cases.jsonl) — small,
  version-controlled evaluation fixtures.

The stages are documented below in their build order. Running ingestion,
database, embedding, or evaluation commands requires the relevant private
credentials and configured AWS/RDS resources.

## Initial setup

1. Create and activate a virtual environment.
2. Install the project with `python -m pip install -e .`.
3. Fill in the local `.env` file. It is ignored by Git; do not commit or share it.
4. Run the RDS connection check with `python -m rag_assistant.check_db_connection`.

The check connects with SSL required, runs
`CREATE EXTENSION IF NOT EXISTS vector;`, and exits with an error if the
configuration, connection, or extension setup fails. The AWS and API settings
are reserved for later ingestion work and are not used by this check.

Prefer AWS IAM roles or a configured AWS profile over long-lived static access
keys when those options are available.

## Step 4: Local FastAPI retrieval and generation API

The local API exposes `GET /health` to verify PostgreSQL connectivity and
`POST /ask` to embed a question, retrieve issue chunks using vector-only or
hybrid pgvector/full-text search, and generate a concise answer grounded only
in those retrieved excerpts. Citation metadata is built from retrieved
database rows, not from model-generated source URLs. Heuristic-resolution
chunks remain labeled low-confidence evidence in the prompt.

Set `OPENAI_API_KEY`, `API_AUTH_TOKEN`, `OPENAI_EMBEDDING_MODEL`,
`OPENAI_GENERATION_MODEL`, `RAG_RETRIEVAL_MODE`, and optionally
`CORS_ALLOWED_ORIGINS` in `.env`. `RAG_RETRIEVAL_MODE` accepts `vector`
(default) or `hybrid`.
`RAG_HNSW_EF_SEARCH` defaults to `100` and accepts integers from 1 to 1000;
set it to `40` to reproduce the original search depth. Retrieval applies this
with `SET LOCAL` inside each query's transaction, independently of the RDS
parameter group. The setting resets when the transaction ends.
`RAG_REPOSITORIES` restricts both vector and full-text candidates before their
limits. It defaults to `GITHUB_REPOS`, or to the three original repository names
when neither is set. The example selects `tiangolo/fastapi`, `encode/starlette`,
and `pydantic/pydantic`; alias rows remain stored but are excluded from retrieval.
`API_AUTH_TOKEN` is required for `/ask`; use a high-entropy token and do not
check it into source control.
The default embedding model is `text-embedding-3-small`; the default
generation model is `gpt-4o-mini`. By default, CORS allows only local
Streamlit development origins at `localhost:8501` and `127.0.0.1:8501`.
Override CORS by supplying a comma-separated list of exact origins.

Current local code sets `OPENAI_GENERATION_MAX_OUTPUT_TOKENS=512` by default
(integer 1–16,384), passed as `max_completion_tokens` to Chat Completions.
`OPENAI_MAX_RETRIES=0` by default (integer 0–10), passed to the OpenAI client
for both embedding and generation calls. Override these environment variables
for production or smoke tests without changing retrieval settings. These
controls were deployed to `github-rag-api` on 2026-10-08. A token limit can truncate a supported answer;
it does not by itself cap input cost or implement an aggregate dollar budget. See
[deployment_cost_controls_preflight.md](../deployment/preflights/deployment_cost_controls_preflight.md) for the conservative live-test bound.

Current local code additionally defaults `RAG_MAX_GENERATION_INPUT_TOKENS` to
12,000 (integer 1–120,000). It counts the complete serialized system/user
messages with the selected model's tokenizer plus a 512-token framing reserve.
If necessary it clips excerpt prefixes while preserving every source ID,
metadata record, and ordering; clipped excerpts are marked incomplete. It
does not change retrieval ranking or the cutoff. Structured API citations
still expose the retrieved sources separately. If the instructions, question,
and source metadata alone cannot fit, the API returns its fixed abstention
without a generation call. Unsupported tokenizer mappings fail before
generation. See [deployment_input_budget_preflight.md](../deployment/preflights/deployment_input_budget_preflight.md) for the revised
two-request bound. These input/output/retry controls were deployed on 2026-10-08;
historical latency measurements predate them.

Install updated dependencies and start the local server from the project root:

```powershell
python -m pip install -e .
python -m uvicorn rag_assistant.api:app --host 127.0.0.1 --port 8000
```

Check database health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Ask a question (the default `top_k` is 5; valid values are 1 through 20):
the terminal must already have `API_AUTH_TOKEN` in its environment for this
example. The FastAPI and Streamlit processes load `.env` themselves; PowerShell
does not automatically import it. Set the token through a protected local
environment mechanism and do not echo it.

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -Headers @{ Authorization = "Bearer $env:API_AUTH_TOKEN" } `
  -ContentType 'application/json' `
  -Body '{"question":"How do I configure middleware?","top_k":5}'
```

The JSON response contains `answer`, a `citations` array with repository,
issue number, issue URL, source URL, chunk type, cosine similarity, and the
mode-specific retrieval score, plus `retrieval_metadata` including requested
`top_k`, retrieved count, and retrieval mode.
Questions must contain non-whitespace text and be no longer than 4,000
characters. Do not expose `.env` or commit credentials.

If the top retrieval score is below `RAG_CONFIDENCE_THRESHOLD`, the API
returns “There isn't enough evidence in the indexed issues to answer this
question.” without making a generation request. The default cutoff is
`0.5370554072220923`, calibrated against the generated 60-case evaluation set
in vector mode. On that small calibration set, it correctly refused all 15
unanswerable questions and wrongly refused 4 of 45 answerable questions
(41 correctly passed through). Treat this as a preliminary estimate; expand
the unanswerable set and recalibrate if the corpus or retrieval mode changes:

```powershell
python scripts/calibrate_confidence.py `
  --cases evaluation/evaluation_cases.generated.jsonl `
  --mode vector
```

The calibration report selects the cutoff with maximum balanced accuracy,
reports correctly refused and wrongly refused counts, and saves the complete
score list to [confidence_calibration_results.json](../experiments/retrieval/confidence_calibration_results.json). The selected value is
also the API default and the example `.env` value.

Current local code also handles a model's insufficient-evidence decision
deterministically: `[INSUFFICIENT_EVIDENCE]` is replaced with
"The retrieved excerpts do not provide enough evidence to answer this question."
Model-written summaries and inline citations are discarded on this path.
Retrieved sources remain separate in the structured `citations` array and UI;
their presence does not establish the unavailable answer. Supported answers
retain the existing cleanup and citation behavior. This hardening has not yet
been verified in the deployed Lambda.

The harder fifteen-case held-out check refused only 1/15 at the fixed 0.537
cutoff. Generation abstained on the fourteen passes, with one auxiliary
citation misattribution in the original run. This does not establish general
cutoff robustness. A later targeted replay of the same fourteen frozen
contexts verified the fixed abstention message and separate structured sources
through the local API with mocked dependencies. It did not test live retrieval
or deployed Lambda behavior. See [heldout_unanswerable_results_review.md](../experiments/abstention/heldout_unanswerable_results_review.md) and
[final_abstention_regression_comparison.md](../experiments/abstention/final_abstention_regression_comparison.md).

Each API request also logs retrieval, generation, and total latency, token
usage, refusal status, and estimated cost to the application log. The
generation/embedding token rates are configurable in `.env`; defaults are
rough estimates and should be checked against current OpenAI pricing. To
measure p50/p95 latency and average estimated cost over the eval questions:

```powershell
python scripts/measure_rag_performance.py `
  --cases evaluation/evaluation_cases.generated.jsonl
```

The detailed sample results are written to [rag_performance_results.json](../measurements/rag_performance_results.json).
The 2026-10-07 vector-mode run over all 60 cases measured p50 latency of
1.896 s, p95 of 3.817 s, average estimated cost of $0.000216/query, and
19 refusals (15 expected unanswerables plus 4 wrongly refused answerables).
These are historical local measurements, not deployed Lambda results or
service-level guarantees; that older script does not represent the final
distinct-issue retrieval configuration.

The final 2026-10-08 measurement ran sixty requests against current local code
with read-only RDS, production models (`text-embedding-3-small` and
`gpt-4o-mini`), vector retrieval, `ef_search=100`, thirty candidates collapsed
to five distinct issues, and cutoff `0.5370554072220923`. It used twelve queries
over five serial rounds, without warmups or retries.

| Observed outcome | Requests | Local total p50 | Local total p95 | Mean API token cost/query |
|---|---:|---:|---:|---:|
| Answered | 25 | 2.047 s | 4.815 s | $0.000257734 |
| Cutoff-refused | 30 | 0.399 s | 1.227 s | $0.000000217 |
| Model-abstained after cutoff pass | 5 | 1.301 s | 1.803 s | $0.000161840 |

Recorded token cost was $0.00725905, below the approved $0.03 cap. These costs
use API-reported usage and cached-input rates, not invoice reconciliation.
Percentiles are descriptive for this small repeated-query sample, especially
the five model abstentions. Client totals include the local test-client and
measurement/checkpoint overhead; setup is separate. No deployed API Gateway,
Lambda cold-start, or live endpoint latency result is claimed. Detailed
per-request tokens, cost, and component latencies are saved in
[final_latency_cost_results.json](../measurements/final_latency_cost_results.json); see [final_latency_cost_report.md](../measurements/final_latency_cost_report.md).

The final 2026-10-08 deployment pushed one image with input/output/retry
controls to the existing ECR repository and updated only the existing
`github-rag-api` Lambda code in `us-east-2`. The digest is
`sha256:1e08220c4cbff6fbd46ea5f9d191532e7c2cd6c24f09731e556123340e2832e4`;
compressed image size is 216,247,900 bytes. Existing images, Lambda
configuration and infrastructure were retained.

Exactly three live smoke checks returned HTTP 200: `/health`, the Starlette
settings question (answered with citations), and the latest-Python-release
question (cutoff-refused without generation). Client wall times were 4.622 s,
6.075 s and 0.912 s respectively. These are individual live smoke timings,
not live p50/p95 metrics or billed Lambda durations. The answerable check
validates response plumbing and citation indices, not an exhaustive factual
review; its illustrative settings endpoint exposes secrets and the response
warns that filtering/masking still needs implementation. The live checks did
not exercise model-selected abstention; that path remains locally verified.

API-reported usage was 29 embedding, 1,213 generation input and 120 output
tokens, costing $0.00025453 at standard uncached rates, below the $0.005 cap.
The verified input/output/retry settings bounded the two requests to
$0.00421498 before execution. Cached-token discounts and actual AWS billed
cost are not reconciled from these responses. No retries, infrastructure
creation, database writes, retrieval/cutoff changes or rollback occurred.
See [final_deployment_live_report.md](../deployment/live/final_deployment_live_report.md) and [final_deployment_live_results.json](../deployment/live/final_deployment_live_results.json).
The earlier health-only deployment attempt remains recorded in
[deployment_live_report.md](../deployment/live/deployment_live_report.md); its skipped `/ask` checks are historical.

## Streamlit interface and Community Cloud deployment

`streamlit_app.py` calls the authenticated `/ask` API from server-side Python.
It displays the grounded answer, the predicted category and confidence of the
top retrieved issue, clickable GitHub citations, and expandable retrieval
metadata. The category is the stored issue classification, not a
classification of the user's question. API tokens are read only from
Streamlit server-side secrets and are never sent to browser code.

For local use, install the UI extra and start the FastAPI server in another
terminal:

```powershell
python -m pip install -e ".[ui]"
python -m uvicorn rag_assistant.api:app --host 127.0.0.1 --port 8000
python -m streamlit run streamlit_app.py
```

To deploy on Streamlit Community Cloud:

1. Push the project to a GitHub repository accessible to the Community Cloud
   account. The root `requirements.txt` installs the application and UI
   dependencies. Keep `.env`, `.streamlit/secrets.toml`, and all credentials
   out of the repository.
2. In Community Cloud, create an app from that repository and select
   `streamlit_app.py` as the app entry point.
3. In the app's **Settings → Secrets** panel, configure these server-side
   secrets (names only; do not put them in source code):
   - `RAG_API_URL` — use the deployed HTTPS endpoint:
     `https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com`
   - `API_AUTH_TOKEN` — the existing bearer token stored in AWS Secrets
     Manager at `github-rag/dev/api-runtime`. Copy it only through a trusted,
     private secret-management workflow; never paste it into code, a commit,
     a URL, or a client-side component.
4. Save the secrets and redeploy/reboot the app. The app reports a clear
   missing-secret, invalid-token (401), connection, or backend error without
   revealing secret values.

For local development only, `.env` remains supported as a fallback. The
Community Cloud app reads `st.secrets` first. A public Streamlit app can be
used by anyone with its URL; the API token is protected from visitors but
requests can incur OpenAI/AWS charges. Monitor API usage and disable the app
when it is no longer needed.

## Docker and AWS deployment package

`Dockerfile` packages FastAPI as an AWS Lambda container image using Mangum;
`.dockerignore` explicitly excludes `.env`, virtual environments, and tests.
Build locally after Docker Desktop is running:

```powershell
docker build -t trustworthy-rag-assistant .
```

The Lambda runtime reads `RAG_SECRETS_ARN` and loads the JSON secret from AWS
Secrets Manager. Store `OPENAI_API_KEY`, `PGPASSWORD`, and `API_AUTH_TOKEN`
there; include `GITHUB_TOKEN` for the ingestion Lambda. Grant the Lambda
execution role only `secretsmanager:GetSecretValue` for that secret. Configure
PostgreSQL host/database/user, model names, S3 bucket/region, and
`RAG_SECRETS_ARN` as Lambda environment settings. Never place `.env` in the
image or pass secret values on a command line.

The dev deployment uses ECR repository `github-rag-api`, Lambda function
`github-rag-api`, HTTP API `github-rag-api-dev`, Secrets Manager secret
`github-rag/dev/api-runtime`, and execution role
`github-rag-lambda-execution`. The public API Gateway endpoint is configured
in the local `.env` as `RAG_API_URL`; `/ask` requires the bearer token while
`/health` is public and checks PostgreSQL.

Lambda runs in two private subnets in a private VPC security group. Its
private route table sends outbound traffic through the single development NAT
gateway in a public subnet. The RDS security group permits PostgreSQL only
from the Lambda security group and the pre-existing administrator client
rule. This single-NAT layout is for development, not high availability.

### Removing the development deployment

In the AWS console in `us-east-2`, delete API `github-rag-api-dev` and Lambda
`github-rag-api` first. To stop the ongoing networking charges, delete the
development NAT gateway, wait until its state is `Deleted`, then release its
associated Elastic IP allocation. The NAT gateway and its Elastic IP are the
ongoing network-cost resources.

After Lambda has been deleted, remove the NAT default route from the
development private route table, disassociate that table from the two
development private subnets, then delete the route table and those subnets.
In the RDS security group, remove only the inbound TCP 5432 rule whose source
is the Lambda security group; keep the existing administrator client rule.
Then delete that Lambda security group, ECR repository `github-rag-api`
(including its images), execution role `github-rag-lambda-execution` and its
inline policy, log group `/aws/lambda/github-rag-api`, and secret
`github-rag/dev/api-runtime` if they are no longer needed. Secret deletion
uses Secrets Manager's recovery window unless force deletion is explicitly
selected.
