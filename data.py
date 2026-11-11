
# Mock seller data for the Snapdeal Virtual KAM.
# SKU-level and cancellation-reason data are assumptions,
# not actual Snapdeal seller records.

SELLER = {
    "seller_id": "SD-48213",
    "name": "Rajesh",
    "store_name": "Rajesh Traders",
    "category": "Fashion & Accessories",
}

LAST_MONTH = {
    "sales": 200000,
    "orders": 400,
    "cancellation_rate": 8,
    "avg_selling_price": 500,
    "out_of_stock": 5,
}

THIS_MONTH = {
    "sales": 135000,
    "orders": 270,
    "cancellation_rate": 14,
    "avg_selling_price": 500,
    "out_of_stock": 18,
}

# Assumption: SKU-level lost orders are estimates.
OUT_OF_STOCK = [
    {"sku": "KRT-BLU-101", "name": "Cotton Kurti Set (Blue)", "days_out": 19, "last_month_orders": 52, "lost_orders": 28},
    {"sku": "EAR-BT-220", "name": "Bluetooth Earbuds", "days_out": 21, "last_month_orders": 38, "lost_orders": 23},
    {"sku": "SHO-RUN-305", "name": "Men's Running Shoes", "days_out": 16, "last_month_orders": 41, "lost_orders": 19},
    {"sku": "BTL-STL-410", "name": "Steel Water Bottle 1L", "days_out": 14, "last_month_orders": 30, "lost_orders": 12},
    {"sku": "BAG-WMN-512", "name": "Women's Handbag", "days_out": 12, "last_month_orders": 27, "lost_orders": 9},
    {"sku": "CSE-PH-618", "name": "Phone Case Pack (3)", "days_out": 10, "last_month_orders": 25, "lost_orders": 7},
    {"sku": "TSH-MEN-701", "name": "Men's Round Neck T-shirt", "days_out": 9, "last_month_orders": 8, "lost_orders": 2},
    {"sku": "SCF-WMN-702", "name": "Women's Printed Scarf", "days_out": 8, "last_month_orders": 7, "lost_orders": 2},
    {"sku": "WLT-MEN-703", "name": "Men's Leather Wallet", "days_out": 8, "last_month_orders": 7, "lost_orders": 1},
    {"sku": "CBL-USB-704", "name": "USB Charging Cable", "days_out": 7, "last_month_orders": 6, "lost_orders": 1},
    {"sku": "CAP-UNI-705", "name": "Unisex Baseball Cap", "days_out": 7, "last_month_orders": 6, "lost_orders": 1},
    {"sku": "SOC-MEN-706", "name": "Men's Socks (5 pair)", "days_out": 6, "last_month_orders": 5, "lost_orders": 1},
    {"sku": "BLT-MEN-707", "name": "Men's Belt", "days_out": 6, "last_month_orders": 5, "lost_orders": 1},
    {"sku": "HDB-WMN-708", "name": "Women's Hair Band Set", "days_out": 5, "last_month_orders": 4, "lost_orders": 1},
    {"sku": "KEY-UNI-709", "name": "Keychain Combo", "days_out": 5, "last_month_orders": 4, "lost_orders": 0},
    {"sku": "STR-WMN-710", "name": "Women's Stole", "days_out": 4, "last_month_orders": 4, "lost_orders": 0},
    {"sku": "SUN-UNI-711", "name": "Sunglasses", "days_out": 4, "last_month_orders": 3, "lost_orders": 0},
    {"sku": "PUR-WMN-712", "name": "Mini Purse", "days_out": 3, "last_month_orders": 3, "lost_orders": 0},
]

# Assumed cancellation reason distribution.
CANCELLATION_REASONS = [
    {"reason": "Seller could not fulfil (stock unavailable)", "share": 58},
    {"reason": "Delayed dispatch / missed courier handover", "share": 17},
    {"reason": "Customer changed mind", "share": 15},
    {"reason": "Address or delivery issue", "share": 10},
]
