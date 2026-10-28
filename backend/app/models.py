from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    paypal_invoice_id: Mapped[str] = mapped_column(String, index=True)
    supplier_name: Mapped[str] = mapped_column(String, index=True)
    supplier_email: Mapped[str] = mapped_column(String, default="", index=True)
    number: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    result: Mapped[dict] = mapped_column(JSON)  
