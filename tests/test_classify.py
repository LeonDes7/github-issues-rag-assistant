import unittest
from unittest.mock import MagicMock

from rag_assistant import classify


class ClassificationTests(unittest.TestCase):
    def test_heuristic_identifies_clear_categories(self):
        self.assertEqual(
            classify.heuristic_classify(
                "Bug: request fails with a RuntimeError",
                "An exception is raised.",
            )["label"],
            "bug",
        )
        self.assertEqual(
            classify.heuristic_classify(
                "[FeatureRequest] configure request.stream chunk size",
                "Please allow callers to set this.",
            )["label"],
            "feature",
        )
        self.assertEqual(
            classify.heuristic_classify(
                "Question about required nullable parameter",
                "How should this be declared?",
            )["label"],
            "usage",
        )

    def test_heuristic_returns_unknown_for_empty_or_ambiguous_input(self):
        self.assertEqual(classify.heuristic_classify(None, None)["label"], "unknown")
        result = classify.heuristic_classify(
            "Middleware",
            "The behavior is mentioned without a clear explanation.",
        )
        self.assertEqual(result["label"], "unknown")
        self.assertEqual(result["confidence"], "low")

    def test_llm_classifier_validates_structured_output(self):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"label":"feature","confidence":"high","rationale":"A feature is requested."}'
                )
            )
        ]

        result = classify.llm_classify(
            client,
            "configured-model",
            "Support a new option",
            "Allow configuring the setting.",
        )

        self.assertEqual(result["label"], "feature")
        self.assertEqual(result["confidence"], "high")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "configured-model")
        self.assertEqual(request["response_format"], {"type": "json_object"})

    def test_llm_classifier_rejects_unknown_schema_values(self):
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"label":"question","confidence":"certain","rationale":"x"}'
                )
            )
        ]

        with self.assertRaisesRegex(ValueError, "invalid labels"):
            classify.llm_classify(client, "model", "Title", "Body")

    def test_metrics_reports_accuracy_macro_f1_and_confusion_matrix(self):
        metrics = classify.classification_metrics(
            ["bug", "feature", "usage", "usage"],
            ["bug", "bug", "usage", "unknown"],
        )

        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["per_label"]["bug"]["precision"], 0.5)
        self.assertEqual(metrics["per_label"]["bug"]["recall"], 1.0)
        self.assertEqual(
            metrics["confusion_matrix_actual_rows_predicted_columns"]["usage"][
                "unknown"
            ],
            1,
        )
        self.assertGreaterEqual(metrics["macro_f1_present_classes"], 0)

    def test_heldout_cases_are_balanced_and_manually_reviewed(self):
        cases = classify.load_classification_cases()

        labels = [case["expected_label"] for case in cases]
        self.assertEqual(len(cases), 12)
        self.assertEqual(labels.count("bug"), 4)
        self.assertEqual(labels.count("feature"), 4)
        self.assertEqual(labels.count("usage"), 4)
        self.assertTrue(
            all(case["verification_status"] == "manually_verified" for case in cases)
        )


if __name__ == "__main__":
    unittest.main()
