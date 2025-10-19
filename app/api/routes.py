"""
API route handlers for swimming OCR application
"""

import tempfile
import uuid

import cv2
import numpy as np

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse

from ..helpers.utils import validate_image_file
from ..helpers.storage import storage
from ..ocr.text_extractor import ocr_single_segment
from ..image_processing.image_splitter import split_image_into_segments

router = APIRouter()


@router.get("/healthz")
async def health_check():
    """Health check endpoint"""
    return {"ok": True}


@router.post("/api/split")
async def split_image(file: UploadFile = File(...)):
    """Split image into individual segments and return segment info"""
    validate_image_file(file)
    
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Could not decode image")
        
        # Split image
        segment_images, segment_info = split_image_into_segments(image)
        
        if not segment_images:
            raise HTTPException(status_code=400, detail="No segments found in image")
        
        # Generate IDs
        split_id = str(uuid.uuid4())
        
        # Store segment images
        for i, (seg_img, seg_info) in enumerate(zip(segment_images, segment_info)):
            _, buffer = cv2.imencode('.png', seg_img)
            storage.store_segment(f"{split_id}_{i}", buffer.tobytes(), seg_info)
        
        return {
            "split_id": split_id,
            "total_segments": len(segment_images),
            "segment_info": segment_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/api/segment/{segment_id}")
async def get_segment_image(segment_id: str):
    """Get individual segment image"""
    try:
        segment_data = storage.get_segment(segment_id)
        image_bytes = segment_data["image"]
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_file.write(image_bytes)
        temp_file.close()
        
        return FileResponse(
            temp_file.name,
            media_type="image/png",
            filename=f"segment_{segment_id}.png"
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Segment not found")


@router.post("/api/ocr-segment/{segment_id}")
async def ocr_individual_segment(segment_id: str):
    """OCR a single segment"""
    try:
        segment_data = storage.get_segment(segment_id)
        image_bytes = segment_data["image"]
        info = segment_data["info"]
        
        # Decode image
        nparr = np.frombuffer(image_bytes, np.uint8)
        segment_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if segment_image is None:
            raise HTTPException(status_code=400, detail="Could not decode segment image")
        
        # OCR the segment with proper lap numbering
        start_lap = info.get("start_lap", 1)
        segment = ocr_single_segment(segment_image, info["segment_id"], start_lap)
        
        return {
            "segment_id": segment_id,
            "segment": segment,
            "info": info
        }
        
    except KeyError:
        raise HTTPException(status_code=404, detail="Segment not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


