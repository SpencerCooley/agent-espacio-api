"""
Git Smart HTTP Protocol backend for public repo cloning.

Implements the server-side of the git smart HTTP protocol, allowing
anonymous users to clone public repositories over HTTP/HTTPS.
"""

import os
import subprocess
from uuid import UUID

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from sqlalchemy.orm import Session

from dependencies import get_db
from models.artifact import Artifact

router = APIRouter(prefix="/git", tags=["git-http"])

STORAGE_PATH = os.environ.get("STORAGE_PATH", "/data")

# Allow git to operate on repos owned by different users (git container vs API container)
subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], capture_output=True)


def _repo_path(repo_id: str) -> str:
    return os.path.join(STORAGE_PATH, "repos", f"{repo_id}.git")


def _check_public_repo(repo_id: str, db: Session) -> Artifact:
    try:
        artifact_id = UUID(repo_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid repository ID")

    artifact = db.query(Artifact).filter(Artifact.id == artifact_id).first()
    if not artifact or artifact.type != "repo":
        raise HTTPException(status_code=404, detail="Repository not found")
    if not artifact.is_public:
        raise HTTPException(status_code=404, detail="Repository not found")
    return artifact


def _ensure_repo_on_disk(repo_id: str) -> str:
    repo_path = _repo_path(repo_id)
    if not os.path.isdir(repo_path):
        raise HTTPException(status_code=404, detail="Repository not found on disk")
    return repo_path


@router.get("/{repo_id}.git/info/refs")
async def info_refs(repo_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Discovery endpoint for both smart and dumb HTTP.

    Smart: GET /repo.git/info/refs?service=git-upload-pack
    Dumb:  GET /repo.git/info/refs
    """
    _check_public_repo(repo_id, db)
    service = request.query_params.get("service", "")

    if service in ("git-upload-pack", "git-receive-pack"):
        # Smart HTTP
        if service == "git-receive-pack":
            raise HTTPException(status_code=403, detail="Push over HTTP not supported. Use SSH.")

        repo_path = _ensure_repo_on_disk(repo_id)
        cmd = ["git", "upload-pack", "--stateless-rpc", "--advertise-refs", repo_path]
        result = subprocess.run(cmd, capture_output=True, timeout=30)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Failed to read repository refs: {result.stderr.decode(errors='replace').strip()}")

        svc_header = f"001e# service={service}\n".encode()
        flush = b"0000"
        content = svc_header + flush + result.stdout

        return Response(
            content=content,
            media_type=f"application/x-{service}-advertisement",
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        )
    else:
        # Dumb HTTP fallback
        repo_path = _ensure_repo_on_disk(repo_id)
        cmd = ["git", "for-each-ref", "--format=%(objectname) %(refname)"]
        result = subprocess.run(cmd, capture_output=True, timeout=30, cwd=repo_path)

        output = b"# pack-refs changed: fully\n"
        for line in result.stdout.splitlines():
            parts = line.split(b" ", 1)
            if len(parts) == 2:
                output += parts[0][:20].hex().encode() + b" " + parts[1] + b"\n"

        return Response(content=output, media_type="text/plain")


@router.post("/{repo_id}.git/git-upload-pack")
async def git_upload_pack(repo_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Smart HTTP clone/fetch. Client sends pkt-line wants/haves,
    server responds with packfile data.
    """
    _check_public_repo(repo_id, db)
    _ensure_repo_on_disk(repo_id)

    body = await request.body()

    cmd = ["git", "upload-pack", "--stateless-rpc", _repo_path(repo_id)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = proc.communicate(input=body, timeout=300)

    return Response(
        content=stdout,
        media_type="application/x-git-upload-pack-result",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )


@router.get("/{repo_id}.git/HEAD")
async def git_head(repo_id: str, db: Session = Depends(get_db)):
    _check_public_repo(repo_id, db)
    repo_path = _ensure_repo_on_disk(repo_id)

    head_path = os.path.join(repo_path, "HEAD")
    if not os.path.isfile(head_path):
        raise HTTPException(status_code=404, detail="HEAD not found")

    return Response(content=open(head_path, "rb").read(), media_type="text/plain")


@router.get("/{repo_id}.git/objects/info/packs")
async def git_packs(repo_id: str, db: Session = Depends(get_db)):
    _check_public_repo(repo_id, db)
    repo_path = _ensure_repo_on_disk(repo_id)

    packs_path = os.path.join(repo_path, "objects", "info", "packs")
    if not os.path.isfile(packs_path):
        return Response(content=b"", media_type="text/plain")

    return Response(content=open(packs_path, "rb").read(), media_type="text/plain")


@router.get("/{repo_id}.git/objects/{object_path:path}")
async def git_object(repo_id: str, object_path: str, db: Session = Depends(get_db)):
    _check_public_repo(repo_id, db)
    repo_path = _ensure_repo_on_disk(repo_id)

    if len(object_path) < 4:
        raise HTTPException(status_code=400, detail="Invalid object path")

    obj_file = os.path.join(repo_path, "objects", object_path[:2], object_path[2:])
    if not os.path.isfile(obj_file):
        raise HTTPException(status_code=404, detail="Object not found")

    return Response(content=open(obj_file, "rb").read(), media_type="application/x-git-loose-object")
