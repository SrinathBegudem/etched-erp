"""
Core ERP data models.

Design principles:
- Every table has created_at / updated_at for auditability
- Foreign keys enforced at DB level, not just application level
- Status fields use strings not integers — readable without a lookup table
- No soft deletes for now — keeps queries simple and fast
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class POStatus(str, enum.Enum):
    DRAFT = "draft"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


# ─── SUPPLIERS ───────────────────────────────────────────────────────────────

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255))
    contact_phone = Column(String(50))
    lead_time_days = Column(Integer, default=0)       # avg delivery time
    payment_terms_days = Column(Integer, default=30)  # net-30, net-60 etc
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


# ─── INVENTORY ───────────────────────────────────────────────────────────────

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    unit = Column(String(50), default="unit")         # unit, kg, litre, etc
    quantity_on_hand = Column(Float, default=0.0)
    reorder_threshold = Column(Float, default=0.0)    # trigger reorder alert
    unit_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    po_line_items = relationship("POLineItem", back_populates="item")
    movements = relationship("InventoryMovement", back_populates="item")


class InventoryMovement(Base):
    """
    Every stock change is recorded as a movement — full audit trail.
    Quantity positive = stock in, negative = stock out.
    """
    __tablename__ = "inventory_movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    quantity_delta = Column(Float, nullable=False)    # +ve = in, -ve = out
    reason = Column(String(255))                      # "PO receipt", "production use", "adjustment"
    reference_id = Column(String(100))               # PO number, work order, etc
    recorded_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("InventoryItem", back_populates="movements")


# ─── PURCHASE ORDERS ─────────────────────────────────────────────────────────

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String(100), unique=True, nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    status = Column(String(50), default=POStatus.DRAFT)
    expected_delivery = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="purchase_orders")
    line_items = relationship("POLineItem", back_populates="purchase_order", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="purchase_order")

    @property
    def total_value(self):
        return sum(li.quantity * li.unit_price for li in self.line_items)


class POLineItem(Base):
    __tablename__ = "po_line_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)

    purchase_order = relationship("PurchaseOrder", back_populates="line_items")
    item = relationship("InventoryItem", back_populates="po_line_items")


# ─── FINANCIALS ──────────────────────────────────────────────────────────────

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(100), unique=True, nullable=False, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    status = Column(String(50), default=InvoiceStatus.PENDING)
    due_date = Column(DateTime)
    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    purchase_order = relationship("PurchaseOrder", back_populates="invoices")
