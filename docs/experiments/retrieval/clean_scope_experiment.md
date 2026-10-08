# Duplicate-scope checkpoint

Saved A and B experiments both used the unfiltered 63,634-chunk table. This rerun compares the accepted ef_search=100, fetch-30, collapse-to-five configuration on the full scope and the three-repository 63,002-chunk scope. All 60 questions use cached embeddings; metrics use the 45 answerable cases. Both variants share one read-only repeatable-read snapshot. No generation calls, index changes, or cutoff retuning.

| Scope | Mode | Hit@5 | Recall@5 | MRR |
|---|---|---:|---:|---:|
| overall | Unfiltered A+B | 0.9333 | 0.9333 | 0.8389 |
| overall | Clean A+B | 0.9333 | 0.9333 | 0.8389 |
| tiangolo/fastapi | Unfiltered A+B | 0.9333 | 0.9333 | 0.7500 |
| tiangolo/fastapi | Clean A+B | 0.9333 | 0.9333 | 0.7500 |
| encode/starlette | Unfiltered A+B | 0.9333 | 0.9333 | 0.9333 |
| encode/starlette | Clean A+B | 0.9333 | 0.9333 | 0.9333 |
| pydantic/pydantic | Unfiltered A+B | 0.9333 | 0.9333 | 0.8333 |
| pydantic/pydantic | Clean A+B | 0.9333 | 0.9333 | 0.8333 |

Per-case metric changes: 0. Refusal changes: 0. Both scopes refuse 15/15 original unanswerables and wrongly refuse 2/45 answerables at 0.5370554072220923. These are calibration-set replays, not held-out results.

B Hit@5 and MRR are over the selected top five distinct (repository, issue_number) identities. Context diversity stays 4.9778 issues on average; 44/45 contexts contain five distinct issues. Mean context characters change slightly (4056.1778 to 4056.2000), so a metric tie does not imply all context text or similarity values are identical.

Production vector and both hybrid candidate queries now filter repository = ANY(configured repositories) before their candidate limits. The active configuration is tiangolo/fastapi, encode/starlette, pydantic/pydantic. RAG_REPOSITORIES overrides GITHUB_REPOS; if neither is set, the three original names are used. ef_search remains 100 with transaction-local settings. No rows are deleted or hidden from database administration. The existing HNSW index still physically covers all rows; this is a scoped query, not a newly built clean-only index. Issue collapse remains the accepted experiment and will be wired into the API at checkpoint 2; Lambda is unchanged.

## Duplicate cleanup proposal ? awaiting approval

Recommend a local archive only, retaining all live rows (already excluded from retrieval). Create archives/fastapi_alias/ with silver.jsonl.gz (76 rows), gold.jsonl.gz (632 rows, including complete embeddings), classifications.jsonl.gz (76 rows), and manifest.json with row counts, exact issue IDs, UTC export time, schema metadata, and SHA-256 hashes. Exclude the archive from Git. Validate the exports before considering any removal. This creates no AWS resources and makes no OpenAI calls. No archive has been created yet.

Alternative, only if explicitly approved after archive validation: in one database transaction, recheck the exact issue IDs, 76 parent rows, 632 chunks, 76 classification rows, matching canonical parents, and foreign-key definitions. Delete only the 76 fastapi/fastapi parents listed below. ON DELETE CASCADE removes the 632 chunks and 76 classifications, for 784 rows total. Abort if the manifest counts or IDs differ. Canonical tiangolo/fastapi rows, Bronze S3 objects, historical evaluation runs/results, other repositories, and AWS resources remain intact. Do not execute a delete without user approval.

| Table | Alias rows |
|---|---:|
| public.github_issue_chunks | 632 |
| public.github_issue_classifications | 76 |
| public.github_issues_clean | 76 |

All 76 alias issues have a canonical tiangolo/fastapi counterpart with matching title and body. This is not a claim that every historical comment or embedding is byte-identical. The aliases came from the earlier October 5 load; the 63,002 snapshot was scoped to the three repositories.

Exact alias issue numbers: 12055, 12133, 12198, 12239, 12240, 12245, 12246, 12290, 12313, 12323, 12402, 12419, 12426, 12459, 12554, 12780, 12901, 12965, 13019, 13022, 13056, 13067, 13111, 13116, 13150, 13175, 13399, 13400, 13440, 13471, 13533, 13606, 13880, 14128, 14221, 14247, 14271, 14316, 14344, 14431, 14444, 14454, 14465, 14466, 14467, 14483, 14484, 14496, 14508, 14680, 14810, 14888, 15118, 15188, 15268, 15401, 15448, 15503, 15612, 15712, 15713, 15714, 15715, 15716, 15762, 15764, 15845, 15969, 16010, 16037, 16138, 16160, 16244, 16253, 16301, 16417.

Foreign keys:

```json
[
  [
    "github_issue_chunks",
    "github_issues_clean",
    "FOREIGN KEY (repository, issue_number) REFERENCES github_issues_clean(repository, issue_number) ON DELETE CASCADE"
  ],
  [
    "github_issue_classifications",
    "github_issues_clean",
    "FOREIGN KEY (repository, issue_number) REFERENCES github_issues_clean(repository, issue_number) ON DELETE CASCADE"
  ]
]
```

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/experiment_clean_scope.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

No paid OpenAI calls are made. The historical A/B scripts explicitly retain the original four-name scope; the new clean-scope script compares both scopes without overwriting historical reports.
