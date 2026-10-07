"""Reconcile Bronze, Silver, and Gold data and fail on hard quality violations."""

import json
import logging
from typing import Any

import psycopg

from rag_assistant import load_bronze_to_rds


LOGGER = logging.getLogger(__name__)
EXPECTED_VECTOR_DIMENSIONS = 1536


class DataQualityError(RuntimeError):
    """Raised when a hard data-quality check fails."""


def quality_report(
    layer: str,
    counts: dict[str, Any],
    hard_failures: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    report = {
        "layer": layer,
        "passed": not hard_failures,
        "counts": counts,
        "hard_failures": hard_failures,
        "warnings": warnings,
    }
    LOGGER.info("data_quality %s", json.dumps(report, default=str))
    return report


def require_pass(report: dict[str, Any]) -> dict[str, Any]:
    if not report["passed"]:
        raise DataQualityError(json.dumps(report, ensure_ascii=False, default=str))
    return report


def check_bronze_layer(client: Any, bucket: str, repositories: list[str] | None = None) -> dict[str, Any]:
    sources, source_counts, parse_rejections = (
        load_bronze_to_rds.read_bronze_records(client, bucket, repositories=repositories)
    )
    cleaned, validation = load_bronze_to_rds.validate_and_clean(
        sources,
        source_counts,
    )
    source_records = validation["source_records"] + parse_rejections
    hard_failures = []
    if parse_rejections:
        hard_failures.append(
            f"{parse_rejections} Bronze record(s) contain malformed JSON"
        )
    if not sources:
        hard_failures.append("Bronze contains no readable issue records")
    warnings = []
    if validation["rejected_records"]:
        warnings.append(
            f"{validation['rejected_records']} Bronze row(s) were rejected, "
            f"including {validation['duplicate_records']} duplicate issue keys"
        )
    report = quality_report(
        "bronze",
        {
            "source_records": source_records,
            "parsed_records": len(sources),
            "valid_unique_issues": len(cleaned),
            "rejected_records": validation["rejected_records"],
            "duplicate_records": validation["duplicate_records"],
            "expected_deduplicated_or_rejected": (
                source_records - len(cleaned)
            ),
        },
        hard_failures,
        warnings,
    )
    report["valid_issue_count"] = len(cleaned)
    report["repositories"] = sorted(source_counts)
    return require_pass(report)


def check_silver_layer(
    settings: dict[str, Any],
    bronze_report: dict[str, Any],
) -> dict[str, Any]:
    repositories = bronze_report["repositories"]
    with psycopg.connect(**load_bronze_to_rds.database_options(settings)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*),
                       COUNT(*) FILTER (
                           WHERE repository IS NULL OR BTRIM(repository) = ''
                              OR issue_number IS NULL OR issue_number < 1
                              OR title IS NULL OR BTRIM(title) = ''
                              OR created_at IS NULL
                       ),
                       COUNT(*) - COUNT(DISTINCT (repository, issue_number)),
                       COALESCE(
                           SUM(
                               CASE
                                   WHEN jsonb_typeof(comments) = 'array'
                                   THEN jsonb_array_length(comments)
                                   ELSE 0
                               END
                           ),
                           0
                       )
                FROM public.github_issues_clean
                WHERE repository = ANY(%s)
                """,
                (repositories,),
            )
            silver_rows, null_key_rows, duplicate_rows, comment_rows = (
                cursor.fetchone()
            )
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM public.github_issues_clean AS issue
                WHERE issue.repository = ANY(%s)
                  AND (
                      jsonb_typeof(issue.comments) IS DISTINCT FROM 'array'
                      OR CASE
                          WHEN jsonb_typeof(issue.comments) = 'array' THEN EXISTS (
                              SELECT 1
                              FROM jsonb_array_elements(issue.comments) AS item
                              WHERE jsonb_typeof(item) IS DISTINCT FROM 'object'
                          )
                          ELSE FALSE
                      END
                  )
                """,
                (repositories,),
            )
            malformed_comment_arrays = cursor.fetchone()[0]

    hard_failures = []
    if silver_rows != bronze_report["valid_issue_count"]:
        hard_failures.append(
            "Silver row count does not match Bronze valid unique issues: "
            f"{silver_rows} != {bronze_report['valid_issue_count']}"
        )
    if null_key_rows:
        hard_failures.append(f"{null_key_rows} Silver row(s) have null/blank key fields")
    if duplicate_rows:
        hard_failures.append(f"{duplicate_rows} duplicate Silver issue key(s)")
    if malformed_comment_arrays:
        hard_failures.append(
            f"{malformed_comment_arrays} Silver row(s) have invalid comment arrays"
        )

    report = quality_report(
        "silver",
        {
            "bronze_valid_unique_issues": bronze_report["valid_issue_count"],
            "silver_rows": silver_rows,
            "silver_comments": comment_rows,
            "null_or_blank_key_rows": null_key_rows,
            "duplicate_issue_keys": duplicate_rows,
            "malformed_comment_arrays": malformed_comment_arrays,
            "comments_are_nested_under_existing_issue_rows": True,
        },
        hard_failures,
        [],
    )
    report["silver_issue_count"] = silver_rows
    report["repositories"] = repositories
    return require_pass(report)


