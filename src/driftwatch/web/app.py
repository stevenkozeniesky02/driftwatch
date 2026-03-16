"""FastAPI application for the DriftWatch web dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from driftwatch import __version__
from driftwatch.db import Database
from driftwatch.web.routes import create_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db: Database | None = None) -> FastAPI:
    app = FastAPI(
        title="DriftWatch",
        version=__version__,
        description="Infrastructure drift detector with predictive analysis",
    )

    if db is not None:
        app.state.db = db

    router = create_router()
    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

    return app
