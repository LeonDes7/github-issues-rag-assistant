import unittest
from pathlib import Path

from rag_assistant import evaluate


def retrieved(repository, issue_number, issue_url=None):
    return {
        "repository": repository,
        "issue_number": issue_number,
        "issue_url": issue_url
        or f"https://github.com/{repository}/issues/{issue_number}",
    }


class EvaluationTests(unittest.TestCase):
    def test_initial_cases_are_small_and_provenance_labeled(self):
        cases = evaluate.load_cases(Path("evaluation_cases.jsonl"))

        self.assertEqual(len(cases), 10)
        self.assertEqual(
            {case["verification_status"] for case in cases},
            {"manually_verified", "heuristic", "unresolved"},
        )
        self.assertTrue(
            all(
                case["expected_abstain"]
                for case in cases
                if case["verification_status"] == "unresolved"
            )
        )

    def test_retrieval_metric_matches_repository_issue_or_url(self):
        case = {
            "expected_issues": [
                {"repository": "fastapi/fastapi", "issue_number": 16160}
            ],
            "expected_issue_urls": [
                "https://github.com/fastapi/fastapi/issues/16160"
            ],
        }
        metrics = evaluate.retrieval_case_metrics(
            case,
            [
                retrieved("encode/starlette", 2845),
                retrieved("fastapi/fastapi", 16160),
            ],
        )

        self.assertEqual(metrics["hit_at_k"], 1)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["mrr"], 0.5)

    def test_retrieval_metric_matches_expected_issue_url(self):
        url = "https://github.com/Kludex/starlette/issues/3048"
        case = {
            "expected_issues": [],
            "expected_issue_urls": [url],
        }

        metrics = evaluate.retrieval_case_metrics(
            case,
            [
                retrieved(
                    "encode/starlette",
                    3048,
                    "https://github.com/Kludex/starlette/issues/3048",
                )
            ],
        )

        self.assertEqual(metrics["hit_at_k"], 1)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["mrr"], 1.0)

    def test_unresolved_case_abstention_is_appropriate(self):
        case = {
            "expected_abstain": True,
        }
        retrieval_metrics = {
            "applicable": False,
            "hit_at_k": None,
        }

        metrics = evaluate.generation_case_metrics(
            case,
            "The retrieved evidence is insufficient to answer.",
            [],
            retrieval_metrics,
        )

        self.assertTrue(metrics["abstained"])
        self.assertTrue(metrics["abstained_appropriately"])
        self.assertTrue(metrics["citations_valid"])
        self.assertTrue(metrics["grounded_in_retrieved_chunks"])

    def test_generation_flags_uncited_or_unsupported_claim(self):
        case = {"expected_abstain": False}
        retrieval_metrics = {"applicable": True, "hit_at_k": 1}
        retrieved_chunks = [
            {
                "chunk_text": (
                    "Repository: fastapi/fastapi Issue #1 Title: Middleware. "
                    "Use app.add_middleware(MyMiddleware)."
                )
            }
        ]

        uncited = evaluate.generation_case_metrics(
            case,
            "Configure the server with an unrelated option.",
            retrieved_chunks,
            retrieval_metrics,
        )
        supported = evaluate.generation_case_metrics(
            case,
            "Use app.add_middleware(MyMiddleware). [1]",
            retrieved_chunks,
            retrieval_metrics,
        )

        self.assertFalse(uncited["citations_valid"])
        self.assertFalse(uncited["grounded_in_retrieved_chunks"])
        self.assertTrue(supported["citations_valid"])
        self.assertTrue(supported["grounded_in_retrieved_chunks"])

    def test_markdown_pull_request_number_is_not_a_citation(self):
        case = {"expected_abstain": False}
        retrieval_metrics = {"applicable": True, "hit_at_k": 1}
        retrieved_chunks = [
            {
                "chunk_text": (
                    "The middleware resolution recommends "
                    "https://github.com/encode/starlette/pull/2017."
                )
            },
            {"chunk_text": "The change will be included in version 0.24.0."},
        ]
        answer = (
            "The resolution points to PR [2017]"
            "(https://github.com/encode/starlette/pull/2017) [1]."
        )

        metrics = evaluate.generation_case_metrics(
            case,
            answer,
            retrieved_chunks,
            retrieval_metrics,
        )

        self.assertEqual(metrics["citation_references"], [1])
        self.assertTrue(metrics["citations_valid"])

    def test_heuristic_metrics_are_separate_from_verified_retrieval(self):
        results = [
            {
                "verification_status": "manually_verified",
                "retrieval_metrics": {
                    "applicable": True,
                    "hit_at_k": 1,
                    "recall_at_k": 1.0,
                    "mrr": 1.0,
                },
                "generation_metrics": {
                    "abstained_appropriately": True,
                    "citations_valid": True,
                    "grounded_in_retrieved_chunks": True,
                },
            },
            {
                "verification_status": "heuristic",
                "retrieval_metrics": {
                    "applicable": True,
                    "hit_at_k": 0,
                    "recall_at_k": 0.0,
                    "mrr": 0.0,
                },
                "generation_metrics": {
                    "abstained_appropriately": False,
                    "citations_valid": True,
                    "grounded_in_retrieved_chunks": True,
                },
            },
        ]

        metrics = evaluate.summarize_metrics(results)

        self.assertEqual(
            metrics["retrieval_manual_verified_only"]["hit_at_k"],
            1.0,
        )
        self.assertEqual(
            metrics["retrieval_by_verification_status"]["heuristic"]["hit_at_k"],
            0.0,
        )
        self.assertIn("not ground-truth", metrics["heuristic_case_note"])

    def test_summary_includes_full_set_and_per_repository_retrieval_metrics(self):
        results = [
            {
                "verification_status": "manually_verified",
                "expected_issues": [
                    {"repository": "tiangolo/fastapi", "issue_number": 1}
                ],
                "retrieval_metrics": {
                    "applicable": True,
                    "hit_at_k": 1,
                    "recall_at_k": 1.0,
                    "mrr": 1.0,
                },
                "generation_metrics": {
                    "abstained_appropriately": True,
                    "citations_valid": True,
                    "grounded_in_retrieved_chunks": True,
                },
            },
            {
                "verification_status": "heuristic",
                "expected_issues": [
                    {"repository": "tiangolo/fastapi", "issue_number": 2}
                ],
                "retrieval_metrics": {
                    "applicable": True,
                    "hit_at_k": 0,
                    "recall_at_k": 0.0,
                    "mrr": 0.0,
                },
                "generation_metrics": {
                    "abstained_appropriately": True,
                    "citations_valid": True,
                    "grounded_in_retrieved_chunks": True,
                },
            },
        ]

        metrics = evaluate.summarize_metrics(results)

        self.assertEqual(
            metrics["retrieval_all_answerable_cases"]["scored_cases"],
            2,
        )
        self.assertEqual(
            metrics["retrieval_all_answerable_cases"]["hit_at_k"],
            0.5,
        )
        self.assertEqual(
            metrics["retrieval_by_repository"]["tiangolo/fastapi"]["mrr"],
            0.5,
        )

    def test_concise_report_includes_only_failed_cases(self):
        result = {
            "case_id": "miss",
            "verification_status": "manually_verified",
            "question": "question",
            "answer": "unsupported answer",
            "citations": [],
            "retrieval_metrics": {"applicable": True, "hit_at_k": 0},
            "generation_metrics": {
                "abstained_appropriately": False,
                "citations_valid": False,
                "grounded_in_retrieved_chunks": False,
            },
        }

        report = evaluate.concise_report([result], {"case_count": 1})

        self.assertEqual(len(report["failure_examples"]), 1)
        self.assertEqual(report["failure_examples"][0]["case_id"], "miss")


if __name__ == "__main__":
    unittest.main()
