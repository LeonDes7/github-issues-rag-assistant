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
- `evaluation_cases.jsonl` and `classification_cases.jsonl` — small,
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

## Step 1: GitHub Issues to the S3 Bronze layer

The ingestion command collects all closed issues from the configured public
repositories via the GitHub REST API. Pull requests are excluded, each issue's
comments are fetched across all pages, and issues without comments are retained
with an empty comment list. Raw GitHub issue and comment response objects are
stored unchanged as one JSON object per S3 key. The default repositories are
`tiangolo/fastapi`, `encode/starlette`, and `pydantic/pydantic`.

Set `GITHUB_TOKEN`, `GITHUB_REPOS`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, and `S3_BUCKET` in the local
`.env` file. `AWS_SESSION_TOKEN` is optional. Separate repository names with
commas and omit spaces where possible. The token is sent only to
`api.github.com`; AWS credentials are used only by the S3 client. `.env` is
ignored by Git.

Run from the project root after installing dependencies:

```powershell
python -m rag_assistant.ingest_github_issues
```

The default is an unbounded historical backfill. Optional command-line or
environment limits (`--target-records-per-repo`,
`--max-entries-to-scan-per-repo`) are available only for deliberately partial
runs. Requests use GitHub's pagination links, bounded retries with exponential
backoff, and primary/secondary rate-limit handling based on response headers.

Each issue is written immediately, so a failed run resumes by skipping
already-present S3 objects rather than repeating comment downloads. The stable
keys are:

```text
bronze/github/repo=tiangolo__fastapi/issue=<number>.json
bronze/github/repo=tiangolo__fastapi/runs/<timestamp>/manifest.json
```

The manifest reports scanned issues, pull requests skipped, resumed issues,
uploaded issues, and downloaded comments. Existing timestamped Bronze JSONL
objects remain readable by the loader.

## Step 2: Clean the selected Bronze data and load RDS

The loader discovers per-issue objects under each repository prefix and also
accepts the earlier selected Bronze JSONL objects; it does not modify Bronze.

The loader uses the AWS and PostgreSQL settings already configured in `.env`.
It creates `public.github_issues_clean`, with a unique constraint on
`(repository, issue_number)`, and uses PostgreSQL upserts so reruns update
changed records rather than adding duplicates or rewriting unchanged rows.
Each clean issue stores a content hash and GitHub `updated_at`; the hash covers
the material used to build its chunks. Labels, comments, and author
associations are stored as JSONB; issue/comment text is normalized while
retaining Markdown and code formatting. The raw API response remains available
unchanged in S3 Bronze.

`resolution_text` is selected from the latest non-empty comment by an
`OWNER`, `MEMBER`, or `COLLABORATOR` posted strictly before issue closure.
`resolution_heuristic` records how that text was selected and
`resolution_confidence` is deliberately `low`: it is a clue, not guaranteed
ground truth. Missing closure dates or eligible comments leave the resolution
empty and are included in validation counts.

Run the focused tests and, when ready, load the three specified objects from
the project root:

```powershell
python -m unittest discover -s tests -p "test_load_bronze_to_rds.py" -v
python -m rag_assistant.load_bronze_to_rds
```

The load prints inserted and updated row counts, the total table row count,
rejected/duplicate record counts, and validation summaries for missing bodies
and heuristic resolutions. Records missing repository, a positive issue
number, or a valid GitHub URL (and duplicate repository/issue keys) are
rejected rather than loaded.

## Step 3: Chunking and embeddings for Gold retrieval

The embedding step reads `public.github_issues_clean` (schema verified before
implementation), creates contextual token-sized chunks from issue bodies and
individual comments, and separately labels a stored heuristic resolution when
one exists. Each chunk includes repository, issue number, and title context;
Markdown/code fences are kept together when they fit the chunk limit. Existing
Bronze objects remain untouched.

Set `OPENAI_API_KEY` in the local `.env` file. The script creates
`public.github_issue_chunks` with a composite foreign key to the clean issue
table, a vector(1536) embedding, a unique chunk identity, and an HNSW cosine
similarity index. It uses `text-embedding-3-small` in batches of 100 and stores
only missing embeddings. Re-running on unchanged text reuses the existing
embedding; changed text resets only that chunk's embedding. Embedding batches
are retried for transient connection, rate-limit, and server errors.

Preview the first 25 issues without writing rows or calling OpenAI:

```powershell
python -m rag_assistant.embed_issue_chunks --limit 25 --dry-run
```

Run the embedding pass for the first 25 issues:

```powershell
python -m rag_assistant.embed_issue_chunks --limit 25
```

The report includes chunk counts by type, estimated/actual API calls and
tokens, an approximate cost at USD 0.02 per million input tokens (verify
current OpenAI pricing before relying on this estimate), failed/skipped
embeddings, and an example nearest-neighbor similarity result without
printing chunk text. `--limit` can be increased after reviewing the test
result.

## Incremental daily pipeline

Run the complete Bronze-to-Gold flow locally with:

```powershell
python -m rag_assistant.incremental_pipeline
```

