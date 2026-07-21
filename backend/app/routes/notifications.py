"""Notification API routes — send alerts and manage channel config."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.engines.notifications import (
    Notification,
    NotificationChannel,
    NotificationResult,
    format_trade_alert,
    parse_active_channels,
    send_alert,
    send_notification,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/send
# ---------------------------------------------------------------------------
@router.post("/send", response_model=NotificationResult)
async def send_notification_endpoint(
    channel: str,
    recipient: str = "",
    subject: str = "",
    body: str = "",
    priority: str = "MEDIUM",
) -> NotificationResult:
    """
    Send a single notification to a specified channel.

    Body params: channel, recipient, subject, body, priority.
    """
    settings = get_settings()

    try:
        ch = NotificationChannel(channel.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel: {channel}. "
                    f"Valid channels: {[c.value for c in NotificationChannel]}",
        )

    notification = Notification(
        channel=ch,
        recipient=recipient,
        subject=subject,
        body=body,
        priority=priority.upper(),
    )

    # Build channel configs from settings
    channel_configs = _build_channel_configs(settings)
    return await send_notification(notification, channel_configs)


# ---------------------------------------------------------------------------
# POST /api/v1/notifications/alert
# ---------------------------------------------------------------------------
@router.post("/alert", response_model=list[NotificationResult])
async def send_alert_endpoint(
    symbol: str,
    decision: str,
    confidence: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    reason: str = "",
) -> list[NotificationResult]:
    """
    Send a trade alert (BUY/SELL signal) to all active channels.

    Body params: symbol, decision, confidence, entry_price, stop_loss,
                 take_profit, reason.
    """
    settings = get_settings()

    # Validate decision
    decision_upper = decision.upper()
    if decision_upper not in ("BUY", "SELL"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: {decision}. Must be BUY or SELL.",
        )

    # Determine active channels
    active_channels = parse_active_channels(settings.NOTIFICATION_CHANNELS)
    if not active_channels:
        raise HTTPException(
            status_code=400,
            detail="No notification channels configured. "
                    "Set NOTIFICATION_CHANNELS in environment.",
        )

    return await send_alert(
        symbol=symbol.upper(),
        decision=decision_upper,
        confidence=confidence,
        entry=entry_price,
        stop=stop_loss,
        target=take_profit,
        reason=reason,
        channels=active_channels,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/channels
# ---------------------------------------------------------------------------
@router.get("/channels")
async def list_channels():
    """
    Return the list of configured active notification channels (no secrets).
    """
    settings = get_settings()

    active_channels = parse_active_channels(settings.NOTIFICATION_CHANNELS)

    # Return channel info without secrets
    channel_info = []
    for ch in NotificationChannel:
        configured = ch in active_channels
        info = {
            "channel": ch.value,
            "active": configured,
        }

        # Add non-secret config status
        if ch == NotificationChannel.EMAIL:
            info["configured"] = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
        elif ch == NotificationChannel.DISCORD:
            info["configured"] = bool(settings.DISCORD_WEBHOOK_URL)
        elif ch == NotificationChannel.TELEGRAM:
            info["configured"] = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
        elif ch == NotificationChannel.SLACK:
            info["configured"] = bool(settings.SLACK_WEBHOOK_URL)
        elif ch == NotificationChannel.SMS:
            info["configured"] = False
            info["note"] = "SMS is log-only in V1; Twilio integration planned for V2."
        elif ch == NotificationChannel.PUSH:
            info["configured"] = False
            info["note"] = "Push is log-only in V1; FCM/OneSignal planned for V2."

        channel_info.append(info)

    return {
        "channels": channel_info,
        "active_channel_names": [c.value for c in active_channels],
    }


# ---------------------------------------------------------------------------
# GET /api/v1/notifications/template-preview
# ---------------------------------------------------------------------------
@router.get("/template-preview")
async def preview_template(
    symbol: str = "AAPL",
    direction: str = "BUY",
    confidence: float = 85.5,
    entry_price: float = 150.00,
    stop_loss: float = 147.00,
    take_profit: float = 159.00,
    reason: str = "Strong momentum breakout with volume confirmation",
):
    """
    Preview the trade alert template formatting without sending.
    """
    return {
        "template": format_trade_alert(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reason,
        ),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_channel_configs(settings) -> dict[str, dict]:
    """Build a dict of channel configs keyed by channel name."""
    return {
        "email": {
            "host": settings.SMTP_HOST,
            "port": settings.SMTP_PORT,
            "user": settings.SMTP_USER,
            "password": settings.SMTP_PASSWORD,
            "from_email": settings.SMTP_FROM_EMAIL,
        },
        "discord": {
            "webhook_url": settings.DISCORD_WEBHOOK_URL,
        },
        "telegram": {
            "bot_token": settings.TELEGRAM_BOT_TOKEN,
            "chat_id": settings.TELEGRAM_CHAT_ID,
        },
        "slack": {
            "webhook_url": settings.SLACK_WEBHOOK_URL,
        },
    }
