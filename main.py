import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import ai_instructions, health, auth, users, api_keys, ssh_keys, folders, assets, artifacts, public, settings, themes, ws, feed, repos, git_http
from routers.repos import _internal_router
from services import events
import routers.ws as ws_router

app = FastAPI(
    title="Agent Espacio API",
    description="Self-hosted collaborative workspace for AI agents and humans",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ai_instructions.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(ssh_keys.router)
app.include_router(api_keys.router)
app.include_router(folders.router)
app.include_router(assets.router)
app.include_router(artifacts.router)
app.include_router(public.router)
app.include_router(settings.router)
app.include_router(themes.router)
app.include_router(feed.router)
app.include_router(repos.router)
app.include_router(repos._internal_router)
app.include_router(git_http.router)
app.include_router(ws.router)

# Serve published static sites
import os
from fastapi.responses import FileResponse, RedirectResponse

PUBLISHED_DIR = os.environ.get("STORAGE_PATH", "/app/storage") + "/published"
os.makedirs(PUBLISHED_DIR, exist_ok=True)

# Create a sync DB session factory for static file serving
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.artifact import Artifact

_db_url = os.environ.get("DATABASE_URL", "postgresql://agentespacio:agentespacio@db:5432/agentespacio_db")
_sync_engine = create_engine(_db_url, pool_pre_ping=True)
_SyncSession = sessionmaker(bind=_sync_engine)

# In-memory cache: slug -> artifact_id (populated on first request)
_slug_cache: dict[str, str] = {}


@app.get("/published/{slug}/{full_path:path}")
async def serve_published_site(slug: str, full_path: str):
    """Serve published static site files."""
    artifact_id = _slug_cache.get(slug)

    if not artifact_id:
        db = _SyncSession()
        try:
            artifacts = db.query(Artifact).filter(
                Artifact.type == "repo",
                Artifact.is_public == True,
            ).all()
            for art in artifacts:
                pub = (art.meta or {}).get("publish", {})
                if pub.get("slug") == slug and pub.get("enabled"):
                    artifact_id = str(art.id)
                    _slug_cache[slug] = artifact_id
                    break
        finally:
            db.close()

    if not artifact_id:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=404, detail="Site not found")

    file_path = os.path.join(PUBLISHED_DIR, artifact_id, full_path)
    if not os.path.isfile(file_path):
        index_path = os.path.join(PUBLISHED_DIR, artifact_id, "index.html")
        if os.path.isfile(index_path):
            file_path = index_path
        else:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)


@app.head("/published/{slug}/{full_path:path}")
async def serve_published_site_head(slug: str, full_path: str):
    """HEAD support for published static files."""
    artifact_id = _slug_cache.get(slug)
    if not artifact_id:
        db = _SyncSession()
        try:
            artifacts = db.query(Artifact).filter(
                Artifact.type == "repo",
                Artifact.is_public == True,
            ).all()
            for art in artifacts:
                pub = (art.meta or {}).get("publish", {})
                if pub.get("slug") == slug and pub.get("enabled"):
                    artifact_id = str(art.id)
                    _slug_cache[slug] = artifact_id
                    break
        finally:
            db.close()

    if not artifact_id:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=404, detail="Site not found")

    file_path = os.path.join(PUBLISHED_DIR, artifact_id, full_path)
    if not os.path.isfile(file_path):
        index_path = os.path.join(PUBLISHED_DIR, artifact_id, "index.html")
        if os.path.isfile(index_path):
            file_path = index_path
        else:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(status_code=404, detail="File not found")

    from starlette.responses import Response
    stat = os.stat(file_path)
    return Response(
        headers={
            "content-length": str(stat.st_size),
            "content-type": "text/html; charset=utf-8" if file_path.endswith(".html") else "application/octet-stream",
            "last-modified": str(stat.st_mtime),
        }
    )


@app.get("/published/{slug}")
async def serve_published_root(slug: str):
    """Redirect /published/{slug} -> /published/{slug}/ for correct relative URL resolution."""
    return RedirectResponse(url=f"/published/{slug}/")

# Start event listener on startup
@app.on_event("startup")
async def startup_event():
    try:
        ws_router._loop = asyncio.get_event_loop()
    except Exception as e:
        print(f"[STARTUP] Failed to get event loop: {e}", flush=True)
    try:
        events.start_event_listener()
        print("[STARTUP] Event listener started", flush=True)
    except Exception as e:
        print(f"[STARTUP] Failed to start event listener: {e}", flush=True)
    


@app.get("/")
async def root():
    return {
        "message": "Agent Espacio API",
        "version": "0.1.0",
        "docs": "/docs"
    }
