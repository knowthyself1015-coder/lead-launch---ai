import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.redis import get_redis, close_redis
from app.routes import health_router, signals_router, stocks_router, portfolio_router, reports_router, scanner_router, sentiment_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info(f"AlphaSight backend starting — env={settings.ENVIRONMENT}")

    # Create tables on startup (dev convenience; use Alembic migrations in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Warm up Redis connection
    await get_redis()

    yield

    # Shutdown
    logger.info("AlphaSight backend shutting down")
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AlphaSight",
        description="AI Stock Trading Agent — Backend API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers under /api/v1
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(signals_router, prefix="/api/v1")
    app.include_router(stocks_router, prefix="/api/v1")
    app.include_router(portfolio_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(scanner_router, prefix="/api/v1")
    app.include_router(sentiment_router, prefix="/api/v1")

    return app


app = create_app()
