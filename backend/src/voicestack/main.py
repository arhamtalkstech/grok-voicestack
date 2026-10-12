from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from voicestack import __version__
from voicestack.config import PROJECT_ROOT, get_settings
from voicestack.db.models import Agent
from voicestack.db.session import init_db, session_scope
from voicestack.runtime.bus import bus
from voicestack.runtime.persistence import close_persistence, open_persistence
from voicestack.security.auth import require_user
from voicestack.tools.plugins import load_plugins

log = logging.getLogger("voicestack")
EXAMPLE = PROJECT_ROOT / "examples" / "landscapes" / "front-desk.yaml"


async def seed_example() -> None:
    settings = get_settings()
    if not settings.seed_example or not EXAMPLE.exists():
        return
    async with session_scope() as db:
        if (await db.execute(select(func.count()).select_from(Agent))).scalar():
            return
        from voicestack.api.landscape import import_landscape

        result = await import_landscape(db, yaml.safe_load(EXAMPLE.read_text()))
        log.info("Seeded example landscape: %s", result)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()
    await open_persistence()
    load_plugins()
    await seed_example()
    log.info("Voice Stack %s ready (role=%s, auth=%s)", __version__, settings.role, settings.auth_mode)
    yield
    for live in list(bus.sessions.values()):
        await live.controller.end("server_shutdown")
    await close_persistence()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Voice Stack", version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        try:
            async with session_scope() as db:
                await db.execute(select(1))
        except Exception as exc:
            return JSONResponse({"status": "unavailable", "error": str(exc)}, status_code=503)
        return JSONResponse({"status": "ready", "live_sessions": len(bus.sessions)})

    from voicestack.api import agents, conversations, integrations, knowledge, landscape, sessions, telephony, voices
    from voicestack.api import settings as settings_api

    if settings.serves_telephony:
        app.include_router(telephony.webhook_router)
    if settings.serves_app:
        guarded = [Depends(require_user)]
        for module in (agents, landscape, integrations, knowledge, voices, conversations, settings_api):
            app.include_router(module.router, dependencies=guarded)
        app.include_router(telephony.router, dependencies=guarded)
        app.include_router(sessions.router, dependencies=guarded)
        app.include_router(sessions.ws_router)  # WebSockets authenticate inside the handler
        _mount_spa(app, settings.static_dir or PROJECT_ROOT / "frontend" / "dist")
    return app


def _mount_spa(app: FastAPI, dist: Path) -> None:
    if not (dist / "index.html").exists():
        return
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "webhooks/")):
            raise HTTPException(404, "Not found")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
