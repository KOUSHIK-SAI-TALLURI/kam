"""
Persistent follow-up tracking for the Snapdeal Virtual KAM demo.

SQLite stores approved follow-up requests and their baseline metrics.
The "Test Follow-up Now" workflow uses clearly labelled simulated
follow-up metrics; it does not claim to retrieve live Snapdeal data.
"""

import json
import sqlite3
from contextlib import closing
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "kam_followups.db"
IST = timezone(timedelta(hours=5, minutes=30))


def _now():
    return datetime.now(IST)


def _connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with closing(_connect()) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS followups (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                days_from_now INTEGER NOT NULL,
                purpose TEXT NOT NULL,
                status TEXT NOT NULL,
                baseline_json TEXT NOT NULL,
                report_json TEXT
            )
        """)
        connection.commit()


def create_followup(days_from_now, purpose, baseline):
    init_db()
    now = _now()
    due = now + timedelta(days=int(days_from_now))
    record_id = "FU-" + uuid.uuid4().hex[:10].upper()

    with closing(_connect()) as connection:
        connection.execute("""
            INSERT INTO followups
            (id, created_at, due_at, days_from_now, purpose,
             status, baseline_json, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        """, (
            record_id,
            now.isoformat(),
            due.isoformat(),
            int(days_from_now),
            str(purpose),
            "scheduled",
            json.dumps(baseline)
        ))
        connection.commit()

    return get_followup(record_id)


def get_followup(record_id):
    init_db()
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT * FROM followups WHERE id = ?",
            (record_id,)
        ).fetchone()

    return _serialise(row) if row else None


def list_followups():
    init_db()
    with closing(_connect()) as connection:
        rows = connection.execute(
            "SELECT * FROM followups ORDER BY created_at DESC"
        ).fetchall()

    return [_serialise(row) for row in rows]


def _serialise(row):
    if row is None:
        return None

    item = dict(row)
    item["baseline"] = json.loads(item.pop("baseline_json"))
    report = item.pop("report_json")
    item["report"] = json.loads(report) if report else None
    return item


def mark_due_followups():
    """Mark scheduled follow-ups as due. Does not fabricate new metrics."""
    init_db()
    now = _now().isoformat()

    with closing(_connect()) as connection:
        cursor = connection.execute("""
            UPDATE followups
            SET status = 'due'
            WHERE status = 'scheduled' AND due_at <= ?
        """, (now,))
        connection.commit()
        updated_count = cursor.rowcount

    return updated_count


def build_simulated_report(record):
    """
    Produce a deterministic demo-only recovery scenario relative to
    the saved baseline. These are simulated values, not live metrics.
    """
    baseline = record["baseline"]
    current = baseline.get("this_month", {})

    base_sales = float(current.get("sales", 0))
    base_orders = int(current.get("orders", 0))
    base_cancel = float(current.get("cancellation_rate", 0))
    base_oos = int(current.get("out_of_stock", 0))

    simulated = {
        "sales": round(base_sales * 1.10),
        "orders": round(base_orders * 1.08),
        "cancellation_rate": max(0, round(base_cancel - 3, 1)),
        "out_of_stock": max(0, base_oos - 8),
        "avg_selling_price": current.get("avg_selling_price")
    }

    def pct(old, new):
        if not old:
            return None
        return round((new - old) / old * 100, 1)

    report = {
        "generated_at": _now().isoformat(),
        "data_mode": "SIMULATED_DEMO_SCENARIO",
        "disclaimer": (
            "This report uses simulated recovery values for demonstration. "
            "It is not based on fresh Snapdeal or seller transaction data."
        ),
        "baseline": current,
        "followup_metrics": simulated,
        "changes": {
            "sales_pct": pct(base_sales, simulated["sales"]),
            "orders_pct": pct(base_orders, simulated["orders"]),
            "cancellation_percentage_points": round(
                simulated["cancellation_rate"] - base_cancel, 1
            ),
            "out_of_stock_change": simulated["out_of_stock"] - base_oos
        },
        "findings": [
            f"Simulated sales changed from ₹{base_sales:,.0f} "
            f"to ₹{simulated['sales']:,.0f}.",
            f"Simulated orders changed from {base_orders} "
            f"to {simulated['orders']}.",
            f"Cancellation rate changed from {base_cancel}% "
            f"to {simulated['cancellation_rate']}%.",
            f"Out-of-stock products changed from {base_oos} "
            f"to {simulated['out_of_stock']}."
        ],
        "recommendations": [
            "Continue monitoring availability of the highest-priority SKUs.",
            "Review cancellation reasons again using verified order-level data.",
            "Compare another reporting period before concluding that recovery is sustained."
        ]
    }

    return report


def complete_with_simulated_report(record_id):
    record = get_followup(record_id)
    if not record:
        raise ValueError("Follow-up record was not found.")

    if record["status"] == "completed" and record["report"]:
        return record

    report = build_simulated_report(record)

    with closing(_connect()) as connection:
        connection.execute("""
            UPDATE followups
            SET status = 'completed', report_json = ?
            WHERE id = ?
        """, (json.dumps(report), record_id))
        connection.commit()

    return get_followup(record_id)


def scheduler_tick():
    """Small scheduler hook: marks due items without inventing live data."""
    return mark_due_followups()
