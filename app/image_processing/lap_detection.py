"""
Lap boundary detection and analysis functions
"""

from typing import List, Tuple
import cv2
import numpy as np
from scipy.signal import find_peaks


def detect_lap_boundaries(image: np.ndarray) -> Tuple[List[int], float, float]:
    """
    Detect actual lap boundaries in the swimming image
    Focus on major separators between swimming laps, not individual text lines
    Returns: (boundary_y_positions, average_lap_height, average_gap_height)
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Method 1: Text density analysis (most reliable for swimming data)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    vertical_projection = np.sum(thresh, axis=1)
    
    # Find valleys in the projection (gaps between laps)
    valleys, _ = find_peaks(-vertical_projection, distance=h//30, prominence=np.std(vertical_projection)*0.3)
    
    boundary_y_positions = []
    if len(valleys) > 5:  # Need at least 5 valleys for reliable detection
        # Filter valleys to get major boundaries
        for valley in valleys:
            # Check if this valley represents a significant gap
            if valley > 50 and valley < h - 50:  # Avoid edges
                boundary_y_positions.append(valley)
        
        print(f"Detected {len(boundary_y_positions)} lap boundaries from text density")
    
    # Method 2: If text density fails, use horizontal line detection
    if len(boundary_y_positions) < 5:
        # Blur the image to reduce noise from individual text lines
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Use adaptive thresholding
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # Detect horizontal lines that are wide enough to be lap separators
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w//3, 2))
        horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Find contours of horizontal separators
        contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Extract y-positions of horizontal lines
        for contour in contours:
            # Only consider wide horizontal lines (major separators)
            if cv2.contourArea(contour) > w//8:
                # Get the y-coordinate of the line
                y_pos = int(np.mean(contour[:, 0, 1]))
                if y_pos > 50 and y_pos < h - 50:  # Avoid edges
                    boundary_y_positions.append(y_pos)
        
        print(f"Detected {len(boundary_y_positions)} lap boundaries from horizontal lines")
    
    # Sort boundaries from top to bottom
    boundary_y_positions.sort()
    
    # Filter out boundaries that are too close together
    filtered_boundaries = []
    if boundary_y_positions:
        filtered_boundaries.append(boundary_y_positions[0])  # Keep first boundary
        for i in range(1, len(boundary_y_positions)):
            # Only keep boundaries that are at least 80px apart
            if boundary_y_positions[i] - filtered_boundaries[-1] > 80:
                filtered_boundaries.append(boundary_y_positions[i])
    
    boundary_y_positions = filtered_boundaries
    
    # Calculate average lap height and gap
    if len(boundary_y_positions) >= 2:
        # Calculate gaps between boundaries
        gaps = [boundary_y_positions[i+1] - boundary_y_positions[i] for i in range(len(boundary_y_positions)-1)]
        average_gap = np.mean(gaps)
        
        # Estimate lap height (gap between boundaries)
        average_lap_height = average_gap
    else:
        # Fallback: estimate based on image height and reasonable lap count
        estimated_laps = max(15, min(30, h // 250))  # 250px per lap is reasonable
        average_lap_height = h / estimated_laps
        average_gap = average_lap_height
    
    print(f"Final: {len(boundary_y_positions)} lap boundaries")
    print(f"Average lap height: {average_lap_height:.1f}px")
    print(f"Average gap: {average_gap:.1f}px")
    
    return boundary_y_positions, average_lap_height, average_gap


def analyze_actual_lap_structure(image: np.ndarray) -> Tuple[int, float]:
    """
    Analyze the actual image to detect real lap structure
    Uses multiple detection methods for better accuracy
    Returns: (actual_lap_count, actual_lap_height)
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Method 1: Text density analysis (most reliable for swimming data)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    vertical_projection = np.sum(thresh, axis=1)
    
    # Find valleys in the projection (gaps between laps)
    valleys, _ = find_peaks(-vertical_projection, distance=h//30, prominence=np.std(vertical_projection)*0.5)
    
    if len(valleys) > 5:  # Need at least 5 valleys for reliable detection
        lap_heights = [valleys[i+1] - valleys[i] for i in range(len(valleys)-1)]
        avg_lap_height = np.mean(lap_heights)
        actual_lap_count = len(valleys) + 1
        
        print(f"Detected {len(valleys)} lap boundaries from text density")
        print(f"Actual lap count: {actual_lap_count}")
        print(f"Actual lap height: {avg_lap_height:.1f}px")
        
        return actual_lap_count, avg_lap_height
    
    # Method 2: Edge detection with better parameters
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=w//3, maxLineGap=20)
    
    if lines is not None:
        horizontal_lines = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Check if line is roughly horizontal
            if abs(y2 - y1) < 15 and abs(x2 - x1) > w//3:
                horizontal_lines.append((y1 + y2) // 2)
        
        # Remove duplicate lines
        horizontal_lines = sorted(set(horizontal_lines))
        filtered_lines = []
        for y in horizontal_lines:
            if not filtered_lines or abs(y - filtered_lines[-1]) > 30:
                filtered_lines.append(y)
        
        if len(filtered_lines) >= 5:
            lap_heights = [filtered_lines[i+1] - filtered_lines[i] for i in range(len(filtered_lines)-1)]
            avg_lap_height = np.mean(lap_heights)
            actual_lap_count = len(filtered_lines) + 1
            
            print(f"Detected {len(filtered_lines)} lap separators from edges")
            print(f"Actual lap count: {actual_lap_count}")
            print(f"Actual lap height: {avg_lap_height:.1f}px")
            
            return actual_lap_count, avg_lap_height
    
    # Method 3: Smart estimation based on image characteristics
    # For swimming screenshots, estimate based on typical patterns
    if h > 5000:  # Long image, likely many laps
        estimated_laps = max(20, h // 200)  # ~200px per lap
    elif h > 3000:  # Medium image
        estimated_laps = max(15, h // 250)  # ~250px per lap
    else:  # Short image
        estimated_laps = max(10, h // 300)  # ~300px per lap
    
    estimated_lap_height = h / estimated_laps
    
    print(f"Using smart estimation: {estimated_laps} laps, {estimated_lap_height:.1f}px per lap")
    return estimated_laps, estimated_lap_height


def detect_optimal_segments(image: np.ndarray) -> int:
    """
    Analyze actual image content to determine optimal segmentation
    Target: 5 laps per segment for optimal OCR processing
    """
    h, w = image.shape[:2]
    
    # Analyze the actual image structure
    actual_lap_count, actual_lap_height = analyze_actual_lap_structure(image)
    
    # Target: 5 laps per segment (fixed target)
    laps_per_segment = 5
    optimal_segments = max(1, actual_lap_count // laps_per_segment)
    
    # For 30 laps: 30/5 = 6 segments
    # For 20 laps: 20/5 = 4 segments
    # Reasonable limits: 3-12 segments for most swimming images
    optimal_segments = max(3, min(optimal_segments, 12))
    
    print(f"Image height: {h}px, Actual laps: {actual_lap_count}, Target: {laps_per_segment} laps per segment, Optimal segments: {optimal_segments}")
    return optimal_segments
