"""Transparent issue classification baseline with an optional LLM classifier."""

import argparse
import json
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from psycopg.types.json import Jsonb

from rag_assistant import api
from rag_assistant.evaluate import database_options


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = PROJECT_ROOT / "evaluation/classification_cases.jsonl"
CLASSIFICATION_TABLE = "public.github_issue_classifications"
LABELS = {"bug", "feature", "usage", "unknown"}
CLASSIFIER_VERSION = "heuristic-v1"
MAX_RETRIES = 5
BUG_PATTERN = re.compile(
    r"\b(?:bug|error|fail(?:s|ed|ure)?|crash(?:es|ed)?|regression|"
    r"incorrect|unexpected|broken|does not work|not working|"
    r"cannot|exception|traceback|fix(?:es|ed)?)\b",
    re.IGNORECASE,
)
FEATURE_PATTERN = re.compile(
    r"\b(?:featurerequest|feature request|request(?:ed)? support|"
    r"support for|add support|implement(?:ation)?|new capability|"
    r"would be useful to|please add|drop support|support\s+\d{3}|"
    r"will \w+ support)\b",
    re.IGNORECASE,
)
USAGE_PATTERN = re.compile(
    r"\b(?:question about|how (?:do|does|can|should|to)|"
    r"how about|when using|usage|example|clarification|"
    r"what is the (?:correct )?(?:way|usage)|required, can be none)\b",
    re.IGNORECASE,
)

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {CLASSIFICATION_TABLE} (
    repository TEXT NOT NULL,
    issue_number BIGINT NOT NULL,
    classification_method TEXT NOT NULL,
    classifier_version TEXT NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('bug', 'feature', 'usage', 'unknown')),
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    rationale TEXT NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (
        repository,
        issue_number,
        classification_method,
        classifier_version
    ),
    FOREIGN KEY (repository, issue_number)
        REFERENCES public.github_issues_clean (repository, issue_number)
        ON DELETE CASCADE
)
"""

UPSERT_SQL = f"""
INSERT INTO {CLASSIFICATION_TABLE} (
    repository, issue_number, classification_method, classifier_version,
    label, confidence, rationale, classified_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
ON CONFLICT (
    repository, issue_number, classification_method, classifier_version
) DO UPDATE SET
    label = EXCLUDED.label,
    confidence = EXCLUDED.confidence,
    rationale = EXCLUDED.rationale,
    classified_at = CURRENT_TIMESTAMP
"""


def heuristic_classify(title: str | None, body: str | None) -> dict[str, str]:
    text = f"{title or ''}\n{body or ''}".strip()
    if not text:
        return {
            "label": "unknown",
            "confidence": "low",
            "rationale": "No title or body text was available.",
        }

    title_text = title or ""
    if FEATURE_PATTERN.search(title_text):
        return {
            "label": "feature",
            "confidence": "high",
            "rationale": "The title contains an explicit feature/support request signal.",
        }
    if BUG_PATTERN.search(title_text):
        return {
            "label": "bug",
            "confidence": "high",
            "rationale": "The title contains an explicit defect or failure signal.",
        }
    if USAGE_PATTERN.search(title_text):
        return {
            "label": "usage",
            "confidence": "high",
            "rationale": "The title is phrased as a usage or how-to question.",
        }

    signals = {
        "bug": len(BUG_PATTERN.findall(text)),
        "feature": len(FEATURE_PATTERN.findall(text)),
        "usage": len(USAGE_PATTERN.findall(text)),
    }
    ordered = sorted(signals.items(), key=lambda item: item[1], reverse=True)
    if ordered[0][1] == 0 or ordered[0][1] == ordered[1][1]:
        return {
            "label": "unknown",
            "confidence": "low",
            "rationale": "The heuristic found no clear, unique category signal.",
        }

    label, score = ordered[0]
    confidence = "medium" if score >= 2 else "low"
    return {
        "label": label,
        "confidence": confidence,
        "rationale": (
            f"Rule-based keyword signals favored {label}; this is a heuristic "
            "classification, not a verified label."
        ),
    }


def llm_classify(
    client: OpenAI,
    model: str,
    title: str | None,
    body: str | None,
) -> dict[str, str]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify a GitHub issue into exactly one category. "
                    "bug means an existing behavior is broken or incorrect. "
                    "feature means a capability or change is requested. "
                    "usage means the author asks how to use or understand "
                    "existing behavior. Use unknown when evidence is ambiguous "
                    "or insufficient. Return JSON with label (bug, feature, "
                    "usage, unknown), confidence (high, medium, low), and a "
                    "brief rationale grounded only in the provided title/body. "
                    "Do not treat an issue's maintainer-comment heuristic as truth."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"title": title, "body": body},
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Classification model returned an empty result")
    result = json.loads(content)
    label = result.get("label")
    confidence = result.get("confidence")
    rationale = result.get("rationale")
    if label not in LABELS or confidence not in {"high", "medium", "low"}:
        raise ValueError("Classification model returned invalid labels or confidence")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("Classification model returned no rationale")
    return {
        "label": label,
        "confidence": confidence,
        "rationale": rationale.strip()[:1000],
    }


def load_classification_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    cases = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on classification case line {line_number}") from exc
        if case.get("expected_label") not in LABELS - {"unknown"}:
            raise ValueError(f"Invalid expected label on line {line_number}")
        if case.get("verification_status") != "manually_verified":
            raise ValueError(
                "Classification evaluation cases must be manually verified"
            )
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"Missing or duplicate case_id on line {line_number}")
        seen.add(case_id)
        cases.append(case)
    if not cases:
        raise ValueError("No classification cases found")
    return cases


def classification_metrics(
    expected: list[str],
    predicted: list[str],
) -> dict[str, Any]:
    if len(expected) != len(predicted):
        raise ValueError("Expected and predicted labels must have equal lengths")
    labels = ("bug", "feature", "usage", "unknown")
    matrix = {label: {target: 0 for target in labels} for label in labels}
    for actual, guess in zip(expected, predicted):
        if actual not in labels or guess not in labels:
            raise ValueError("Encountered an unsupported classification label")
        matrix[actual][guess] += 1

    count = len(expected)
    accuracy = (
        sum(matrix[label][label] for label in labels) / count if count else 0.0
    )
    per_label: dict[str, dict[str, float | int]] = {}
    f1_scores = []
    for label in labels:
        true_positive = matrix[label][label]
        false_positive = sum(matrix[actual][label] for actual in labels) - true_positive
        false_negative = sum(matrix[label][guess] for guess in labels) - true_positive
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        if sum(matrix[label].values()):
            f1_scores.append(f1)
        per_label[label] = {
            "support": sum(matrix[label].values()),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "case_count": count,
        "accuracy": accuracy,
        "macro_f1_present_classes": (
            sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
        ),
        "labels": list(labels),
        "confusion_matrix_actual_rows_predicted_columns": matrix,
        "per_label": per_label,
    }


def evaluate_cases(
    cases: list[dict[str, Any]],
    method: str,
    client: OpenAI | None,
    model: str,
    connection: psycopg.Connection[Any],
) -> dict[str, Any]:
    results = []
    expected = []
    predicted = []
    for case in cases:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT title, body
                FROM public.github_issues_clean
                WHERE repository = %s AND issue_number = %s
                """,
                (case["repository"], case["issue_number"]),
            )
            issue = cursor.fetchone()
        if issue is None:
            raise ValueError(
                f"Evaluation issue is missing from RDS: "
                f"{case['repository']}#{case['issue_number']}"
            )
        title, body = issue
        if method == "heuristic":
            classification = heuristic_classify(title, body)
        elif method == "llm":
            if client is None:
                raise ValueError("LLM evaluation requires an OpenAI client")
            classification = llm_classify(client, model, title, body)
        else:
            raise ValueError(f"Unknown classification method: {method}")
        expected_label = case["expected_label"]
        results.append(
            {
                "case_id": case["case_id"],
                "repository": case["repository"],
                "issue_number": case["issue_number"],
                "expected_label": expected_label,
                "predicted_label": classification["label"],
                "confidence": classification["confidence"],
                "rationale": classification["rationale"],
                "correct": classification["label"] == expected_label,
            }
        )
        expected.append(expected_label)
        predicted.append(classification["label"])
    return {
        "method": method,
        "metrics": classification_metrics(expected, predicted),
        "cases": results,
    }


