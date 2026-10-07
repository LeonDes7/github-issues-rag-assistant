import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from rag_assistant import evaluate
from scripts import build_evaluation_set


class EvaluationSetBuilderTests(unittest.TestCase):
    def test_builds_runner_compatible_cases_and_review_csv(self):
        issue = {
            "repository": "encode/starlette",
            "issue_number": 4321,
            "title": "Unexpected middleware order",
            "body": "Middleware is initialized in an unexpected order.",
            "comments": [{"body": "The stack order is reversed."}],
            "github_url": "https://github.com/encode/starlette/issues/4321",
        }
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {"question": "Why is the middleware initialized backwards?"}
                    )
                )
            )
        ]

        cases = build_evaluation_set.build_cases([issue], client, "test-model")

        self.assertEqual(len(cases), 16)
        self.assertEqual(
            cases[0]["gold_issue_id"],
            {"repository": "encode/starlette", "issue_number": 4321},
        )
        self.assertEqual(sum(case["expected_abstain"] for case in cases), 15)
        with tempfile.TemporaryDirectory() as directory:
            jsonl_path = Path(directory) / "cases.jsonl"
            csv_path = Path(directory) / "review.csv"
            build_evaluation_set.write_cases(cases, jsonl_path, csv_path)

            self.assertEqual(len(evaluate.load_cases(jsonl_path)), 16)
            csv_text = csv_path.read_text(encoding="utf-8-sig")
            self.assertIn("gold_issue_number", csv_text)
            self.assertIn("4321", csv_text)


if __name__ == "__main__":
    unittest.main()
