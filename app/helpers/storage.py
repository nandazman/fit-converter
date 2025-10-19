"""
In-memory storage management for the application
"""

from typing import Dict, Any, List
import uuid


class StorageManager:
    """Manages in-memory storage for CSV data, debug images, and segments"""
    
    def __init__(self):
        self.csv_storage: Dict[str, List[Dict[str, Any]]] = {}
        self.debug_images: Dict[str, bytes] = {}
        self.segment_storage: Dict[str, Dict[str, Any]] = {}
    
    def store_csv(self, data: List[Dict[str, Any]]) -> str:
        """Store CSV data and return ID"""
        csv_id = str(uuid.uuid4())
        self.csv_storage[csv_id] = data
        return csv_id
    
    def get_csv(self, csv_id: str) -> List[Dict[str, Any]]:
        """Get CSV data by ID"""
        if csv_id not in self.csv_storage:
            raise KeyError("CSV not found")
        return self.csv_storage[csv_id]
    
    def store_debug_image(self, image_bytes: bytes) -> str:
        """Store debug image and return ID"""
        debug_id = str(uuid.uuid4())
        self.debug_images[debug_id] = image_bytes
        return debug_id
    
    def get_debug_image(self, debug_id: str) -> bytes:
        """Get debug image by ID"""
        if debug_id not in self.debug_images:
            raise KeyError("Debug image not found")
        return self.debug_images[debug_id]
    
    def store_segment(self, segment_id: str, image_bytes: bytes, info: Dict[str, Any]) -> None:
        """Store segment image and info"""
        self.segment_storage[segment_id] = {
            "image": image_bytes,
            "info": info
        }
    
    def get_segment(self, segment_id: str) -> Dict[str, Any]:
        """Get segment data by ID"""
        if segment_id not in self.segment_storage:
            raise KeyError("Segment not found")
        return self.segment_storage[segment_id]


# Global storage instance
storage = StorageManager()
