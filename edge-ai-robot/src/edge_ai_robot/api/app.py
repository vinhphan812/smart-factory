"""Minimal HTTP API for edge-ai-robot (E2E smoke-test compatibility).

Exposes:
    GET /health  — service health check
    GET /        — service info
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from edge_ai_robot import __version__

logger = logging.getLogger("edge_ai_robot.api")


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    service: str = "edge-ai-robot"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Edge-AI Robot API started (version=%s)", __version__)
    yield
    logger.info("Edge-AI Robot API shutting down")


app = FastAPI(
    title="Edge AI Robot API",
    version=__version__,
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, service="edge-ai-robot")


@app.get("/")
async def root() -> dict:
    return {
        "service": "edge-ai-robot",
        "version": __version__,
        "endpoints": ["/health"],
    }
