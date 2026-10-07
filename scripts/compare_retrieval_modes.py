"""Compare vector and hybrid retrieval using the same question embeddings."""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg

from rag_assistant import api, evaluate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "evaluation_cases.generated.jsonl"
DEFAULT_RESULTS = PROJECT_ROOT / "retrieval_comparison_results.json"
MODES = ("vector", "hybrid")


def summarize(
    case_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    scored = [
        item for item in case_results if item["retrieval_metrics"]["applicable"]
    ]
    by_repository: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scored:
        by_repository[item["repository"]].append(item)
    return (
        _metrics(scored),
        {
            repository: _metrics(items)
            for repository, items in sorted(by_repository.items())
        },
    )


def _metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [item["retrieval_metrics"] for item in items]
    count = len(metrics)
    return {
        "scored_cases": count,
        "hit_at_k": (
            sum(item["hit_at_k"] for item in metrics) / count if count else None
        ),
        "recall_at_k": (
            sum(item["recall_at_k"] for item in metrics) / count if count else None
        ),
        "mrr": sum(item["mrr"] for item in metrics) / count if count else None,
    }


def run_comparison(
    cases_path: Path,
    top_k: int = 5,
) -> dict[str, Any]:
    cases = evaluate.load_cases(cases_path)
    settings = api.get_settings()
    client = api.get_openai_client()
    outputs: dict[str, list[dict[str, Any]]] = {mode: [] for mode in MODES}

    with psycopg.connect(**evaluate.database_options(settings)) as connection:
        for case in cases:
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
            repository = (
                case["expected_issues"][0]["repository"]
                if case["expected_issues"]
                else "unanswerable"
            )
            for mode in MODES:
                if mode == "hybrid":
                    retrieved = api.retrieve_chunks(
                        connection,
                        embedding,
                        top_k,
                        retrieval_mode=mode,
                        query_text=case["question"],
                    )
                else:
                    retrieved = api.retrieve_chunks(connection, embedding, top_k)
                outputs[mode].append(
                    {
                        "case_id": case["case_id"],
                        "repository": repository,
                        "retrieval_metrics": evaluate.retrieval_case_metrics(
                            case,
                            retrieved,
                        ),
                        "retrieved_issues": [
                            {
                                "repository": chunk["repository"],
                                "issue_number": chunk["issue_number"],
                                "retrieval_score": chunk["retrieval_score"],
                            }
                            for chunk in retrieved
                        ],
                    }
                )

    metrics = {}
    for mode, results in outputs.items():
        overall, by_repository = summarize(results)
        metrics[mode] = {
            "all_answerable_cases": overall,
            "by_repository": by_repository,
        }
    return {
        "case_file": str(cases_path),
        "case_count": len(cases),
        "top_k": top_k,
        "embedding_model": settings["OPENAI_EMBEDDING_MODEL"],
        "metrics": metrics,
        "case_results": outputs,
    }


def print_comparison(report: dict[str, Any]) -> None:
    top_k = report["top_k"]
    print(f"{'Mode':<12} {'Hit@' + str(top_k):>10} {'Recall@' + str(top_k):>12} {'MRR':>10}")
    for mode in MODES:
        metrics = report["metrics"][mode]["all_answerable_cases"]
        print(
            f"{mode:<12} "
            f"{_format_metric(metrics['hit_at_k']):>10} "
            f"{_format_metric(metrics['recall_at_k']):>12} "
            f"{_format_metric(metrics['mrr']):>10}"
        )
    repositories = sorted(
        {
            repository
            for mode in MODES
            for repository in report["metrics"][mode]["by_repository"]
        }
    )
    if repositories:
        print("\nPer repository")
        for repository in repositories:
            print(repository)
            for mode in MODES:
                metrics = report["metrics"][mode]["by_repository"].get(
                    repository,
                    {},
                )
                print(
                    f"  {mode:<10} Hit={_format_metric(metrics.get('hit_at_k'))} "
                    f"Recall={_format_metric(metrics.get('recall_at_k'))} "
                    f"MRR={_format_metric(metrics.get('mrr'))}"
                )


def _format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare vector-only and hybrid retrieval."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20")
    try:
        report = run_comparison(args.cases, args.top_k)
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Retrieval comparison failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print_comparison(report)
    print(f"\nSaved detailed results to {args.output}")


if __name__ == "__main__":
    main()
