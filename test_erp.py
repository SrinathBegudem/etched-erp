"""
End-to-end ERP flow test.
Run: pytest -v

Simulates a full real-world workflow:
  supplier → inventory item → purchase order → receive → invoice → pay
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db

# ── Use a fresh in-memory DB for every test run — no leftover state ──────────
TEST_DB = "sqlite:///./test_erp.db"
engine = create_engine(TEST_DB, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate all tables before each test — guaranteed clean state."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ── THE TEST ─────────────────────────────────────────────────────────────────

def test_full_erp_flow():
    """
    Full workflow: supplier → item → PO → receive → verify → invoice → pay
    This is the core ERP loop that must always work correctly.
    """

    # 1. Create a supplier
    res = client.post("/suppliers", json={"name": "TSMC", "lead_time_days": 90, "payment_terms_days": 60})
    assert res.status_code == 200
    supplier_id = res.json()["id"]

    # 2. Create an inventory item (starts at zero stock)
    res = client.post("/inventory/items", json={
        "sku": "CHIP-001",
        "name": "AI Chip",
        "unit_cost": 0.0,
        "reorder_threshold": 50,
    })
    assert res.status_code == 200
    item_id = res.json()["id"]

    # 3. Create a purchase order
    res = client.post("/purchase-orders", json={
        "po_number": "PO-TEST-001",
        "supplier_id": supplier_id,
        "line_items": [{"item_id": item_id, "quantity": 100, "unit_price": 150.0}],
    })
    assert res.status_code == 200
    po_id = res.json()["id"]
    assert res.json()["total_value"] == 15000.0

    # 4. Receive the PO — triggers inventory update + cost recalculation
    res = client.post(f"/purchase-orders/{po_id}/receive")
    assert res.status_code == 200
    result = res.json()
    assert result["event"] == "po_received"
    assert "inventory_quantity_updated" in result["actions_triggered"]
    assert "unit_cost_recalculated_weighted_average" in result["actions_triggered"]

    # 5. Verify inventory updated correctly
    res = client.get(f"/inventory/items/{item_id}")
    assert res.status_code == 200
    item = res.json()
    assert item["quantity_on_hand"] == 100.0
    assert item["unit_cost"] == 150.0
    assert item["stock_value"] == 15000.0
    assert item["low_stock"] is False          # 100 > threshold of 50

    # 6. Create invoice tied to the PO
    res = client.post("/finance/invoices", json={
        "invoice_number": "INV-TEST-001",
        "supplier_id": supplier_id,
        "purchase_order_id": po_id,
        "amount": 15000.0,
    })
    assert res.status_code == 200
    invoice_id = res.json()["id"]

    # 7. Pay the invoice
    res = client.post(f"/finance/invoices/{invoice_id}/pay")
    assert res.status_code == 200
    assert res.json()["amount"] == 15000.0

    # 8. Financial summary reflects reality
    res = client.get("/finance/summary")
    assert res.status_code == 200
    summary = res.json()
    assert summary["total_paid_usd"] == 15000.0
    assert summary["total_pending_payable_usd"] == 0.0
