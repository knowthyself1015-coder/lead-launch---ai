import logging

from fastapi import APIRouter

from app.schemas import HealthResponse, HealthReadyResponse
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check():
    """Service health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
    )


@router.get("/health/ready", response_model=HealthReadyResponse, tags=["system"])
async def health_ready():
    """Readiness check — verifies Alpaca API keys work."""
    settings = get_settings()
    checks: dict[str, str] = {}

    # --- Check Alpaca ---
    if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
        checks["alpaca"] = "missing"
    else:
        try:
            import httpx
            async with httpx.AsyncClient(
                base_url=settings.ALPACA_BASE_URL,
                timeout=httpx.Timeout(10.0),
                headers={
                    "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
                    "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
                },
            ) as client:
                resp = await client.get("/v2/account")
                if resp.status_code == 200:
                    checks["alpaca"] = "ok"
                elif resp.status_code == 401:
                    checks["alpaca"] = "invalid"
                else:
                    checks["alpaca"] = f"error_{resp.status_code}"
        except Exception as exc:
            logger.warning("Alpaca readiness check failed: %s", exc)
            checks["alpaca"] = "invalid"

    ready = all(v == "ok" for v in checks.values())

    return HealthReadyResponse(
        ready=ready,
        checks=checks,
    )