def check_gold_layer(
    settings: dict[str, Any],
    silver_report: dict[str, Any],
) -> dict[str, Any]:
    repositories = silver_report["repositories"]
    with psycopg.connect(**load_bronze_to_rds.database_options(settings)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM public.github_issues_clean AS issue
                WHERE issue.repository = ANY(%s)
                  AND (
                      NULLIF(BTRIM(issue.body), '') IS NOT NULL
                      OR NULLIF(BTRIM(issue.resolution_text), '') IS NOT NULL
                      OR EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements(issue.comments) AS item
                          WHERE NULLIF(BTRIM(item->>'body'), '') IS NOT NULL
                      )
                  )
                """,
                (repositories,),
            )
            chunkable_issues = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT COUNT(*),
                       COUNT(DISTINCT (chunks.repository, chunks.issue_number)),
                       COUNT(*) FILTER (WHERE chunks.embedding IS NULL),
                       COUNT(*) FILTER (
                           WHERE chunks.embedding IS NOT NULL
                             AND vector_dims(chunks.embedding) <> %s
                       ),
                       COUNT(*) FILTER (WHERE issue.repository IS NULL)
                FROM public.github_issue_chunks AS chunks
                LEFT JOIN public.github_issues_clean AS issue
                  ON issue.repository = chunks.repository
                 AND issue.issue_number = chunks.issue_number
                WHERE chunks.repository = ANY(%s)
                """,
                (EXPECTED_VECTOR_DIMENSIONS, repositories),
            )
            (
                chunk_rows,
                gold_issue_count,
                missing_embeddings,
                wrong_dimensions,
                orphan_chunks,
            ) = cursor.fetchone()

    expected_content_drops = (
        silver_report["silver_issue_count"] - chunkable_issues
    )
    hard_failures = []
    if gold_issue_count != chunkable_issues:
        hard_failures.append(
            "Gold issue coverage does not match Silver chunkable issues: "
            f"{gold_issue_count} != {chunkable_issues}"
        )
    if missing_embeddings:
        hard_failures.append(f"{missing_embeddings} Gold chunk(s) lack embeddings")
    if wrong_dimensions:
        hard_failures.append(
            f"{wrong_dimensions} Gold embedding(s) are not "
            f"{EXPECTED_VECTOR_DIMENSIONS}-dimensional"
        )
    if orphan_chunks:
        hard_failures.append(f"{orphan_chunks} Gold chunk(s) have no Silver issue")
    warnings = []
    if expected_content_drops:
        warnings.append(
            f"{expected_content_drops} Silver issue(s) have no chunkable body, "
            "comment, or resolution and are expected not to appear in Gold"
        )

    return require_pass(
        quality_report(
            "gold",
            {
                "silver_rows": silver_report["silver_issue_count"],
                "silver_chunkable_issues": chunkable_issues,
                "expected_no_content_drops": expected_content_drops,
                "gold_issues_with_chunks": gold_issue_count,
                "gold_chunks": chunk_rows,
                "chunks_without_embeddings": missing_embeddings,
                "embeddings_with_wrong_dimensions": wrong_dimensions,
                "orphan_chunks": orphan_chunks,
                "embedding_dimensions": EXPECTED_VECTOR_DIMENSIONS,
            },
            hard_failures,
            warnings,
        )
    )


def run_quality_checks() -> dict[str, Any]:
    settings = load_bronze_to_rds.required_environment()
    client = load_bronze_to_rds.create_s3_client(settings)
    bronze = check_bronze_layer(client, settings["S3_BUCKET"])
    silver = check_silver_layer(settings, bronze)
    gold = check_gold_layer(settings, silver)
    return {
        "passed": True,
        "layers": [bronze, silver, gold],
    }


def main() -> None:
    try:
        report = run_quality_checks()
    except (DataQualityError, psycopg.Error, ValueError, RuntimeError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2))
        raise SystemExit(1) from exc
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
