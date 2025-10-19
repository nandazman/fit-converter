"""
Utility functions used across the application
"""

from typing import List
from fastapi import HTTPException, UploadFile


def seconds_to_mmss(seconds: float) -> str:
    """Convert seconds to MM:SS format"""
    if seconds <= 0:
        return "0:00"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def validate_image_file(file: UploadFile) -> None:
    """Validate uploaded image file"""
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
