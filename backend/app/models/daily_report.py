from sqlalchemy import Column, Integer, Float, DateTime, Text, JSON
from sqlalchemy.sql import func

from app.database import Base


class DailyReport(Base):
    """Daily performance snapshots and summaries."""

    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    starting_equity = Column(Float, nullable=False)
    ending_equity = Column(Float, nullable=False)
    net_pnl = Column(Float, nullable=False)
    net_pnl_pct = Column(Float, nullable=False)
    win_rate = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    max_drawdown_pct = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    signals_generated = Column(Integer, default=0)
    signals_accepted = Column(Integer, default=0)
    signals_rejected = Column(Integer, default=0)
    summary_text = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
