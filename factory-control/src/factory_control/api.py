"""Minimal HTTP API for factory-control (E2E smoke-test compatibility).

Exposes:
    GET /health  — service health check
    GET /        — service info
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from factory_control import __version__

logger = logging.getLogger("factory_control.api")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    service: str = "factory-control"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Factory-control API started (version=%s)", __version__)
    yield
    logger.info("Factory-control API shutting down")


app = FastAPI(
    title="Factory Control API",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, service="factory-control")


@app.get("/")
async def root() -> dict:
    return {
        "service": "factory-control",
        "version": __version__,
        "endpoints": ["/health"],
    }
