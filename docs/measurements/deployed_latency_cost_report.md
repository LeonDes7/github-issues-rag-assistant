# Deployed API latency and OpenAI cost - October 16, 2026

One GET /health passed (HTTP 200, database reachable), followed by exactly ten approved answerable sequential POST /ask requests from the approved fixed plan. All ten returned HTTP 200. No retries, redirects, warmups, replacement requests, AWS changes, secret changes, or Streamlit changes. No additional OpenAI calls for review.

## Successful cited answers only

**7/10 were successful, supported cited answers** and qualified after citation and source-support review. Deployed HTTPS end-to-end p50: **2.538 s**; p95: **4.311 s**.

Average OpenAI cost per qualifying answer: **$0.00031237**. Total for seven qualifying answers: **$0.00218658**. Total for all ten requests, including exclusions: **$0.00322565**.

Costs use API-reported embedding, generation input, and generation output tokens at standard uncached rates ($0.02, $0.15, and $0.60 per million respectively). Cached invoice breakdown and AWS billed cost are unavailable. The recorded call count is inferred from nonzero embedding/generation token usage: ten embedding and ten generation calls. No usage is missing.

## Per-request observations

| Case | Outcome | HTTPS round-trip seconds | OpenAI USD |
|---|---|---:|---:|
| generated-tiangolo-fastapi-2071 | successful_cited_answer | 4.915 | 0.00017841 |
| generated-encode-starlette-542 | successful_cited_answer | 2.351 | 0.00026566 |
| generated-tiangolo-fastapi-618 | excluded_missing_inline_citations | 3.601 | 0.00063674 |
| generated-pydantic-pydantic-4999 | successful_cited_answer | 2.146 | 0.00037129 |
| generated-pydantic-pydantic-8499 | excluded_model_abstention | 2.646 | 0.00016649 |
| generated-tiangolo-fastapi-1873 | excluded_off_target | 2.677 | 0.00023584 |
| generated-pydantic-pydantic-1060 | successful_cited_answer | 2.902 | 0.00047372 |
| generated-pydantic-pydantic-10131 | successful_cited_answer | 2.882 | 0.00023536 |
| generated-encode-starlette-1454 | successful_cited_answer | 2.065 | 0.00025503 |
| generated-encode-starlette-818 | successful_cited_answer | 2.538 | 0.00040711 |

FastAPI #618 lacked inline citations; Pydantic #8499 abstained; FastAPI #1873 returned cited dependency-injection discussion but did not answer the requested testing limitation. These three are excluded from both latency percentiles and qualifying-answer cost averages, but included in total spend.

Timing starts immediately before sending the deployed HTTPS POST and ends after the full response is received. It includes client/network, API Gateway and Lambda processing. It contains no local TestClient/API latency. Health latency is excluded. The first ask remains included if it qualifies; health preceded it and cold-start status is unknown. Percentiles use linear interpolation and only seven observations; they are descriptive demo measurements, not an SLO or general answer-accuracy result.

Support checks used existing saved issue excerpts for #2071, #542 and #4999, and read-only public GitHub issue/comment reads for the other candidate answers. This is Codex review, not new human verification.

Artifacts: [exact plan](deployed_latency_cost_plan.json), [raw results and support decisions](deployed_latency_cost_results.json).


## Reproduction

The committed runner previews the fixed plan offline by default:

```powershell
.\.venv\Scripts\python.exe scripts/measure_deployed_latency_cost.py
```

After reviewing the current endpoint, model settings, pricing, and receiving
explicit approval for paid requests, run with a new output filename:

```powershell
.\.venv\Scripts\python.exe scripts/measure_deployed_latency_cost.py --execute --output artifacts/deployed_latency_cost_new_run.json
```

The output directory must exist. The runner refuses existing output files, checks
health first, stops without `/ask` calls if health fails, and disables retries and
redirects. It does not change AWS resources or settings. New responses may differ;
the published measurement is preserved. Candidate cited answers require a separate
source-support and relevance review before inclusion. The runner saves raw timing,
usage, costs, and citation checks; it does not automatically reproduce the manual
review decisions or publish final percentiles. Compute percentiles from qualifying
`client_latency_ms` values using linear interpolation at `(n - 1) * p`; sum their
`standard_rate_openai_cost_usd` values and divide by their count for average cost.
