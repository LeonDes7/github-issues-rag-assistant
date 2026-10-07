"""Run local retrieval/generation evaluation cases and persist results in RDS."""

import argparse
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from openai import OpenAI
from psycopg.types.json import Jsonb

from rag_assistant import api


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = PROJECT_ROOT / "evaluation_cases.jsonl"
RUNS_TABLE = "public.rag_evaluation_runs"
RESULTS_TABLE = "public.rag_evaluation_case_results"
ABSTENTION_PATTERN = re.compile(
    r"\b(?:insufficient evidence|evidence is insufficient|"
    r"evidence does not (?:provide|support|contain)|"
    r"cannot (?:answer|determine|provide)|can't (?:answer|determine)|"
    r"not enough evidence|unable to answer|do not have enough)\b",
    re.IGNORECASE,
)
TOKEN_PATTERN = re.compile(r"[a-z0-9_]{3,}", re.IGNORECASE)
CITATION_REFERENCE_PATTERN = re.compile(r"(?<![!\\])\[(\d+)\](?!\s*\()")
STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "before",
    "from",
    "into",
    "issue",
    "more",
    "only",
    "reported",
    "that",
    "the",
    "their",
    "then",
    "this",
    "through",
    "using",
    "what",
    "when",
    "with",
}

CREATE_RUNS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {RUNS_TABLE} (
    run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    embedding_model TEXT NOT NULL,
    generation_model TEXT NOT NULL,
    top_k INTEGER NOT NULL,
    case_count INTEGER NOT NULL,
    judge_enabled BOOLEAN NOT NULL,
    metrics JSONB NOT NULL
)
"""

CREATE_RESULTS_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {RESULTS_TABLE} (
    run_id UUID NOT NULL REFERENCES {RUNS_TABLE}(run_id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    verification_status TEXT NOT NULL CHECK (
        verification_status IN ('manually_verified', 'heuristic', 'unresolved')
    ),
    question TEXT NOT NULL,
    case_result JSONB NOT NULL,
    PRIMARY KEY (run_id, case_id)
)
"""


def database_options(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": settings["PGHOST"],
        "port": settings["PGPORT"],
        "dbname": settings["PGDATABASE"],
        "user": settings["PGUSER"],
        "password": settings["PGPASSWORD"],
        "sslmode": settings["PGSSLMODE"],
        "connect_timeout": 10,
    }


def load_cases(path: Path = DEFAULT_CASES_PATH) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path.name} line {line_number}") from exc
        required = {
            "case_id",
            "question",
            "expected_issues",
            "expected_issue_urls",
            "verification_status",
            "expected_abstain",
            "verification_note",
        }
        if not isinstance(case, dict) or not required.issubset(case):
            raise ValueError(f"Evaluation case line {line_number} has missing fields")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id or case_id in seen_ids:
            raise ValueError(f"Invalid or duplicate case_id on line {line_number}")
        if case["verification_status"] not in {
            "manually_verified",
            "heuristic",
            "unresolved",
        }:
            raise ValueError(f"Invalid verification status on line {line_number}")
        if not isinstance(case["question"], str) or not case["question"].strip():
            raise ValueError(f"Question is empty on line {line_number}")
        if not isinstance(case["expected_issues"], list) or not isinstance(
            case["expected_issue_urls"], list
        ):
            raise ValueError(f"Expected sources must be lists on line {line_number}")
        if case["verification_status"] == "unresolved" and (
            case["expected_issues"] or case["expected_issue_urls"]
        ):
            raise ValueError("Unresolved cases cannot assert an expected issue")
        seen_ids.add(case_id)
        cases.append(case)
    if not cases:
        raise ValueError("Evaluation case file contains no cases")
    return cases


def matched_expected_reference(
    expected: dict[str, Any],
    result: dict[str, Any],
) -> bool:
    identifier_matches = (
        expected.get("repository") == result.get("repository")
        and expected.get("issue_number") == result.get("issue_number")
    )
    url = expected.get("issue_url")
    return identifier_matches or (bool(url) and url == result.get("issue_url"))


