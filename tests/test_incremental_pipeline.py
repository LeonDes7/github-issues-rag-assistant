import unittest
from unittest.mock import patch

from rag_assistant import incremental_pipeline


class MemoryCursor:
    def __init__(self, watermarks):
        self.watermarks = watermarks
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, parameters=None):
        if "SELECT repository, last_successful_updated_at" in query:
            repositories = parameters[0]
            self.rows = [
                (repository, value)
                for repository, value in self.watermarks.items()
                if repository in repositories
            ]
        elif "INSERT INTO public.github_ingestion_watermarks" in query:
            repository, updated_at = parameters
            self.watermarks[repository] = updated_at

    def fetchall(self):
        return self.rows


class MemoryConnection:
    def __init__(self, watermarks):
        self.watermarks = watermarks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self):
        return MemoryCursor(self.watermarks)

    def commit(self):
        pass


class IncrementalPipelineTests(unittest.TestCase):
    def test_second_run_uses_watermark_and_preserves_silver_row_count(self):
        repository = "encode/starlette"
        updated_at = "2026-04-02T10:30:00Z"
        watermarks = {}
        github_settings = {
            "GITHUB_REPOS": [repository],
            "TARGET_RECORDS_PER_REPO": None,
            "MAX_ENTRIES_TO_SCAN_PER_REPO": None,
        }
        database_settings = {
            "PGHOST": "host",
            "PGPORT": 5432,
            "PGDATABASE": "database",
            "PGUSER": "user",
            "PGPASSWORD": "password",
            "PGSSLMODE": "require",
        }
        ingest_calls = []

        def ingest(repo, target, maximum, settings, s3, since=None):
            ingest_calls.append(since)
            return {
                "repository": repo,
                "records_uploaded": 2 if since is None else 0,
                "comments_uploaded": 3 if since is None else 0,
                "max_updated_at": updated_at,
            }

        with (
            patch.object(incremental_pipeline, "load_runtime_secrets"),
            patch.object(
                incremental_pipeline.ingest_github_issues,
                "required_environment",
                return_value=github_settings,
            ),
            patch.object(
                incremental_pipeline.load_bronze_to_rds,
                "required_environment",
                return_value=database_settings,
            ),
            patch.object(
                incremental_pipeline.embed_issue_chunks,
                "required_environment",
            ),
            patch.object(
                incremental_pipeline.ingest_github_issues,
                "s3_client",
                return_value=object(),
            ),
            patch.object(
                incremental_pipeline.ingest_github_issues,
                "ingest_repository",
                side_effect=ingest,
            ),
            patch.object(
                incremental_pipeline.load_bronze_to_rds,
                "run_load",
                return_value={"total_rows_in_rds": 7},
            ),
            patch.object(
                incremental_pipeline.embed_issue_chunks,
                "run_embedding",
                return_value={"chunk_count": 9},
            ),
            patch.object(
                incremental_pipeline.psycopg,
                "connect",
                side_effect=lambda **_: MemoryConnection(watermarks),
            ),
        ):
            first = incremental_pipeline.run_pipeline()
            second = incremental_pipeline.run_pipeline()

        self.assertEqual(ingest_calls, [None, updated_at])
        self.assertEqual(first["silver"]["total_rows_in_rds"], 7)
        self.assertEqual(second["silver"]["total_rows_in_rds"], 7)
        self.assertEqual(first["totals"]["chunks"], 9)
        self.assertEqual(second["totals"]["chunks"], 9)
        self.assertEqual(watermarks[repository], updated_at)


if __name__ == "__main__":
    unittest.main()
