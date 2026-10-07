"""Sample closed issues and draft a reviewable retrieval evaluation set."""

import argparse
import csv
import json
import random
import re
from pathlib import Path
from typing import Any

import psycopg
from openai import OpenAI

from rag_assistant import api


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSONL = PROJECT_ROOT / "evaluation_cases.generated.jsonl"
DEFAULT_CSV = PROJECT_ROOT / "evaluation_cases.review.csv"
REPOSITORIES = ("tiangolo/fastapi", "encode/starlette", "pydantic/pydantic")
UNANSWERABLE_CASES = (
    "What is the latest stable Python release today?",
    "Which AWS IAM policy should I attach for production access?",
    "What is the current price of a PostgreSQL RDS instance?",
    "Can you diagnose my private production server from this repository?",
    "Who won the most recent international football tournament?",
    "What is the weather forecast for Tokyo tomorrow?",
    "Convert 37 degrees Celsius to Fahrenheit.",
    "Write a short birthday message for my coworker.",
    "What is the current balance in my bank account?",
    "Which restaurant near me has the best reviews?",
    "Summarize the contents of a file on my personal computer.",
    "What time does the sun set in Chicago today?",
    "Recommend a movie released this weekend.",
    "How many calories are in the lunch I ate today?",
    "What is the latest stock price for a company I own?",
)

QUESTION_SYSTEM_PROMPT = """Draft one realistic user question that can be answered
from the supplied closed GitHub issue discussion. Ask about the reported
problem, behavior, workaround, or resolution. Do not mention the repository,
issue number, or say that you are quoting an issue. Return JSON with one
non-empty string field named question. Do not answer the question."""


def draft_question(client: OpenAI, model: str, issue: dict[str, Any]) -> str:
    context = {
        "title": issue["title"],
        "body": (issue["body"] or "")[:5000],
        "comments": [
            (comment.get("body") or "")[:1500]
            for comment in issue["comments"][:4]
            if isinstance(comment, dict) and comment.get("body")
        ],
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Question-generation model returned an empty response")
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Question-generation model returned invalid JSON") from exc
    question = result.get("question") if isinstance(result, dict) else None
    if not isinstance(question, str) or not question.strip():
        raise RuntimeError("Question-generation model did not return a question")
    return re.sub(r"\s+", " ", question).strip()


def sample_issues(
    connection: psycopg.Connection[Any],
    count_per_repository: int,
    seed: int,
) -> list[dict[str, Any]]:
    random.seed(seed)
    database_seed = random.random()
    issues: list[dict[str, Any]] = []
    with connection.cursor() as cursor:
        cursor.execute("SELECT setseed(%s)", (database_seed,))
        for repository in REPOSITORIES:
            cursor.execute(
                """
                SELECT repository, issue_number, title, body, comments, github_url
                FROM public.github_issues_clean
                WHERE repository = %s AND closed_at IS NOT NULL
                ORDER BY random()
                LIMIT %s
                """,
                (repository, count_per_repository),
            )
            columns = [description.name for description in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            if len(rows) < count_per_repository:
                raise ValueError(
                    f"{repository} has only {len(rows)} closed issues; "
                    f"{count_per_repository} are required"
                )
            issues.extend(rows)
    random.shuffle(issues)
    return issues


def build_cases(
    issues: list[dict[str, Any]],
    client: OpenAI,
    model: str,
) -> list[dict[str, Any]]:
    cases = []
    seen_questions: set[str] = set()
    for issue in issues:
        question = draft_question(client, model, issue)
        normalized_question = question.casefold()
        if normalized_question in seen_questions:
            raise RuntimeError("Question-generation model produced a duplicate question")
        seen_questions.add(normalized_question)
        repository = issue["repository"]
        issue_number = int(issue["issue_number"])
        note = "LLM-drafted; manually verify the question and gold issue ID."
        cases.append(
            {
                "case_id": f"generated-{repository.replace('/', '-')}-{issue_number}",
                "question": question,
                "gold_issue_id": {
                    "repository": repository,
                    "issue_number": issue_number,
                },
                "expected_issues": [
                    {
                        "repository": repository,
                        "issue_number": issue_number,
                    }
                ],
                "expected_issue_urls": [],
                "verification_status": "heuristic",
                "expected_abstain": False,
                "verification_note": note,
                "notes": note,
            }
        )

    for index, question in enumerate(UNANSWERABLE_CASES, start=1):
        note = "Intentionally outside the indexed closed-issue corpus."
        cases.append(
            {
                "case_id": f"unanswerable-{index:02d}",
                "question": question,
                "gold_issue_id": None,
                "expected_issues": [],
                "expected_issue_urls": [],
                "verification_status": "unresolved",
                "expected_abstain": True,
                "verification_note": note,
                "notes": note,
            }
        )
    return cases


def write_cases(
    cases: list[dict[str, Any]],
    jsonl_path: Path,
    csv_path: Path,
) -> None:
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "case_id",
                "question",
                "gold_repository",
                "gold_issue_number",
                "gold_issue_url",
                "notes",
                "manual_review_status",
            ],
        )
        writer.writeheader()
        for case in cases:
            gold = case["gold_issue_id"] or {}
            repository = gold.get("repository", "")
            issue_number = gold.get("issue_number", "")
            writer.writerow(
                {
                    "case_id": case["case_id"],
                    "question": case["question"],
                    "gold_repository": repository,
                    "gold_issue_number": issue_number,
                    "gold_issue_url": (
                        f"https://github.com/{repository}/issues/{issue_number}"
                        if repository
                        else ""
                    ),
                    "notes": case["notes"],
                    "manual_review_status": (
                        "needs_review" if gold else "unanswerable"
                    ),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draft a balanced retrieval evaluation set."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=45,
        help="Number of sampled answerable cases (15 per repository by default)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    if args.count < 3 or args.count > 45 or args.count % 3:
        parser.error("--count must be a multiple of 3 between 3 and 45")

    settings = api.get_settings()
    model = settings["OPENAI_GENERATION_MODEL"]
    client = api.get_openai_client()
    try:
        with psycopg.connect(**api_settings_to_db_options(settings)) as connection:
            issues = sample_issues(connection, args.count // 3, args.seed)
        cases = build_cases(issues, client, model)
        write_cases(cases, args.jsonl, args.csv)
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Evaluation-set generation failed: {exc}") from exc
    print(
        json.dumps(
            {
                "cases": len(cases),
                "sampled_answerable": args.count,
                "unanswerable": len(UNANSWERABLE_CASES),
                "jsonl": str(args.jsonl),
                "review_csv": str(args.csv),
            },
            indent=2,
        )
    )


def api_settings_to_db_options(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "host": settings["PGHOST"],
        "port": settings["PGPORT"],
        "dbname": settings["PGDATABASE"],
        "user": settings["PGUSER"],
        "password": settings["PGPASSWORD"],
        "sslmode": settings["PGSSLMODE"],
        "connect_timeout": 10,
    }


if __name__ == "__main__":
    main()
