"""
Artifacts router.

Endpoints for artifact management:
- GET /artifacts - List artifacts with optional filters
- POST /artifacts - Create a new artifact
- GET /artifacts/{artifact_id} - Get artifact metadata
- PUT /artifacts/{artifact_id} - Update artifact
- DELETE /artifacts/{artifact_id} - Delete artifact
- GET /artifacts/docs - List all artifact type definitions
- GET /artifacts/docs/{type_key} - Get specific artifact type docs
"""
from typing import Any, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from dependencies.dependencies import get_db, require_auth
from models.user import User
from types_definitions.artifact import (
    CreateArtifactRequest,
    UpdateArtifactRequest,
    ArtifactResponse,
    ArtifactListResponse,
    DeleteArtifactResponse,
    ArtifactTypeResponse,
    ArtifactTypeListResponse,
    PreviewArtifactResponse,
)
from artifact_types import get_artifact_type, list_artifact_types
import controllers
from services.events import publish_event
from controllers.settings import get_public_theme

router = APIRouter(
    prefix="/artifacts",
    tags=["Artifacts"],
    responses={404: {"description": "Not found"}}
)


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    folder_id: UUID = None,
    type: str = None,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    List artifacts with optional filters.

    - **folder_id**: Filter by parent folder
    - **type**: Filter by artifact type key (e.g., "note")
    """
    artifacts = controllers.artifact.list_artifacts(
        db=db,
        folder_id=folder_id,
        type=type
    )

    return ArtifactListResponse(artifacts=artifacts, total=len(artifacts))


@router.post("", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    request: CreateArtifactRequest,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Create a new artifact.

    - **name**: Display name
    - **type**: Artifact type key (see /artifacts/docs for available types)
    - **description**: Optional readme for AI context
    - **content**: Artifact content JSONB (structure depends on type)
    - **folder_id**: Parent folder ID
    """
    try:
        artifact = controllers.artifact.create_artifact(
            db=db,
            name=request.name,
            type=request.type,
            content=request.content,
            folder_id=request.folder_id,
            created_by=current_user,
            description=request.description,
        )
        actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
        folder_id = str(request.folder_id) if request.folder_id else "00000000-0000-0000-0000-000000000001"
        publish_event(
            event_type="artifact.created",
            folder_id=folder_id,
            resource_id=str(artifact.id),
            payload={"name": artifact.name, "type": artifact.type},
            actor=actor,
        )
        publish_event(
            event_type="folder_contents_changed",
            folder_id=folder_id,
            resource_id=str(artifact.id),
            payload={"name": artifact.name},
            actor=actor,
        )
        return artifact
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/docs", response_model=ArtifactTypeListResponse)
async def list_artifact_types_docs(
    current_user: Optional[User] = Depends(require_auth),
):
    """
    List all artifact type definitions.

    Returns documentation for every supported artifact type.
    Use this to discover what artifacts are available and how to create them.
    """
    types_data = list_artifact_types()
    types = [ArtifactTypeResponse(**t) for t in types_data]

    return ArtifactTypeListResponse(types=types, total=len(types))


@router.get("/docs/{type_key}", response_model=ArtifactTypeResponse)
async def get_artifact_type_docs(
    type_key: str,
    current_user: Optional[User] = Depends(require_auth),
):
    """
    Get documentation for a specific artifact type.

    - **type_key**: The artifact type key (e.g., "note")
    """
    type_data = get_artifact_type(type_key)

    if not type_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact type '{type_key}' not found"
        )

    return ArtifactTypeResponse(**type_data)


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get artifact metadata by ID.
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)

    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )

    return artifact


@router.put("/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    artifact_id: UUID,
    request: UpdateArtifactRequest,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Update an artifact.

    All fields are optional. Only provided fields will be updated.
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)

    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )

    try:
        original_folder_id = str(artifact.folder_id) if artifact.folder_id else "00000000-0000-0000-0000-000000000001"
        updated = controllers.artifact.update_artifact(
            db=db,
            artifact=artifact,
            name=request.name,
            type=request.type,
            description=request.description,
            content=request.content,
            folder_id=request.folder_id,
        )
        new_folder_id = str(updated.folder_id) if updated.folder_id else "00000000-0000-0000-0000-000000000001"
        
        # Emit move event if folder changed
        if request.folder_id is not None and new_folder_id != original_folder_id:
            actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
            publish_event(
                event_type="artifact.moved",
                folder_id=new_folder_id,
                resource_id=str(artifact_id),
                payload={"name": updated.name, "source_folder_id": original_folder_id},
                actor=actor,
            )
        
        return updated
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{artifact_id}", response_model=DeleteArtifactResponse)
async def delete_artifact(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Delete an artifact.

    This action cannot be undone.
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)

    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )

    folder_id = str(artifact.folder_id) if artifact.folder_id else "00000000-0000-0000-0000-000000000001"
    artifact_name = artifact.name
    controllers.artifact.delete_artifact(db, artifact)

    actor = {"type": "user", "id": str(current_user.id) if current_user else None, "name": current_user.email if current_user else None}
    publish_event(
        event_type="artifact.deleted",
        folder_id=folder_id,
        resource_id=str(artifact_id),
        payload={"name": artifact_name},
        actor=actor,
    )
    publish_event(
        event_type="folder_contents_changed",
        folder_id=folder_id,
        resource_id=str(artifact_id),
        payload={"name": artifact_name},
        actor=actor,
    )

    return DeleteArtifactResponse(deleted_artifact_id=artifact_id)


@router.post("/{artifact_id}/share", response_model=ArtifactResponse)
async def share_artifact(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Toggle public sharing for an artifact.
    
    Generates a public_magic_id when making public, clears it when making private.
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    updated = controllers.artifact.share.toggle_artifact_share(db, artifact)
    return updated


@router.get("/{artifact_id}/preview", response_model=PreviewArtifactResponse)
async def preview_artifact(
    artifact_id: UUID,
    current_user: Optional[User] = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Get artifact data formatted for preview.
    
    Returns artifact in the same format as public view, but requires authentication.
    This allows users to preview how their artifact will appear when shared publicly
    without making it public first.
    """
    artifact = controllers.artifact.get_artifact(db, artifact_id)
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found"
        )
    
    # Get public theme for accurate preview rendering
    public_theme = get_public_theme(db)
    
    return PreviewArtifactResponse(
        kind="artifact",
        artifact={
            "id": str(artifact.id),
            "name": artifact.name,
            "type": artifact.type,
            "description": artifact.description,
            "content": artifact.content,
            "public_magic_id": str(artifact.public_magic_id) if artifact.public_magic_id else str(artifact.id),
        },
        public_theme=public_theme,
    )
