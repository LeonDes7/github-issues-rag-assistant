# Evaluation reference

Historical commands below can call paid services, write data or change infrastructure.
They are documentation, not authorization to execute. Historical checkpoints are dated;
see the root README and live reports for current verification.

## Step 6: Local RAG evaluation

[evaluation_cases.jsonl](../../evaluation/evaluation_cases.jsonl) is a small, version-controlled held-out suite of 10
cases selected from the current corpus. Each case is labeled
`manually_verified`, `heuristic`, or `unresolved`, with a note describing the
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
[evaluation_cases.generated.jsonl](../../evaluation/evaluation_cases.generated.jsonl) and [evaluation_cases.review.csv](../../evaluation/evaluation_cases.review.csv); review
the issue IDs and questions against each source issue before marking cases
`manually_verified` in the JSONL. The checked-in run output contains the
manually reviewed 45 answerable cases and 15 off-topic cases.

Run the generated set locally with top-5 retrieval:

```powershell
python -m rag_assistant.evaluate `
  --cases evaluation/evaluation_cases.generated.jsonl `
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
On the 45 manually verified answerable cases in the 2026-10-07 baseline,
vector and hybrid both scored Hit@5 0.8000, Recall@5 0.8000, and MRR 0.7526.
Per-repository metrics and complete case-level results are in the saved JSON.

The full 2026-10-07 corpus snapshot is recorded in [corpus_snapshot.json](../corpus/corpus_snapshot.json):
9,555 unique issues, 43,535 comments, and 63,002 embedded chunks. Data-quality
checks passed; 276 duplicate Bronze rows were deduplicated, and 14 issues with
no chunkable content were expected not to appear in Gold.
