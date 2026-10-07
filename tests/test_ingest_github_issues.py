from unittest.mock import Mock, patch
import unittest

from rag_assistant import ingest_github_issues as ingestion


class GithubIssueIngestionTests(unittest.TestCase):
    def test_collects_across_pages_until_target_and_preserves_payload(self):
        first_issue = {
            "number": 10,
            "comments": 1,
            "comments_url": "https://api.github.com/issue/10/comments",
            "body": "raw first issue body",
        }
        second_issue = {
            "number": 11,
            "comments": 2,
            "comments_url": "https://api.github.com/issue/11/comments",
            "body": "raw second issue body",
        }
        first_comment = {"id": 99, "body": "raw first comment"}
        second_comments = [
            {"id": 100, "body": "raw second comment"},
            {"id": 101, "body": "raw third comment"},
        ]
        pages = [
            (
                [
                    {"number": 1, "pull_request": {}, "comments": 2},
                    first_issue,
                ],
                "https://api.github.com/page/2",
            ),
            ([first_comment], None),
            ([second_issue], "https://api.github.com/page/3"),
            (second_comments[:1], "https://api.github.com/issue/11/comments?page=2"),
            (second_comments[1:], None),
        ]

        with patch.object(ingestion, "get_json", side_effect=pages) as get_json:
            records, counts = ingestion.collect_closed_issues(
                Mock(),
                "fastapi/fastapi",
                target_records=2,
                max_entries_to_scan=10,
            )

        self.assertEqual(
            records,
            [
                {"issue": first_issue, "comments": [first_comment]},
                {"issue": second_issue, "comments": second_comments},
            ],
        )
        self.assertEqual(
            counts,
            {
                "issues_seen": 3,
                "pull_requests_skipped": 1,
                "resumed_issues": 0,
                "records_uploaded": 2,
                "comments_uploaded": 3,
                "max_updated_at": None,
            },
        )
        self.assertEqual(get_json.call_count, 5)

    def test_scan_limit_includes_issues_without_comments(self):
        issue_page = [
            {"number": 1, "pull_request": {}, "comments": 1},
            {
                "number": 2,
                "comments": 0,
                "comments_url": "https://api.github.com/issue/2/comments",
            },
            {
                "number": 3,
                "comments": 1,
                "comments_url": "https://api.github.com/issue/3/comments",
            },
        ]
        with patch.object(
            ingestion,
            "get_json",
            side_effect=[
                (issue_page, "https://api.github.com/page/2"),
                ([], None),
            ],
        ) as get_json:
            records, counts = ingestion.collect_closed_issues(
                Mock(),
                "fastapi/fastapi",
                target_records=2,
                max_entries_to_scan=2,
            )

        self.assertEqual(
            records,
            [{"issue": issue_page[1], "comments": []}],
        )
        self.assertEqual(
            counts,
            {
                "issues_seen": 2,
                "pull_requests_skipped": 1,
                "resumed_issues": 0,
                "records_uploaded": 1,
                "comments_uploaded": 0,
                "max_updated_at": None,
            },
        )
        self.assertEqual(get_json.call_count, 2)

    def test_resumed_issue_skips_comment_requests(self):
        issue = {
            "number": 10,
            "comments": 1,
            "comments_url": "https://api.github.com/issue/10/comments",
            "updated_at": "2026-04-01T12:00:00Z",
        }
        with patch.object(
            ingestion,
            "get_json",
            return_value=([issue], None),
        ) as get_json:
            records, counts = ingestion.collect_closed_issues(
                Mock(),
                "fastapi/fastapi",
                issue_exists=lambda issue_number: issue_number == 10,
            )

        self.assertEqual(records, [])
        self.assertEqual(counts["resumed_issues"], 1)
        self.assertEqual(counts["max_updated_at"], "2026-04-01T12:00:00Z")
        get_json.assert_called_once()

    def test_since_is_passed_to_github_issue_listing(self):
        issue = {
            "number": 12,
            "comments": 0,
            "comments_url": "https://api.github.com/issue/12/comments",
        }
        with patch.object(
            ingestion,
            "get_json",
            side_effect=[([issue], None), ([], None)],
        ) as get_json:
            ingestion.collect_closed_issues(
                Mock(),
                "fastapi/fastapi",
                since="2026-04-01T12:00:00Z",
            )

        self.assertEqual(
            get_json.call_args_list[0].kwargs["params"],
            {
                "state": "closed",
                "per_page": 100,
                "page": 1,
                "since": "2026-04-01T12:00:00Z",
            },
        )

    def test_get_json_retries_primary_rate_limit(self):
        limited_response = Mock()
        limited_response.status_code = 403
        limited_response.headers = {"X-RateLimit-Remaining": "0"}
        limited_response.links = {}
        limited_response.json.return_value = []
        success_response = Mock()
        success_response.status_code = 200
        success_response.headers = {}
        success_response.links = {}
        success_response.json.return_value = [{"number": 1}]

        session = Mock()
        session.get.side_effect = [limited_response, success_response]

        with patch.object(ingestion, "retry_delay", return_value=0), patch.object(
            ingestion.time, "sleep"
        ) as sleep:
            data, next_link = ingestion.get_json(
                session,
                "https://api.github.com/issues",
            )

        self.assertEqual(data, [{"number": 1}])
        self.assertIsNone(next_link)
        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
