"""
SSH Keys router.

Endpoints for managing SSH public keys used for git repository access:
- POST /ssh-keys - Register a new SSH key
- GET /ssh-keys - List current user's SSH keys
- DELETE /ssh-keys/{key_id} - Remove an SSH key

Keys are stored in the database and queried directly by the git container's
AuthorizedKeysCommand for SSH authentication.
"""
import base64
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies.dependencies import get_db, require_user
from models.user import User
from models.repo_ssh_key import RepoSshKey
from types_definitions.ssh_key import (
    AddSshKeyRequest,
    SshKeyResponse,
    SshKeyListResponse,
    DeleteSshKeyResponse,
)

router = APIRouter(
    prefix="/ssh-keys",
    tags=["SSH Keys"],
    responses={404: {"description": "Not found"}}
)


def _compute_fingerprint(public_key: str) -> str:
    """Compute SHA256 fingerprint of an OpenSSH public key."""
    parts = public_key.strip().split()
    if len(parts) < 2:
        raise ValueError("Invalid public key format")
    key_data = parts[1]
    try:
        key_bytes = base64.b64decode(key_data)
        digest = hashlib.sha256(key_bytes).digest()
        fingerprint = base64.b64encode(digest).rstrip(b"=").decode()
        return f"SHA256:{fingerprint}"
    except Exception:
        raise ValueError("Could not parse public key")


@router.post(
    "",
    response_model=SshKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register SSH key",
    description="Add an SSH public key for git repository access. The git container queries the database directly to authenticate push/pull operations.",
)
async def add_ssh_key(
    request: AddSshKeyRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    try:
        fingerprint = _compute_fingerprint(request.public_key)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    existing = db.query(RepoSshKey).filter(
        RepoSshKey.user_id == current_user.id,
        RepoSshKey.fingerprint == fingerprint
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This SSH key is already registered"
        )

    ssh_key = RepoSshKey(
        user_id=current_user.id,
        name=request.name,
        public_key=request.public_key.strip(),
        fingerprint=fingerprint,
    )
    db.add(ssh_key)
    db.commit()
    db.refresh(ssh_key)

    return SshKeyResponse(
        id=ssh_key.id,
        name=ssh_key.name,
        fingerprint=ssh_key.fingerprint,
        created_at=ssh_key.created_at.isoformat() if ssh_key.created_at else "",
    )


@router.get(
    "",
    response_model=SshKeyListResponse,
    summary="List SSH keys",
    description="List all SSH keys registered by the current authenticated user.",
)
async def list_ssh_keys(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    keys = db.query(RepoSshKey).filter(
        RepoSshKey.user_id == current_user.id
    ).all()

    return SshKeyListResponse(
        keys=[
            SshKeyResponse(
                id=k.id,
                name=k.name,
                fingerprint=k.fingerprint,
                created_at=k.created_at.isoformat() if k.created_at else "",
            )
            for k in keys
        ],
        total=len(keys),
    )


@router.delete(
    "/{key_id}",
    response_model=DeleteSshKeyResponse,
    summary="Delete SSH key",
    description="Remove a registered SSH key. Users can only delete their own keys.",
)
async def delete_ssh_key(
    key_id: int,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    key = db.query(RepoSshKey).filter(
        RepoSshKey.id == key_id,
        RepoSshKey.user_id == current_user.id
    ).first()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SSH key not found"
        )

    db.delete(key)
    db.commit()

    return DeleteSshKeyResponse(deleted_key_id=key_id)
