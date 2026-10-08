"""Select an abstention cutoff from answerable and intentionally unanswerable cases."""

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg

from rag_assistant import api, evaluate


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "evaluation/evaluation_cases.generated.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "docs/experiments/retrieval/confidence_calibration_results.json"


def select_threshold(
    scores: list[dict[str, Any]],
) -> dict[str, Any]:
    answerable = [item for item in scores if item["answerable"]]
    unanswerable = [item for item in scores if not item["answerable"]]
    if not answerable or not unanswerable:
        raise ValueError(
            "Calibration requires at least one answerable and one unanswerable case"
        )

    observed_scores = sorted({item["score"] for item in scores})
    candidates = {0.0, 1.0}
    for index, score in enumerate(observed_scores):
        next_score = (
            observed_scores[index + 1]
            if index + 1 < len(observed_scores)
            else 1.0
        )
        if score < next_score:
            candidates.add((score + next_score) / 2)

    best_threshold = 0.0
    best_balanced_accuracy = -1.0
    best_counts: dict[str, int] = {}
    for threshold in sorted(candidates):
        correctly_refused = sum(
            item["score"] < threshold for item in unanswerable
        )
        wrongly_refused = sum(item["score"] < threshold for item in answerable)
        correctly_answered = len(answerable) - wrongly_refused
        missed_unanswerable = len(unanswerable) - correctly_refused
        balanced_accuracy = (
            correctly_refused / len(unanswerable)
            + correctly_answered / len(answerable)
        ) / 2
        if balanced_accuracy > best_balanced_accuracy:
            best_threshold = threshold
            best_balanced_accuracy = balanced_accuracy
            best_counts = {
                "correctly_refused": correctly_refused,
                "wrongly_refused": wrongly_refused,
                "correctly_answered": correctly_answered,
                "missed_unanswerable": missed_unanswerable,
            }
    return {
        "recommended_threshold": best_threshold,
        "balanced_accuracy": best_balanced_accuracy,
        "unanswerable_cases": len(unanswerable),
        "answerable_cases": len(answerable),
        **best_counts,
    }


def run_calibration(
    cases_path: Path,
    retrieval_mode: str | None = None,
) -> dict[str, Any]:
    cases = evaluate.load_cases(cases_path)
    settings = api.get_settings()
    mode = retrieval_mode or settings.get("RAG_RETRIEVAL_MODE", "vector")
    client = api.get_openai_client()
    scores = []
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
            answerable = bool(
                case["expected_issues"] or case["expected_issue_urls"]
            ) and not case["expected_abstain"]
            scores.append(
                {
                    "case_id": case["case_id"],
                    "answerable": answerable,
                    "score": api.retrieval_score(retrieved),
                }
            )
    return {
        "case_file": str(cases_path),
        "retrieval_mode": mode,
        "top_k": 5,
        "selection_method": "maximum balanced accuracy; ties choose lower cutoff",
        "threshold_selection": select_threshold(scores),
        "cases": scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calibrate the RAG abstention confidence threshold."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mode", choices=("vector", "hybrid"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = run_calibration(args.cases, args.mode)
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Confidence calibration failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["threshold_selection"], indent=2))
    print(f"Suggested setting: RAG_CONFIDENCE_THRESHOLD={report['threshold_selection']['recommended_threshold']:.6f}")
    print(f"Saved calibration data to {args.output}")


if __name__ == "__main__":
    main()
