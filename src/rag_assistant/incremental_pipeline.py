"""Run the resumable Bronze-to-Gold ingestion pipeline with per-repo watermarks."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import psycopg
from dotenv import load_dotenv

from rag_assistant import (
    data_quality,
    embed_issue_chunks,
    ingest_github_issues,
    load_bronze_to_rds,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WATERMARK_TABLE = "public.github_ingestion_watermarks"
CREATE_WATERMARK_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {WATERMARK_TABLE} (
    repository TEXT PRIMARY KEY,
    last_successful_updated_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def load_runtime_secrets() -> None:
    secret_arn = os.getenv("RAG_SECRETS_ARN")
    if not secret_arn:
        return
    response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("RAG_SECRETS_ARN must reference a text JSON secret")
    try:
        values = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise RuntimeError("RAG Secrets Manager value must contain valid JSON") from exc
    if not isinstance(values, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in values.items()
    ):
        raise RuntimeError("RAG secret must be a JSON object containing string values")
    for name in ("GITHUB_TOKEN", "OPENAI_API_KEY", "PGPASSWORD"):
        if name in values:
            os.environ.setdefault(name, values[name])


def watermark_string(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def read_watermarks(
    connection: psycopg.Connection[Any],
    repositories: list[str],
) -> dict[str, str | None]:
    with connection.cursor() as cursor:
        cursor.execute(CREATE_WATERMARK_TABLE_SQL)
        cursor.execute(
            f"""
            SELECT repository, last_successful_updated_at
            FROM {WATERMARK_TABLE}
            WHERE repository = ANY(%s)
            """,
            (repositories,),
        )
        rows = cursor.fetchall()
    watermarks = {repository: None for repository in repositories}
    watermarks.update(
        {
            repository: watermark_string(updated_at)
            for repository, updated_at in rows
        }
    )
    connection.commit()
    return watermarks


def advance_watermarks(
    connection: psycopg.Connection[Any],
    results: list[dict[str, Any]],
) -> None:
    with connection.cursor() as cursor:
        for result in results:
            updated_at = result.get("max_updated_at")
            if not updated_at:
                continue
            cursor.execute(
                f"""
                INSERT INTO {WATERMARK_TABLE} AS watermark (
                    repository, last_successful_updated_at, updated_at
                ) VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (repository) DO UPDATE SET
                    last_successful_updated_at = GREATEST(
                        watermark.last_successful_updated_at,
                        EXCLUDED.last_successful_updated_at
                    ),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (result["repository"], watermark_string(updated_at)),
            )
    connection.commit()


def run_pipeline(repositories: list[str] | None = None) -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    load_runtime_secrets()
    github_settings = ingest_github_issues.required_environment()
    database_settings = load_bronze_to_rds.required_environment()
    embed_issue_chunks.required_environment()
    selected_repositories = repositories or github_settings["GITHUB_REPOS"]

    database_options = load_bronze_to_rds.database_options(database_settings)
    with psycopg.connect(**database_options) as connection:
        watermarks = read_watermarks(connection, selected_repositories)

    s3 = ingest_github_issues.s3_client(github_settings)
    ingestion_results = [
        ingest_github_issues.ingest_repository(
            repository,
            github_settings["TARGET_RECORDS_PER_REPO"],
            github_settings["MAX_ENTRIES_TO_SCAN_PER_REPO"],
            github_settings,
            s3,
            since=watermarks[repository],
        )
        for repository in selected_repositories
    ]
    bronze_quality = data_quality.check_bronze_layer(
        s3,
        github_settings["S3_BUCKET"],
    )
    silver_result = load_bronze_to_rds.run_load()
    silver_quality = data_quality.check_silver_layer(
        database_settings,
        bronze_quality,
    )
    gold_result = embed_issue_chunks.run_embedding(limit=None)
    gold_quality = data_quality.check_gold_layer(
        database_settings,
        silver_quality,
    )

    with psycopg.connect(**database_options) as connection:
        advance_watermarks(connection, ingestion_results)

    return {
        "repositories": ingestion_results,
        "silver": silver_result,
        "gold": gold_result,
        "data_quality": {
            "passed": True,
            "layers": [bronze_quality, silver_quality, gold_quality],
        },
        "totals": {
            "issues_uploaded": sum(
                result["records_uploaded"] for result in ingestion_results
            ),
            "comments_uploaded": sum(
                result["comments_uploaded"] for result in ingestion_results
            ),
            "chunks": gold_result["chunk_count"],
        },
    }


def main() -> None:
    try:
        result = run_pipeline()
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Incremental ingestion failed: {exc}") from exc
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
