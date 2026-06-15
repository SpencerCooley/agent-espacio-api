import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import ai_instructions, health, auth, users, api_keys, folders, assets, artifacts, public, settings, ws
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
app.include_router(api_keys.router)
app.include_router(folders.router)
app.include_router(assets.router)
app.include_router(artifacts.router)
app.include_router(public.router)
app.include_router(settings.router)
app.include_router(ws.router)

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
