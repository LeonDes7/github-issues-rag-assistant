"""Measure RAG query latency and estimated token cost over evaluation cases."""

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

import psycopg

from rag_assistant import api, evaluate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "evaluation/evaluation_cases.generated.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/measurements/rag_performance_results.json"


def percentile(values: list[float], percentile_value: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile_value
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _token_count(response: Any, field: str) -> int:
    usage = getattr(response, "usage", None)
    value = getattr(usage, field, 0) if usage else 0
    return value if isinstance(value, int) else 0


def run_measurement(cases_path: Path) -> dict[str, Any]:
    cases = evaluate.load_cases(cases_path)
    settings = api.get_settings()
    mode = settings.get("RAG_RETRIEVAL_MODE", "vector")
    threshold = settings.get(
        "RAG_CONFIDENCE_THRESHOLD",
        api.DEFAULT_CONFIDENCE_THRESHOLD,
    )
    client = api.get_openai_client()
    results = []
    with psycopg.connect(**evaluate.database_options(settings)) as connection:
        for case in cases:
            total_started = time.perf_counter()
            retrieval_started = total_started
            embedding_response = client.embeddings.create(
                model=settings["OPENAI_EMBEDDING_MODEL"],
                input=case["question"],
                dimensions=api.VECTOR_DIMENSIONS,
            )
            embedding = embedding_response.data[0].embedding
            if len(embedding) != api.VECTOR_DIMENSIONS:
                raise RuntimeError(
                    f"Question {case['case_id']} embedding has an invalid dimension"
                )
            if mode == "hybrid":
                retrieved = api.retrieve_chunks(
                    connection,
                    embedding,
                    5,
                    retrieval_mode=mode,
                    query_text=case["question"],
                )
            else:
                retrieved = api.retrieve_chunks(connection, embedding, 5)
            retrieval_ms = (time.perf_counter() - retrieval_started) * 1000

            refused = api.should_refuse(retrieved, threshold)
            llm_ms = 0.0
            prompt_tokens = 0
            completion_tokens = 0
            if not refused:
                llm_started = time.perf_counter()
                _, prompt_tokens, completion_tokens = (
                    api.generate_grounded_answer_with_usage(
                        client,
                        settings["OPENAI_GENERATION_MODEL"],
                        case["question"],
                        retrieved,
                    )
                )
                llm_ms = (time.perf_counter() - llm_started) * 1000

            total_ms = (time.perf_counter() - total_started) * 1000
            embedding_tokens = _token_count(embedding_response, "prompt_tokens")
            cost = api.estimate_request_cost(
                settings,
                embedding_tokens,
                prompt_tokens,
                completion_tokens,
            )
            results.append(
                {
                    "case_id": case["case_id"],
                    "retrieval_score": api.retrieval_score(retrieved),
                    "refused": refused,
                    "retrieval_latency_ms": retrieval_ms,
                    "llm_latency_ms": llm_ms,
                    "total_latency_ms": total_ms,
                    "embedding_tokens": embedding_tokens,
                    "generation_prompt_tokens": prompt_tokens,
                    "generation_completion_tokens": completion_tokens,
                    "estimated_cost_usd": cost,
                }
            )

    latencies = [item["total_latency_ms"] for item in results]
    return {
        "case_file": str(cases_path),
        "case_count": len(results),
        "retrieval_mode": mode,
        "confidence_threshold": threshold,
        "latency_ms": {
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "average": statistics.mean(latencies) if latencies else None,
            "average_retrieval": statistics.mean(
                [item["retrieval_latency_ms"] for item in results]
            )
            if results
            else None,
            "average_llm": statistics.mean(
                [item["llm_latency_ms"] for item in results]
            )
            if results
            else None,
        },
        "average_cost_per_query_usd": (
            statistics.mean([item["estimated_cost_usd"] for item in results])
            if results
            else None
        ),
        "refused_queries": sum(item["refused"] for item in results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure RAG latency and estimated API cost."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = run_measurement(args.cases)
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"RAG performance measurement failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    print(f"Saved detailed results to {args.output}")


if __name__ == "__main__":
    main()