def retrieval_case_metrics(
    case: dict[str, Any],
    retrieved: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = case["expected_issues"]
    if not expected and not case["expected_issue_urls"]:
        return {
            "applicable": False,
            "hit_at_k": None,
            "recall_at_k": None,
            "mrr": None,
            "matched_expected": [],
        }

    expected_references = expected or [
        {"issue_url": url} for url in case["expected_issue_urls"]
    ]
    matched: list[dict[str, Any]] = []
    matched_keys: set[tuple[Any, ...]] = set()
    first_rank: int | None = None
    for rank, result in enumerate(retrieved, 1):
        expected_item = next(
            (
                item
                for item in expected_references
                if matched_expected_reference(item, result)
            ),
            None,
        )
        if expected_item is not None:
            key = (
                "issue",
                expected_item.get("repository"),
                expected_item.get("issue_number"),
            )
            if expected_item.get("issue_url"):
                key = ("url", expected_item["issue_url"])
            if key not in matched_keys:
                matched_keys.add(key)
                matched.append(expected_item)
                if first_rank is None:
                    first_rank = rank
    return {
        "applicable": True,
        "hit_at_k": int(first_rank is not None),
        "recall_at_k": len(matched) / len(expected_references),
        "mrr": 1 / first_rank if first_rank is not None else 0.0,
        "matched_expected": matched,
    }


def answer_is_abstention(answer: str) -> bool:
    return bool(ABSTENTION_PATTERN.search(answer))


def _content_terms(text: str) -> set[str]:
    terms = {
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if token.lower() not in STOP_WORDS
    }
    return terms


def generation_case_metrics(
    case: dict[str, Any],
    answer: str,
    retrieved: list[dict[str, Any]],
    retrieval_metrics: dict[str, Any],
) -> dict[str, Any]:
    abstained = answer_is_abstention(answer)
    expected_sources_present = retrieval_metrics["applicable"] and bool(
        retrieval_metrics["hit_at_k"]
    )
    should_abstain = case["expected_abstain"] or (
        retrieval_metrics["applicable"] and not expected_sources_present
    )
    references = [
        int(match.group(1))
        for match in CITATION_REFERENCE_PATTERN.finditer(answer)
    ]
    valid_reference_numbers = set(range(1, len(retrieved) + 1))
    citations_valid = all(
        reference in valid_reference_numbers for reference in references
    )
    if not abstained and retrieved:
        citations_valid = citations_valid and bool(references)
    elif not abstained and not retrieved:
        citations_valid = False

    grounded_claims = []
    answer_lines = re.split(r"(?<=[.!?])\s+(?!\[\d+\])|\n+", answer)
    for line in answer_lines:
        claim = re.sub(r"\[\d+\]", "", line).strip(" `>*-#\t")
        terms = _content_terms(claim)
        if len(terms) < 2 or ABSTENTION_PATTERN.search(claim):
            continue
        line_references = [
            int(match.group(1))
            for match in CITATION_REFERENCE_PATTERN.finditer(line)
        ]
        supported = False
        for reference in line_references:
            if not 1 <= reference <= len(retrieved):
                continue
            evidence_terms = _content_terms(retrieved[reference - 1]["chunk_text"])
            overlap = len(terms & evidence_terms) / len(terms)
            if overlap >= 0.25:
                supported = True
                break
        grounded_claims.append(supported)

    grounded = all(grounded_claims) if grounded_claims else abstained
    return {
        "abstained": abstained,
        "should_abstain": should_abstain,
        "abstained_appropriately": abstained == should_abstain,
        "citation_references": references,
        "citations_valid": citations_valid,
        "grounded_in_retrieved_chunks": grounded,
        "grounding_method": "automated lexical overlap heuristic, not truth validation",
        "factual_claims_grounded": grounded_claims,
    }


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _retrieval_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scored_cases": len(items),
        "hit_at_k": _mean([item["hit_at_k"] for item in items]),
        "recall_at_k": _mean([item["recall_at_k"] for item in items]),
        "mrr": _mean([item["mrr"] for item in items]),
    }


