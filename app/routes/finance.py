"""
Financial data flows — invoices, payment tracking, and reporting.
Designed to be the source of truth for AP (accounts payable) data.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.core.database import get_db
from app.models.models import Invoice, Supplier, PurchaseOrder, InvoiceStatus

router = APIRouter(prefix="/finance", tags=["Finance"])


# ─── SCHEMAS ─────────────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    invoice_number: str
    purchase_order_id: Optional[int] = None
    supplier_id: int
    amount: float
    currency: str = "USD"
    due_date: Optional[datetime] = None


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@router.get("/invoices", summary="List all invoices with optional status filter")
def list_invoices(status: Optional[str] = None, supplier_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Invoice)
    if status:
        query = query.filter(Invoice.status == status)
    if supplier_id:
        query = query.filter(Invoice.supplier_id == supplier_id)
    invoices = query.order_by(Invoice.created_at.desc()).all()
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "supplier_id": inv.supplier_id,
            "amount": inv.amount,
            "currency": inv.currency,
            "status": inv.status,
            "due_date": inv.due_date,
            "paid_at": inv.paid_at,
        }
        for inv in invoices
    ]


@router.post("/invoices", summary="Create an invoice")
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    supplier = db.query(Supplier).filter(Supplier.id == payload.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    existing = db.query(Invoice).filter(Invoice.invoice_number == payload.invoice_number).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Invoice '{payload.invoice_number}' already exists")

    if payload.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == payload.purchase_order_id).first()
        if not po:
            raise HTTPException(status_code=404, detail="Purchase order not found")

    invoice = Invoice(**payload.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return {"message": "Invoice created", "id": invoice.id, "invoice_number": invoice.invoice_number}


@router.post("/invoices/{invoice_id}/pay", summary="Mark invoice as paid")
def mark_paid(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot pay a cancelled invoice")

    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.utcnow()
    db.commit()
    return {
        "message": f"Invoice {invoice.invoice_number} marked as paid",
        "amount": invoice.amount,
        "currency": invoice.currency,
        "paid_at": invoice.paid_at,
    }


@router.get("/summary", summary="Financial summary — payables, cash flow snapshot")
def financial_summary(db: Session = Depends(get_db)):
    """
    Lightweight financial snapshot — no complex aggregation pipelines needed.
    Designed to be the data source for executive dashboards or forecasting tools.
    """
    all_invoices = db.query(Invoice).all()

    total_payable = sum(i.amount for i in all_invoices if i.status == InvoiceStatus.PENDING)
    total_paid = sum(i.amount for i in all_invoices if i.status == InvoiceStatus.PAID)
    total_overdue = sum(i.amount for i in all_invoices if i.status == InvoiceStatus.OVERDUE)

    # Per-supplier breakdown
    # Load all suppliers once — avoids N+1 query (one DB hit per invoice in a loop)
    supplier_map = {s.id: s.name for s in db.query(Supplier).all()}
    supplier_breakdown = {}
    for inv in all_invoices:
        name = supplier_map.get(inv.supplier_id, "Unknown")
        if name not in supplier_breakdown:
            supplier_breakdown[name] = {"pending": 0.0, "paid": 0.0, "overdue": 0.0}
        supplier_breakdown[name][inv.status] = supplier_breakdown[name].get(inv.status, 0.0) + inv.amount

    return {
        "total_pending_payable_usd": round(total_payable, 2),
        "total_paid_usd": round(total_paid, 2),
        "total_overdue_usd": round(total_overdue, 2),
        "total_invoices": len(all_invoices),
        "supplier_breakdown": supplier_breakdown,
    }
