# Trustworthy RAG Assistant for GitHub Issues

An evidence-grounded assistant for closed FastAPI, Starlette and Pydantic issues.
It retrieves PostgreSQL issue discussions, answers from the retrieved evidence,
and returns GitHub source links. Unsupported questions can be refused.

## Current status

The existing `github-rag-api` Lambda in `us-east-2` is deployed and smoke-tested.
Health, safe model abstention and a supported cited answer passed on 2026-10-08.
These checks establish behavior for their individual cases, not general accuracy.

The API endpoint is:
`https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com`
`/ask` requires bearer authentication; `/health` is public.
The Streamlit interface calls the API from server-side Python.
The backend remediation is deployed. Streamlit safeguards are committed and pushed,
but public rollout is not independently verified.

## Architecture

1. GitHub closed issues and comments are stored unchanged in S3 Bronze.
2. Clean issue records are upserted into PostgreSQL Silver.
3. Issue/comment chunks and embeddings form the Gold retrieval corpus.
4. FastAPI retrieves evidence, applies confidence/safety controls and generates answers.
5. Mangum serves the API through Lambda and API Gateway; Streamlit displays results.

Pull requests are excluded. Issues without comments are retained.
Heuristic resolutions select eligible maintainer comments before closure.
They are low-confidence clues, not verified ground truth.

The recorded corpus contains **9,555 issues, 43,535 comments and 63,002 chunks**.
Data-quality checks passed; 276 duplicate Bronze rows were deduplicated.
Fourteen issues without chunkable content were expected not to appear in Gold.
Duplicate/alias auditing is complete; alias rows remain stored, without deletion.
Retrieval is restricted to the three configured repository names.

## Repository layout

| Path | Purpose |
|---|---|
| `src/rag_assistant/` | API, ingestion, cleaning, embeddings, evaluation, classification |
| `streamlit_app.py` | Streamlit UI and source links |
| `scripts/` | Explicitly invoked maintenance, experiment and verification tools |
| `tests/` | Local unit tests using mocks where services would otherwise be required |
| `evaluation/` | Reviewed evaluation fixtures and review CSV |
| [docs/](docs/README.md) | Detailed reports, preflights, operations and historical evidence |
| `artifacts/` | Ignored disposable outputs from future runs |

## Local setup and tests

Create a virtual environment, then install from the repository root:

```powershell
python -m pip install -e .
python -m unittest discover -s tests -q
```

The current local checkpoint has **104 passing tests**.
Copy setting names from `.env.example` into a private local `.env` as needed.
Do not commit credentials, connection strings or `.streamlit/secrets.toml`.
Prefer IAM roles or an AWS profile to long-lived static access keys.

Running the API requires authorized PostgreSQL and OpenAI access:

```powershell
python -m uvicorn rag_assistant.api:app --host 127.0.0.1 --port 8000
```

For the local UI, install the extra and use a separate terminal:

```powershell
python -m pip install -e ".[ui]"
python -m streamlit run streamlit_app.py
```

Tests are local; ingestion, evaluation, embedding and deployment commands can
make paid calls, write data or change infrastructure. Review their scope first.
The database connection setup command creates the vector extension if missing;
it is not a read-only health check.

## API usage

`GET /health` checks PostgreSQL connectivity.
`POST /ask` takes a nonblank question of at most 4,000 characters.
The default `top_k` is 5; valid values are 1 through 20.

With the bearer token already set through a private environment mechanism:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/ask `
  -Headers @{ Authorization = "Bearer $env:API_AUTH_TOKEN" } `
  -ContentType 'application/json' `
  -Body '{"question":"What problem did the reporter observe when sending larger base64-encoded video frames over a WebSocket?","top_k":5}'
```

PowerShell does not automatically load `.env`; do not echo the token.
FastAPI and local Streamlit load `.env` themselves.
The JSON response includes `answer`, structured `citations`,
`retrieval_metadata` and `performance` with latency/token/cost information.
Source URLs and metadata come from retrieved rows, not model-created URLs.
Classification/confidence describes the retrieved issue, not the user's question.
Heuristic classification and lexical grounding checks are estimates.

## Production settings and safeguards

| Control | Current setting |
|---|---|
| Repositories | `tiangolo/fastapi`, `encode/starlette`, `pydantic/pydantic` |
| Embeddings | `text-embedding-3-small`, 1,536 dimensions |
| Generation | `gpt-4o-mini` |
| Retrieval | Vector, `ef_search=100`, fetch 30, collapse to five distinct issues |
| Confidence cutoff | `0.5370554072220923` |
| Generation input | `RAG_MAX_GENERATION_INPUT_TOKENS=12000` |
| Generation output | `OPENAI_GENERATION_MAX_OUTPUT_TOKENS=512` |
| OpenAI retries | `OPENAI_MAX_RETRIES=0` |

Below the cutoff, no generation call is made. The fixed answer is:
?There isn't enough evidence in the indexed issues to answer this question.?
A model insufficient-evidence decision returns only:
?The retrieved excerpts do not provide enough evidence to answer this question.?
Model-written side claims and inline citations are discarded on that path.
Retrieved sources remain separate; their presence does not prove the unavailable answer.

