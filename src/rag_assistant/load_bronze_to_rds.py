"""Clean the selected S3 Bronze issue records and load them into RDS."""

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import psycopg
from botocore.exceptions import BotoCoreError
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRONZE_SOURCES = (
    (
        "tiangolo/fastapi",
        "bronze/github/repo=fastapi__fastapi/ingested_at=20261005T101821560700Z/",
    ),
    (
        "encode/starlette",
        "bronze/github/repo=encode__starlette/ingested_at=20261005T101851267365Z/",
    ),
    (
        "pydantic/pydantic",
        "bronze/github/repo=pydantic__pydantic/ingested_at=20261005T101918016130Z/",
    ),
)
MAINTAINER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
TABLE_NAME = "public.github_issues_clean"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    repository TEXT NOT NULL,
    issue_number BIGINT NOT NULL,
    title TEXT,
    body TEXT,
    github_url TEXT NOT NULL,
    labels JSONB NOT NULL,
    created_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    content_hash TEXT NOT NULL DEFAULT '',
    comment_count INTEGER NOT NULL,
    comments JSONB NOT NULL,
    author_associations JSONB NOT NULL,
    resolution_text TEXT,
    resolution_heuristic TEXT NOT NULL,
    resolution_confidence TEXT NOT NULL,
    bronze_prefix TEXT NOT NULL,
    source_line_number INTEGER NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT github_issues_clean_repo_issue_unique
        UNIQUE (repository, issue_number)
)
"""

ALTER_TABLE_SQL = f"""
ALTER TABLE {TABLE_NAME}
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS content_hash TEXT NOT NULL DEFAULT ''
"""

UPSERT_SQL = f"""
INSERT INTO {TABLE_NAME} AS existing (
    repository,
    issue_number,
    title,
    body,
    github_url,
    labels,
    created_at,
    closed_at,
    updated_at,
    content_hash,
    comment_count,
    comments,
    author_associations,
    resolution_text,
    resolution_heuristic,
    resolution_confidence,
    bronze_prefix,
    source_line_number,
    loaded_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    CURRENT_TIMESTAMP
)
ON CONFLICT (repository, issue_number) DO UPDATE SET
    title = EXCLUDED.title,
    body = EXCLUDED.body,
    github_url = EXCLUDED.github_url,
    labels = EXCLUDED.labels,
    created_at = EXCLUDED.created_at,
    closed_at = EXCLUDED.closed_at,
    updated_at = EXCLUDED.updated_at,
    content_hash = EXCLUDED.content_hash,
    comment_count = EXCLUDED.comment_count,
    comments = EXCLUDED.comments,
    author_associations = EXCLUDED.author_associations,
    resolution_text = EXCLUDED.resolution_text,
    resolution_heuristic = EXCLUDED.resolution_heuristic,
    resolution_confidence = EXCLUDED.resolution_confidence,
    bronze_prefix = EXCLUDED.bronze_prefix,
    source_line_number = EXCLUDED.source_line_number,
    loaded_at = CURRENT_TIMESTAMP
