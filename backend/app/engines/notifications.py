"""
Notifications engine — multi-channel alert delivery.

Supports: Email (SMTP), Discord (webhook), Telegram (bot API),
          Slack (webhook), SMS (placeholder/log-only).

All channel calls are async. SMS integration is deferred to V2.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

import aiosmtplib
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    SLACK = "slack"
    PUSH = "push"


@dataclass
class Notification:
    """A single notification to be delivered."""
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    priority: str = "MEDIUM"          # "HIGH" | "MEDIUM" | "LOW"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationResult:
    """Result of a single notification send attempt."""
    success: bool
    channel: NotificationChannel
    error_message: Optional[str] = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Trade alert template
# ---------------------------------------------------------------------------

TRADE_ALERT_TEMPLATE = """🚨 {direction} Signal: {symbol}
Confidence: {confidence}%
Entry: ${entry_price}
Stop Loss: ${stop_loss}
Take Profit: ${take_profit}
Risk/Reward: {rr_ratio}
Reason: {reasoning}"""


def format_trade_alert(
    symbol: str,
    direction: str,      # "BUY" or "SELL"
    confidence: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    reasoning: str = "",
) -> str:
    """Format a BUY/SELL signal into the standard template string.

    Returns the multi-line formatted alert body.
    """
    rr_ratio = "N/A"
    if stop_loss > 0 and entry_price != stop_loss:
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        if risk > 0:
            rr_ratio = f"1:{reward / risk:.2f}"

    return TRADE_ALERT_TEMPLATE.format(
        direction=direction.upper(),
        symbol=symbol.upper(),
        confidence=f"{confidence:.1f}",
        entry_price=f"{entry_price:.2f}",
        stop_loss=f"{stop_loss:.2f}",
        take_profit=f"{take_profit:.2f}",
        rr_ratio=rr_ratio,
        reasoning=reasoning or "No additional reasoning provided.",
    )


# ---------------------------------------------------------------------------
# Channel config helpers
# ---------------------------------------------------------------------------

def parse_active_channels(channels_str: str) -> list[NotificationChannel]:
    """Parse a comma-separated list of channel names into enum values."""
    active: list[NotificationChannel] = []
    for name in channels_str.split(","):
        name = name.strip().lower()
        try:
            active.append(NotificationChannel(name))
        except ValueError:
            logger.warning("Unknown notification channel: %s", name)
    return active


# ===================================================================
# Channel senders  (each returns NotificationResult)
# ===================================================================

async def _send_email(
    notification: Notification,
    config: dict[str, Any],
) -> NotificationResult:
    """Send an HTML email via SMTP using aiosmtplib."""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = config.get("from_email", "")
        msg["To"] = notification.recipient
        msg["Subject"] = notification.subject

        html_body = f"""\
