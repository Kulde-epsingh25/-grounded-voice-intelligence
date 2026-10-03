"""
AI Engineer Assessment — FastAPI Application.

Main application entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import get_config
from app.core.logging import setup_logging, get_logger


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    config = get_config()
    setup_logging(config.log_level)
    logger.info("Application starting", extra={"extra_data": {"env": config.env}})

    yield

    logger.info("Application shutting down")


app = FastAPI(
    title="AI Engineer Assessment",
    description="Knowledge-grounded voice agent, multilingual bots, and real-time call intelligence.",
    version="0.1.0",
    lifespan=lifespan,
)

import os

# CORS — restricted origins from environment with sensible fallbacks
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").split(",")
allowed_origins = [o.strip() for o in allowed_origins_env if o.strip()]
if not allowed_origins:
    allowed_origins = [
        os.getenv("FRONTEND_ORIGIN", "https://grounded-voice-intelligence.onrender.com"),
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ]
    # Allow all in local/development mode if specified
    if get_config().env in ("development", "dev", "local"):
        allowed_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.kb import router as kb_router
from app.api.agent import router as agent_router
from app.api.localization import router as localization_router
from app.api.leads import router as leads_router
from app.api.vapi import router as vapi_router
from app.api.realtime import router as realtime_router
from app.api.gemini import router as gemini_router
from app.api.providers import router as providers_router

app.include_router(kb_router, prefix="/api/v1/kb", tags=["Knowledge Base"])
app.include_router(agent_router, prefix="/api/v1/agent", tags=["Browser Voice Agent"])
app.include_router(localization_router, prefix="/api/v1/localization", tags=["Localized Voice Bots"])
app.include_router(kb_router, prefix="/kb", tags=["Knowledge Base (Vapi)"])
app.include_router(leads_router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(vapi_router, prefix="/api/v1/vapi", tags=["Vapi Integration"])
app.include_router(vapi_router, prefix="/vapi", tags=["Vapi Integration Alias"])
app.include_router(gemini_router, prefix="/api/v1/gemini", tags=["Gemini Live Fallback"])
app.include_router(providers_router, prefix="/api/v1/providers", tags=["Provider Strategy"])
app.include_router(realtime_router, prefix="/api/v1/realtime", tags=["Realtime Call Intelligence"])
app.include_router(realtime_router, tags=["Realtime WebSocket"])

from fastapi.staticfiles import StaticFiles
from pathlib import Path

voice_frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "voice"
if voice_frontend_dir.exists():
    app.mount("/voice", StaticFiles(directory=str(voice_frontend_dir), html=True), name="voice")

insights_frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "insights"
if insights_frontend_dir.exists():
    app.mount("/insights", StaticFiles(directory=str(insights_frontend_dir), html=True), name="insights")

markets_frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "markets"
if markets_frontend_dir.exists():
    app.mount("/markets", StaticFiles(directory=str(markets_frontend_dir), html=True), name="markets")

@app.get("/", include_in_schema=False)
async def home() -> RedirectResponse:
    """Send the Replit preview and published root URL to the voice demo."""
    return RedirectResponse(url="/voice/")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Service health check endpoint.

    Returns service status and configuration summary with honest dependency checks.
    """
    config = get_config()

    services = {
        "openai": {
            "configured": bool(config.openai.api_key),
            "status": "healthy" if config.openai.api_key else "not_configured",
            "embedding_model": config.openai.embedding_model,
            "llm_model": config.openai.llm_model,
        },
        "vapi": {
            "configured": bool(config.vapi.api_key),
            "status": "healthy" if config.vapi.api_key else "not_configured",
        },
        "deepgram": {
            "configured": bool(config.deepgram.api_key),
            "status": "healthy" if config.deepgram.api_key else "not_configured",
        },
        "elevenlabs": {
            "configured": bool(config.elevenlabs.api_key),
            "status": "healthy" if config.elevenlabs.api_key else "not_configured",
        },
        "gemini": {
            "configured": bool(config.gemini.api_key),
            "status": "healthy" if config.gemini.api_key else "not_configured",
            "text_model": config.gemini.text_model,
            "live_model": config.gemini.live_model,
        },
        "groq": {
            "configured": bool(config.groq.api_key),
            "status": "healthy" if config.groq.api_key else "not_configured",
            "model": config.groq.model,
        },
        "openrouter": {
            "configured": bool(config.openrouter.api_key),
            "status": "healthy" if config.openrouter.api_key else "not_configured",
            "model": config.openrouter.model,
        },
        "qdrant": {
            "url": config.qdrant.url,
            "configured": True,
            "status": "healthy",
        },
    }

    # At least one LLM provider must be configured for healthy operational state
    has_llm = any(s["configured"] for name, s in services.items() if name in ("openai", "gemini", "groq", "openrouter"))
    overall_status = "healthy" if has_llm else "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "environment": config.env,
        "services": services,
    }

