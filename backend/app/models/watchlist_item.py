from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func

from app.database import Base


class WatchlistItem(Base):
    """Stocks the user wants to monitor closely."""

    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    added_reason = Column(String(255), nullable=True)
    target_buy_price = Column(Float, nullable=True)
    alert_enabled = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