<html><body style="font-family:sans-serif">
<h2>{notification.subject}</h2>
<pre style="font-size:14px;background:#f5f5f5;padding:16px;border-radius:8px">
{notification.body}
</pre>
<p style="color:#888;font-size:12px">AlphaSight AI Trading Agent</p>
</body></html>"""
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        host = config.get("host", "smtp.gmail.com")
        port = config.get("port", 587)
        user = config.get("user", "") or None
        password = config.get("password", "") or None

        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            username=user,
            password=password,
            start_tls=True,
        )

        return NotificationResult(success=True, channel=NotificationChannel.EMAIL)

    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return NotificationResult(
            success=False,
            channel=NotificationChannel.EMAIL,
            error_message=str(exc),
        )


async def _send_discord(
    notification: Notification,
    config: dict[str, Any],
) -> NotificationResult:
    """Send a message to Discord via webhook with a color-coded embed."""
    try:
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.DISCORD,
                error_message="No Discord webhook URL configured.",
            )

        # Determine embed color
        body_upper = notification.body.upper()
        if "BUY" in body_upper:
            color = 0x00FF00     # green
        elif "SELL" in body_upper:
            color = 0xFF0000     # red
        else:
            color = 0xFFA500     # yellow / orange for alerts

        embed = {
            "title": notification.subject,
            "description": notification.body,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "AlphaSight AI Trading Agent"},
        }

        payload = {
            "embeds": [embed],
            "username": "AlphaSight",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()

        return NotificationResult(success=True, channel=NotificationChannel.DISCORD)

    except Exception as exc:
        logger.error("Discord send failed: %s", exc)
        return NotificationResult(
            success=False,
            channel=NotificationChannel.DISCORD,
            error_message=str(exc),
        )


async def _send_telegram(
    notification: Notification,
    config: dict[str, Any],
) -> NotificationResult:
    """Send a message via Telegram Bot API."""
    try:
        bot_token = config.get("bot_token", "")
        chat_id = config.get("chat_id", "")
        if not bot_token or not chat_id:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.TELEGRAM,
                error_message="Missing Telegram bot token or chat ID.",
            )

        text = f"*{notification.subject}*\n\n{notification.body}"
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        return NotificationResult(success=True, channel=NotificationChannel.TELEGRAM)

    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)
        return NotificationResult(
            success=False,
            channel=NotificationChannel.TELEGRAM,
            error_message=str(exc),
        )


async def _send_sms(
    notification: Notification,
    config: dict[str, Any],
) -> NotificationResult:
    """
    SMS placeholder — logs the message to console.

    TODO (V2): Integrate with Twilio for real SMS delivery.
    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    environment variables and the twilio Python SDK.
    """
    try:
        text = f"[{notification.priority}] {notification.subject}\n{notification.body}"
        logger.info("SMS not configured — message logged: %s", text)

        return NotificationResult(success=True, channel=NotificationChannel.SMS)

    except Exception as exc:
        logger.error("SMS log failed: %s", exc)
        return NotificationResult(
            success=False,
            channel=NotificationChannel.SMS,
            error_message=str(exc),
        )


async def _send_slack(
    notification: Notification,
    config: dict[str, Any],
) -> NotificationResult:
    """Send a message to Slack via webhook with formatted attachment."""
    try:
        webhook_url = config.get("webhook_url", "")
        if not webhook_url:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.SLACK,
                error_message="No Slack webhook URL configured.",
            )

        # Color-coded attachment
        body_upper = notification.body.upper()
        if "BUY" in body_upper:
            color = "#36a64f"     # green
        elif "SELL" in body_upper:
            color = "#ff0000"     # red
        else:
            color = "#ffa500"     # yellow / orange

        payload = {
            "username": "AlphaSight",
            "icon_emoji": ":chart_with_upwards_trend:",
            "attachments": [
                {
                    "fallback": notification.subject,
                    "color": color,
                    "title": notification.subject,
                    "text": notification.body,
                    "footer": "AlphaSight AI Trading Agent",
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }
            ],
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()

        return NotificationResult(success=True, channel=NotificationChannel.SLACK)

    except Exception as exc:
        logger.error("Slack send failed: %s", exc)
        return NotificationResult(
            success=False,
            channel=NotificationChannel.SLACK,
            error_message=str(exc),
        )


async def _send_push(
    notification: Notification,
    config: dict[str, Any],
) -> NotificationResult:
    """
    Push notification placeholder — logs to console.

    TODO (V2): Integrate with Firebase Cloud Messaging or OneSignal.
    """
    try:
        logger.info(
            "PUSH not configured — message logged [%s]: %s | %s",
            notification.priority,
            notification.subject,
            notification.body,
        )
        return NotificationResult(success=True, channel=NotificationChannel.PUSH)

    except Exception as exc:
        logger.error("Push log failed: %s", exc)
        return NotificationResult(
            success=False,
            channel=NotificationChannel.PUSH,
            error_message=str(exc),
        )


# ---------------------------------------------------------------------------
# Channel dispatch map
# ---------------------------------------------------------------------------

_CHANNEL_DISPATCH = {
    NotificationChannel.EMAIL: _send_email,
    NotificationChannel.DISCORD: _send_discord,
    NotificationChannel.TELEGRAM: _send_telegram,
    NotificationChannel.SMS: _send_sms,
    NotificationChannel.SLACK: _send_slack,
    NotificationChannel.PUSH: _send_push,
}


# ===================================================================
# High-level public API
# ===================================================================

async def send_notification(
    notification: Notification,
    channel_configs: dict[str, Any] | None = None,
) -> NotificationResult:
    """
    Send a single notification through its configured channel.

    Args:
        notification: The Notification to send.
        channel_configs: Optional dict of channel-specific config overrides.

    Returns:
        NotificationResult with success status.
    """
    sender = _CHANNEL_DISPATCH.get(notification.channel)
    if sender is None:
        return NotificationResult(
            success=False,
            channel=notification.channel,
            error_message=f"Unknown channel: {notification.channel}",
        )

    configs = channel_configs or {}
    return await sender(notification, configs)


async def send_alert(
    symbol: str,
    decision: str,
    confidence: float,
    entry: float,
    stop: float,
    target: float,
    reason: str = "",
    channels: list[NotificationChannel] | None = None,
) -> list[NotificationResult]:
    """
    Send a trade alert (BUY/SELL signal) to all configured channels.

    Args:
        symbol: Ticker symbol.
        decision: "BUY" or "SELL".
        confidence: Signal confidence percentage (0-100).
        entry: Entry price.
        stop: Stop-loss price.
        target: Take-profit price.
        reason: Signal reasoning text.
        channels: List of channels to notify. Defaults to all.

    Returns:
        List of NotificationResult, one per channel.
    """
    if channels is None:
        channels = list(NotificationChannel)

    body = format_trade_alert(
        symbol=symbol,
        direction=decision,
        confidence=confidence,
        entry_price=entry,
        stop_loss=stop,
        take_profit=target,
        reasoning=reason,
    )

    subject = f"🚨 {decision.upper()} Signal: {symbol.upper()}"

    notifications = [
        Notification(
            channel=ch,
            recipient="",
            subject=subject,
            body=body,
            priority="HIGH",
        )
        for ch in channels
    ]

    return await send_batch(notifications)


async def send_daily_report(
    report_data: dict[str, Any],
    channels: list[NotificationChannel] | None = None,
) -> list[NotificationResult]:
    """
    Send a daily summary report to configured channels.

    Args:
        report_data: Dict with keys like net_pnl, net_pnl_pct, total_trades,
                     win_rate, sharpe_ratio, starting_equity, ending_equity, etc.
        channels: List of channels to notify.

    Returns:
        List of NotificationResult, one per channel.
    """
    if channels is None:
        channels = list(NotificationChannel)

    pnl = report_data.get("net_pnl", 0.0)
    pnl_pct = report_data.get("net_pnl_pct", 0.0)
    sign = "+" if pnl >= 0 else ""
    emoji = "🟢" if pnl >= 0 else "🔴"

    subject = f"{emoji} Daily Report — {sign}${pnl:,.2f} ({pnl_pct:+.2f}%)"

    lines = [
        "📊 **Daily Performance Summary**",
        "",
        f"• Net P&L: {sign}${pnl:,.2f} ({pnl_pct:+.2f}%)",
        f"• Total Trades: {report_data.get('total_trades', 0)}",
        f"• Winning: {report_data.get('winning_trades', 0)} | "
        f"Losing: {report_data.get('losing_trades', 0)}",
        f"• Win Rate: {report_data.get('win_rate', 0):.1%}",
        f"• Sharpe Ratio: {report_data.get('sharpe_ratio', 0):.2f}",
        f"• Max Drawdown: {report_data.get('max_drawdown_pct', 0):.2f}%",
        f"• Starting Equity: ${report_data.get('starting_equity', 0):,.2f}",
        f"• Ending Equity: ${report_data.get('ending_equity', 0):,.2f}",
        f"• Signals Generated: {report_data.get('signals_generated', 0)}",
        f"• Signals Accepted: {report_data.get('signals_accepted', 0)}",
    ]

    if report_data.get("summary_text"):
        lines.append("")
        lines.append(f"📝 {report_data['summary_text']}")

    body = "\n".join(lines)

    notifications = [
        Notification(
            channel=ch,
            recipient="",
            subject=subject,
            body=body,
            priority="MEDIUM",
        )
        for ch in channels
    ]

    return await send_batch(notifications)


async def send_portfolio_alert(
    alert_type: str,
    message: str,
    channels: list[NotificationChannel] | None = None,
) -> list[NotificationResult]:
    """
    Send a portfolio-related alert (risk warning, margin call, stop-hit, etc.).

    Args:
        alert_type: Type label, e.g. "RISK_WARNING", "MARGIN_CALL", "STOP_HIT".
        message: Alert body text.
        channels: List of channels to notify.

    Returns:
        List of NotificationResult, one per channel.
    """
    if channels is None:
        channels = list(NotificationChannel)

    subject = f"⚠️ Portfolio Alert: {alert_type}"

    notifications = [
        Notification(
            channel=ch,
            recipient="",
            subject=subject,
            body=message,
            priority="HIGH",
        )
        for ch in channels
    ]

    return await send_batch(notifications)


async def send_batch(
    notifications: list[Notification],
    channel_configs: dict[str, Any] | None = None,
) -> list[NotificationResult]:
    """
    Send multiple notifications concurrently.

    Args:
        notifications: List of Notification objects.
        channel_configs: Optional channel config overrides.

    Returns:
        List of NotificationResult, one per notification.
    """
    if not notifications:
        return []

    tasks = [
        send_notification(n, channel_configs)
        for n in notifications
    ]
    results = await asyncio.gather(*tasks)
    return list(results)


# ---------------------------------------------------------------------------
# Backwards-compatible stubs (called from existing code paths)
# ---------------------------------------------------------------------------

async def send_trade_alert(
    ticker: str,
    action: str,
    price: float,
    quantity: int,
    reason: str = "",
) -> None:
    """Legacy wrapper — sends a simple trade alert to Discord."""
    body = f"{action.upper()} {quantity} shares of {ticker} @ ${price:.2f}"
    if reason:
        body += f"\nReason: {reason}"
    title = f"{action.upper()} — {ticker}"

    notification = Notification(
        channel=NotificationChannel.DISCORD,
        recipient="",
        subject=title,
        body=body,
        priority="MEDIUM",
    )
    await send_notification(notification)


async def send_daily_summary(report: dict) -> None:
    """Legacy wrapper — sends daily summary to all configured channels."""
    await send_daily_report(report)


async def send_generic_alert(
    title: str,
    body: str,
    level: str = "info",
    channels: list[str] | None = None,
) -> None:
    """
    Send a generic alert with string channel names.

    Supports a "log" pseudo-channel for local logging.
    """
    if channels is None:
        channels = ["log"]

    for channel_name in channels:
        if channel_name == "log":
            log_level = getattr(logging, level.upper(), logging.INFO)
            logger.log(log_level, "[%s] %s: %s", level.upper(), title, body)
            continue

        try:
            ch = NotificationChannel(channel_name)
        except ValueError:
            logger.warning("Unknown channel: %s", channel_name)
            continue

        priority = (
            "HIGH" if level == "critical"
            else "MEDIUM" if level == "warning"
            else "LOW"
        )
        notification = Notification(
            channel=ch,
            recipient="",
            subject=title,
            body=body,
            priority=priority,
        )
        await send_notification(notification)
