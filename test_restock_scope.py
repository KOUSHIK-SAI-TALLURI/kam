import unittest

from data import OUT_OF_STOCK
from tools import KamSession


class RestockScopeTests(unittest.TestCase):
    def setUp(self):
        self.kam = KamSession()

    def test_default_stock_lookup_returns_all_products(self):
        result = self.kam.call("get_out_of_stock_products")
        self.assertEqual(result["total_out_of_stock"], 18)
        self.assertEqual(len(result["top_products"]), 18)
        self.assertEqual(result["selection_scope"], "all")

    def test_explicit_top_five_lookup_returns_five(self):
        result = self.kam.call("get_out_of_stock_products", {"top_n": 5})
        self.assertEqual(result["total_out_of_stock"], 18)
        self.assertEqual(len(result["top_products"]), 5)
        self.assertEqual(result["selection_scope"], "top_n")

    def test_data_has_unique_skus(self):
        skus = [item["sku"] for item in OUT_OF_STOCK]
        self.assertEqual(len(skus), 18)
        self.assertEqual(len(set(skus)), 18)

    def test_restock_handler_records_all_18_verified_skus(self):
        skus = [item["sku"] for item in OUT_OF_STOCK]
        result = self.kam.call(
            "create_restock_task",
            {"skus": skus, "priority": "high", "scope": "all"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["task"]["product_count"], 18)
        self.assertEqual(len(result["task"]["skus"]), 18)

    def test_restock_handler_rejects_unknown_sku(self):
        with self.assertRaises(ValueError):
            self.kam.call(
                "create_restock_task",
                {"skus": ["NOT-A-REAL-SKU"], "priority": "high"},
            )


if __name__ == "__main__":
    unittest.main()
