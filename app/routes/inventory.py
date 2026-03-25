"""
Inventory routes — stock management and movement tracking.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.models import InventoryItem, InventoryMovement

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ─── SCHEMAS ─────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    unit: str = "unit"
    quantity_on_hand: float = 0.0
    reorder_threshold: float = 0.0
    unit_cost: float = 0.0


class MovementCreate(BaseModel):
    item_id: int
    quantity_delta: float
    reason: str
    reference_id: Optional[str] = None


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@router.get("/items", summary="List all inventory items")
def list_items(low_stock_only: bool = False, db: Session = Depends(get_db)):
    items = db.query(InventoryItem).all()
    result = []
    for item in items:
        low_stock = item.quantity_on_hand <= item.reorder_threshold
        if low_stock_only and not low_stock:
            continue
        result.append({
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "unit": item.unit,
            "quantity_on_hand": item.quantity_on_hand,
            "reorder_threshold": item.reorder_threshold,
            "unit_cost": item.unit_cost,
            "low_stock": low_stock,
            "stock_value": round(item.quantity_on_hand * item.unit_cost, 2),
        })
    return result


@router.post("/items", summary="Create a new inventory item")
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    existing = db.query(InventoryItem).filter(InventoryItem.sku == payload.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"SKU '{payload.sku}' already exists")
    item = InventoryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"message": "Item created", "id": item.id, "sku": item.sku}


@router.get("/items/{item_id}", summary="Get a single inventory item")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    movements = db.query(InventoryMovement).filter(
        InventoryMovement.item_id == item_id
    ).order_by(InventoryMovement.recorded_at.desc()).limit(10).all()
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "quantity_on_hand": item.quantity_on_hand,
        "reorder_threshold": item.reorder_threshold,
        "unit_cost": item.unit_cost,
        "stock_value": round(item.quantity_on_hand * item.unit_cost, 2),
        "low_stock": item.quantity_on_hand <= item.reorder_threshold,
        "recent_movements": [
            {
                "delta": m.quantity_delta,
                "reason": m.reason,
                "reference": m.reference_id,
                "at": m.recorded_at,
            }
            for m in movements
        ],
    }


@router.post("/movements", summary="Record a stock movement (in or out)")
def record_movement(payload: MovementCreate, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.id == payload.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    new_qty = item.quantity_on_hand + payload.quantity_delta
    if new_qty < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock. Current: {item.quantity_on_hand}, requested delta: {payload.quantity_delta}"
        )

    previous_qty = item.quantity_on_hand  # capture BEFORE update
    movement = InventoryMovement(**payload.model_dump())
    item.quantity_on_hand = new_qty
    db.add(movement)
    db.commit()

    return {
        "message": "Movement recorded",
        "item": item.name,
        "previous_qty": previous_qty,
        "new_qty": new_qty,
        "low_stock_alert": new_qty <= item.reorder_threshold,
    }


@router.get("/summary", summary="Inventory summary — total value, low stock alerts")
def inventory_summary(db: Session = Depends(get_db)):
    items = db.query(InventoryItem).all()
    total_value = sum(i.quantity_on_hand * i.unit_cost for i in items)
    low_stock = [i.name for i in items if i.quantity_on_hand <= i.reorder_threshold]
    return {
        "total_items": len(items),
        "total_stock_value_usd": round(total_value, 2),
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock,
    }