WHERE (
    existing.title, existing.body, existing.github_url, existing.labels,
    existing.created_at, existing.closed_at, existing.updated_at,
    existing.content_hash, existing.comment_count, existing.comments,
    existing.author_associations, existing.resolution_text,
    existing.resolution_heuristic, existing.resolution_confidence
) IS DISTINCT FROM (
    EXCLUDED.title, EXCLUDED.body, EXCLUDED.github_url, EXCLUDED.labels,
    EXCLUDED.created_at, EXCLUDED.closed_at, EXCLUDED.updated_at,
    EXCLUDED.content_hash, EXCLUDED.comment_count, EXCLUDED.comments,
    EXCLUDED.author_associations, EXCLUDED.resolution_text,
    EXCLUDED.resolution_heuristic, EXCLUDED.resolution_confidence
)
RETURNING (xmax = 0)
"""


def required_environment() -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    required_names = (
        "AWS_DEFAULT_REGION",
        "S3_BUCKET",
        "PGHOST",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
    )
    missing = [name for name in required_names if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing required .env settings: {', '.join(missing)}")
    if bool(os.getenv("AWS_ACCESS_KEY_ID")) != bool(os.getenv("AWS_SECRET_ACCESS_KEY")):
        raise ValueError(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set together"
        )

    try:
        port = int(os.getenv("PGPORT", "5432"))
    except ValueError as exc:
        raise ValueError("PGPORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PGPORT must be between 1 and 65535")

    return {
        **{name: os.environ[name] for name in required_names},
        "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "AWS_SESSION_TOKEN": os.getenv("AWS_SESSION_TOKEN"),
        "PGPORT": port,
        "PGSSLMODE": os.getenv("PGSSLMODE", "require"),
    }


def create_s3_client(settings: dict[str, Any]) -> Any:
    options: dict[str, Any] = {"region_name": settings["AWS_DEFAULT_REGION"]}
    if settings["AWS_ACCESS_KEY_ID"] and settings["AWS_SECRET_ACCESS_KEY"]:
        options["aws_access_key_id"] = settings["AWS_ACCESS_KEY_ID"]
        options["aws_secret_access_key"] = settings["AWS_SECRET_ACCESS_KEY"]
    if settings["AWS_SESSION_TOKEN"] and "aws_access_key_id" in options:
        options["aws_session_token"] = settings["AWS_SESSION_TOKEN"]
    return boto3.client("s3", **options)


def read_bronze_records(
    client: Any,
    bucket: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]], int]:
    sources: list[dict[str, Any]] = []
    source_counts = {
        repository: {
            "source_records": 0,
            "rejected_records": 0,
            "valid_records": 0,
            "duplicate_records": 0,
            "missing_bodies": 0,
            "missing_heuristic_resolutions": 0,
        }
        for repository, _ in BRONZE_SOURCES
    }
    total_rejected = 0

    source_keys: dict[str, list[tuple[str, str]]] = {
        repository: [] for repository, _ in BRONZE_SOURCES
    }
    for repository, _ in BRONZE_SOURCES:
        safe_repository = re.sub(r"[^A-Za-z0-9_.-]", "__", repository)
        list_prefix = f"bronze/github/repo={safe_repository}/issue="
        continuation_token = None
        while True:
            parameters: dict[str, Any] = {"Bucket": bucket, "Prefix": list_prefix}
            if continuation_token:
                parameters["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**parameters)
            if not isinstance(response, dict):
                break
            for item in response.get("Contents", []):
                key = item.get("Key")
                if isinstance(key, str) and key.endswith(".json"):
                    source_keys[repository].append((key, list_prefix))
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
            if not continuation_token:
                raise RuntimeError("S3 returned a truncated page without a continuation token")

    for repository, legacy_prefix in BRONZE_SOURCES:
        source_keys[repository].append(
            (f"{legacy_prefix}issues.jsonl", legacy_prefix)
        )

    for repository, keyed_sources in source_keys.items():
        for key, prefix in keyed_sources:
            response = client.get_object(Bucket=bucket, Key=key)
            body = response["Body"]
            try:
                content = body.read()
            finally:
                body.close()

            lines = (
                content.decode("utf-8").splitlines()
                if key.endswith(".jsonl")
                else [content.decode("utf-8")]
            )
            for line_number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                source_counts[repository]["source_records"] += 1
                try:
                    raw_record = json.loads(line)
                except json.JSONDecodeError:
                    source_counts[repository]["rejected_records"] += 1
                    total_rejected += 1
                    continue
                if not isinstance(raw_record, dict):
                    source_counts[repository]["rejected_records"] += 1
                    total_rejected += 1
                    continue
                sources.append(
                    {
                        "repository": repository,
                        "bronze_prefix": prefix,
                        "source_line_number": line_number,
                        "raw": raw_record,
                    }
                )

    return sources, source_counts, total_rejected


def normalize_title(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("title must be text")
    return re.sub(r"\s+", " ", unescape(value).replace("\x00", "")).strip()


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("text fields must be text")
    return unescape(value).replace("\r\n", "\n").replace("\r", "\n").replace(
        "\x00", ""
    ).strip()


def parse_timestamp(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("timestamp fields must be ISO-formatted text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_labels(raw_labels: Any) -> list[str]:
    if raw_labels is None:
        return []
    if not isinstance(raw_labels, list):
        raise ValueError("labels must be a list")
    labels = []
    for label in raw_labels:
        value = label.get("name") if isinstance(label, dict) else label
        if isinstance(value, str) and value.strip():
            normalized = normalize_title(value)
            if normalized:
                labels.append(normalized)
    return labels


def clean_comments(raw_comments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_comments, list):
        raise ValueError("comments must be a list")
    comments: list[dict[str, Any]] = []
    for comment in raw_comments:
        if not isinstance(comment, dict):
            raise ValueError("each comment must be an object")
        author = comment.get("user")
        author_login = author.get("login") if isinstance(author, dict) else None
        created_at = parse_timestamp(comment.get("created_at"))
        comments.append(
            {
                "id": comment.get("id"),
                "body": normalize_text(comment.get("body")),
                "created_at": created_at.isoformat() if created_at else None,
                "author_login": author_login,
                "author_association": comment.get("author_association"),
                "html_url": comment.get("html_url"),
            }
        )
    return comments


def choose_resolution(
    comments: list[dict[str, Any]],
    closed_at: datetime | None,
) -> tuple[str | None, str, str]:
    if closed_at is None:
        return None, "unavailable_missing_closed_at", "none"

    candidates = []
    for comment in comments:
        created_at = parse_timestamp(comment["created_at"])
        if (
            created_at is not None
            and created_at < closed_at
            and comment["author_association"] in MAINTAINER_ASSOCIATIONS
        ):
            candidates.append((created_at, comment))
    if not candidates:
        return None, "unavailable_no_maintainer_comment_before_closure", "none"

    _, last_candidate = max(candidates, key=lambda candidate: candidate[0])
    resolution_text = last_candidate["body"]
    if not resolution_text:
        return None, "unavailable_last_maintainer_comment_has_no_text", "none"
    return resolution_text, "last_maintainer_comment_before_closure", "low"


def clean_record(source: dict[str, Any]) -> dict[str, Any]:
    repository = source.get("repository")
    raw_record = source.get("raw")
    if not isinstance(repository, str) or not repository.strip():
        raise ValueError("repository is required")
    if not isinstance(raw_record, dict):
        raise ValueError("record must contain an issue object")
    issue = raw_record.get("issue")
    if not isinstance(issue, dict):
        raise ValueError("issue is required")

    issue_number = issue.get("number")
    if isinstance(issue_number, bool) or not isinstance(issue_number, (int, str)):
        raise ValueError("issue number is required and must be an integer")
    try:
        issue_number = int(issue_number)
    except ValueError as exc:
        raise ValueError("issue number is required and must be an integer") from exc
    if issue_number < 1:
        raise ValueError("issue number must be positive")

    github_url = issue.get("html_url")
    parsed_url = urlparse(github_url) if isinstance(github_url, str) else None
    if (
        parsed_url is None
        or parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
    ):
        raise ValueError("a valid GitHub issue URL is required")

    created_at = parse_timestamp(issue.get("created_at"))
    closed_at = parse_timestamp(issue.get("closed_at"))
    comments = clean_comments(raw_record.get("comments"))
    resolution_text, resolution_heuristic, resolution_confidence = (
        choose_resolution(comments, closed_at)
    )
    updated_at = parse_timestamp(issue.get("updated_at"))
    author = issue.get("user")
    issue_author_association = issue.get("author_association")
    title = normalize_title(issue.get("title"))
    body = normalize_text(issue.get("body"))
    labels = clean_labels(issue.get("labels"))
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "title": title,
                "body": body,
                "github_url": github_url,
                "comments": [
                    {"body": comment["body"], "html_url": comment["html_url"]}
                    for comment in comments
                    if comment["body"]
                ],
                "resolution_text": resolution_text,
                "resolution_confidence": resolution_confidence,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "repository": repository,
        "issue_number": issue_number,
        "title": title,
        "body": body,
        "github_url": github_url,
        "labels": labels,
        "created_at": created_at,
        "closed_at": closed_at,
        "updated_at": updated_at,
        "content_hash": content_hash,
        "comment_count": len(comments),
        "comments": comments,
        "author_associations": {
            "issue_author": {
                "login": author.get("login") if isinstance(author, dict) else None,
                "association": issue_author_association,
            },
            "comment_authors": [
                {
                    "login": comment["author_login"],
                    "association": comment["author_association"],
                }
                for comment in comments
            ],
        },
        "resolution_text": resolution_text,
        "resolution_heuristic": resolution_heuristic,
        "resolution_confidence": resolution_confidence,
        "bronze_prefix": source["bronze_prefix"],
        "source_line_number": source["source_line_number"],
    }


def validate_and_clean(
    sources: list[dict[str, Any]],
    source_counts: dict[str, dict[str, int]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen: set[tuple[str, int]] = set()
    cleaned: list[dict[str, Any]] = []
    rejected_reasons: list[dict[str, Any]] = []
    missing_bodies = 0
    missing_resolutions = 0

    for source in sources:
        repository = source["repository"]
        try:
            row = clean_record(source)
        except ValueError as exc:
            source_counts[repository]["rejected_records"] += 1
            rejected_reasons.append(
                {
                    "repository": repository,
                    "source_line_number": source["source_line_number"],
                    "reason": str(exc),
                }
            )
            continue

        identity = (row["repository"], row["issue_number"])
        if identity in seen:
            source_counts[repository]["rejected_records"] += 1
            source_counts[repository]["duplicate_records"] += 1
            rejected_reasons.append(
                {
                    "repository": repository,
                    "source_line_number": source["source_line_number"],
                    "reason": "duplicate repository and issue number",
                }
            )
            continue
        seen.add(identity)

        source_counts[repository]["valid_records"] += 1
        if not row["body"]:
            missing_bodies += 1
            source_counts[repository]["missing_bodies"] += 1
        if not row["resolution_text"]:
            missing_resolutions += 1
            source_counts[repository]["missing_heuristic_resolutions"] += 1
        cleaned.append(row)

    return cleaned, {
        "source_records": sum(
            counts["source_records"] for counts in source_counts.values()
        ),
        "valid_records": len(cleaned),
        "rejected_records": sum(
            counts["rejected_records"] for counts in source_counts.values()
        ),
        "duplicate_records": sum(
            1
            for reason in rejected_reasons
            if reason["reason"] == "duplicate repository and issue number"
        ),
        "missing_bodies": missing_bodies,
        "missing_heuristic_resolutions": missing_resolutions,
        "rejected_reasons": rejected_reasons,
        "by_repository": source_counts,
    }


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


def upsert_records(
    records: list[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[int, int, int]:
    inserted = 0
    updated = 0
    with psycopg.connect(**database_options(settings)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
            cursor.execute(ALTER_TABLE_SQL)
            for record in records:
                values = (
                    record["repository"],
                    record["issue_number"],
                    record["title"],
                    record["body"],
                    record["github_url"],
                    Jsonb(record["labels"]),
                    record["created_at"],
                    record["closed_at"],
                    record["updated_at"],
                    record["content_hash"],
                    record["comment_count"],
                    Jsonb(record["comments"]),
                    Jsonb(record["author_associations"]),
                    record["resolution_text"],
                    record["resolution_heuristic"],
                    record["resolution_confidence"],
                    record["bronze_prefix"],
                    record["source_line_number"],
                )
                cursor.execute(UPSERT_SQL, values)
                result = cursor.fetchone()
                if result is None:
                    continue
                if result[0]:
                    inserted += 1
                else:
                    updated += 1
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            total_rows = cursor.fetchone()[0]
    return inserted, updated, total_rows


def run_load() -> dict[str, Any]:
    settings = required_environment()
    s3 = create_s3_client(settings)
    sources, source_counts, parse_rejections = read_bronze_records(
        s3,
        settings["S3_BUCKET"],
    )
    cleaned, validation = validate_and_clean(sources, source_counts)
    validation["rejected_records"] += parse_rejections

    inserted, updated, total_rows = upsert_records(cleaned, settings)
    return {
        "bronze_inputs": [
            {
                "repository": repository,
                "s3_path": f"s3://{settings['S3_BUCKET']}/{prefix}issues.jsonl",
            }
            for repository, prefix in BRONZE_SOURCES
        ],
        "rows_inserted": inserted,
        "rows_updated": updated,
        "total_rows_in_rds": total_rows,
        "validation": validation,
        "resolution_note": (
            "Resolution text is a low-confidence heuristic based on the last "
            "maintainer-associated comment before closure; it is not guaranteed "
            "ground truth."
        ),
    }


def main() -> None:
    try:
        print(json.dumps(run_load(), indent=2, default=str))
    except (BotoCoreError, psycopg.Error, ValueError) as exc:
        raise SystemExit(f"Bronze-to-RDS load failed: {exc}") from exc


if __name__ == "__main__":
    main()
