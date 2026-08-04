"""
File storage service for managing asset files on disk.

Handles file uploads, downloads, deletions, and storage path management.
All files are stored with ID-based naming for easy correlation with database records.
"""
import os
import shutil
import mimetypes
import threading
from pathlib import Path
from typing import Optional, Tuple
from uuid import UUID

# Configuration
STORAGE_PATH = os.environ.get("STORAGE_PATH", "/app/storage")
ASSETS_DIR = os.path.join(STORAGE_PATH, "assets")
TEMP_DIR = os.path.join(STORAGE_PATH, "temp")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def ensure_directories():
    """Ensure storage directories exist. Called on startup."""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Removes dangerous characters and limits length.
    """
    # Remove path separators and null bytes
    filename = filename.replace("/", "_").replace("\\", "_").replace("\x00", "")
    
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) > 31)
    
    # Strip leading/trailing dots and spaces
    filename = filename.strip(". ")
    
    # Limit length to 200 chars (leave room for UUID prefix)
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200 - len(ext)] + ext
    
    # If empty after sanitization, use a default
    if not filename:
        filename = "unnamed_file"
    
    return filename


def get_mime_type(filename: str, file_content: Optional[bytes] = None) -> str:
    """
    Detect MIME type from filename and optionally file content.
    
    Returns a sensible default if type cannot be determined.
    """
    # Try to guess from filename
    mime_type, _ = mimetypes.guess_type(filename)
    
    if mime_type:
        return mime_type
    
    # Fallback based on extension
    ext = Path(filename).suffix.lower()
    fallback_types = {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".json": "application/json",
        ".txt": "text/plain",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
    }
    
    return fallback_types.get(ext, "application/octet-stream")


def generate_storage_filename(asset_id: UUID, original_filename: str) -> str:
    """
    Generate the storage filename format: {uuid}_{sanitized_name}
    
    This makes it easy to correlate files on disk with database records.
    """
    sanitized = sanitize_filename(original_filename)
    return f"{asset_id}_{sanitized}"


def parse_storage_filename(storage_filename: str) -> Tuple[Optional[UUID], str]:
    """
    Parse a storage filename to extract the asset ID and original name.
    
    Returns (asset_id, original_name) or (None, storage_filename) if parsing fails.
    """
    try:
        # Find first underscore
        if "_" not in storage_filename:
            return None, storage_filename
        
        uuid_str, original_name = storage_filename.split("_", 1)
        asset_id = UUID(uuid_str)
        return asset_id, original_name
    except (ValueError, IndexError):
        return None, storage_filename


def get_asset_path(storage_filename: str) -> str:
    """Get the full filesystem path for an asset file."""
    return os.path.join(ASSETS_DIR, storage_filename)


def get_temp_path(filename: str) -> str:
    """Get a path for a temporary file during upload."""
    return os.path.join(TEMP_DIR, sanitize_filename(filename))


def save_uploaded_file(temp_path: str, storage_filename: str) -> str:
    """
    Move an uploaded file from temp to the assets directory.
    
    Args:
        temp_path: Path to the temporary uploaded file
        storage_filename: Target filename in assets directory
    
    Returns:
        Full path to the saved file
    
    Raises:
        FileNotFoundError: If temp file doesn't exist
        IOError: If move fails
    """
    if not os.path.exists(temp_path):
        raise FileNotFoundError(f"Temporary file not found: {temp_path}")
    
    dest_path = get_asset_path(storage_filename)
    
    # Ensure assets directory exists
    os.makedirs(ASSETS_DIR, exist_ok=True)
    
    # Move file from temp to assets
    shutil.move(temp_path, dest_path)
    
    return dest_path


def delete_file(storage_filename: str) -> bool:
    """
    Delete an asset file from disk.
    
    Args:
        storage_filename: The storage filename to delete
    
    Returns:
        True if file was deleted or didn't exist
        False if deletion failed
    """
    file_path = get_asset_path(storage_filename)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except OSError:
        return False


def get_file_size(storage_filename: str) -> Optional[int]:
    """
    Get the size of an asset file in bytes.
    
    Returns None if file doesn't exist.
    """
    file_path = get_asset_path(storage_filename)
    
    try:
        return os.path.getsize(file_path)
    except OSError:
        return None


def file_exists(storage_filename: str) -> bool:
    """Check if an asset file exists on disk."""
    return os.path.exists(get_asset_path(storage_filename))


def read_file(storage_filename: str, chunk_size: int = 8192):
    """
    Generator to read a file in chunks by storage filename.
    
    Useful for streaming file downloads without loading entire file into memory.
    
    Args:
        storage_filename: The storage filename to read
        chunk_size: Size of chunks to yield (default 8KB)
    
    Yields:
        File chunks as bytes
    
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = get_asset_path(storage_filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {storage_filename}")
    
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


def read_file_from_path(file_path: str, chunk_size: int = 8192):
    """
    Generator to read a file in chunks from an absolute path.
    
    Args:
        file_path: Absolute path to the file
        chunk_size: Size of chunks to yield (default 8KB)
    
    Yields:
        File chunks as bytes
    
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk


def read_text_file(storage_filename: str) -> str:
    """
    Read a text file's content by storage filename.
    
    Args:
        storage_filename: The storage filename to read
    
    Returns:
        File content as a string
    
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = get_asset_path(storage_filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {storage_filename}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(storage_filename: str, content: str) -> str:
    """
    Write text content to a file, overwriting existing content.
    
    Args:
        storage_filename: The storage filename to write
        content: Text content to write
    
    Returns:
        Full path to the written file
    """
    file_path = get_asset_path(storage_filename)
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return file_path


def cleanup_temp_files(max_age_hours: int = 24):
    """
    Clean up temporary files older than specified hours.
    
    This is useful for periodic cleanup of abandoned uploads.
    Can be called from a scheduled task.
    """
    import time
    
    if not os.path.exists(TEMP_DIR):
        return
    
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        try:
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    os.remove(file_path)
        except OSError:
            pass  # Ignore cleanup errors


def validate_file_size(size_bytes: int) -> Tuple[bool, Optional[str]]:
    """
    Validate that file size is within limits.
    
    Returns:
        (is_valid, error_message)
    """
    if size_bytes > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        return False, f"File size {actual_mb:.1f}MB exceeds maximum allowed size of {max_mb:.0f}MB"
    
    return True, None


THUMBNAIL_SIZES = [256, 512]
"""Standard thumbnail sizes (max dimension in pixels). Generated on upload for images."""


def generate_thumbnails(asset_id: UUID, source_path: str) -> tuple[dict, dict]:
    """
    Generate thumbnails for an image asset.
    
    Args:
        asset_id: The asset UUID (used for naming thumbnails)
        source_path: Path to the original image file
        
    Returns:
        Tuple of (thumbnail_meta, image_info):
        - thumbnail_meta: dict mapping size -> {w, h, size_bytes}
        - image_info: dict with {width, height, has_alpha}
    
    Only generates thumbnails if the original image is larger than the target size
    (never upscales). Skips thumbnails for non-image files silently.
    """
    try:
        from PIL import Image
    except ImportError:
        return {}, {}

    thumbnails = {}
    image_info = {}

    try:
        with Image.open(source_path) as img:
            orig_w, orig_h = img.size
            has_alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
            image_info = {"width": orig_w, "height": orig_h, "has_alpha": has_alpha}

            for size in THUMBNAIL_SIZES:
                if orig_w <= size and orig_h <= size:
                    continue

                thumb = img.copy()
                thumb.thumbnail((size, size), Image.LANCZOS)

                thumb_filename = f"{asset_id}_thumb_{size}.webp"
                thumb_path = os.path.join(ASSETS_DIR, thumb_filename)

                save_kwargs = {"quality": 85, "method": 6}
                if has_alpha:
                    thumb.save(thumb_path, "WEBP", **save_kwargs, lossless=False)
                else:
                    thumb.save(thumb_path, "WEBP", **save_kwargs)

                thumb_size = os.path.getsize(thumb_path)
                thumbnails[str(size)] = {
                    "w": thumb.width,
                    "h": thumb.height,
                    "size_bytes": thumb_size,
                }

                thumb.close()

            return thumbnails, image_info

    except Exception:
        return {}, {}


def generate_video_thumbnail(asset_id: UUID, source_path: str) -> dict:
    """
    Generate a thumbnail for a video asset by extracting a frame with ffmpeg.

    Args:
        asset_id: The asset UUID (used for naming thumbnails)
        source_path: Path to the original video file

    Returns:
        dict mapping size -> {w, h, size_bytes}

    Only generates thumbnails if the original video is larger than the target size.
    """
    import subprocess
    import json

    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}

    # Get video duration and dimensions
    try:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=duration,width,height",
                "-of", "json",
                source_path,
            ],
            capture_output=True, text=True, check=True, timeout=30
        )
        info = json.loads(probe.stdout)
        stream = info.get("streams", [{}])[0]
        duration = float(stream.get("duration", 0))
        video_width = int(stream.get("width", 0))
        video_height = int(stream.get("height", 0))
    except Exception:
        return {}

    # Choose a frame at 1 second or 10% of the video duration
    seek_time = min(1.0, duration * 0.1) if duration > 0 else 0

    thumbnails = {}

    for size in THUMBNAIL_SIZES:
        # Skip if video is smaller than target size (never upscale)
        if video_width <= size and video_height <= size:
            continue

        # Scale to fit within size x size while maintaining aspect ratio
        scale = f"scale='if(gt(iw,ih),{size},-1)':'if(gt(iw,ih),-1,{size})'"

        thumb_filename = f"{asset_id}_thumb_{size}.webp"
        thumb_path = os.path.join(ASSETS_DIR, thumb_filename)

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-ss", str(seek_time),
                    "-i", source_path,
                    "-frames:v", "1",
                    "-vf", scale,
                    "-q:v", "2",
                    thumb_path,
                ],
                capture_output=True, check=True, timeout=60
            )

            if os.path.exists(thumb_path):
                thumb_size = os.path.getsize(thumb_path)
                thumb_w, thumb_h = video_width, video_height
                # Get actual thumbnail dimensions with PIL
                try:
                    from PIL import Image
                    with Image.open(thumb_path) as thumb_img:
                        thumb_w, thumb_h = thumb_img.size
                except Exception:
                    pass

                thumbnails[str(size)] = {
                    "w": thumb_w,
                    "h": thumb_h,
                    "size_bytes": thumb_size,
                }
        except Exception:
            pass  # Skip this size if extraction fails

    return thumbnails


