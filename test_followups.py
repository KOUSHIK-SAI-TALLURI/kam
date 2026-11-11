import tempfile
import unittest
from pathlib import Path

import followups


class FollowupStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = followups.DB_PATH
        followups.DB_PATH = Path(self.temp_dir.name) / "test.sqlite3"

    def tearDown(self):
        followups.DB_PATH = self.original_db
        self.temp_dir.cleanup()

    def test_create_and_list_followup(self):
        baseline = {
            "this_month": {
                "sales": 135000,
                "orders": 270,
                "cancellation_rate": 14,
                "out_of_stock": 18,
                "avg_selling_price": 500,
            }
        }
        item = followups.create_followup(
            3, "Review stock and sales", baseline
        )
        self.assertEqual(item["status"], "scheduled")
        self.assertEqual(len(followups.list_followups()), 1)
        self.assertIn("+05:30", item["due_at"])

    def test_test_now_report_is_explicitly_simulated(self):
        baseline = {
            "this_month": {
                "sales": 135000,
                "orders": 270,
                "cancellation_rate": 14,
                "out_of_stock": 18,
            }
        }
        item = followups.create_followup(3, "Review recovery", baseline)
        completed = followups.complete_with_simulated_report(item["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(
            completed["report"]["data_mode"],
            "SIMULATED_DEMO_SCENARIO"
        )
        self.assertIn("not based on fresh", completed["report"]["disclaimer"])

if __name__ == "__main__":
    unittest.main()
