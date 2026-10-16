# Trustworthy RAG Assistant for GitHub Issues

An evidence-grounded assistant for closed **FastAPI, Starlette, and Pydantic**
issues. Ask a question, retrieve relevant issue discussions, and get an answer
with GitHub citations. When the evidence is insufficient, the assistant can abstain.

Deployed on **AWS** using **S3, RDS for PostgreSQL/pgvector, ECR, Lambda,
API Gateway, and Secrets Manager**, with FastAPI, OpenAI, and a Streamlit interface.

![GitHub Issues Assistant question form](docs/images/streamlit-issues-assistant.png)

**Demo video:** [link pending]

## Architecture

```mermaid
flowchart LR
    GitHub[Closed GitHub issues and comments] --> S3
    UI[Streamlit] --> Gateway
    subgraph AWS[AWS deployment]
        S3[Amazon S3: Bronze data] --> RDS[Amazon RDS: Silver issues and Gold pgvector chunks]
        Gateway[Amazon API Gateway] --> Lambda[AWS Lambda: FastAPI / Mangum]
        ECR[Amazon ECR: container image] -. deployed to .-> Lambda
        Secrets[AWS Secrets Manager] -. runtime secrets .-> Lambda
        Lambda --> RDS
    end
    Lambda --> OpenAI[OpenAI: embeddings and generation]
    Lambda --> Answer[Answer with GitHub citations or abstention]
    Answer --> UI
```

The pipeline stores raw issue discussions, cleans and chunks them, and builds
embeddings for retrieval. The API retrieves 30 candidate chunks and selects up
to five distinct issues before applying confidence and generation safeguards.
The Streamlit client calls the authenticated API from server-side Python.

### AWS implementation

The development backend is deployed in **us-east-2 (Ohio)**. AWS provides both
the data storage and the API runtime:

| Service | Role in the project |
|---|---|
| **Amazon S3** | Stores raw GitHub issues and comments in the Bronze layer. |
| **Amazon RDS for PostgreSQL** | Stores cleaned Silver records and Gold chunks with pgvector embeddings for similarity search. |
| **Amazon ECR** | Stores the container images used to deploy the backend. |
| **AWS Lambda + Amazon API Gateway** | Exposes FastAPI through Mangum as an HTTPS API, including authenticated `/ask` and public `/health` routes. |
| **AWS Secrets Manager** | Supplies the OpenAI API key, database password, and API bearer token to the Lambda runtime. |
| **Amazon VPC, security groups, and NAT gateway** | Place Lambda in private subnets, restrict database access, and provide outbound access for external API calls. |

The deployment uses a Lambda execution role for AWS access. Database ingress is
restricted to the Lambda security group and an existing administrator client rule.
The single-NAT, single-AZ RDS setup is a development topology; infrastructure
costs are separate from the per-query OpenAI costs reported below.

The backend has been deployed and checked through its live API Gateway endpoint.
The pipeline's rerun safety was also verified against the real database. New-issue
incremental ingestion remains untested, and no ingestion schedule is deployed.
See [AWS deployment and networking](docs/operations/deployment.md),
[deployment verification](docs/deployment/live/remediation_deployment_live_report.md),
and [database replay evidence](docs/deployment/live/idempotency_live_report.md).

## Results at a glance

Recorded corpus: **9,555 issues, 43,535 comments, and 63,002 chunks** across the
three configured repositories. Pull requests are excluded.

| Evidence | Scope and result |
|---|---|
| Historical retrieval development set | **45 generated answerable cases**, before author review. Hit@5 **0.8000 to 0.9333**; Recall@5 **0.9333** and MRR **0.7526 to 0.8389** for final retrieval. |
| Author-approved retrieval set | **44 kept answerable cases** (43 approved + one edited), plus 15 off-topic cases. Rescore: **41/44 hits**, Hit@5 / Recall@5 **0.9318**, MRR **0.8504**; **2/44** false refusals at the unchanged cutoff. |
| Deployed API measurement, October 16, 2026 | Health passed; all **10 approved answerable requests** returned HTTP 200. **7/10** were successful, supported cited answers after Codex source-support review. |
| Deployed latency, seven qualifying answers | End-to-end **p50 2.538 s / p95 4.311 s**. |
| OpenAI cost, seven qualifying answers | Average **$0.00031237/answer**; total **$0.00218658**. Across all ten attempts: **$0.00322565**. |