GLB_THUMBNAIL_BACKDROP = (120, 133, 155)
"""Neutral light-gray backdrop (RGB) composited behind GLB thumbnail renders."""

_glb_render_lock = threading.Lock()
"""Serialize GLB renders — pyrender's OffscreenRenderer holds a global EGL context."""


def _mesh_center_extent(bounds):
    """Return (center, extent) for an AABB array of shape (2, 3)."""
    if bounds is None:
        return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    center = (bounds[0] + bounds[1]) / 2.0
    extent = bounds[1] - bounds[0]
    return center, extent


def _look_at_pose(eye, target, up=(0.0, 1.0, 0.0)):
    """Build a 4x4 view pose with -Z pointing from eye toward target."""
    import numpy as np

    eye = np.asarray(eye, dtype=float)
    target = np.asarray(target, dtype=float)
    up = np.asarray(up, dtype=float)

    z = eye - target  # camera +Z points back at the eye so -Z aims at target
    norm = np.linalg.norm(z)
    if norm < 1e-9:
        z = np.array([0.0, 0.0, 1.0])
    else:
        z = z / norm

    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-9:
        x = np.array([1.0, 0.0, 0.0])
    else:
        x = x / np.linalg.norm(x)
    y = np.cross(z, x)

    pose = np.eye(4)
    pose[:3, 0] = x
    pose[:3, 1] = y
    pose[:3, 2] = z
    pose[:3, 3] = eye
    return pose


