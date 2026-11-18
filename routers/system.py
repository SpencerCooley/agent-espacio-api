"""System monitoring endpoints for the current host and application storage."""
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, require_admin
from models.user import User

router = APIRouter(prefix="/system", tags=["System"])

STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
CACHE_SECONDS = 15
_cache_lock = threading.Lock()
_cache: Optional[tuple[float, dict]] = None


def _read_int(path: str) -> Optional[int]:
    try:
        value = Path(path).read_text().strip()
        parsed = int(value)
        # cgroup v1 uses this value to represent an unlimited allocation.
        return None if parsed >= (1 << 60) else parsed
    except (OSError, ValueError):
        return None


def _disk_metrics() -> dict:
    stats = os.statvfs(STORAGE_PATH)
    block_size = stats.f_frsize
    return {
        "total_bytes": stats.f_blocks * block_size,
        "used_bytes": (stats.f_blocks - stats.f_bfree) * block_size,
        "available_bytes": stats.f_bavail * block_size,
    }


def _asset_type_metrics(db: Session) -> list[dict]:
    """Sum original asset sizes, using MIME types with filename fallbacks."""
    rows = db.execute(
        text("""
            SELECT kind, SUM(size_bytes) AS size_bytes
            FROM (
                SELECT
                    CASE
                        WHEN mime_type LIKE 'image/%' THEN 'images'
                        WHEN mime_type LIKE 'video/%' THEN 'videos'
                        WHEN mime_type LIKE 'audio/%' THEN 'audio'
                        WHEN mime_type IN ('text/markdown', 'text/x-markdown')
                          OR LOWER(name) LIKE '%.md'
                          OR LOWER(name) LIKE '%.markdown' THEN 'markdown'
                        WHEN mime_type = 'application/json'
                          OR LOWER(name) LIKE '%.json' THEN 'json'
                        WHEN mime_type = 'application/pdf'
                          OR LOWER(name) LIKE '%.pdf' THEN 'pdf'
                        WHEN mime_type IN ('model/gltf-binary', 'model/gltf+json')
                          OR LOWER(name) LIKE '%.glb'
                          OR LOWER(name) LIKE '%.gltf' THEN '3d models'
                        ELSE 'other'
                    END AS kind,
                    size_bytes
                FROM assets
            ) AS categorized_assets
            GROUP BY kind
            ORDER BY size_bytes DESC
        """)
    ).mappings().all()
    return [dict(row) for row in rows]


def _database_metrics(db: Session) -> dict:
    database = db.execute(
        text("SELECT current_database() AS name, pg_database_size(current_database()) AS size_bytes")
    ).mappings().one()
    tables = db.execute(
        text("""
            SELECT c.relname AS name, pg_total_relation_size(c.oid) AS size_bytes
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
              AND c.relkind IN ('r', 'm', 'p')
            ORDER BY size_bytes DESC
            LIMIT 10
        """)
    ).mappings().all()
    return {
        "name": database["name"],
        "size_bytes": database["size_bytes"],
        "tables": [dict(row) for row in tables],
    }


def _host_metrics() -> dict:
    memory_total = None
    memory_available = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            if key == "MemTotal":
                memory_total = int(value.strip().split()[0]) * 1024
            elif key == "MemAvailable":
                memory_available = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError, IndexError):
        pass

    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        uptime_seconds = None

    return {
        "cpu_count": os.cpu_count(),
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        "uptime_seconds": uptime_seconds,
        "memory_total_bytes": memory_total,
        "memory_used_bytes": (
            memory_total - memory_available
            if memory_total is not None and memory_available is not None
            else None
        ),
    }


def _container_metrics() -> dict:
    # cgroup v2, with a cgroup v1 fallback for older hosts.
    memory_limit = _read_int("/sys/fs/cgroup/memory.max")
    memory_used = _read_int("/sys/fs/cgroup/memory.current")
    if memory_limit is None:
        memory_limit = _read_int("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if memory_used is None:
        memory_used = _read_int("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    return {
        "memory_limit_bytes": memory_limit,
        "memory_used_bytes": memory_used,
    }


def _collect_metrics(db: Session) -> dict:
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "disk": _disk_metrics(),
        "asset_types": _asset_type_metrics(db),
        "database": _database_metrics(db),
        "host": _host_metrics(),
        "container": _container_metrics(),
    }


@router.get("/monitor")
def get_system_monitor(
    current_user: Optional[User] = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return a cached snapshot of host, storage, and database metrics."""
    global _cache
    now = time.monotonic()
    with _cache_lock:
        if _cache is None or now - _cache[0] >= CACHE_SECONDS:
            _cache = (now, _collect_metrics(db))
        return _cache[1]
