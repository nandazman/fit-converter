"""
Image processing functionality for swimming data extraction
"""

from .preprocessing import preprocess_for_small_text
from .lap_detection import (
    detect_lap_boundaries,
    analyze_actual_lap_structure,
    detect_optimal_segments
)
from .image_splitter import (
    split_image_into_segments
)

__all__ = [
    'preprocess_for_small_text',
    'detect_lap_boundaries',
    'analyze_actual_lap_structure', 
    'detect_optimal_segments',
    'split_image_into_segments'
]