The deployed summary excludes one answer without inline citations, one abstention,
and one off-target answer; their costs remain in the all-attempt total. Percentiles
are descriptive because the qualifying sample is seven. Costs use reported tokens
at standard uncached rates, without invoice reconciliation. **No local latency is
included in these deployed numbers.**

The 44-case rescore completed on October 16, 2026 using read-only database retrieval
and one 13-token embedding call ($0.00000026). It measures retrieval with the
production configuration, not generated-answer quality or deployed latency.
Historical 45-case scores use a different case set and remain separate.

Evidence: [retrieval experiments](docs/experiments/retrieval/issue_collapse_experiment.md),
[44-case rescore results](docs/experiments/retrieval/author_reviewed_rescore_report.md),
and [deployed measurement with raw results](docs/measurements/deployed_latency_cost_report.md).

## Quick start

Use Python 3.10 or newer. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[ui]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

**105 tests pass** at this checkpoint. Unit tests use mocks where external services
would otherwise be required.

Copy [.env.example](.env.example) to a private `.env` and configure PostgreSQL,
OpenAI access, and `API_AUTH_TOKEN`. Keep credentials and Streamlit secrets out of
Git. The API and local Streamlit app load `.env`; PowerShell does not load it
automatically.

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn rag_assistant.api:app --host 127.0.0.1 --port 8000
```

Start the UI in another terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

`GET /health` checks database connectivity. `POST /ask` requires bearer
authentication and accepts `question` and `top_k` (default 5). Responses include
an answer, structured citations, retrieval metadata, and latency/token/cost fields.
See [API usage and configuration](docs/operations/deployment.md) for examples,
deployed settings, safeguards, and deployment instructions. Ingestion, embeddings,
and evaluation can incur paid calls or write data; they are separate from unit tests.

## Limitations

- Evaluation sets are small. Historical retrieval metrics and the deployed sample
  do not establish general answer accuracy.
- On 15 harder held-out unanswerables, the retrieval cutoff refused only **1/15**.
  Generation abstained on the other 14 in the original run, with one auxiliary
  citation misattribution. [Abstention review](docs/experiments/abstention/heldout_unanswerable_results_review.md).
- Credential redaction and unsafe-pattern filtering are pattern-based protections.
  Heuristic resolutions, classification confidence, and lexical grounding checks
  are estimates rather than human ground truth.
- Rerun safety is verified on already loaded data. Incremental ingestion with
  new issues remains untested, and no refresh schedule is deployed.
- The development deployment uses single-AZ RDS and a single NAT gateway; it is
  not highly available. Infrastructure and public API usage can incur ongoing costs.
- Live Streamlit checks passed for a cited answer, an off-topic refusal, and a
  safe settings response. These checks establish behavior for those individual cases.

## Project guide

| Path | Contents |
|---|---|
| `src/rag_assistant/` | API, ingestion, cleaning, embeddings, evaluation, classification |
| `streamlit_app.py` | Streamlit interface and source links |
| `evaluation/` | Author-reviewed fixtures, original cases, and review CSV |
| `tests/` | Local unit tests |
| `scripts/` | Maintenance, experiments, and verification tools |
| [docs/](docs/README.md) | Reports, operational references, and historical evidence |

- [Evaluation methodology and reviewed fixtures](docs/operations/evaluation.md)
- [Deployed latency and cost report](docs/measurements/deployed_latency_cost_report.md)
- [Historical local measurements](docs/measurements/final_latency_cost_report.md)
- [API, safeguards, deployment history, and operations](docs/operations/deployment.md)
- [Data pipeline and classification](docs/operations/pipeline.md)
- [Real-database idempotency verification](docs/deployment/live/idempotency_live_report.md)
- [Security review](docs/security/live_answer_secret_review.md)
- [All reports and preflights](docs/README.md)
