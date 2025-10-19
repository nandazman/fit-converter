"""
Image preprocessing functions for OCR
"""

from typing import Tuple
import cv2
import numpy as np


def preprocess_for_small_text(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Aggressive preprocessing for small text on dark background
    Returns: (processed_image, debug_image)
    """
    original = image.copy()
    
    # Resize to make text larger (3x scaling)
    h, w = image.shape[:2]
    if h < 2000:
        scale = 3.0
        image = cv2.resize(image, (int(w * scale), int(h * scale)), 
                          interpolation=cv2.INTER_CUBIC)
    
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Invert (dark bg -> light bg)
    inv = cv2.bitwise_not(gray)
    
    # Heavy denoising
    denoised = cv2.fastNlMeansDenoising(inv, h=10)
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    
    # Threshold to pure black and white
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Slight morphology to connect broken characters
    kernel = np.ones((2, 2), np.uint8)
    processed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # Create debug visualization
    debug = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    
    return processed, debug