The pipeline creates `public.github_ingestion_watermarks`, calls GitHub with
each repository's last successful `updated_at` watermark, loads Bronze
idempotently, embeds only issues whose content hash differs from Gold, and
advances watermarks only after every stage succeeds. AWS SDK credentials are
optional when running with an IAM role; `AWS_DEFAULT_REGION` and `S3_BUCKET`
are still required. The ingestion Lambda entry point is
`rag_assistant.ingestion_lambda_handler.handler`. Deploy a dedicated ingestion
Lambda from the existing ECR image with its image command set to that handler;
the existing API Lambda keeps `rag_assistant.lambda_handler.handler`.

Create the daily 03:00 UTC EventBridge Scheduler rule after creating a role
that trusts `scheduler.amazonaws.com` and can invoke the ingestion Lambda:

```powershell
.\scripts\create_daily_ingestion_schedule.ps1 `
  -LambdaArn "arn:aws:lambda:us-east-2:123456789012:function:github-rag-ingestion" `
  -ScheduleRoleArn "arn:aws:iam::123456789012:role/github-rag-scheduler" `
  -Region "us-east-2"
```

## Step 4: Local FastAPI retrieval and generation API

The local API exposes `GET /health` to verify PostgreSQL connectivity and
`POST /ask` to embed a question, retrieve the nearest issue chunks with
pgvector cosine distance, and generate a concise answer grounded only in those
retrieved excerpts. Citation metadata is built from retrieved database rows,
not from model-generated source URLs. Heuristic-resolution chunks remain
labeled low-confidence evidence in the prompt.

Set `OPENAI_API_KEY`, `API_AUTH_TOKEN`, `OPENAI_EMBEDDING_MODEL`,
`OPENAI_GENERATION_MODEL`, and optionally `CORS_ALLOWED_ORIGINS` in `.env`.
`API_AUTH_TOKEN` is required for `/ask`; use a high-entropy token and do not
check it into source control.
The default embedding model is `text-embedding-3-small`; the default
generation model is `gpt-4o-mini`. By default, CORS allows only local
Streamlit development origins at `localhost:8501` and `127.0.0.1:8501`.
Override CORS by supplying a comma-separated list of exact origins.

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
issue number, issue URL, source URL, chunk type and cosine similarity score,
and `retrieval_metadata` including requested `top_k` and retrieved count.
Questions must contain non-whitespace text and be no longer than 4,000
characters. Do not expose `.env` or commit credentials.

## Step 6: Local RAG evaluation

`evaluation_cases.jsonl` is a small, version-controlled held-out suite of 10
cases selected from the current corpus. Each case is labeled
`manually_verified`, `heuristic`, or `unresolved`, with a note describing the
label. Cases marked `heuristic` rely on the extracted maintainer-comment
resolution and are reported separately; that signal is uncertain and is not
treated as guaranteed ground truth. Unresolved cases intentionally expect an
abstention.

Run the suite locally with top-5 retrieval:

```powershell
python -m rag_assistant.evaluate --top-k 5
```

The command calls the local retrieval/generation components, prints a concise
metrics summary and up to five failure examples, and stores run metadata and
per-case outputs in `public.rag_evaluation_runs` and
`public.rag_evaluation_case_results`. Stored metadata includes UTC timestamps,
embedding and generation model names, `top_k`, case counts, and metrics.
Retrieval Hit@k, Recall@k, and MRR are computed against expected repositories
and issue numbers or issue URLs. The primary retrieval summary uses only
`manually_verified` cases; heuristic cases are reported separately as
exploratory results.

Generation evaluation records appropriate abstention, valid citation
references, and whether factual sentences have cited evidence with lexical
overlap. Lexical grounding is an automated screening heuristic, not factual
verification. LLM-as-judge scoring is optional:

```powershell
python -m rag_assistant.evaluate --top-k 5 --judge
```

Judge results are labeled automated estimates, not absolute truth. The
evaluation command does not alter issue or chunk rows.

## Step 5: Bug/feature/usage classification

The classification layer assigns each clean issue one category:
`bug`, `feature`, `usage`, or `unknown`. The transparent heuristic baseline
uses title/body signals and includes a short rationale and a high/medium/low
confidence. `unknown` is a valid abstention when signals are weak or
conflicting. The optional LLM classifier uses the configured generation model
and the same explicit category definitions; its rationale/confidence is a
model estimate, not a human label.

The curated, version-controlled `classification_cases.jsonl` file contains 12
manually reviewed examples, balanced across bug, feature, and usage. Evaluate
the baseline and LLM on those cases without writing predictions:

```powershell
python -m rag_assistant.classify --mode both --evaluate-only
```

Classify all clean issue rows with the heuristic and print its held-out
evaluation:

```powershell
python -m rag_assistant.classify --mode heuristic --limit 1000
```

Persist optional LLM predictions for all issues (makes one model request per
issue) and compare against the same cases:

```powershell
python -m rag_assistant.classify --mode llm --limit 1000
```

`--mode both` runs and persists both classifiers for the selected issues.
Predictions are stored idempotently in `public.github_issue_classifications`,
keyed by issue, classification method, and classifier version/model. The
evaluation output includes accuracy, per-label precision/recall/F1, and a
confusion matrix. This small labeled sample is a smoke evaluation, not a
production-quality benchmark; review and expand labels before relying on the
classifier.

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
