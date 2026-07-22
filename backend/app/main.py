import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.redis import get_redis, close_redis
from app.routes import (
    health_router, signals_router, stocks_router, portfolio_router,
    reports_router, scanner_router, pipeline_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("AlphaSight backend starting — env=%s", settings.ENVIRONMENT)

    # Create tables on startup (graceful — DB is optional for paper trading)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database connected and tables ready")
    except Exception:
        logger.warning("Database unavailable — running without persistence (paper mode OK)")

    # Warm up Redis connection (graceful)
    try:
        await get_redis()
        logger.info("Redis connected")
    except Exception:
        logger.warning("Redis unavailable — running without cache")

    # ── Auto-start the pipeline loop ─────────────────────────────
    if settings.AUTO_START_PIPELINE:
        from app.engines.orchestrator import get_orchestrator
        logger.info(
            "AUTO_START_PIPELINE=TRUE — starting pipeline loop (interval=%ds, "
            "auto_execute=%s, score_threshold=%s)",
            settings.PIPELINE_INTERVAL_SECONDS,
            "ON" if settings.AUTO_EXECUTE else "OFF",
            settings.SCORE_THRESHOLD,
        )
        get_orchestrator().start()
    else:
        logger.info("AUTO_START_PIPELINE=FALSE — pipeline must be started manually")

    yield

    # Shutdown
    logger.info("AlphaSight backend shutting down")
    try:
        from app.engines.orchestrator import get_orchestrator
        get_orchestrator().stop()
    except Exception:
        pass
    try:
        await close_redis()
    except Exception:
        pass
    try:
        await engine.dispose()
    except Exception:
        pass


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
    app.include_router(pipeline_router, prefix="/api/v1")

    return app


app = create_app()