The input budget counts system/user messages with the model tokenizer and a
512-token framing reserve. Excerpts can be clipped while source IDs, ordering
and metadata remain intact; clipped text is marked incomplete.
If instructions/question/source metadata cannot fit, generation is skipped.
Unsupported tokenizer mappings fail before generation.
Output limits can truncate an answer; token limits are not an aggregate dollar budget.

Recognizable literal credentials are redacted before generation and in answers.
The known unsafe settings-dump pattern is removed from fenced evidence and
withheld if generated. Source links and citation metadata remain available.
This is pattern-based protection, not complete credential or unsafe-code detection.
Setting-name references and masked examples are not proof of a credential leak.

## Retrieval and abstention evidence

On the original 45 generated answerable cases, not yet human-verified, final retrieval
scored **Hit@5 0.9333, Recall@5 0.9333 and MRR 0.8389**.
This is a small evaluation, not a general accuracy guarantee.
The earlier vector/hybrid baseline both scored 0.8000/0.8000/0.7526.
Full case evidence is in [retrieval reports](docs/experiments/retrieval/issue_collapse_experiment.md).

The small original calibration refused 15/15 unanswerables and wrongly refused
4/45 answerables (41 passed). The harder held-out set refused only **1/15**
at the fixed rounded 0.537 cutoff. Do not treat that cutoff as generally robust.
Generation abstained on the remaining 14, with one auxiliary citation
misattribution in the original run and no unsupported requested solution.
A later 14-case frozen-context replay verified fixed abstentions and separate
sources through the local API with mocked dependencies; it did not test live retrieval.
See [held-out review](docs/experiments/abstention/heldout_unanswerable_results_review.md)
and [final regression](docs/experiments/abstention/final_abstention_regression_comparison.md).

## Historical local latency and cost

The final local measurement used 60 requests: 12 queries over five serial rounds,
read-only RDS, production models, no warmups and no retries.
It predates deployed input/output controls and redaction remediation.

| Outcome | Requests | Local p50 | Local p95 | Mean token cost/query |
|---|---:|---:|---:|---:|
| Answered | 25 | 2.047 s | 4.815 s | $0.000257734 |
| Cutoff-refused | 30 | 0.399 s | 1.227 s | $0.000000217 |
| Model-abstained | 5 | 1.301 s | 1.803 s | $0.000161840 |

Total recorded token cost: **$0.00725905**, below the $0.03 approved cap.
Costs use API usage and cached-input rates, not reconciled invoices.
Small repeated samples give descriptive percentiles, especially five abstentions.
Client totals include local test-client/checkpoint overhead; setup is separate.
These are **local current-code measurements, not deployed Lambda latency**.
The older 60-case run measured p50 1.896 s, p95 3.817 s,
$0.000216/query and 19 refusals; it predates final distinct-issue retrieval.
See [measurement report](docs/measurements/final_latency_cost_report.md).

## Live verification

Current remediation image: **216,254,880 compressed bytes**.
Digest: `sha256:3ee06641a7814eec96ed08c553ab7a15fdb82095e5f0ef983636d2c6f1855330`.
Only the existing Ohio Lambda code image was updated; prior images were retained.

| Check | Verified outcome | Client time | Token cost |
|---|---|---:|---:|
| Remediation `/health` | HTTP 200, database reachable | 3.919 s | $0 |
| Settings-dump `/ask` | Fixed safe model abstention, five separate sources | 5.725 s | $0.00021760 |
| Safe video-frame `/ask` | Supported disconnect answer citing FastAPI #2071 | 8.784 s | $0.00019041 |

These are individual live smoke observations, not live p50/p95 or billed durations.
Standard uncached usage costs exclude invoice/cache reconciliation; AWS billed costs
are unavailable. No retries, infrastructure creation or database writes occurred.
The earlier settings answer was an unsafe recommendation, not a literal credential.
Historical failed/skipped checks and the prior $0.00025453 deployment remain recorded.
See [remediation](docs/deployment/live/remediation_deployment_live_report.md),
[supported answer](docs/deployment/live/safe_answer_live_report.md),
and [security review](docs/security/live_answer_secret_review.md).

## Operations and limitations

The development deployment uses existing ECR/Lambda/API Gateway, Secrets Manager,
a single NAT gateway and single-AZ RDS. This topology is not high availability.
Retained ECR images, RDS, NAT and public IPv4 can accrue ongoing costs.
A public UI protects its server-side token but visitors can incur paid API usage.
Keep credentials private and monitor usage; don't infer an unlimited spending cap.
The 10-case evaluation and 12-case classification fixtures are small samples.
Optional judge scores and classification confidence are not human ground truth.

Detailed setup, commands, historical measurements and teardown guidance:

- [Pipeline and classification](docs/operations/pipeline.md)
- [Evaluation methodology](docs/operations/evaluation.md)
- [API, UI and deployment operations](docs/operations/deployment.md)
- [All reports and preflights](docs/README.md)
