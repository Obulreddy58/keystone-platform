"""
Self-Service Infrastructure Platform
Frontend dashboard + API layer + Jira webhook handler.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import structlog

from app.config import settings
from app.database import close_db, init_db
from app.routers import accounts, admin, api, argocd, auth, health, upgrades, webhooks, ws

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables. Shutdown: close DB pool."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="Infrastructure Self-Service Platform",
    description="Dashboard + API for self-service infrastructure provisioning",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(webhooks.router)
app.include_router(api.router)
app.include_router(accounts.router)
app.include_router(upgrades.router)
app.include_router(argocd.router)
app.include_router(admin.router)
app.include_router(ws.router)

# Serve static frontend
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the dashboard SPA."""
    return FileResponse(str(STATIC_DIR / "index.html"))
