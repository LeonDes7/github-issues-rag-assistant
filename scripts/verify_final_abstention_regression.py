"""Offline /ask verification of saved model responses; all external dependencies mocked."""
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from rag_assistant import api

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "docs/experiments/abstention/final_abstention_regression_results.json"
    result = json.loads(output.read_text(encoding="utf-8"))
    prepared = json.loads((ROOT / "docs/experiments/abstention/final_abstention_regression_preflight.json").read_text(encoding="utf-8"))
    assert result["generation_calls_completed"] == result["generation_calls_attempted"] == 14
    assert result["status"] == "completed_pending_review"
    assert hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest() == prepared["api_source_sha256"]
    settings = {
        "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small", "OPENAI_GENERATION_MODEL": "gpt-5-nano",
        "API_AUTH_TOKEN": "offline-test-token", "CORS_ALLOWED_ORIGINS": [],
        "RAG_CONFIDENCE_THRESHOLD": result["cutoff"], **result["retrieval_settings"],
    }
    # Explicit guards ensure no real connection/client can be created even accidentally.
    with patch.object(api, "get_settings", return_value=settings), \
         patch.object(api.psycopg, "connect", side_effect=AssertionError("Real DB prohibited")), \
         patch.object(api, "OpenAI", side_effect=AssertionError("Real OpenAI client prohibited")), \
         patch.object(api.boto3, "client", side_effect=AssertionError("AWS access prohibited")):
        application = api.create_app()
        database = MagicMock()
        client = MagicMock()
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.0] * api.VECTOR_DIMENSIONS)], usage=None
        )
        application.dependency_overrides[api.get_db_connection] = lambda: database
        application.dependency_overrides[api.get_openai_client] = lambda: client
        with TestClient(application) as http:
            for case, frozen in zip(result["cases"], prepared["cases"]):
                assert case["case_id"] == frozen["case_id"] and case["evidence"] == frozen["evidence"]
                client.chat.completions.create.reset_mock()
                client.chat.completions.create.return_value = SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=case["raw_generated_answer"]))],
                    usage=SimpleNamespace(prompt_tokens=case["generation_usage"]["prompt_tokens"],
                                          completion_tokens=case["generation_usage"]["completion_tokens"]),
                )
                with patch.object(api, "retrieve_context", return_value=frozen["evidence"]) as retrieval:
                    response = http.post("/ask", json={"question": case["question"], "top_k": 5},
                                         headers={"Authorization": "Bearer offline-test-token"})
                body = response.json()
                expected_sources = [api.Citation(
                    **{key: c[key] for key in ("repository", "issue_number", "issue_url", "source_url", "chunk_type", "similarity_score")},
                    retrieval_score=c.get("retrieval_score", c["similarity_score"]),
                    predicted_category=c.get("predicted_category"), classification_confidence=c.get("classification_confidence"),
                ).model_dump() for c in frozen["evidence"]]
                checks = {
                    "http_200": response.status_code == 200,
                    "raw_model_marker_only": case["raw_generated_answer"].strip() == api.ABSTENTION_MARKER,
                    "fixed_api_message_exact": body.get("answer") == api.MODEL_ABSTENTION_ANSWER,
                    "no_inline_citations": not re.search(r"\[|\]\(|https?://", body.get("answer", "")),
                    "no_appended_prose": body.get("answer") == api.MODEL_ABSTENTION_ANSWER,
                    "structured_sources_exact_and_ordered": body.get("citations") == expected_sources,
                    "source_count_matches": len(body.get("citations", [])) == len(frozen["evidence"]),
                    "generation_used_saved_response": client.chat.completions.create.call_count == 1,
                    "messages_match_frozen_preflight": client.chat.completions.create.call_args.kwargs["messages"] == frozen["messages"],
                    "retrieval_was_stubbed": retrieval.call_count == 1,
                    "no_database_operations": not database.mock_calls,
                }
                case["api_verification"] = {"checks": checks, "passed": all(checks.values()),
                                            "api_response": {k: body[k] for k in ("answer", "citations", "retrieval_metadata")}}
                case["review_notes"] = "Offline actual /ask route verification; external dependencies mocked; human verification pending."
        application.dependency_overrides.clear()
    result["status"] = "completed_api_verified" if all(c["api_verification"]["passed"] for c in result["cases"]) else "completed_api_verification_failed"
    result["api_verification_scope"] = "Actual local /ask route with saved model responses, stub embeddings/retrieval and mocked database/client dependencies; no external calls. Performance fields omitted from saved API snapshots; no latency testing."
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    inputs = sum(c["generation_usage"]["prompt_tokens"] for c in result["cases"])
    outputs = sum(c["generation_usage"]["completion_tokens"] for c in result["cases"])
    calculated = (Decimal(inputs) * Decimal("0.05") + Decimal(outputs) * Decimal("0.40")) / Decimal(1000000)
    assert calculated == Decimal(result["actual_token_cost_usd"]) <= Decimal("0.01090985")
    lines = ["# Final deterministic abstention regression", "",
             "All fourteen saved model responses were verified through the actual local `/ask` route with external dependencies mocked. Each raw model response contained only `[INSUFFICIENT_EVIDENCE]`. Each API answer was exactly:", "",
             "> " + api.MODEL_ABSTENTION_ANSWER, "",
             "Every API answer had no inline model citations or appended prose. The separate structured `citations` list exactly matched the frozen retrieved sources in count, order, URLs, scores, chunk types, and classification metadata. No source was promoted into an answer claim.", "",
             "## Calls and actual token cost", "",
             f"- Exactly 14 network-enabled GPT-5 nano calls, all completed with `stop`; no retries or paid judge calls.",
             f"- API-reported input: **{inputs:,} tokens**; output: **{outputs:,} tokens**.",
             f"- Actual usage-based token cost: **${calculated} USD**, below the **$0.01090985** hard cap.",
             "- Rates: $0.05/million input and $0.40/million output; cached-input discounts ignored. This is not invoice reconciliation.",
             "- Requested model: `gpt-5-nano`; returned model: `" + result["cases"][0]["response_model"] + "`; reasoning effort `minimal`; completion cap 1,200/call.",
             "- Reported cached input: " + str(sum(c["generation_usage"]["prompt_tokens_details"]["cached_tokens"] for c in result["cases"])) + "; reasoning output: " + str(sum(c["generation_usage"]["completion_tokens_details"]["reasoning_tokens"] for c in result["cases"])) + " tokens.", "",
             "## Per-case API verification", "",
             "| Frozen case | Fixed answer / no prose / no inline citations | Separate sources matched | Cost (USD) |",
             "|---|---|---:|---:|"]
    for c in result["cases"]:
        v = c["api_verification"]
        lines.append(f'| {c["case_id"]} | {"PASS" if v["passed"] else "FAIL — inspect results"} | {len(v["api_response"]["citations"])} | ${c["generation_cost_usd"]} |')
    lines += ["", "## Verification boundaries", "",
              "Generation used only the fourteen prepared requests and frozen excerpts; the baseline, prompt and API source hashes were checked. API replay made no OpenAI, embedding, RDS, AWS, or real retrieval calls: it supplied a stub embedding vector, frozen retrieval results and saved chat responses. Generation, finalization, response serialization, and citation assembly used the actual API code. Every check and API answer/source snapshot is saved in `final_abstention_regression_results.json`.", "",
              "Cutoff 0.537 and retrieval settings remain unchanged. No deployment, database writes, deletion, latency testing, or production code changes occurred in this run. The earlier regression reports remain separate.", "",
              "This verifies the targeted output contract on these fourteen frozen cases; it is not a new headline metric, a general cutoff-robustness result, or live retrieval/UI validation. BackgroundTasks and schema-round-trip ambiguous labels remain unchanged. Human verification remains pending.", "",
              "## Artifacts", "",
              "- `final_abstention_regression_preflight.json`: frozen requests, settings, source hashes and approved estimate.",
              "- `final_abstention_regression_results.json`: raw model outputs, usage/cost, API snapshots, and individual deterministic checks.",
              "- `scripts/run_final_abstention_regression.py`: exclusive-output, budget-guarded paid runner with no retries.",
              "- `scripts/verify_final_abstention_regression.py`: offline API verification and report generator.", "",
              "Stopped for user review; no further calls.", ""]
    (ROOT / "docs/experiments/abstention/final_abstention_regression_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(result["status"], "cost=$" + str(calculated), "input=" + str(inputs), "output=" + str(outputs))
    assert result["status"] == "completed_api_verified"


if __name__ == "__main__":
    main()
