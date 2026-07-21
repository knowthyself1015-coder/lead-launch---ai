"""Tests for the notifications engine."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.engines.notifications import (
    Notification,
    NotificationChannel,
    NotificationResult,
    _CHANNEL_DISPATCH,
    _send_discord,
    _send_email,
    _send_push,
    _send_slack,
    _send_sms,
    _send_telegram,
    format_trade_alert,
    parse_active_channels,
    send_alert,
    send_batch,
    send_daily_report,
    send_notification,
    send_portfolio_alert,
    send_generic_alert,
    send_trade_alert,
    send_daily_summary,
)


# ======================================================================
# Template formatting
# ======================================================================

def test_format_buy_signal():
    """Trade alert template is correctly formatted for a BUY signal."""
    result = format_trade_alert(
        symbol="AAPL",
        direction="BUY",
        confidence=85.5,
        entry_price=150.00,
        stop_loss=147.00,
        take_profit=159.00,
        reasoning="Strong breakout above resistance",
    )
    assert "🚨 BUY Signal: AAPL" in result
    assert "Confidence: 85.5%" in result
    assert "Entry: $150.00" in result
    assert "Stop Loss: $147.00" in result
    assert "Take Profit: $159.00" in result
    assert "Risk/Reward: 1:3.00" in result
    assert "Strong breakout above resistance" in result


def test_format_sell_signal():
    """Trade alert template is correctly formatted for a SELL signal."""
    result = format_trade_alert(
        symbol="TSLA",
        direction="SELL",
        confidence=72.0,
        entry_price=250.00,
        stop_loss=255.00,
        take_profit=235.00,
        reasoning="Bearish divergence on RSI",
    )
    assert "🚨 SELL Signal: TSLA" in result
    assert "Confidence: 72.0%" in result
    assert "Entry: $250.00" in result
    assert "Stop Loss: $255.00" in result
    assert "Take Profit: $235.00" in result
    assert "Risk/Reward: 1:3.00" in result
    assert "Bearish divergence on RSI" in result


def test_format_trade_alert_default_reasoning():
    """Trade alert uses default reasoning when none provided."""
    result = format_trade_alert(
        symbol="NVDA",
        direction="BUY",
        confidence=90.0,
        entry_price=100.00,
        stop_loss=95.00,
        take_profit=115.00,
    )
    assert "No additional reasoning provided." in result


def test_format_trade_alert_zero_stop():
    """Trade alert handles zero or negative stop loss gracefully."""
    result = format_trade_alert(
        symbol="META",
        direction="BUY",
        confidence=50.0,
        entry_price=300.00,
        stop_loss=0,
        take_profit=320.00,
    )
    assert "Risk/Reward: N/A" in result


# ======================================================================
# Discord embed formatting
# ======================================================================

@pytest.mark.asyncio
async def test_discord_embed_buy_color_green():
    """Discord embed uses green color for BUY signals."""
    notification = Notification(
        channel=NotificationChannel.DISCORD,
        recipient="",
        subject="BUY Signal",
        body="🚨 BUY Signal: AAPL\nConfidence: 85.5%",
        priority="HIGH",
    )
    config = {"webhook_url": "https://discord.com/api/webhooks/test"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await _send_discord(notification, config)
        assert result.success is True

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        embed = payload["embeds"][0]
        assert embed["color"] == 0x00FF00  # green for BUY


@pytest.mark.asyncio
async def test_discord_embed_sell_color_red():
    """Discord embed uses red color for SELL signals."""
    notification = Notification(
        channel=NotificationChannel.DISCORD,
        recipient="",
        subject="SELL Signal",
        body="🚨 SELL Signal: TSLA\nConfidence: 72.0%",
        priority="HIGH",
    )
    config = {"webhook_url": "https://discord.com/api/webhooks/test"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await _send_discord(notification, config)
        assert result.success is True

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        embed = payload["embeds"][0]
        assert embed["color"] == 0xFF0000  # red for SELL


@pytest.mark.asyncio
async def test_discord_embed_alert_color_yellow():
    """Discord embed uses yellow/orange color for generic alerts."""
    notification = Notification(
        channel=NotificationChannel.DISCORD,
        recipient="",
        subject="Alert",
        body="Something happened",
        priority="MEDIUM",
    )
    config = {"webhook_url": "https://discord.com/api/webhooks/test"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await _send_discord(notification, config)
        assert result.success is True

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        embed = payload["embeds"][0]
        assert embed["color"] == 0xFFA500  # yellow/orange for alerts


# ======================================================================
# Telegram message formatting
# ======================================================================

@pytest.mark.asyncio
async def test_telegram_message_formatting():
    """Telegram sends correctly formatted Markdown message."""
    notification = Notification(
        channel=NotificationChannel.TELEGRAM,
        recipient="",
        subject="BUY Signal: AAPL",
        body="Confidence: 85.5%\nEntry: $150.00",
        priority="HIGH",
    )
    config = {"bot_token": "test_token_123", "chat_id": "123456789"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await _send_telegram(notification, config)
        assert result.success is True

        call_args = mock_post.call_args
        url = call_args[0][0]
        payload = call_args[1]["json"]

        assert "test_token_123" in url
        assert payload["chat_id"] == "123456789"
        assert payload["parse_mode"] == "Markdown"
        assert "BUY Signal: AAPL" in payload["text"]


@pytest.mark.asyncio
async def test_telegram_missing_config():
    """Telegram fails gracefully when token or chat_id is missing."""
    notification = Notification(
        channel=NotificationChannel.TELEGRAM,
        recipient="",
        subject="Test",
        body="test",
        priority="LOW",
    )

    result = await _send_telegram(notification, {})
    assert result.success is False
    assert "Missing Telegram bot token or chat ID" in result.error_message


# ======================================================================
# SMS logging behavior
# ======================================================================

def test_sms_logs_instead_of_sends(caplog):
    """SMS channel logs the message instead of sending — real SMS is V2."""
    notification = Notification(
        channel=NotificationChannel.SMS,
        recipient="+15551234567",
        subject="Trade Alert",
        body="BUY AAPL",
        priority="HIGH",
    )

    with caplog.at_level(logging.INFO):
        result = asyncio.run(_send_sms(notification, {}))
        assert result.success is True
        assert "SMS not configured — message logged" in caplog.text
        assert "Trade Alert" in caplog.text
        assert "BUY AAPL" in caplog.text
        # Verify the TODO comment exists in the source
        import inspect
        source = inspect.getsource(_send_sms)
        assert "TODO" in source
        assert "V2" in source
        assert "Twilio" in source


# ======================================================================
# Batch sending
# ======================================================================

@pytest.mark.asyncio
async def test_batch_sends_concurrently():
    """send_batch dispatches multiple notifications concurrently."""
    notifications = [
        Notification(
            channel=NotificationChannel.SMS,
            recipient="",
            subject=f"Alert {i}",
            body=f"Body {i}",
            priority="MEDIUM",
        )
        for i in range(5)
    ]

    # SMS is synchronous (just logs), so batch works fine without mocking
    results = await send_batch(notifications)
    assert len(results) == 5
    assert all(r.success for r in results)
    assert all(r.channel == NotificationChannel.SMS for r in results)


@pytest.mark.asyncio
async def test_batch_empty_list():
    """send_batch returns empty list for empty input."""
    results = await send_batch([])
    assert results == []


# ======================================================================
# Channel config validation
# ======================================================================

def test_parse_active_channels_valid():
    """parse_active_channels parses comma-separated valid channels."""
    result = parse_active_channels("discord,email,sms")
    assert len(result) == 3
    assert NotificationChannel.DISCORD in result
    assert NotificationChannel.EMAIL in result
    assert NotificationChannel.SMS in result


def test_parse_active_channels_whitespace():
    """parse_active_channels handles whitespace around names."""
    result = parse_active_channels(" discORD ,  teleGRAM  ")
    assert NotificationChannel.DISCORD in result
    assert NotificationChannel.TELEGRAM in result


def test_parse_active_channels_unknown_skipped():
    """parse_active_channels silently skips unknown channel names."""
    result = parse_active_channels("discord,invalid_channel,slack")
    assert len(result) == 2
    assert NotificationChannel.DISCORD in result
    assert NotificationChannel.SLACK in result


def test_parse_active_channels_empty_string():
    """parse_active_channels returns empty list for empty string."""
    result = parse_active_channels("")
    assert result == []


# ======================================================================
# send_notification
# ======================================================================

@pytest.mark.asyncio
async def test_send_notification_unknown_channel():
    """send_notification returns error for unsupported channel."""
    # Reaching into internals to test edge case — dispatch map handles it
    notification = Notification(
        channel=NotificationChannel.EMAIL,
        recipient="",
        subject="test",
        body="test",
    )

    # If we remove it from dispatch, it should fail gracefully
    original = _CHANNEL_DISPATCH.get(NotificationChannel.EMAIL)
    del _CHANNEL_DISPATCH[NotificationChannel.EMAIL]
    try:
        result = await send_notification(notification)
        assert result.success is False
        assert "Unknown channel" in result.error_message
    finally:
        _CHANNEL_DISPATCH[NotificationChannel.EMAIL] = original


# ======================================================================
# send_alert (trade signal)
# ======================================================================

@pytest.mark.asyncio
async def test_send_alert_uses_correct_template():
    """send_alert formats a trade signal and sends to all channels."""
    with patch("app.engines.notifications.send_batch") as mock_batch:
        mock_batch.return_value = [NotificationResult(
            success=True,
            channel=NotificationChannel.DISCORD,
        )]

        results = await send_alert(
            symbol="AAPL",
            decision="BUY",
            confidence=85.5,
            entry=150.0,
            stop=147.0,
            target=159.0,
            reason="Test signal",
            channels=[NotificationChannel.DISCORD],
        )

        assert len(results) == 1
        assert results[0].success is True

        # Verify the sent notification contains template content
        call_args = mock_batch.call_args
        notifications = call_args[0][0]
        assert len(notifications) == 1
        n = notifications[0]
        assert "🚨 BUY Signal: AAPL" in n.subject
        assert "85.5%" in n.body
        assert n.priority == "HIGH"


# ======================================================================
# send_daily_report
# ======================================================================

@pytest.mark.asyncio
async def test_send_daily_report_formatting():
    """send_daily_report formats report data correctly."""
    report_data = {
        "net_pnl": 1500.50,
        "net_pnl_pct": 2.35,
        "total_trades": 12,
        "winning_trades": 8,
        "losing_trades": 4,
        "win_rate": 0.667,
        "sharpe_ratio": 1.85,
        "max_drawdown_pct": -3.2,
        "starting_equity": 100000,
        "ending_equity": 101500.50,
        "signals_generated": 20,
        "signals_accepted": 12,
        "summary_text": "Good day for tech stocks.",
    }

    with patch("app.engines.notifications.send_batch") as mock_batch:
        mock_batch.return_value = [NotificationResult(
            success=True,
            channel=NotificationChannel.DISCORD,
        )]

        results = await send_daily_report(
            report_data,
            channels=[NotificationChannel.DISCORD],
        )
        assert len(results) == 1

        call_args = mock_batch.call_args
        notifications = call_args[0][0]
        n = notifications[0]
        assert "🟢 Daily Report" in n.subject
        assert "+$1,500.50" in n.body
        assert "Good day for tech stocks" in n.body
        assert "Win Rate: 66.7%" in n.body


# ======================================================================
# send_portfolio_alert
# ======================================================================

@pytest.mark.asyncio
async def test_send_portfolio_alert():
    """send_portfolio_alert sends risk warnings with HIGH priority."""
    with patch("app.engines.notifications.send_batch") as mock_batch:
        mock_batch.return_value = [NotificationResult(
            success=True,
            channel=NotificationChannel.DISCORD,
        )]

        results = await send_portfolio_alert(
            alert_type="MARGIN_CALL",
            message="Portfolio margin at 95% — reduce exposure immediately.",
            channels=[NotificationChannel.DISCORD],
        )
        assert len(results) == 1

        call_args = mock_batch.call_args
        notifications = call_args[0][0]
        n = notifications[0]
        assert "⚠️ Portfolio Alert: MARGIN_CALL" in n.subject
        assert n.priority == "HIGH"


# ======================================================================
# send_generic_alert (legacy)
# ======================================================================

@pytest.mark.asyncio
async def test_send_generic_alert_logs(caplog):
    """send_generic_alert with 'log' channel writes to logger."""
    with caplog.at_level(logging.INFO):
        await send_generic_alert(
            title="Test Alert",
            body="Testing 123",
            level="info",
            channels=["log"],
        )
        assert "Test Alert" in caplog.text
        assert "Testing 123" in caplog.text


# ======================================================================
# Legacy stubs
# ======================================================================

@pytest.mark.asyncio
async def test_send_trade_alert_legacy():
    """Legacy send_trade_alert sends to Discord."""
    with patch("app.engines.notifications.send_notification") as mock_send:
        mock_send.return_value = NotificationResult(
            success=True,
            channel=NotificationChannel.DISCORD,
        )
        await send_trade_alert(
            ticker="AAPL",
            action="BUY",
            price=150.0,
            quantity=100,
            reason="Test",
        )
        assert mock_send.called
        notification = mock_send.call_args[0][0]
        assert notification.channel == NotificationChannel.DISCORD


@pytest.mark.asyncio
async def test_send_daily_summary_legacy():
    """Legacy send_daily_summary delegates to send_daily_report."""
    with patch("app.engines.notifications.send_daily_report") as mock_report:
        mock_report.return_value = [NotificationResult(
            success=True,
            channel=NotificationChannel.DISCORD,
        )]
        await send_daily_summary({"net_pnl": 100.0})
        assert mock_report.called


# ======================================================================
# Slack formatting
# ======================================================================

@pytest.mark.asyncio
async def test_slack_buy_color():
    """Slack uses green color for BUY signals."""
    notification = Notification(
        channel=NotificationChannel.SLACK,
        recipient="",
        subject="BUY Signal",
        body="🚨 BUY Signal: AAPL",
        priority="HIGH",
    )
    config = {"webhook_url": "https://hooks.slack.com/test"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await _send_slack(notification, config)
        assert result.success is True
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        attachment = payload["attachments"][0]
        assert attachment["color"] == "#36a64f"  # green


@pytest.mark.asyncio
async def test_slack_sell_color():
    """Slack uses red color for SELL signals."""
    notification = Notification(
        channel=NotificationChannel.SLACK,
        recipient="",
        subject="SELL Signal",
        body="🚨 SELL Signal: TSLA",
        priority="HIGH",
    )
    config = {"webhook_url": "https://hooks.slack.com/test"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await _send_slack(notification, config)
        assert result.success is True
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        attachment = payload["attachments"][0]
        assert attachment["color"] == "#ff0000"  # red


# ======================================================================
# Push notification placeholder
# ======================================================================

def test_push_logs_instead_of_sends(caplog):
    """Push channel logs — real push is V2."""
    notification = Notification(
        channel=NotificationChannel.PUSH,
        recipient="device_token_abc",
        subject="Alert",
        body="Test push",
        priority="HIGH",
    )
    with caplog.at_level(logging.INFO):
        result = asyncio.run(_send_push(notification, {}))
        assert result.success is True
        assert "PUSH not configured" in caplog.text


# ======================================================================
# Email (SMTP) — mock aiosmtplib
# ======================================================================

@pytest.mark.asyncio
async def test_email_sends_html():
    """Email channel builds HTML multipart message and sends via SMTP."""
    notification = Notification(
        channel=NotificationChannel.EMAIL,
        recipient="trader@example.com",
        subject="BUY AAPL",
        body="Confidence: 85.5%",
        priority="HIGH",
    )
    config = {
        "host": "smtp.test.com",
        "port": 587,
        "user": "user",
        "password": "pass",
        "from_email": "bot@test.com",
    }

    with patch("aiosmtplib.send") as mock_smtp:
        mock_smtp.return_value = None  # success

        result = await _send_email(notification, config)
        assert result.success is True
        assert mock_smtp.called

        # Verify the message contains expected headers
        msg = mock_smtp.call_args[0][0]
        assert msg["From"] == "bot@test.com"
        assert msg["To"] == "trader@example.com"
        assert msg["Subject"] == "BUY AAPL"


@pytest.mark.asyncio
async def test_email_smtp_failure():
    """Email channel returns failure on SMTP error."""
    notification = Notification(
        channel=NotificationChannel.EMAIL,
        recipient="trader@example.com",
        subject="Test",
        body="Test",
    )
    config = {"host": "bad.host", "port": 587}

    with patch("aiosmtplib.send", side_effect=ConnectionError("No route to host")):
        result = await _send_email(notification, config)
        assert result.success is False
        assert "No route to host" in result.error_message


# ======================================================================
# Discord missing webhook
# ======================================================================

@pytest.mark.asyncio
async def test_discord_missing_webhook_url():
    """Discord returns failure if webhook URL is not configured."""
    notification = Notification(
        channel=NotificationChannel.DISCORD,
        recipient="",
        subject="Test",
        body="Test",
    )
    result = await _send_discord(notification, {"webhook_url": ""})
    assert result.success is False
    assert "No Discord webhook URL configured" in result.error_message


# ======================================================================
# NotificationResult dataclass
# ======================================================================

def test_notification_result_defaults():
    """NotificationResult dataclass has correct defaults."""
    result = NotificationResult(
        success=True,
        channel=NotificationChannel.DISCORD,
    )
    assert result.success is True
    assert result.channel == NotificationChannel.DISCORD
    assert result.error_message is None
    assert result.sent_at is not None
