# Pipeline reference

Historical commands below can call paid services, write data or change infrastructure.
They are documentation, not authorization to execute. Historical checkpoints are dated;
see the root README and live reports for current verification.

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

Preview the first 25 issues without writing rows or calling OpenAI. To preview
the complete requested three-repository corpus, use `--all`. The CLI supports
`--repos` to restrict the run:

```powershell
python -m rag_assistant.embed_issue_chunks --all --dry-run --repos tiangolo/fastapi,encode/starlette,pydantic/pydantic
```

Review the pending chunk count, token count, and estimated cost before
embedding. The estimate excludes chunks with reusable embeddings and checks
content hashes; existing-chunk checks are batched to stay within PostgreSQL's
parameter limit. Run the full embedding pass for the three repositories with:

```powershell
python -m rag_assistant.embed_issue_chunks --all --repos tiangolo/fastapi,encode/starlette,pydantic/pydantic
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
runs data-quality checks after each layer before advancing watermarks. A
standalone report can be run against an already populated Bronze/Silver/Gold
pipeline:

```powershell
python -m rag_assistant.data_quality
```

Malformed Bronze JSON, Silver key/null/duplicate/comment-shape violations,
missing Gold embeddings, wrong vector dimensions, orphan chunks, and
unexplained count differences fail loudly. Dedupe/rejection counts and issues
without chunkable content are called out in the layer reports as expected
drops. AWS SDK credentials are
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

## Step 5: Bug/feature/usage classification

The classification layer assigns each clean issue one category:
`bug`, `feature`, `usage`, or `unknown`. The transparent heuristic baseline
uses title/body signals and includes a short rationale and a high/medium/low
confidence. `unknown` is a valid abstention when signals are weak or
conflicting. The optional LLM classifier uses the configured generation model
and the same explicit category definitions; its rationale/confidence is a
model estimate, not a human label.

The curated, version-controlled [classification_cases.jsonl](../../evaluation/classification_cases.jsonl) file contains 12
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
