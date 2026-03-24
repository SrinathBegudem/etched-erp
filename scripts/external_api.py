"""
External Supplier API Simulation
=================================
Real-world supplier APIs are messy. Different vendors return the same data
in completely different formats — inconsistent field names, mixed types,
nested structures, missing fields.

This directly addresses the JD requirement:
"Ability to build custom integrations and connect systems where APIs are not well defined"
"""

import json
from datetime import datetime

MESSY_RESPONSES = [
    # Vendor A — cost as string with currency, quantity as string
    {"item_code": "WAFER-300MM", "cost": "148.50 USD", "qty": "500", "delivery_date": "2025-09-15", "vendor": "TSMC"},
    # Vendor B — nested structure, "amount" instead of "cost"
    {"product": {"sku": "WAFER-300MM"}, "pricing": {"amount": 151.0, "currency": "USD"}, "quantity": 500.0, "expected_by": "Sept 15 2025", "supplier_name": "GlobalFoundries"},
    # Vendor C — flat, unix timestamp for date
    {"sku": "WAFER-300MM", "unit_price": 149.99, "unit_count": 500, "deliver_by_ts": 1757894400, "from": "Samsung Foundry"},
]


def normalize_supplier_response(raw: dict) -> dict:
    def extract_cost(data):
        if "cost" in data:
            val = data["cost"]
            return float(val.split()[0]) if isinstance(val, str) else float(val)
        if "pricing" in data:
            return float(data["pricing"]["amount"])
        if "unit_price" in data:
            return float(data["unit_price"])
        return 0.0

    def extract_quantity(data):
        for key in ("qty", "quantity", "unit_count"):
            if key in data:
                return float(data[key])
        return 0.0

    def extract_sku(data):
        if "item_code" in data: return data["item_code"]
        if "sku" in data: return data["sku"]
        if "product" in data: return data["product"].get("sku", "UNKNOWN")
        return "UNKNOWN"

    def extract_supplier(data):
        for key in ("vendor", "supplier_name", "from"):
            if key in data: return data[key]
        return "UNKNOWN"

    def extract_delivery(data):
        if "delivery_date" in data: return data["delivery_date"]
        if "expected_by" in data:
            try: return datetime.strptime(data["expected_by"], "%b %d %Y").date().isoformat()
            except ValueError: return data["expected_by"]
        if "deliver_by_ts" in data:
            return datetime.utcfromtimestamp(data["deliver_by_ts"]).date().isoformat()
        return None

    cost, quantity = extract_cost(raw), extract_quantity(raw)
    normalized = {
        "sku": extract_sku(raw),
        "supplier": extract_supplier(raw),
        "unit_cost_usd": cost,
        "quantity": quantity,
        "total_cost_usd": round(cost * quantity, 2),
        "expected_delivery": extract_delivery(raw),
        "normalized_at": datetime.utcnow().isoformat(),
        "warnings": [],
    }
    if cost == 0.0: normalized["warnings"].append("cost_missing_or_unparseable")
    if quantity == 0.0: normalized["warnings"].append("quantity_missing_or_zero")
    return normalized


if __name__ == "__main__":
    print("=" * 60)
    print("EXTERNAL SUPPLIER API — NORMALIZATION DEMO")
    print("=" * 60)
    for i, raw in enumerate(MESSY_RESPONSES, 1):
        print(f"\n[Vendor {i}] RAW:"); print(json.dumps(raw, indent=2))
        print(f"\n[Vendor {i}] NORMALIZED:"); print(json.dumps(normalize_supplier_response(raw), indent=2))
        print("-" * 60)
    print("\n✅ All vendor formats normalized. Ready for ERP ingestion.")
