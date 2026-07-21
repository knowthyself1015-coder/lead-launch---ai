from app.routes.health import router as health_router
from app.routes.signals import router as signals_router
from app.routes.stocks import router as stocks_router
from app.routes.portfolio import router as portfolio_router
from app.routes.reports import router as reports_router
from app.routes.scanner import router as scanner_router
from app.routes.notifications import router as notifications_router

__all__ = [
    "health_router",
    "signals_router",
    "stocks_router",
    "portfolio_router",
    "reports_router",
    "scanner_router",
    "notifications_router",
]
