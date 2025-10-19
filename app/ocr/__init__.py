"""
OCR functionality for extracting swimming data from images
"""

from .text_extractor import (
    extract_swimming_data_v2,
    extract_by_regions,
    parse_segment_text,
    parse_ocr_data_structured,
    parse_text_simple,
    ocr_single_segment
)

__all__ = [
    'extract_swimming_data_v2',
    'extract_by_regions', 
    'parse_segment_text',
    'parse_ocr_data_structured',
    'parse_text_simple',
    'ocr_single_segment'
]
