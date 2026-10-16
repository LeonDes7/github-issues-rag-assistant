# Evaluation reference

Historical commands below can call paid services, write data or change infrastructure.
They are documentation, not authorization to execute. Historical checkpoints are dated;
see the root README and live reports for current verification.

## Step 6: Local RAG evaluation

[evaluation_cases.jsonl](../../evaluation/evaluation_cases.jsonl) is a small, version-controlled held-out suite of 10
cases selected from the current corpus. Each case is labeled
`codex_checked`, `heuristic`, or `unresolved`, with a note describing the
label. Cases marked `heuristic` rely on the extracted maintainer-comment
resolution and are reported separately; that signal is uncertain and is not
treated as guaranteed ground truth. Unresolved cases intentionally expect an
abstention.

Build a 60-case set (15 randomly sampled closed issues per repository, plus
15 deliberately unanswerable questions) and a review-friendly CSV with:

```powershell
python scripts/build_evaluation_set.py --seed 42
```

This uses the configured Postgres corpus and generation model. It writes
[evaluation_cases.generated.jsonl](../../evaluation/evaluation_cases.generated.jsonl) and
`evaluation/evaluation_cases.draft.csv`; review the issue IDs and questions against
each source issue. The draft CSV filename keeps generation separate from the
completed review. The original 60-case generated set is preserved as
[evaluation_cases.original.jsonl](../../evaluation/evaluation_cases.original.jsonl)
for historical provenance. The matching generated JSONL now contains the approved 59 cases.

The replacement [evaluation_cases_reviewed.csv](../../evaluation/evaluation_cases_reviewed.csv)
is the source of truth for the author-approved verdicts. Its `human_verified` column
records 58 `yes` decisions, one `no`, and one `edit` with replacement question text.
Notes and `manual_review_status` now reflect the author approval, edit, or rejection;
the supplied decisions, questions, and gold issue identities are preserved.
The derived [evaluation_cases_reviewed.jsonl](../../evaluation/evaluation_cases_reviewed.jsonl)
contains 59 cases: 44 answerable and 15 unanswerable. It excludes FastAPI #5108,
uses the supplied edited question for Pydantic #11491, and records human-review
provenance. Answerable cases are `manually_verified`; unanswerable cases retain
`unresolved` to preserve the evaluator's abstention convention.
The separate 10-case suite and harder held-out unanswerable suite are unchanged.
Historical metrics have not been rerun on this reviewed set. The retrieval-only
rescore uses `scripts/rescore_reviewed_retrieval.py --execute` on only the 44 kept
answerable cases, with production vector retrieval, ef_search=100, 30 candidates
collapsed to five issues, the three configured repositories, and the unchanged cutoff.
Run the script without `--execute` for an offline call/token/cost preflight. Execution
was approved by the author on October 16, 2026, but the attempt was blocked because
RDS is stopped. No OpenAI calls, database writes, or infrastructure changes occurred.
See the [attempt report](../experiments/retrieval/author_reviewed_rescore_report.md).
No generation or judge calls are part of this rescore.

Run the reviewed set locally with top-5 retrieval:

```powershell
python -m rag_assistant.evaluate `
  --cases evaluation/evaluation_cases_reviewed.jsonl `
  --top-k 5
```

The command calls the local retrieval/generation components, prints a concise
metrics summary and up to five failure examples, and stores run metadata and
per-case outputs in `public.rag_evaluation_runs` and
`public.rag_evaluation_case_results`. Stored metadata includes UTC timestamps,
embedding and generation model names, `top_k`, case counts, and metrics.
Retrieval Hit@k, Recall@k, and MRR are computed over every answerable case,
with both full-set and per-repository breakdowns. Verification-status
breakdowns remain available so generated, not-yet-reviewed labels are clearly
distinguished from manually verified cases.

Generation evaluation records appropriate abstention, valid citation
references, and whether factual sentences have cited evidence with lexical
overlap. Lexical grounding is an automated screening heuristic, not factual
verification. LLM-as-judge scoring is optional:

```powershell
python -m rag_assistant.evaluate --top-k 5 --judge
```

Judge results are labeled automated estimates, not absolute truth. The
evaluation command does not alter issue or chunk rows.

Hybrid retrieval combines a pgvector candidate list with English PostgreSQL
full-text candidates and fuses their ranks with reciprocal rank fusion
(`k=60`). Gold setup creates a generated `tsvector` and GIN index. Compare both
modes over the same generated evaluation set without calling the answer
generation model:

```powershell
python scripts/compare_retrieval_modes.py `
  --cases evaluation/evaluation_cases.generated.jsonl `
  --top-k 5
```

The script prints side-by-side Hit@5, Recall@5, and MRR (or the selected `k`),
prints per-repository rows, and writes full run data to
[retrieval_comparison_results.json](../experiments/retrieval/retrieval_comparison_results.json).
On the 45 Codex-checked, not human-verified answerable development cases in the 2026-10-07 baseline,
vector and hybrid both scored Hit@5 0.8000, Recall@5 0.8000, and MRR 0.7526.
Per-repository metrics and complete case-level results are in the saved JSON.

The full 2026-10-07 corpus snapshot is recorded in [corpus_snapshot.json](../corpus/corpus_snapshot.json):
9,555 unique issues, 43,535 comments, and 63,002 embedded chunks. Data-quality
checks passed; 276 duplicate Bronze rows were deduplicated, and 14 issues with
no chunkable content were expected not to appear in Gold.

The evaluator accepts `codex_checked` separately from `manually_verified`; Codex-checked cases do not enter the manually verified aggregate. New result tables accept the status; an existing database CHECK constraint may need an explicitly authorized update before persisting new runs. No database change or evaluation run was performed for this relabeling.


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
See [measurement report](../measurements/final_latency_cost_report.md).
