"""
Notifications engine — sends alerts via Discord, email, SMS, etc.

Responsible for:
- Sending trade alerts (entry, exit, stop-hit)
- Delivering daily report summaries
- Broadcasting critical risk warnings
- Rate-limiting to avoid spam
"""

import logging

logger = logging.getLogger(__name__)


async def send_alert(
    title: str,
    body: str,
    level: str = "info",
    channels: list[str] | None = None,
) -> None:
    """Send an alert to configured notification channels.

    Args:
        title: Short alert title.
        body: Detailed message body.
        level: One of 'info', 'warning', 'critical'.
        channels: List of channels ('discord', 'email', etc.). Defaults to all.
    """
    if channels is None:
        channels = ["discord", "log"]

    for channel in channels:
        if channel == "log":
            log_level = getattr(logging, level.upper(), logging.INFO)
            logger.log(log_level, f"[{level.upper()}] {title}: {body}")
        elif channel == "discord":
            # TODO: Send via Discord webhook
            pass
        elif channel == "email":
            # TODO: Send via email (SMTP / SendGrid)
            pass


async def send_trade_alert(
    ticker: str,
    action: str,
    price: float,
    quantity: int,
    reason: str = "",
) -> None:
    """Send a trade execution alert."""
    title = f"{action.upper()} — {ticker}"
    body = f"{action.upper()} {quantity} shares of {ticker} @ ${price:.2f}"
    if reason:
        body += f"\nReason: {reason}"
    await send_alert(title, body, level="info")


async def send_daily_summary(report: dict) -> None:
    """Send the daily performance summary."""
    pnl = report.get("net_pnl", 0.0)
    pnl_pct = report.get("net_pnl_pct", 0.0)
    title = f"Daily Report — {'+' if pnl >= 0 else ''}${pnl:.2f} ({pnl_pct:+.2f}%)"
    body = f"Trades: {report.get('total_trades', 0)} | "
    body += f"Win rate: {report.get('win_rate', 0):.0%} | "
    body += f"Sharpe: {report.get('sharpe_ratio', 0):.2f}"
    await send_alert(title, body, level="info")