def generate_glb_thumbnail(asset_id: UUID, source_path: str) -> dict:
    """
    Generate thumbnails for a GLB/GLTF 3D asset by offscreen rendering.

    Args:
        asset_id: The asset UUID (used for naming thumbnails)
        source_path: Path to the original GLB/GLTF file

    Returns:
        dict mapping size -> {w, h, size_bytes}

    Renders the mesh once at 512x512 with pyrender (EGL + Mesa software
    rendering), composites onto a neutral gray backdrop, then downscales to
    256. Returns an empty dict if the renderer is unavailable or rendering
    fails (silent fallback, matching the image/video thumbnail behavior).
    """
    try:
        import numpy as np
        import trimesh
        import pyrender
        from PIL import Image, ImageFilter
    except Exception:
        return {}

    try:
        with _glb_render_lock:
            loaded = trimesh.load(source_path, process=False)

            scene = pyrender.Scene()
            if isinstance(loaded, trimesh.Scene):
                # dump() returns copies of each geometry baked to its instance
                # (world) transform, preserving per-mesh materials/textures.
                geometries = loaded.dump()
                bounds = loaded.bounds
            else:
                geometries = [loaded]
                bounds = loaded.bounds

            for geom in geometries:
                if geom is None or len(geom.vertices) == 0:
                    continue
                scene.add(pyrender.Mesh.from_trimesh(geom, smooth=True))

            renderer = pyrender.OffscreenRenderer(512, 512)
            try:
                # Key light from above-front
                light_dir = np.array([1.0, 1.5, 1.0])
                light_dir = light_dir / np.linalg.norm(light_dir)
                light_pose = _look_at_pose(-light_dir, np.zeros(3))
                scene.add(
                    pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=1.0),
                    pose=light_pose,
                )

                # Soft fill from the opposite side
                fill_pose = _look_at_pose(light_dir, np.zeros(3))
                scene.add(
                    pyrender.DirectionalLight(color=[0.55, 0.6, 0.7], intensity=0.5),
                    pose=fill_pose,
                )

                # Ambient fill (pyrender has no HemisphereLight primitive; use
                # Scene.ambient_light, a scalar or 0-1 vector scalar multiplier)
                scene.ambient_light = np.array([0.18, 0.18, 0.22])

                # Fit camera to the mesh bounding box
                center, extent = _mesh_center_extent(bounds)
                radius = float(np.linalg.norm(extent))
                if radius < 1e-6:
                    radius = 1.0
                yfov = float(np.deg2rad(40))
                distance = radius / (2.0 * np.tan(yfov / 2.0)) * 1.35
                camera_pose = _look_at_pose(
                    [center[0], center[1] + distance * 0.25, center[2] + distance],
                    center,
                )
                camera = pyrender.PerspectiveCamera(yfov=yfov, aspectRatio=1.0)
                scene.add(camera, pose=camera_pose)

                color, depth = renderer.render(scene)
            finally:
                renderer.delete()

            color_arr = np.asarray(color)
            depth_arr = np.asarray(depth)

            # Build a foreground mask from the depth buffer and composite the
            # render onto the backdrop. This guarantees the model silhouette is
            # visible even for light-colored scans that the (previously white)
            # render would wash out against a light backdrop.
            rgb = color_arr[:, :, :3].astype(np.uint8)
            if depth_arr.ndim == 2 and depth_arr.size:
                # pyrender depth buffer: background is cleared to the minimum
                # (0.0), drawn model pixels are view-space depth > 0.
                fg = depth_arr > depth_arr.min() + 1e-6
                alpha = np.where(fg, 255, 0).astype(np.uint8)
            else:
                alpha = np.full((rgb.shape[0], rgb.shape[1]), 255, np.uint8)
            rgba = np.dstack([rgb, alpha])
            image = Image.fromarray(rgba, mode="RGBA")
            # Feather the alpha edge 1px so the silhouette blends onto the
            # backdrop instead of looking cut with a hard 1px halo.
            image.putalpha(image.getchannel("A").filter(ImageFilter.GaussianBlur(0.8)))
            backdrop = Image.new("RGBA", image.size, (*GLB_THUMBNAIL_BACKDROP, 255))
            img = Image.alpha_composite(backdrop, image).convert("RGB")

            thumbnails = {}
            for size in (512, 256):
                thumb = img.resize((size, size), Image.LANCZOS) if size < 512 else img
                thumb_filename = f"{asset_id}_thumb_{size}.webp"
                thumb_path = os.path.join(ASSETS_DIR, thumb_filename)
                thumb.save(thumb_path, "WEBP", quality=85, method=6)
                thumbnails[str(size)] = {
                    "w": thumb.width,
                    "h": thumb.height,
                    "size_bytes": os.path.getsize(thumb_path),
                }
            return thumbnails
    except Exception:
        return {}


