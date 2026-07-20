from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.sql import func

from app.database import Base


class Trade(Base):
    """Executed trades (fills)."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    side = Column(String(4), nullable=False)  # "buy" or "sell"
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    notional = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    order_type = Column(String(20), default="market")
    signal_id = Column(Integer, nullable=True)  # FK to signals if triggered
    alpaca_order_id = Column(String(64), nullable=True)
    filled_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)
