import unittest

from scripts.calibrate_confidence import select_threshold
from scripts.measure_rag_performance import percentile


class MeasurementScriptTests(unittest.TestCase):
    def test_threshold_selection_reports_refusal_confusion_counts(self):
        result = select_threshold(
            [
                {"answerable": True, "score": 0.8},
                {"answerable": True, "score": 0.2},
                {"answerable": False, "score": 0.1},
                {"answerable": False, "score": 0.3},
            ]
        )

        self.assertAlmostEqual(result["recommended_threshold"], 0.15, places=6)
        self.assertEqual(result["correctly_refused"], 1)
        self.assertEqual(result["wrongly_refused"], 0)
        self.assertEqual(result["correctly_answered"], 2)
        self.assertEqual(result["missed_unanswerable"], 1)

    def test_percentile_interpolates_between_observations(self):
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.5), 2.5)
        self.assertAlmostEqual(percentile([1.0, 2.0, 3.0, 4.0], 0.95), 3.85)
        self.assertIsNone(percentile([], 0.95))


if __name__ == "__main__":
    unittest.main()
