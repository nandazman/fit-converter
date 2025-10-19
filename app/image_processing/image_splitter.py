"""
Image splitting functionality for segmenting swimming data
"""

import math
from typing import List, Dict, Any, Tuple
import cv2
import numpy as np
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d


def split_image_into_segments(
    image: np.ndarray,
    laps_per_segment: int = 5,
) -> Tuple[List[np.ndarray], List[Dict[str, Any]], np.ndarray]:
    """
    Robust, size-adaptive lap splitter.

    Pipeline
    --------
    1) Binarize (invert) and compute horizontal projection.
    2) Detect candidate gap valleys.
    3) Build boundaries = [top] + valleys + [bottom].
    4) Clean:
       - merge near-duplicates (< 0.35 * est_lap_h)
       - insert missing boundaries inside any interval > 1.35 * est_lap_h
         using local minima; if none, insert at ~est_lap_h step.
       - remove spurious tiny intervals (< 0.35 * est_lap_h)
    5) Segment strictly: every 5 laps per image (last may be fewer).
       - start slightly ABOVE the gap (keep header visible),
         end slightly ABOVE the next gap (avoid next-lap leak).
    Returns: (segment_images [BGR], segment_info [dict], debug_image [BGR])
    """

    # ---------- helpers ----------
    def _normalize_contrast(gray: np.ndarray) -> np.ndarray:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)

    def _binarize(gray: np.ndarray) -> np.ndarray:
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        # invert so white UI text/lines are white
        _, th = cv2.threshold(255 - blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN,
                              cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3)), 1)
        return th

    def _row_projection(bin_img: np.ndarray, sigma: float) -> np.ndarray:
        proj = bin_img.sum(axis=1).astype(np.float32)
        return gaussian_filter1d(proj, sigma=sigma)

    def _detect_valleys(proj_sm: np.ndarray, min_distance_px: int, prom_ratio: float) -> np.ndarray:
        inv = -proj_sm
        prominence = max(1.0, float(np.std(proj_sm) * prom_ratio))
        valleys, _ = find_peaks(inv, distance=max(2, int(min_distance_px)), prominence=prominence)
        return valleys.astype(int)

    def _merge_close(sorted_positions: np.ndarray, min_sep: int) -> np.ndarray:
        if sorted_positions.size == 0:
            return sorted_positions
        out = [int(sorted_positions[0])]
        for y in sorted_positions[1:]:
            if y - out[-1] < min_sep:
                out[-1] = int(y)  # keep later one (closer to gap end)
            else:
                out.append(int(y))
        return np.array(out, dtype=int)

    def _median_interval(boundaries: np.ndarray) -> int:
        if len(boundaries) < 3:
            return 0
        diffs = np.diff(boundaries).astype(float)
        q1, q3 = np.percentile(diffs, [25, 75])
        iqr = q3 - q1
        keep = diffs[(diffs >= q1 - 1.5 * iqr) & (diffs <= q3 + 1.5 * iqr)]
        if keep.size == 0:
            keep = diffs
        return max(1, int(round(np.median(keep))))

    # ---------- pipeline ----------
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = _normalize_contrast(gray)
    bin_img = _binarize(gray)

    # smoothing scales with image height (works for small & large)
    sigma = max(2.0, h / 900.0)
    proj_sm = _row_projection(bin_img, sigma=sigma)

    # initial valleys (coarse)
    coarse_step = max(16, int(round(h / 30)))  # ~30 laps view as a coarse guess
    valleys = _detect_valleys(proj_sm, min_distance_px=int(coarse_step * 0.6), prom_ratio=0.30)

    # preliminary boundaries
    prelim = np.unique(np.clip(np.concatenate(([0], valleys, [h])), 0, h))
    est_h = _median_interval(prelim)
    if est_h <= 1:
        # uniform fallback ~30 laps
        assumed = 30
        step = max(1, int(round(h / assumed)))
        boundaries = np.arange(0, h + 1, step, dtype=int)
        if boundaries[-1] != h:
            boundaries = np.append(boundaries, h)
        est_h = step
    else:
        # merge near duplicates
        boundaries = _merge_close(prelim, min_sep=max(2, int(round(0.35 * est_h))))

    # ---- repair long intervals by inserting missing boundaries ----
    # We keep doing local repairs until every interval <= 1.35 * est_h
    max_len = int(round(1.35 * est_h))
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(boundaries) - 1:
            y0, y1 = int(boundaries[i]), int(boundaries[i + 1])
            span = y1 - y0
            if span > max_len:
                # search for a deep local minimum inside (avoid 20% borders)
                a = y0 + int(0.20 * est_h)
                b = y1 - int(0.20 * est_h)
                if b <= a:
                    a, b = y0 + span // 3, y1 - span // 3
                window = proj_sm[max(0, a):min(h, b)]
                if window.size > 0:
                    offset = int(np.argmin(window))
                    split_y = int(np.clip(a + offset, y0 + 4, y1 - 4))
                else:
                    split_y = int(y0 + round(est_h))  # synthetic split
                boundaries = np.insert(boundaries, i + 1, split_y)
                changed = True
            else:
                i += 1

    # re-estimate after repair
    est_h = _median_interval(boundaries)

    # ---- remove tiny intervals produced by noise / over-splits ----
    min_len = max(1, int(round(0.35 * est_h)))
    cleaned = [int(boundaries[0])]
    for b in boundaries[1:]:
        if b - cleaned[-1] < min_len:
            cleaned[-1] = int(b)
        else:
            cleaned.append(int(b))
    boundaries = np.array(cleaned, dtype=int)

    total_laps = len(boundaries) - 1
    if total_laps <= 0:
        # last resort split into 5 equal parts
        boundaries = np.linspace(0, h, 6, dtype=int)
        total_laps = 5
        est_h = int(round(h / 30)) if h > 0 else 20

    # ---------- segment assembly (STRICT: 5 laps each) ----------
    num_segments = math.ceil(total_laps / laps_per_segment)

    # padding scales with lap height
    pad_up = max(1, int(round(0.08 * est_h)))         # start slightly above gap (keeps header)
    pad_end_guard = max(1, int(round(0.06 * est_h)))  # end above next gap (no next-lap sliver)

    segment_images: List[np.ndarray] = []
    segment_info: List[Dict[str, Any]] = []

    debug_img = image.copy()
    for y in boundaries:
        cv2.line(debug_img, (0, int(y)), (w, int(y)), (128, 128, 128), 1)

    prev_end = 0
    for seg_idx in range(num_segments):
        start_lap_idx = seg_idx * laps_per_segment
        end_lap_idx = min(start_lap_idx + laps_per_segment, total_laps)  # exclusive

        base_start = int(boundaries[start_lap_idx])   # gap before first lap in segment
        base_end = int(boundaries[end_lap_idx])       # gap after last lap in segment

        # keep header visible, but never cross into next lap
        y_start = max(0, base_start - pad_up)
        y_start = max(prev_end - 1, y_start)
        y_end = max(y_start + 1, min(h, base_end - pad_end_guard))

        seg = image[y_start:y_end, :]
        segment_images.append(seg)

        color = (0, 255, 0) if seg_idx % 2 == 0 else (255, 0, 0)
        cv2.line(debug_img, (0, int(y_end)), (w, int(y_end)), color, 3)
        cv2.putText(debug_img,
                    f"Seg {seg_idx+1}: L{start_lap_idx+1}-{end_lap_idx}",
                    (10, max(20, int(y_end) - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        segment_info.append({
            "segment_id": int(seg_idx + 1),
            "bbox": (0, int(y_start), int(w), int(y_end - y_start)),
            "start_y": int(y_start),
            "end_y": int(y_end),
            "height": int(y_end - y_start),
            "start_lap": int(start_lap_idx + 1),
            "end_lap": int(end_lap_idx),
            "laps_in_segment": int(end_lap_idx - start_lap_idx),
            "estimated_lap_height": int(est_h),
            "total_detected_laps": int(total_laps),
            "pad_up": int(pad_up),
            "pad_end_guard": int(pad_end_guard),
        })
        prev_end = y_end

    return segment_images, segment_info, debug_img
