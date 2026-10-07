"""Prepare a held-out challenge set and read-only evidence audit; no OpenAI calls."""
import json
from pathlib import Path

import psycopg
import tiktoken
from rag_assistant import api, evaluate

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = [
    ("tiangolo/fastapi", "oauth-revocation", "How can a FastAPI OAuth2 dependency revoke an already authenticated WebSocket connection across four Uvicorn workers within 30 seconds, and what indexed issue demonstrates that guarantee?", "oauth websocket revocation", "Requires a demonstrated cross-worker revocation guarantee, beyond authentication examples."),
    ("tiangolo/fastapi", "yield-cancellation", "Which FastAPI dependency-with-yield pattern guarantees exactly-once transaction rollback when a streaming response is cancelled after headers are sent, including process termination?", "dependency yield rollback streaming", "Requires an exactly-once guarantee including process failure, beyond cleanup advice."),
    ("tiangolo/fastapi", "upload-benchmark", "What measured p95 latency and peak RSS does the indexed FastAPI corpus report for 100 concurrent 1 GiB multipart uploads using UploadFile on a 2-vCPU host?", "uploadfile multipart memory benchmark", "Requests benchmark results for a precise workload absent from reviewed related evidence."),
    ("tiangolo/fastapi", "openapi-tenant-signing", "How do the indexed FastAPI issues implement tenant-specific OpenAPI schemas whose OAuth scopes are cryptographically signed and refreshed without restarting workers?", "openapi tenant oauth scope", "Requests a combined tenant-schema/signing implementation, beyond individual OpenAPI scope discussions."),
    ("tiangolo/fastapi", "background-durable", "Which FastAPI BackgroundTasks configuration provides durable exactly-once execution after a worker crash, and where is the failure-recovery protocol specified in the indexed issues?", "backgroundtasks crash durable", "Requires a durable crash-recovery protocol, not ordinary in-process task scheduling."),
    ("encode/starlette", "middleware-benchmark", "What measured throughput improvement does pure ASGI middleware give over BaseHTTPMiddleware with 64 concurrent streaming clients, 256 KiB responses, and TLS on a 2-vCPU host?", "basehttpmiddleware streaming performance", "Requests a precise measured workload rather than general middleware performance discussion."),
    ("encode/starlette", "websocket-replay", "Which Starlette WebSocket reconnection recipe in the indexed issues guarantees ordered exactly-once delivery with persisted replay across a server restart?", "websocket reconnect replay delivery", "Requires persisted delivery guarantees beyond WebSocket transport handling."),
    ("encode/starlette", "lifespan-failover", "How does Starlette lifespan coordinate atomic failover of a shared PostgreSQL connection pool across multiple workers without losing any in-flight transaction?", "lifespan pool worker transaction", "Requests distributed atomic failover, beyond local resource lifecycle management."),
    ("encode/starlette", "multipart-integrity", "Which Starlette multipart upload design verifies a client-provided SHA-256 incrementally, resumes an interrupted upload at a byte offset, and guarantees no duplicate bytes in the stored file?", "multipart upload resume checksum", "Requests a complete resumable integrity protocol, beyond multipart parsing."),
    ("encode/starlette", "cors-policy-proof", "What indexed Starlette issue proves a dynamically reloaded per-tenant CORS policy cannot leak one tenant's allowed origins to another during concurrent configuration updates?", "cors tenant origin concurrent", "Requests a concurrency/isolation proof for a specific dynamic policy."),
    ("pydantic/pydantic", "validator-benchmark", "What measured speedup do the indexed Pydantic issues report for a 50-field discriminated union with three nested model levels over 10 million records on an ARM64 2-vCPU host?", "discriminated union benchmark performance", "Requests exact benchmark results for an unspecified corpus/workload."),
    ("pydantic/pydantic", "migration-proof", "Which indexed Pydantic migration procedure proves byte-for-byte identical JSON serialization between v1 and v2 for recursive generics, custom encoders, aliases, and timezone-aware datetimes together?", "migration recursive generic encoder alias datetime", "Requires a comprehensive equivalence proof, beyond individual migration workarounds."),
    ("pydantic/pydantic", "settings-secret-rotation", "How do indexed Pydantic settings issues rotate encrypted secrets across multiple running processes atomically while preserving rollback to the previous key after a failed deployment?", "settings secret rotation process", "Requires an atomic multi-process encrypted-secret rotation protocol."),
    ("pydantic/pydantic", "schema-lossless-roundtrip", "Which Pydantic implementation in the indexed issues provides lossless JSON Schema to model to JSON Schema round-tripping, including recursive references, custom validators, and field ordering?", "json schema roundtrip recursive validator", "Requires a lossless bidirectional implementation with all listed features."),
    ("pydantic/pydantic", "validator-sandbox", "Which Pydantic validator configuration safely executes tenant-supplied Python validation code with enforced CPU and memory limits and a documented sandbox escape analysis?", "validator sandbox memory limit", "Requires an executable-code security sandbox, beyond validation hooks."),
]


