"""
Supplier and Purchase Order routes.
PO receipt automatically updates inventory — no manual sync needed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.models.models import Supplier, PurchaseOrder, POLineItem, InventoryItem, InventoryMovement, POStatus

router = APIRouter(tags=["Suppliers & Purchase Orders"])


# ─── SCHEMAS ─────────────────────────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    lead_time_days: int = 0
    payment_terms_days: int = 30


class LineItemCreate(BaseModel):
    item_id: int
    quantity: float
    unit_price: float


class POCreate(BaseModel):
    po_number: str
    supplier_id: int
    expected_delivery: Optional[datetime] = None
    notes: Optional[str] = None
    line_items: List[LineItemCreate]


# ─── SUPPLIER ROUTES ─────────────────────────────────────────────────────────

@router.get("/suppliers", summary="List all suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    suppliers = db.query(Supplier).all()
    # Count active POs per supplier at DB level — avoids loading all POs into memory
    active_po_counts = dict(
        db.query(PurchaseOrder.supplier_id, func.count(PurchaseOrder.id))
        .filter(PurchaseOrder.status.notin_(["received", "cancelled"]))
        .group_by(PurchaseOrder.supplier_id)
        .all()
    )
    return [
        {
            "id": s.id,
            "name": s.name,
            "contact_email": s.contact_email,
            "lead_time_days": s.lead_time_days,
            "payment_terms_days": s.payment_terms_days,
            "active_pos": active_po_counts.get(s.id, 0),
        }
        for s in suppliers
    ]


@router.post("/suppliers", summary="Add a new supplier")
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return {"message": "Supplier created", "id": supplier.id, "name": supplier.name}


# ─── PURCHASE ORDER ROUTES ───────────────────────────────────────────────────

@router.get("/purchase-orders", summary="List all purchase orders")
def list_pos(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    pos = query.order_by(PurchaseOrder.created_at.desc()).all()
    return [
        {
            "id": po.id,
            "po_number": po.po_number,
            "supplier": po.supplier.name,
            "status": po.status,
            "total_value": round(po.total_value, 2),
            "line_items": len(po.line_items),
            "expected_delivery": po.expected_delivery,
            "created_at": po.created_at,
        }
        for po in pos
    ]


@router.post("/purchase-orders", summary="Create a purchase order")
def create_po(payload: POCreate, db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    existing = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == payload.po_number).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"PO number '{payload.po_number}' already exists")

    po = PurchaseOrder(
        po_number=payload.po_number,
        supplier_id=payload.supplier_id,
        expected_delivery=payload.expected_delivery,
        notes=payload.notes,
        status=POStatus.DRAFT,
    )
    db.add(po)
    db.flush()

    for li in payload.line_items:
        item = db.query(InventoryItem).filter(InventoryItem.id == li.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Inventory item {li.item_id} not found")
        line = POLineItem(
            purchase_order_id=po.id,
            item_id=li.item_id,
            quantity=li.quantity,
            unit_price=li.unit_price,
        )
        db.add(line)

    db.commit()
    db.refresh(po)
    return {
        "message": "Purchase order created",
        "id": po.id,
        "po_number": po.po_number,
        "total_value": round(po.total_value, 2),
        "status": po.status,
    }


@router.post("/purchase-orders/{po_id}/receive", summary="Mark PO as received — auto-updates inventory, recalculates cost")
def receive_po(po_id: int, db: Session = Depends(get_db)):
    """
    PO receipt triggers a chain of events automatically:
      1. Inventory quantity updated
      2. Unit cost recalculated using weighted average (existing stock + incoming)
      3. Inventory valuation updated
      4. InventoryMovement record created for full audit trail

    Weighted average cost formula:
      new_unit_cost = (existing_qty * old_cost + incoming_qty * po_unit_price)
                      / (existing_qty + incoming_qty)

    This ensures inventory valuation always reflects actual landed cost,
    not just the last purchase price.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if po.status == POStatus.RECEIVED:
        raise HTTPException(status_code=400, detail="PO already received")
    if po.status == POStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot receive a cancelled PO")

    updated_items = []
    for li in po.line_items:
        item = db.query(InventoryItem).filter(InventoryItem.id == li.item_id).first()

        # Weighted average cost — standard inventory valuation method
        existing_qty = item.quantity_on_hand
        existing_cost = item.unit_cost
        incoming_qty = li.quantity
        incoming_cost = li.unit_price

        total_qty = existing_qty + incoming_qty
        if total_qty > 0:
            new_unit_cost = round(
                (existing_qty * existing_cost + incoming_qty * incoming_cost) / total_qty, 4
            )
        else:
            new_unit_cost = incoming_cost

        old_valuation = round(existing_qty * existing_cost, 2)
        item.quantity_on_hand = total_qty
        item.unit_cost = new_unit_cost
        new_valuation = round(total_qty * new_unit_cost, 2)

        movement = InventoryMovement(
            item_id=item.id,
            quantity_delta=incoming_qty,
            reason="PO receipt",
            reference_id=po.po_number,
        )
        db.add(movement)

        updated_items.append({
            "sku": item.sku,
            "name": item.name,
            "qty_before": existing_qty,
            "qty_added": incoming_qty,
            "qty_after": total_qty,
            "unit_cost_before": existing_cost,
            "unit_cost_after": new_unit_cost,
            "inventory_value_before_usd": old_valuation,
            "inventory_value_after_usd": new_valuation,
            "cost_delta_usd": round(new_valuation - old_valuation, 2),
        })

    po.status = POStatus.RECEIVED
    db.commit()

    return {
        "event": "po_received",
        "po_number": po.po_number,
        "supplier": po.supplier.name,
        "timestamp": datetime.utcnow().isoformat(),
        "actions_triggered": [
            "inventory_quantity_updated",
            "unit_cost_recalculated_weighted_average",
            "inventory_valuation_updated",
            "audit_movement_recorded",
        ],
        "items_updated": updated_items,
    }


@router.patch("/purchase-orders/{po_id}/status", summary="Update PO status")
def update_po_status(po_id: int, status: str, db: Session = Depends(get_db)):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    if status not in [s.value for s in POStatus]:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from: {[s.value for s in POStatus]}")
    po.status = status
    db.commit()
    return {"message": f"PO status updated to '{status}'", "po_number": po.po_number}
