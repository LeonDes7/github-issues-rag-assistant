import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from rag_assistant.demo_guard import reserve_question

class DemoGuardTests(unittest.TestCase):
    def test_session_limit(self):
        with tempfile.TemporaryDirectory() as d:
            state = {}; path = Path(d)/"quota.db"
            for _ in range(5): self.assertIsNone(reserve_question(state,path,"2026-10-08"))
            self.assertIn("session",reserve_question(state,path,"2026-10-08"))
            self.assertEqual(state["demo_questions"],5)

    def test_daily_limit_across_sessions_and_day_reset(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"quota.db"
            for _ in range(50): self.assertIsNone(reserve_question({},path,"2026-10-08"))
            self.assertIn("Today",reserve_question({},path,"2026-10-08"))
            self.assertIsNone(reserve_question({},path,"2026-10-09"))

    def test_concurrent_reservations_do_not_exceed_daily_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"quota.db"
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes=list(pool.map(lambda _:reserve_question({},path,"2026-10-08"),range(60)))
            self.assertEqual(outcomes.count(None),50)
