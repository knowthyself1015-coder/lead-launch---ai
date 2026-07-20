"""
Reports engine — generates daily and weekly performance summaries.

Responsible for:
- Aggregating daily trade activity
- Computing KPIs: P&L, win rate, Sharpe, max drawdown
- Storing DailyReport records for historical tracking
- Generating the summary text / narrative
"""


async def generate_daily_report(date_str: str | None = None) -> dict:
    """Generate a daily performance report.

    Args:
        date_str: ISO date string. Defaults to today.

    Returns a dict matching the DailyReport schema.
    """
    # TODO: Implement report generation from trade & portfolio data
    return {
        "report_date": date_str or "today",
        "starting_equity": 0.0,
        "ending_equity": 0.0,
        "net_pnl": 0.0,
        "net_pnl_pct": 0.0,
        "win_rate": None,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "max_drawdown_pct": None,
        "sharpe_ratio": None,
        "signals_generated": 0,
        "signals_accepted": 0,
        "signals_rejected": 0,
        "summary_text": "",
    }


async def get_reports(limit: int = 30) -> list[dict]:
    """Retrieve the most recent daily reports."""
    # TODO: Fetch from database
    return []
