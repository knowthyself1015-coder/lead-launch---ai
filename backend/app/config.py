import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Shared configuration loaded from environment variables."""

    # -----------------------------------------------------------
    # General
    # -----------------------------------------------------------
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    # -----------------------------------------------------------
    # Market Data — Polygon.io
    # -----------------------------------------------------------
    POLYGON_API_KEY: str = os.getenv("POLYGON_API_KEY", "")
    POLYGON_BASE_URL: str = "https://api.polygon.io"

    # -----------------------------------------------------------
    # Trading — Alpaca
    # -----------------------------------------------------------
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    ALPACA_DATA_URL: str = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")

    # -----------------------------------------------------------
    # AI / LLM — OpenAI
    # -----------------------------------------------------------
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # -----------------------------------------------------------
    # Database
    # -----------------------------------------------------------
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://alphsight:alphsight@localhost:5432/alphsight",
    )

    # -----------------------------------------------------------
    # Redis
    # -----------------------------------------------------------
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # -----------------------------------------------------------
    # Notifications — SMTP (Email)
    # -----------------------------------------------------------
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "alphsight@example.com")

    # -----------------------------------------------------------
    # Notifications — Discord
    # -----------------------------------------------------------
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # -----------------------------------------------------------
    # Notifications — Telegram
    # -----------------------------------------------------------
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # -----------------------------------------------------------
    # Notifications — Slack
    # -----------------------------------------------------------
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # -----------------------------------------------------------
    # Notifications — Active Channels
    # -----------------------------------------------------------
    NOTIFICATION_CHANNELS: str = os.getenv("NOTIFICATION_CHANNELS", "discord")

    # -----------------------------------------------------------
    # Risk Parameters
    # -----------------------------------------------------------
    MAX_POSITION_SIZE_PCT: float = float(os.getenv("MAX_POSITION_SIZE_PCT", "0.05"))
    MAX_PORTFOLIO_RISK_PCT: float = float(os.getenv("MAX_PORTFOLIO_RISK_PCT", "0.02"))
    DEFAULT_STOP_LOSS_PCT: float = float(os.getenv("DEFAULT_STOP_LOSS_PCT", "0.02"))

    # -----------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------
    SIGNAL_CONFIDENCE_THRESHOLD: float = float(os.getenv("SIGNAL_CONFIDENCE_THRESHOLD", "0.70"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()
