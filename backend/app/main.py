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

# CORS — permissive for development, restrict in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.kb import router as kb_router
from app.api.leads import router as leads_router
from app.api.vapi import router as vapi_router
from app.api.realtime import router as realtime_router
from app.api.gemini import router as gemini_router
from app.api.providers import router as providers_router
from app.api.agent import router as agent_router

app.include_router(kb_router, prefix="/api/v1/kb", tags=["Knowledge Base"])
app.include_router(kb_router, prefix="/kb", tags=["Knowledge Base (Vapi)"])
app.include_router(leads_router, prefix="/api/v1/leads", tags=["Leads"])
app.include_router(vapi_router, prefix="/api/v1/vapi", tags=["Vapi Integration"])
app.include_router(vapi_router, prefix="/vapi", tags=["Vapi Integration Alias"])
app.include_router(gemini_router, prefix="/api/v1/gemini", tags=["Gemini Live Fallback"])
app.include_router(providers_router, prefix="/api/v1/providers", tags=["Provider Strategy"])
app.include_router(realtime_router, prefix="/api/v1/realtime", tags=["Realtime Call Intelligence"])
app.include_router(realtime_router, tags=["Realtime WebSocket"])
app.include_router(agent_router, prefix="/api/v1/agent", tags=["Voice Agent"])

from fastapi.staticfiles import StaticFiles
from pathlib import Path

voice_frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "voice"
if voice_frontend_dir.exists():
    app.mount("/voice", StaticFiles(directory=str(voice_frontend_dir), html=True), name="voice")

insights_frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "insights"
if insights_frontend_dir.exists():
    app.mount("/insights", StaticFiles(directory=str(insights_frontend_dir), html=True), name="insights")




@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Service health check endpoint.

    Returns service status and configuration summary.
    No secrets are exposed.
    """
    config = get_config()

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "environment": config.env,
        "services": {
            "openai": {
                "configured": bool(config.openai.api_key),
                "embedding_model": config.openai.embedding_model,
                "llm_model": config.openai.llm_model,
            },
            "vapi": {
                "configured": bool(config.vapi.api_key),
            },
            "deepgram": {
                "configured": bool(config.deepgram.api_key),
            },
            "elevenlabs": {
                "configured": bool(config.elevenlabs.api_key),
            },
            "gemini": {
                "configured": bool(config.gemini.api_key),
                "text_model": config.gemini.text_model,
                "live_model": config.gemini.live_model,
            },
            "groq": {
                "configured": bool(config.groq.api_key),
                "model": config.groq.model,
            },
            "openrouter": {
                "configured": bool(config.openrouter.api_key),
                "model": config.openrouter.model,
            },
            "hf_local": {
                "available": config.hf.local_enabled,
            },
            "qdrant": {
                "url": config.qdrant.url,
                "configured": True,
            },
        },
    }