def summarize_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_status[result["verification_status"]].append(result)

    retrieval_by_status: dict[str, Any] = {}
    generation_by_status: dict[str, Any] = {}
    for status, group in by_status.items():
        retrieval = [
            item["retrieval_metrics"]
            for item in group
            if item["retrieval_metrics"]["applicable"]
        ]
        retrieval_by_status[status] = {
            "scored_cases": len(retrieval),
            "hit_at_k": _mean([item["hit_at_k"] for item in retrieval]),
            "recall_at_k": _mean([item["recall_at_k"] for item in retrieval]),
            "mrr": _mean([item["mrr"] for item in retrieval]),
        }
        generation_by_status[status] = {
            "cases": len(group),
            "abstention_appropriate_rate": _mean(
                [
                    float(item["generation_metrics"]["abstained_appropriately"])
                    for item in group
                ]
            ),
            "valid_citation_rate": _mean(
                [
                    float(item["generation_metrics"]["citations_valid"])
                    for item in group
                ]
            ),
            "lexically_grounded_rate": _mean(
                [
                    float(
                        item["generation_metrics"][
                            "grounded_in_retrieved_chunks"
                        ]
                    )
                    for item in group
                ]
            ),
        }

    verified_retrieval = retrieval_by_status.get(
        "manually_verified",
        {"scored_cases": 0, "hit_at_k": None, "recall_at_k": None, "mrr": None},
    )
    all_answerable_retrieval = [
        result["retrieval_metrics"]
        for result in results
        if result["retrieval_metrics"]["applicable"]
    ]
    by_repository: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        metrics = result["retrieval_metrics"]
        if not metrics["applicable"]:
            continue
        repositories = {
            expected["repository"]
            for expected in result.get("expected_issues", [])
            if expected.get("repository")
        }
        for repository in repositories:
            by_repository[repository].append(metrics)

    return {
        "case_count": len(results),
        "retrieval_all_answerable_cases": _retrieval_summary(
            all_answerable_retrieval
        ),
        "retrieval_by_repository": {
            repository: _retrieval_summary(group)
            for repository, group in sorted(by_repository.items())
        },
        "retrieval_manual_verified_only": verified_retrieval,
        "retrieval_by_verification_status": retrieval_by_status,
        "generation_by_verification_status": generation_by_status,
        "grounding_metric_note": (
            "Lexical overlap is an automated screening heuristic and does not "
            "establish factual truth."
        ),
        "heuristic_case_note": (
            "Cases marked heuristic are exploratory and are not ground-truth "
            "labels because maintainer-comment resolution extraction is uncertain."
        ),
    }


def run_case(
    case: dict[str, Any],
    top_k: int,
    client: OpenAI,
    connection: psycopg.Connection[Any],
    embedding_model: str,
    generation_model: str,
) -> dict[str, Any]:
    embedded = client.embeddings.create(
        model=embedding_model,
        input=case["question"],
        dimensions=api.VECTOR_DIMENSIONS,
    )
    vector = embedded.data[0].embedding
    if len(vector) != api.VECTOR_DIMENSIONS:
        raise RuntimeError("Evaluation question embedding has an invalid dimension")
    retrieved = api.retrieve_chunks(connection, vector, top_k)
    answer = api.generate_grounded_answer(
        client,
        generation_model,
        case["question"],
        retrieved,
    )
    retrieval_metrics = retrieval_case_metrics(case, retrieved)
    generation_metrics = generation_case_metrics(
        case,
        answer,
        retrieved,
        retrieval_metrics,
    )
    citations = [
        {
            "repository": chunk["repository"],
            "issue_number": chunk["issue_number"],
            "issue_url": chunk["issue_url"],
            "source_url": chunk["source_url"],
            "chunk_type": chunk["chunk_type"],
            "similarity_score": chunk["similarity_score"],
        }
        for chunk in retrieved
    ]
    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "verification_status": case["verification_status"],
        "expected_issues": case["expected_issues"],
        "expected_issue_urls": case["expected_issue_urls"],
        "expected_abstain": case["expected_abstain"],
        "verification_note": case["verification_note"],
        "answer": answer,
        "citations": citations,
        "retrieved_count": len(retrieved),
        "retrieval_metrics": retrieval_metrics,
        "generation_metrics": generation_metrics,
    }


