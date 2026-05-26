from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import health, auth, users, api_keys, folders, assets

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
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(folders.router)
app.include_router(assets.router)

@app.get("/")
async def root():
    return {
        "message": "Agent Espacio API",
        "version": "0.1.0",
        "docs": "/docs"
    }
