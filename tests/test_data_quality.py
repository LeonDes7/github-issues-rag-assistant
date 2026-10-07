import unittest
from unittest.mock import MagicMock, patch

from rag_assistant import data_quality


class DataQualityTests(unittest.TestCase):
    def test_bronze_report_accounts_for_expected_dedupe_and_rejections(self):
        sources = [{"raw": {}}, {"raw": {}}, {"raw": {}}]
        counts = {"valid_records": 2}
        validation = {
            "source_records": 3,
            "valid_records": 2,
            "rejected_records": 1,
            "duplicate_records": 1,
        }
        with (
            patch.object(
                data_quality.load_bronze_to_rds,
                "read_bronze_records",
                return_value=(sources, {"encode/starlette": counts}, 0),
            ),
            patch.object(
                data_quality.load_bronze_to_rds,
                "validate_and_clean",
                return_value=(sources[:2], validation),
            ),
        ):
            report = data_quality.check_bronze_layer(MagicMock(), "bucket")

        self.assertTrue(report["passed"])
        self.assertEqual(report["counts"]["valid_unique_issues"], 2)
        self.assertEqual(report["counts"]["expected_deduplicated_or_rejected"], 1)
        self.assertIn("duplicate issue keys", report["warnings"][0])

    def test_silver_report_fails_on_null_key_columns(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(2, 1, 0, 4), (0,)]
        settings = {
            "PGHOST": "host",
            "PGPORT": 5432,
            "PGDATABASE": "database",
            "PGUSER": "user",
            "PGPASSWORD": "password",
            "PGSSLMODE": "require",
        }
        bronze = {"valid_issue_count": 2, "repositories": ["encode/starlette"]}
        with patch.object(data_quality.psycopg, "connect") as connect:
            connect.return_value.__enter__.return_value = connection
            with self.assertRaises(data_quality.DataQualityError):
                data_quality.check_silver_layer(settings, bronze)

    def test_gold_report_allows_only_explained_no_content_drops(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(2,), (5, 2, 0, 0, 0)]
        settings = {
            "PGHOST": "host",
            "PGPORT": 5432,
            "PGDATABASE": "database",
            "PGUSER": "user",
            "PGPASSWORD": "password",
            "PGSSLMODE": "require",
        }
        silver = {"silver_issue_count": 3, "repositories": ["encode/starlette"]}
        with patch.object(data_quality.psycopg, "connect") as connect:
            connect.return_value.__enter__.return_value = connection
            report = data_quality.check_gold_layer(settings, silver)

        self.assertTrue(report["passed"])
        self.assertEqual(report["counts"]["expected_no_content_drops"], 1)
        self.assertIn("no chunkable", report["warnings"][0])
        self.assertEqual(report["counts"]["embedding_dimensions"], 1536)


if __name__ == "__main__":
    unittest.main()
