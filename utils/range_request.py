"""
HTTP Range Request utilities for streaming files with seek support.

This module provides support for HTTP Range requests (RFC 7233), which allows
video and audio players to seek/scrub to arbitrary positions without downloading
the entire file first.
"""
import os
import re
from typing import Optional, Tuple
from fastapi import Request
from fastapi.responses import StreamingResponse


def parse_range_header(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """
    Parse HTTP Range header and return start/end byte positions.
    
    Supports the following range formats:
    - bytes=start-end (specific range)
    - bytes=start- (from start to end of file)
    - bytes=-end (last N bytes)
    
    Args:
        range_header: The Range header value (e.g., "bytes=0-1023")
        file_size: Total size of the file in bytes
        
    Returns:
        Tuple of (start, end) byte positions, or None if invalid/unsupported
        Start and end are inclusive (0-indexed)
    """
    if not range_header:
        return None
    
    if not range_header.startswith("bytes="):
        return None
    
    range_value = range_header[6:]  # Remove "bytes=" prefix
    
    # We only support single ranges for simplicity
    # Multiple ranges (e.g., "bytes=0-1023,2048-3071") would require multipart responses
    if "," in range_value:
        return None  # Multiple ranges not supported
    
    match = re.match(r"^(\d*)-(\d*)$", range_value)
    if not match:
        return None
    
    start_str, end_str = match.groups()
    
    if start_str and end_str:
        # Format: bytes=start-end
        start = int(start_str)
        end = min(int(end_str), file_size - 1)
    elif start_str:
        # Format: bytes=start- (from start to end of file)
        start = int(start_str)
        end = file_size - 1
    elif end_str:
        # Format: bytes=-end (last N bytes)
        suffix_length = int(end_str)
        end = file_size - 1
        start = max(0, file_size - suffix_length)
    else:
        return None
    
    # Validate range
    if start >= file_size or start > end or start < 0:
        return None
        
    return (start, end)


def create_streaming_response_with_range(
    file_path: str,
    request: Request,
    media_type: str,
    filename: str,
    read_file_func,
    read_range_func,
    chunk_size: int = 8192
) -> StreamingResponse:
    """
    Create a streaming response with HTTP Range request support.
    
    This function handles both regular streaming and HTTP range requests
    for video/audio seeking support. It automatically detects if a Range
    header is present and returns the appropriate response.
    
    Args:
        file_path: Absolute path to the file
        request: The FastAPI request object (to check for Range header)
        media_type: MIME type of the file (e.g., "video/mp4")
        filename: Original filename for Content-Disposition header
        read_file_func: Generator function to read the full file (start to end)
        read_range_func: Generator function to read a specific byte range
        chunk_size: Size of chunks for streaming (default 8KB)
        
    Returns:
        StreamingResponse with proper headers:
        - Regular request: 200 OK with Accept-Ranges: bytes
        - Range request: 206 Partial Content with Content-Range header
        
    Example:
        response = create_streaming_response_with_range(
            file_path="/storage/assets/video.mp4",
            request=request,
            media_type="video/mp4",
            filename="video.mp4",
            read_file_func=read_file,
            read_range_func=read_file_range,
        )
    """
    file_size = os.path.getsize(file_path)
    
    # Check for Range header
    range_header = request.headers.get("range")
    
    if range_header:
        range_tuple = parse_range_header(range_header, file_size)
        
        if range_tuple:
            start, end = range_tuple
            content_length = end - start + 1
            
            headers = {
                "Content-Type": media_type,
                "Content-Disposition": f'inline; filename="{filename}"',
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
            }
            
            return StreamingResponse(
                read_range_func(start, end, chunk_size),
                media_type=media_type,
                headers=headers,
                status_code=206  # Partial Content
            )
    
    # No valid range request - return full file
    headers = {
        "Content-Type": media_type,
        "Content-Disposition": f'inline; filename="{filename}"',
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
    }
    
    return StreamingResponse(
        read_file_func(chunk_size),
        media_type=media_type,
        headers=headers,
    )