def main():
    settings = api.get_settings()
    expected = {"RAG_RETRIEVAL_MODE": "vector", "RAG_HNSW_EF_SEARCH": 100, "RAG_CONTEXT_MODE": "issues"}
    for key, value in expected.items():
        if settings[key] != value:
            raise RuntimeError(f"Current retrieval setting differs from accepted configuration: {key}")
    cases = [{"case_id": f"heldout-{repo.split('/')[0]}-{name}", "repository": repo, "question": question, "expected_abstain": True, "expected_issues": [], "codex_checked": False, "human_verified": "", "unanswerable_rationale": rationale, "audit_terms": terms} for repo, name, question, terms, rationale in QUESTIONS]
    audit = {"threshold": 0.537, "threshold_retuned": False, "openai_calls": 0, "retrieval_settings": {k: settings[k] for k in (*expected, "RAG_REPOSITORIES")}, "label_limit": "Candidate unanswerable labels require evidence review; lexical absence alone cannot prove corpus-wide absence.", "cases": []}
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = sum(len(encoding.encode(c["question"])) for c in cases)
    with psycopg.connect(**evaluate.database_options(settings)) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        max_bytes = conn.execute("SELECT coalesce(max(octet_length(chunk_text)),0) FROM public.github_issue_chunks WHERE repository=ANY(%s)", (settings["RAG_REPOSITORIES"],)).fetchone()[0]
        for case in cases:
            rows = conn.execute("SELECT repository,issue_number,source_url,chunk_text,ts_rank_cd(to_tsvector('english',chunk_text),websearch_to_tsquery('english',%s)) AS score FROM public.github_issue_chunks WHERE repository=ANY(%s) AND to_tsvector('english',chunk_text) @@ websearch_to_tsquery('english',%s) ORDER BY score DESC LIMIT 3", (" OR ".join(case["audit_terms"].split()), [case["repository"]], " OR ".join(case["audit_terms"].split()))).fetchall()
            audit["cases"].append({"case_id": case["case_id"], "question": case["question"], "closest_lexical_evidence": [{"repository": r[0], "issue_number": r[1], "url": r[2], "excerpt": r[3], "fts_rank": r[4]} for r in rows]})
    # Each UTF-8 byte is a conservative token bound, including JSON escaping.
    # Evidence text serialization uses ensure_ascii=False in the API prompt.
    input_bound_per_call = 5 * max_bytes * 6 + 5000
    audit["cost_estimate"] = {"embedding_model": "text-embedding-3-small", "embedding_input_tokens": tokens, "embedding_rate_usd_per_million": 0.02, "estimated_embedding_cost_usd": tokens * 0.02 / 1e6, "generation_model_if_cutoff_passed": "gpt-5-nano", "max_generation_calls": 15, "max_completion_tokens_per_call": 1200, "generation_input_rate_usd_per_million": 0.05, "generation_output_rate_usd_per_million": 0.4, "max_chunk_utf8_bytes": max_bytes, "conservative_input_token_bound_per_call": input_bound_per_call, "conservative_all_pass_cost_bound_usd": (tokens * 0.02 + 15 * input_bound_per_call * 0.05 + 15 * 1200 * 0.4) / 1e6, "generation_only_for_false_accepts": True}
    previous = json.loads((ROOT / "context_comparison_answers.json").read_text())
    mean_prompt = sum(a["prompt_tokens"] for a in previous["answers"]) / len(previous["answers"])
    audit["cost_estimate"].update({"estimated_all_pass_cost_usd_using_previous_mean_prompt_and_output_cap": tokens * 0.02 / 1e6 + 15 * (mean_prompt * 0.05 + 1200 * 0.4) / 1e6, "previous_mean_prompt_tokens": mean_prompt, "proposed_run_budget_usd": 0.02, "budget_enforcement": "Before each generation call, count its actual prepared prompt locally and reserve its maximum output cost. Stop if the remaining approved budget is insufficient; do not retry or request more spend automatically."})
    (ROOT / "heldout_unanswerable_cases.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8")
    (ROOT / "heldout_unanswerable_preflight.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(audit["cost_estimate"], indent=2))


if __name__ == "__main__":
    main()
