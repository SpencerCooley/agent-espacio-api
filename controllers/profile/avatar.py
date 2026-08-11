"""
Profile avatar upload controller.

Handles avatar upload using derivative files (like gallery covers).
Avatars are stored in STORAGE_PATH/derived/avatars/ without creating Asset records.
"""
import os
import shutil
from uuid import uuid4
from PIL import Image

from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from models import Profile, User

# Avatar storage - derivative files, not Assets
STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
AVATARS_DIR = os.path.join(STORAGE_PATH, "derived", "avatars")

# Avatar thumbnail sizes
AVATAR_SIZES = [128, 256, 512]


def _ensure_avatars_dir():
    """Ensure avatars directory exists."""
    os.makedirs(AVATARS_DIR, exist_ok=True)


def _get_avatar_path(user_id: int, size: int = 256) -> str:
    """Get filesystem path for an avatar file."""
    return os.path.join(AVATARS_DIR, f"{user_id}_{size}.webp")


def _process_avatar(input_path: str, user_id: int) -> dict:
    """
    Process uploaded image into multiple avatar sizes.
    
    Returns dict of size -> filepath
    """
    _ensure_avatars_dir()
    
    results = {}
    
    with Image.open(input_path) as img:
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGBA')
            # Create white background for transparency
            background = Image.new('RGBA', img.size, (255, 255, 255))
            img = Image.alpha_composite(background, img).convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        for size in AVATAR_SIZES:
            output_path = _get_avatar_path(user_id, size)
            
            # Resize maintaining aspect ratio, then crop to square
            img_copy = img.copy()
            
            # Use thumbnail to resize within bounds
            img_copy.thumbnail((size, size), Image.LANCZOS)
            
            # Create square canvas and paste centered
            square = Image.new('RGB', (size, size), (255, 255, 255))
            
            # Calculate paste position to center
            x = (size - img_copy.width) // 2
            y = (size - img_copy.height) // 2
            
            square.paste(img_copy, (x, y))
            square.save(output_path, 'WEBP', quality=85)
            
            results[size] = output_path
    
    return results


def upload_avatar(db: Session, user: User, file: UploadFile) -> Profile:
    """
    Upload a new avatar for a user.
    
    Processes the image into multiple sizes and stores as derivative files.
    Old avatars are overwritten.
    
    Args:
        db: Database session
        user: User object
        file: Uploaded image file
        
    Returns:
        Updated Profile object
        
    Raises:
        HTTPException: If file is not an image or upload fails
    """
    # Validate file is an image
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Avatar must be an image file"
        )
    
    # Get user's profile (create if missing)
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
        db.flush()
    
    # Read file content and save to temp location
    import tempfile
    temp_path = None
    
    try:
        # Read the uploaded file content
        file.file.seek(0)
        content = file.file.read()
        
        # Create temp file with the content
        fd, temp_path = tempfile.mkstemp(suffix=".tmp")
        try:
            os.write(fd, content)
        finally:
            os.close(fd)
        
        # Process into avatar sizes
        _process_avatar(temp_path, user.id)
        
        # Mark avatar as present
        profile.avatar_user_id = user.id
        db.commit()
        db.refresh(profile)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process avatar: {str(e)}"
        )
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
    
    return profile


def get_avatar_url(user_id: int, size: int = 256) -> str:
    """
    Get the URL path for a user's avatar with cache-busting timestamp.
    
    Returns None if avatar doesn't exist.
    """
    path = _get_avatar_path(user_id, size)
    if os.path.exists(path):
        mtime = int(os.path.getmtime(path))
        return f"/profiles/avatar/{user_id}/{size}?v={mtime}"
    return None


def delete_avatar(user_id: int):
    """Delete all avatar files for a user."""
    for size in AVATAR_SIZES:
        path = _get_avatar_path(user_id, size)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