def judge_case(
    client: OpenAI,
    model: str,
    case: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    request = {
        "question": case["question"],
        "answer": result["answer"],
        "retrieved_sources": result["citations"],
        "verification_status": case["verification_status"],
        "warning": (
            "Heuristic cases are uncertain and must not be treated as ground truth."
        ),
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Score the answer as an automated estimate, not absolute truth. "
                    "Return JSON with grounded (boolean), citation_support "
                    "(boolean), abstention_appropriate (boolean), and brief_reason."
                ),
            },
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM judge returned an empty result")
    judgment = json.loads(content)
    return {"label": "automated_estimate_not_absolute_truth", **judgment}


def persist_evaluation(
    connection: psycopg.Connection[Any],
    run_id: uuid.UUID,
    started_at: datetime,
    finished_at: datetime,
    embedding_model: str,
    generation_model: str,
    top_k: int,
    judge_enabled: bool,
    metrics: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(CREATE_RUNS_TABLE_SQL)
        cursor.execute(CREATE_RESULTS_TABLE_SQL)
        cursor.execute(
            f"""
            INSERT INTO {RUNS_TABLE} (
                run_id, started_at, finished_at, embedding_model,
                generation_model, top_k, case_count, judge_enabled, metrics
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                started_at,
                finished_at,
                embedding_model,
                generation_model,
                top_k,
                len(results),
                judge_enabled,
                Jsonb(metrics),
            ),
        )
        for result in results:
            cursor.execute(
                f"""
                INSERT INTO {RESULTS_TABLE} (
                    run_id, case_id, verification_status, question, case_result
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    result["case_id"],
                    result["verification_status"],
                    result["question"],
                    Jsonb(result),
                ),
            )
    connection.commit()


def concise_report(results: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for result in results:
        retrieval = result["retrieval_metrics"]
        generation = result["generation_metrics"]
        failed = (
            (retrieval["applicable"] and not retrieval["hit_at_k"])
            or not generation["abstained_appropriately"]
            or not generation["citations_valid"]
            or not generation["grounded_in_retrieved_chunks"]
        )
        if failed:
            failures.append(
                {
                    "case_id": result["case_id"],
                    "verification_status": result["verification_status"],
                    "question": result["question"],
                    "retrieval_hit": retrieval["hit_at_k"],
                    "abstained_appropriately": generation[
                        "abstained_appropriately"
                    ],
                    "citations_valid": generation["citations_valid"],
                    "grounded_in_retrieved_chunks": generation[
                        "grounded_in_retrieved_chunks"
                    ],
                    "answer": result["answer"],
                    "citations": result["citations"],
                }
            )
    return {
        "metrics": metrics,
        "failure_examples": failures[:5],
    }


def run_evaluation(
    cases_path: Path = DEFAULT_CASES_PATH,
    top_k: int = 5,
    use_judge: bool = False,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    settings = api.get_settings()
    embedding_model = settings["OPENAI_EMBEDDING_MODEL"]
    generation_model = settings["OPENAI_GENERATION_MODEL"]
    run_id = uuid.uuid4()
    started_at = datetime.now(timezone.utc)
    client = api.get_openai_client()
    results: list[dict[str, Any]] = []

    with psycopg.connect(**database_options(settings)) as connection:
        for case in cases:
            result = run_case(
                case,
                top_k,
                client,
                connection,
                embedding_model,
                generation_model,
            )
            if use_judge:
                result["llm_judge"] = judge_case(
                    client,
                    generation_model,
                    case,
                    result,
                )
            results.append(result)

        finished_at = datetime.now(timezone.utc)
        metrics = summarize_metrics(results)
        persist_evaluation(
            connection,
            run_id,
            started_at,
            finished_at,
            embedding_model,
            generation_model,
            top_k,
            use_judge,
            metrics,
            results,
        )

    return {
        "run_id": str(run_id),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "embedding_model": embedding_model,
        "generation_model": generation_model,
        "top_k": top_k,
        **concise_report(results, metrics),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local GitHub issue RAG evaluation suite."
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Add optional LLM-as-judge scores, labeled automated estimates",
    )
    args = parser.parse_args()
    if not 1 <= args.top_k <= 20:
        parser.error("--top-k must be between 1 and 20")
    try:
        print(json.dumps(run_evaluation(args.cases, args.top_k, args.judge), indent=2))
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Evaluation failed: {exc}") from exc


if __name__ == "__main__":
    main()