def delete_thumbnails(asset_id: UUID):
    """Delete all thumbnail files for a given asset ID."""
    for size in THUMBNAIL_SIZES:
        thumb_filename = f"{asset_id}_thumb_{size}.webp"
        thumb_path = os.path.join(ASSETS_DIR, thumb_filename)
        try:
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except OSError:
            pass


def get_thumbnail_path(asset_id: UUID, size: int) -> str:
    """Get the full filesystem path for a thumbnail file."""
    thumb_filename = f"{asset_id}_thumb_{size}.webp"
    return os.path.join(ASSETS_DIR, thumb_filename)


def thumbnail_exists(asset_id: UUID, size: int) -> bool:
    """Check if a thumbnail file exists on disk."""
    return os.path.exists(get_thumbnail_path(asset_id, size))


# Range request support for streaming video/audio
def read_file_range(storage_filename: str, start: int, end: int, chunk_size: int = 8192):
    """
    Generator to read a specific byte range from a file by storage filename.
    
    Args:
        storage_filename: The storage filename to read
        start: Start byte position
        end: End byte position (inclusive)
        chunk_size: Size of chunks to yield (default 8KB)
    
    Yields:
        File chunks as bytes
    
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    file_path = get_asset_path(storage_filename)
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {storage_filename}")
    
    remaining = end - start + 1
    
    with open(file_path, "rb") as f:
        f.seek(start)
        
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def read_file_range_from_path(file_path: str, start: int, end: int, chunk_size: int = 8192):
    """
    Generator to read a specific byte range from a file at an absolute path.
    
    Args:
        file_path: Absolute path to the file
        start: Start byte position
        end: End byte position (inclusive)
        chunk_size: Size of chunks to yield (default 8KB)
    
    Yields:
        File chunks as bytes
    
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    remaining = end - start + 1
    
    with open(file_path, "rb") as f:
        f.seek(start)
        
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