def fetch_issues(
    connection: psycopg.Connection[Any],
    limit: int,
) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT repository, issue_number, title, body
            FROM public.github_issues_clean
            ORDER BY repository, issue_number
            LIMIT %s
            """,
            (limit,),
        )
        columns = [description.name for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def upsert_predictions(
    connection: psycopg.Connection[Any],
    repository: str,
    issue_number: int,
    method: str,
    version: str,
    result: dict[str, str],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            UPSERT_SQL,
            (
                repository,
                issue_number,
                method,
                version,
                result["label"],
                result["confidence"],
                result["rationale"],
            ),
        )


def classify_database(
    method: str,
    limit: int,
    client: OpenAI | None,
    model: str,
) -> dict[str, Any]:
    settings = api.get_settings()
    version = CLASSIFIER_VERSION if method == "heuristic" else model
    counts: Counter[str] = Counter()
    with psycopg.connect(**database_options(settings)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        rows = fetch_issues(connection, limit)
        for row in rows:
            if method == "heuristic":
                result = heuristic_classify(row["title"], row["body"])
            else:
                if client is None:
                    raise ValueError("LLM classification requires an OpenAI client")
                result = llm_classify(
                    client,
                    model,
                    row["title"],
                    row["body"],
                )
            upsert_predictions(
                connection,
                row["repository"],
                row["issue_number"],
                method,
                version,
                result,
            )
            counts[result["label"]] += 1
        connection.commit()
    return {
        "method": method,
        "classifier_version": version,
        "issues_processed": len(rows),
        "label_counts": dict(counts),
        "persistence_table": CLASSIFICATION_TABLE,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify clean GitHub issues and evaluate the classifier."
    )
    parser.add_argument(
        "--mode",
        choices=("heuristic", "llm", "both"),
        default="heuristic",
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--evaluate-only", action="store_true")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")

    try:
        settings = api.get_settings()
        llm_client = api.get_openai_client() if args.mode in {"llm", "both"} else None
        results: dict[str, Any] = {}
        if args.evaluate_only:
            cases = load_classification_cases(args.cases)
            modes = ("heuristic", "llm") if args.mode == "both" else (args.mode,)
            with psycopg.connect(**database_options(settings)) as connection:
                for method in modes:
                    results[method] = evaluate_cases(
                        cases,
                        method,
                        llm_client,
                        settings["OPENAI_GENERATION_MODEL"],
                        connection,
                    )
        else:
            modes = ("heuristic", "llm") if args.mode == "both" else (args.mode,)
            results["classification"] = [
                classify_database(
                    method,
                    args.limit,
                    llm_client,
                    settings["OPENAI_GENERATION_MODEL"],
                )
                for method in modes
            ]
            cases = load_classification_cases(args.cases)
            with psycopg.connect(**database_options(settings)) as connection:
                for method in modes:
                    results[method + "_evaluation"] = evaluate_cases(
                        cases,
                        method,
                        llm_client,
                        settings["OPENAI_GENERATION_MODEL"],
                        connection,
                    )
        print(json.dumps(results, indent=2))
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Classification failed: {exc}") from exc


if __name__ == "__main__":
    main()
