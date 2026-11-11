
from data import (
    SELLER,
    LAST_MONTH,
    THIS_MONTH,
    OUT_OF_STOCK,
    CANCELLATION_REASONS,
)


def pct_change(old, new):
    return round((new - old) / old * 100, 1)


class KamSession:
    """Stores seller information and actions for one conversation."""

    def __init__(self):
        self.actions = []

    def call(self, name, args=None):
        args = args or {}

        handler = getattr(self, f"_{name}", None)

        if handler is None:
            return {"error": f"Unknown tool: {name}"}

        return handler(**args)

    # READ-ONLY TOOLS

    def _get_seller_metrics(self):
        lm = LAST_MONTH
        tm = THIS_MONTH

        gross_last = lm["orders"] / (1 - lm["cancellation_rate"] / 100)
        gross_this = tm["orders"] / (1 - tm["cancellation_rate"] / 100)

        demand_loss = (
            gross_last - gross_this
        ) * (1 - lm["cancellation_rate"] / 100)

        cancel_loss = (
            gross_this
            * (tm["cancellation_rate"] - lm["cancellation_rate"])
            / 100
        )

        total = lm["orders"] - tm["orders"]

        return {
            "seller": SELLER,
            "last_month": lm,
            "this_month": tm,
            "sales_change_pct": pct_change(
                lm["sales"], tm["sales"]
            ),
            "orders_change_pct": pct_change(
                lm["orders"], tm["orders"]
            ),
            "price_changed": (
                lm["avg_selling_price"]
                != tm["avg_selling_price"]
            ),
            "out_of_stock_change": (
                f'{lm["out_of_stock"]} to {tm["out_of_stock"]}'
            ),
            "drop_breakdown": {
                "total_orders_lost": total,
                "from_fewer_orders_placed": round(demand_loss),
                "from_extra_cancellations": round(cancel_loss),
                "share_from_fewer_orders_pct": round(
                    demand_loss / total * 100
                ),
                "share_from_cancellations_pct": round(
                    cancel_loss / total * 100
                ),
            },
        }

    def _get_out_of_stock_products(self, top_n=None):
        ranked = sorted(
            OUT_OF_STOCK,
            key=lambda p: p["lost_orders"],
            reverse=True,
        )

        if top_n is None:
            selected = ranked
        else:
            try:
                count = int(top_n)
            except (TypeError, ValueError):
                raise ValueError("top_n must be a whole number.") from None
            if count < 1 or count > len(ranked):
                raise ValueError(
                    f"top_n must be between 1 and {len(ranked)}."
                )
            selected = ranked[:count]

        total_lost = sum(p["lost_orders"] for p in OUT_OF_STOCK)
        selected_lost = sum(p["lost_orders"] for p in selected)

        return {
            "total_out_of_stock": len(OUT_OF_STOCK),
            # Keep the existing key for compatibility with the frontend.
            "top_products": selected,
            "returned_product_count": len(selected),
            "selection_scope": (
                "all" if len(selected) == len(OUT_OF_STOCK) else "top_n"
            ),
            "selected_share_of_estimated_lost_orders_pct": (
                round(selected_lost / total_lost * 100)
                if total_lost else 0
            ),
            "estimated_revenue_lost_selected": (
                selected_lost * THIS_MONTH["avg_selling_price"]
            ),
        }

    def _get_cancellation_breakdown(self):
        return {
            "rate_last_month_pct": LAST_MONTH["cancellation_rate"],
            "rate_this_month_pct": THIS_MONTH["cancellation_rate"],
            "reasons": CANCELLATION_REASONS,
            "data_type": "mock_assumptions",
        }

    # MOCK ACTION TOOLS

    def _log(self, kind, detail):
        item = {
            "id": f"{kind.upper()}-{len(self.actions) + 1:03d}",
            "type": kind,
            **detail,
        }

        self.actions.append(item)

        return item

    def _create_restock_task(self, skus, priority, scope=None):
        if not isinstance(skus, list) or not skus:
            raise ValueError("A restock task must contain at least one SKU.")

        valid_skus = {product["sku"] for product in OUT_OF_STOCK}
        clean_skus = list(dict.fromkeys(str(sku).strip() for sku in skus))

        unknown = [sku for sku in clean_skus if sku not in valid_skus]
        if unknown:
            raise ValueError(
                "Cannot record unknown SKU(s): " + ", ".join(unknown)
            )

        if len(clean_skus) > len(OUT_OF_STOCK):
            raise ValueError("Restock task exceeds the unavailable SKU count.")

        if priority not in {"low", "medium", "high"}:
            raise ValueError("Priority must be low, medium or high.")

        item = self._log(
            "restock",
            {
                "skus": clean_skus,
                "product_count": len(clean_skus),
                "scope": scope or ("all" if len(clean_skus) == len(OUT_OF_STOCK) else "selected"),
                "priority": priority,
                "status": "created",
            },
        )

        return {"ok": True, "task": item}

    def _send_whatsapp_summary(self, message):
        item = self._log(
            "whatsapp",
            {
                "message": message,
                "status": "queued (mock)",
            },
        )

        return {"ok": True, "sent": item}

    def _schedule_followup_call(self, days_from_now, purpose):
        item = self._log(
            "followup",
            {
                "days_from_now": days_from_now,
                "purpose": purpose,
                "status": "scheduled (mock)",
            },
        )

        return {"ok": True, "scheduled": item}
