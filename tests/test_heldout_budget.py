"""Budget and fixed-boundary checks without paid API calls."""
import importlib.util
from pathlib import Path
import unittest
from rag_assistant import api

spec = importlib.util.spec_from_file_location("heldout_run", Path(__file__).resolve().parents[1] / "scripts/run_heldout_unanswerables.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class HeldoutBudgetTests(unittest.TestCase):
    def test_call_is_blocked_before_exceeding_cap(self):
        self.assertTrue(runner.allowed_call(0.01, 0.01, 0.02))
        self.assertFalse(runner.allowed_call(0.01, 0.010001, 0.02))

    def test_exact_requested_cutoff_boundary(self):
        self.assertEqual(runner.CUTOFF, 0.537)
        self.assertFalse(api.should_refuse([{"retrieval_score": 0.537}], runner.CUTOFF))
        self.assertTrue(api.should_refuse([{"retrieval_score": 0.536999}], runner.CUTOFF))
