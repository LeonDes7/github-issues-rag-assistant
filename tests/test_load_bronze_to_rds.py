import io
import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from rag_assistant import load_bronze_to_rds as loader


def source_record(
    number=17,
    body="## Details\r\n\r\n```python\r\n    print('hello')\r\n```",
    closed_at="2026-01-03T00:00:00Z",
):
    return {
        "repository": loader.BRONZE_SOURCES[0][0],
        "bronze_prefix": loader.BRONZE_SOURCES[0][1],
        "source_line_number": number,
        "raw": {
            "issue": {
                "number": number,
                "title": "  Bug\t report ",
                "body": body,
                "html_url": f"https://github.com/fastapi/fastapi/issues/{number}",
                "labels": [{"name": "bug"}],
                "created_at": "2026-01-01T00:00:00Z",
                "closed_at": closed_at,
                "author_association": "CONTRIBUTOR",
                "user": {"login": "issue-author"},
            },
            "comments": [
                {
                    "id": 1,
                    "body": "First fix suggestion",
                    "created_at": "2026-01-02T00:00:00Z",
                    "author_association": "MEMBER",
                    "user": {"login": "member"},
                },
                {
                    "id": 2,
                    "body": "After closure",
                    "created_at": "2026-01-04T00:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner"},
                },
            ],
        },
    }


class BronzeRdsLoaderTests(unittest.TestCase):
    def test_clean_record_preserves_code_and_selects_preclosure_maintainer(self):
        cleaned = loader.clean_record(source_record())

        self.assertEqual(cleaned["title"], "Bug report")
        self.assertIn("    print('hello')", cleaned["body"])
        self.assertEqual(cleaned["labels"], ["bug"])
        self.assertEqual(cleaned["comment_count"], 2)
        self.assertEqual(cleaned["resolution_text"], "First fix suggestion")
        self.assertEqual(
            cleaned["resolution_heuristic"],
            "last_maintainer_comment_before_closure",
        )
        self.assertEqual(cleaned["resolution_confidence"], "low")
        self.assertIsInstance(cleaned["comments"][0]["created_at"], str)
        self.assertEqual(
            cleaned["content_hash"],
            loader.clean_record(source_record())["content_hash"],
        )

    def test_content_hash_changes_when_issue_content_changes(self):
        original = loader.clean_record(source_record())
        changed = loader.clean_record(
            source_record(body="A newly edited issue body.")
        )

        self.assertNotEqual(original["content_hash"], changed["content_hash"])

    def test_validation_rejects_duplicate_key_and_summarizes_gaps(self):
        sources = [
            source_record(number=21, body=""),
            source_record(number=21, body="duplicate"),
        ]
        counts = {
            repository: {
                "source_records": 0,
                "rejected_records": 0,
                "valid_records": 0,
                "duplicate_records": 0,
                "missing_bodies": 0,
                "missing_heuristic_resolutions": 0,
            }
            for repository, _ in loader.BRONZE_SOURCES
        }
        counts[loader.BRONZE_SOURCES[0][0]]["source_records"] = 2

        cleaned, summary = loader.validate_and_clean(sources, counts)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(summary["rejected_records"], 1)
        self.assertEqual(summary["duplicate_records"], 1)
        self.assertEqual(summary["missing_bodies"], 1)
        self.assertEqual(summary["missing_heuristic_resolutions"], 0)
        self.assertEqual(counts[loader.BRONZE_SOURCES[0][0]]["valid_records"], 1)

    def test_no_resolution_when_closed_date_is_missing(self):
        cleaned = loader.clean_record(source_record(closed_at=None))

        self.assertIsNone(cleaned["resolution_text"])
        self.assertEqual(
            cleaned["resolution_heuristic"],
            "unavailable_missing_closed_at",
        )
        self.assertEqual(cleaned["resolution_confidence"], "none")

    def test_rejects_missing_issue_number_or_github_url(self):
        missing_number = source_record(number=31)
        del missing_number["raw"]["issue"]["number"]
        missing_url = source_record(number=32)
        del missing_url["raw"]["issue"]["html_url"]

        with self.assertRaisesRegex(ValueError, "issue number is required"):
            loader.clean_record(missing_number)
        with self.assertRaisesRegex(ValueError, "valid GitHub issue URL"):
            loader.clean_record(missing_url)

    def test_reads_only_the_three_configured_bronze_objects(self):
        client = Mock()
        content = (json.dumps({"issue": {}, "comments": []}) + "\n").encode()
        client.get_object.side_effect = lambda **_: {"Body": io.BytesIO(content)}

        records, counts, rejected = loader.read_bronze_records(
            client,
            "example-bucket",
        )

        self.assertEqual(client.get_object.call_count, 3)
        self.assertEqual(
            [call.kwargs["Key"] for call in client.get_object.call_args_list],
            [prefix + "issues.jsonl" for _, prefix in loader.BRONZE_SOURCES],
        )
        self.assertEqual(len(records), 3)
        self.assertEqual(rejected, 0)
        self.assertEqual(
            sum(count["source_records"] for count in counts.values()),
            3,
        )

    def test_upsert_uses_unique_key_and_reports_insert_update_totals(self):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.side_effect = [(True,), (False,), (8,)]
        settings = {
            "PGHOST": "host",
            "PGPORT": 5432,
            "PGDATABASE": "database",
            "PGUSER": "user",
            "PGPASSWORD": "password",
            "PGSSLMODE": "require",
        }

        with patch.object(loader.psycopg, "connect") as connect:
            connect.return_value.__enter__.return_value = connection
            inserted, updated, total_rows = loader.upsert_records(
                [
                    loader.clean_record(source_record(1)),
                    loader.clean_record(source_record(2)),
                ],
                settings,
            )

        self.assertEqual((inserted, updated, total_rows), (1, 1, 8))
        executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("UNIQUE (repository, issue_number)", loader.CREATE_TABLE_SQL)
        self.assertTrue(
            any("ON CONFLICT (repository, issue_number)" in sql for sql in executed_sql)
        )
        self.assertIn("IS DISTINCT FROM", loader.UPSERT_SQL)


if __name__ == "__main__":
    unittest.main()
