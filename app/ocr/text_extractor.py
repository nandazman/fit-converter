"""
Text extraction and parsing functions for swimming data (fixed)
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Tuple, Optional

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from ..helpers.utils import seconds_to_mmss

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# =========================
# Shared helpers & patterns
# =========================

STROKE_CANON = {
    "breaststroke": "Breaststroke",
    "freestyle": "Freestyle",
    "backstroke": "Backstroke",
    "butterfly": "Butterfly",
}

STROKE_ALIASES: Dict[str, str] = {
    r"\bbreast(?:stroke|stro|st)?\b": "Breaststroke",
    r"\bfree(?:style|styl|st)?\b": "Freestyle",
    r"\bback(?:stroke|strok|st)?\b": "Backstroke",
    r"\bbutter(?:fly|fl)?\b": "Butterfly",
    r"\bfly\b": "Butterfly",
    r"\bbr\b": "Breaststroke",
    r"\bfr\b": "Freestyle",
    r"\bbk\b": "Backstroke",
    r"\bba\b": "Backstroke",
    r"\bbf\b": "Butterfly",
    r"\bfl\b": "Butterfly",
}

PACE_PATTERNS = [
    re.compile(r"(\d+)[\'′](\d+)[\"″]"),
    re.compile(r"(\d+):(\d{2})"),
    re.compile(r"(\d+)\s*min\s*(\d{1,2})\s*sec", re.IGNORECASE),
]

TIME_PATTERNS = [
    re.compile(r"(\d{1,2}):(\d{2}):(\d{2})"),
    re.compile(r"(\d{1,2}):(\d{2})"),
    re.compile(r"(\d+)[\'′](\d{2})[\"″]"),
]


def _to_seconds(m: int, s: int) -> int:
    return int(m) * 60 + int(s)


def _extract_pace_seconds(text: str) -> int:
    for pat in PACE_PATTERNS:
        m = pat.search(text)
        if m:
            return _to_seconds(int(m.group(1)), int(m.group(2)))
    return 120


def _extract_time_seconds(text: str) -> int:
    for pat in TIME_PATTERNS:
        m = pat.search(text)
        if m:
            if len(m.groups()) == 3:
                h, mm, ss = map(int, m.groups())
                return h * 3600 + mm * 60 + ss
            elif len(m.groups()) == 2:
                mm, ss = map(int, m.groups())
                return _to_seconds(mm, ss)
    return 90


def _detect_stroke(text: str) -> Optional[str]:
    low = text.lower()
    for pat, canon in STROKE_ALIASES.items():
        if re.search(pat, low):
            return canon
    for k, v in STROKE_CANON.items():
        if k in low:
            return v
    return None


def _extract_length_from_header(header_text: str, default: int = 50) -> int:
    m = re.search(r"(?<!/)\b(25|50|75|100|150|200)\s*m(?:eters?|etres?)?\b",
                  header_text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if val in (25, 50):
            return val
        if val == 100 and re.search(r"/\s*100\s*m", header_text, re.IGNORECASE):
            return 50
        return val
    return default


# =========================
# Robust metric extraction (anchored to labels)
# =========================

_LABELS_ANYWHERE_RE = re.compile(
    r"Strokes?\D{0,10}(\d{1,3}).{0,60}?SWOLF\D{0,10}(\d{1,3}).{0,120}?(?:Pace[^0-9]*(.*))?",
    re.IGNORECASE | re.DOTALL,
)

def _numbers_plausible(strokes: int, swolf: int) -> bool:
    return 5 <= strokes <= 120 and 50 <= swolf <= 300


def _extract_metrics_by_labels_anywhere(text: str) -> Optional[Tuple[int, int, int]]:
    m = _LABELS_ANYWHERE_RE.search(text)
    if not m:
        return None
    strokes = int(m.group(1))
    swolf = int(m.group(2))
    pace_tail = m.group(3) or ""
    pace_sec = _extract_pace_seconds(pace_tail) if pace_tail else _extract_pace_seconds(text)
    if not _numbers_plausible(strokes, swolf):
        return None
    return strokes, swolf, pace_sec


def _extract_from_values_row(lines: List[str]) -> Optional[Tuple[int, int, int]]:
    label_re = re.compile(r"\bStrokes?\b.*\bSWOLF\b", re.IGNORECASE)
    for i, ln in enumerate(lines):
        if label_re.search(ln):
            for j in range(i + 1, min(i + 3, len(lines))):
                row = re.sub(r"/\s*100\s*m", "", lines[j], flags=re.IGNORECASE)
                ints = [int(x) for x in re.findall(r"\b\d{1,3}\b", row)]
                if len(ints) >= 2:
                    strokes, swolf = ints[0], ints[1]
                    if _numbers_plausible(strokes, swolf):
                        pace_sec = _extract_pace_seconds(row)
                        if pace_sec == 120:
                            pace_sec = _extract_pace_seconds(" ".join(lines))
                        return strokes, swolf, pace_sec
    return None


def _rescue_numbers_from_blob(text: str) -> Optional[Tuple[int, int]]:
    after = re.search(r"Strokes?.*?SWOLF", text, re.IGNORECASE | re.DOTALL)
    zone = text[after.end():] if after else text
    zone = re.sub(r"/\s*100\s*m", "", zone, flags=re.IGNORECASE)
    ints = [int(x) for x in re.findall(r"\b\d{1,3}\b", zone)]
    for k in range(len(ints) - 1):
        s, w = ints[k], ints[k + 1]
        if _numbers_plausible(s, w):
            return s, w
    return None


def _extract_strokes_swolf_pace(text: str, lines: Optional[List[str]] = None) -> Tuple[int, int, int]:
    t = _extract_metrics_by_labels_anywhere(text)
    if t:
        return t

    if lines:
        t = _extract_from_values_row(lines)
        if t:
            return t

    pair = _rescue_numbers_from_blob(text)
    pace_sec = _extract_pace_seconds(text)
    if pair:
        return pair[0], pair[1], pace_sec

    ints = [int(x) for x in re.findall(r"\b\d{1,3}\b", re.sub(r"/\s*100\s*m", "", text, flags=re.IGNORECASE))]
    plausible = [n for n in ints if 5 <= n <= 300]
    if len(plausible) >= 2:
        strokes, swolf = plausible[0], plausible[1]
        if not _numbers_plausible(strokes, swolf):
            swolf = max(swolf, 50)
        return strokes, swolf, pace_sec

    duration = _extract_time_seconds(text)
    strokes = 25
    swolf = max(50, strokes + duration)
    return strokes, swolf, pace_sec


def _postprocess_and_sort(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not segments:
        return segments
    if any("y_top" in s for s in segments):
        segments.sort(key=lambda s: (s.get("y_top", 0), s.get("x_left", 0)))
    else:
        segments.sort(key=lambda s: (s.get("lap", 10**9)))
    laps = [s.get("lap") for s in segments]
    if not all(laps[i] is not None and laps[i + 1] is not None and laps[i] < laps[i + 1]
               for i in range(len(laps) - 1)):
        for idx, s in enumerate(segments, start=1):
            s["lap"] = idx
    return segments


# =========================
# Parsing functions
# =========================

def parse_segment_text(text: str, expected_lap: int) -> Optional[Dict[str, Any]]:
    if not text or not text.strip():
        return None

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    blob = " ".join(lines)

    # need at least Strokes & SWOLF in the blob
    if not (re.search(r"\bStrokes?\b", blob, re.IGNORECASE) and
            re.search(r"\bSWOLF\b", blob, re.IGNORECASE)):
        return None

    header_line = None
    for ln in lines:
        if _detect_stroke(ln):
            header_line = ln
            break
    if header_line is None:
        header_line = lines[0]

    stroke = _detect_stroke(header_line) or "Freestyle"
    lap_m = re.search(r"\b(\d{1,3})\b", header_line)
    lap_num = int(lap_m.group(1)) if lap_m else expected_lap
    lap_length = _extract_length_from_header(header_line, default=50)

    trio = _extract_metrics_by_labels_anywhere(blob)
    if not trio:
        trio = _extract_from_values_row(lines)
    if not trio:
        trio = _extract_strokes_swolf_pace(blob, lines)
    strokes, swolf, pace_per_100m_sec = trio

    if not _numbers_plausible(strokes, swolf):
        pair = _rescue_numbers_from_blob(blob)
        if pair and _numbers_plausible(pair[0], pair[1]):
            strokes, swolf = pair

    duration_sec = _extract_time_seconds(blob)
    if lap_length == 100:
        lap_length = 50

    return {
        "lap": lap_num,
        "stroke_type": stroke,
        "lap_length_m": lap_length,
        "duration_sec": duration_sec,
        "strokes": strokes,
        "swolf": swolf,
        "pace_per_100m_sec": pace_per_100m_sec,
    }


def _is_header_line(txt: str) -> bool:
    return bool(re.search(
        r"\b(\d{1,3})\b.*?(breast|free|back|butter|fly|br|fr|bk|ba|bf|fl)",
        txt, re.IGNORECASE
    ))


def parse_ocr_data_structured(data: dict) -> List[Dict[str, Any]]:
    # collect word boxes
    text_blocks = []
    for i, t in enumerate(data.get("text", [])):
        t = (t or "").strip()
        if not t:
            continue
        try:
            conf_val = float(str(data["conf"][i]))
        except Exception:
            conf_val = -1.0
        text_blocks.append({
            "text": t,
            "x": int(data["left"][i]),
            "y": int(data["top"][i]),
            "w": int(data["width"][i]),
            "h": int(data["height"][i]),
            "conf": conf_val,
        })

    # sort and group into lines
    text_blocks.sort(key=lambda b: (b["y"], b["x"]))

    lines = []
    current = []
    last_y = None

    def flush():
        if not current:
            return
        ys = [x["y"] for x in current]
        xs = [x["x"] for x in current]
        lines.append({
            "y_top": min(ys),
            "x_left": min(xs),
            "text": " ".join(x["text"] for x in sorted(current, key=lambda z: z["x"]))
        })

    for b in text_blocks:
        thresh = max(12, int(0.6 * b["h"]))
        if last_y is None or abs(b["y"] - last_y) <= thresh:
            current.append(b)
            last_y = b["y"] if last_y is None else (last_y + b["y"]) // 2
        else:
            flush()
            current = [b]
            last_y = b["y"]
    flush()

    # ---- FIX: build context from this header up to the next header (no hard cap) ----
    segments: List[Dict[str, Any]] = []
    i = 0
    while i < len(lines):
        row = lines[i]["text"]

        if not _is_header_line(row):
            i += 1
            continue

        # find the next header index
        j = i + 1
        while j < len(lines) and not _is_header_line(lines[j]["text"]):
            j += 1

        # take ALL lines from this header until (but not including) the next header
        ctx_lines = [lines[k]["text"] for k in range(i, j)]
        ctx_blob = "  ".join(ctx_lines)

        if not (re.search(r"\bStrokes?\b", ctx_blob, re.IGNORECASE) and
                re.search(r"\bSWOLF\b", ctx_blob, re.IGNORECASE)):
            # if labels are noisy, try still to parse (fallback uses rescue logic)
            seg = parse_segment_text("\n".join(ctx_lines), expected_lap=1)
        else:
            seg = parse_segment_text("\n".join(ctx_lines), expected_lap=1)

        if seg:
            seg["lap_length_m"] = _extract_length_from_header(row, default=50)
            seg["y_top"] = lines[i]["y_top"]
            seg["x_left"] = lines[i]["x_left"]
            segments.append(seg)

        # move to the next header found (j), or advance one if none
        i = j if j > i else i + 1

    segments = _postprocess_and_sort(segments)

    for s in segments:
        s.pop("y_top", None)
        s.pop("x_left", None)
        if s["lap_length_m"] == 100:
            s["lap_length_m"] = 50

    return segments


def parse_text_simple(text: str) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    if not text:
        return segments

    lines = [l for l in text.splitlines() if l.strip()]
    expected = 1
    for i, line in enumerate(lines):
        ctx = [line]
        if i + 1 < len(lines): ctx.append(lines[i + 1])
        if i + 2 < len(lines): ctx.append(lines[i + 2])
        blob = "  ".join(ctx)

        if not (re.search(r"\bStrokes?\b", blob, re.IGNORECASE) and
                re.search(r"\bSWOLF\b", blob, re.IGNORECASE)):
            continue

        lap_m = re.search(r"^\s*(\d{1,3})\b", line.strip())
        lap_num = int(lap_m.group(1)) if lap_m else expected

        seg = parse_segment_text(blob, lap_num)
        if seg:
            segments.append(seg)
            expected = seg["lap"] + 1

    return _postprocess_and_sort(segments)


# =========================
# Region-based extraction (unchanged)
# =========================

def extract_by_regions(image: np.ndarray, debug_img: np.ndarray) -> Tuple[List[Dict[str, Any]], np.ndarray]:
    from ..image_processing.preprocessing import preprocess_for_small_text

    processed, _ = preprocess_for_small_text(image)
    h, w = processed.shape

    boxes: List[Tuple[int, int, int, int]] = []

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 20), 1))
    detect_horizontal = cv2.morphologyEx(processed, cv2.MORPH_OPEN, horizontal_kernel)
    cnts, _ = cv2.findContours(cv2.bitwise_not(detect_horizontal), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y, ww, hh = cv2.boundingRect(c)
        if hh > 20 and ww > 80:
            boxes.append((x, y, ww, hh))

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(processed, connectivity=8)
    for i in range(1, num_labels):
        x, y, ww, hh, area = stats[i]
        if hh > 18 and ww > 60 and area > 450:
            overlaps = False
            for ex, ey, ew, eh in boxes:
                if (x < ex + ew and x + ww > ex and y < ey + eh and y + hh > ey):
                    overlaps = True
                    break
            if not overlaps:
                boxes.append((x, y, ww, hh))

    strip_n = min(40, max(20, h // 40))
    strip_height = max(12, h // strip_n)
    for i in range(strip_n):
        y0 = i * strip_height
        y1 = min(h, (i + 1) * strip_height)
        strip = processed[y0:y1, :]
        text_pixels = int((strip == 0).sum())
        if text_pixels > max(80, (y1 - y0) * w * 0.01):
            cnts, _ = cv2.findContours(strip, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in cnts:
                x, y_rel, ww, hh = cv2.boundingRect(c)
                y_abs = y0 + y_rel
                if hh > 14 and ww > 50:
                    overlaps = False
                    for ex, ey, ew, eh in boxes:
                        if (x < ex + ew and x + ww > ex and y_abs < ey + eh and y_abs + hh > ey):
                            overlaps = True
                            break
                    if not overlaps:
                        boxes.append((x, y_abs, ww, hh))

    bottom_start = int(h * 0.8)
    bottom_region = processed[bottom_start:, :]
    cnts, _ = cv2.findContours(bottom_region, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts:
        x, y_rel, ww, hh = cv2.boundingRect(c)
        y_abs = bottom_start + y_rel
        if hh > 10 and ww > 40:
            overlaps = False
            for ex, ey, ew, eh in boxes:
                if (x < ex + ew and x + ww > ex and y_abs < ey + eh and y_abs + hh > ey):
                    overlaps = True
                    break
            if not overlaps:
                boxes.append((x, y_abs, ww, hh))

    # dedupe
    filtered: List[Tuple[int, int, int, int]] = []
    for x, y, ww, hh in sorted(boxes, key=lambda b: (b[1], b[0])):
        is_dup = False
        for ex, ey, ew, eh in filtered:
            overlap_w = max(0, min(x + ww, ex + ew) - max(x, ex))
            overlap_h = max(0, min(y + hh, ey + eh) - max(y, ey))
            overlap_area = overlap_w * overlap_h
            min_area = min(ww * hh, ew * eh)
            if min_area > 0 and overlap_area > 0.3 * min_area:
                is_dup = True
                break
        if not is_dup:
            filtered.append((x, y, ww, hh))

    boxes = sorted(filtered, key=lambda b: b[1])

    debug_with_boxes = debug_img.copy()
    segments: List[Dict[str, Any]] = []
    lap_counter = 1

    for idx, (x, y, ww, hh) in enumerate(boxes):
        color = (0, 255, 0) if idx % 2 == 0 else (255, 0, 0)
        cv2.rectangle(debug_with_boxes, (x, y), (x + ww, y + hh), color, 2)
        cv2.putText(debug_with_boxes, f"#{lap_counter}", (x + 5, y + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        pad = 5
        xs = max(0, x - pad)
        ys = max(0, y - pad)
        xe = min(w, x + ww + pad)
        ye = min(h, y + hh + pad)

        region = processed[ys:ye, xs:xe]

        text = ""
        for psm in (6, 4, 3):
            try:
                text = pytesseract.image_to_string(region, config=f'--psm {psm} --oem 3')
                if text.strip():
                    break
            except Exception:
                pass

        seg = parse_segment_text(text, lap_counter)
        if not seg:
            orig = image[ys:ye, xs:xe]
            g = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY) if len(orig.shape) == 3 else orig
            try:
                _, bin_img = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            except Exception:
                bin_img = g
            for psm in (6, 4, 3):
                try:
                    text = pytesseract.image_to_string(bin_img, config=f'--psm {psm} --oem 3')
                    if text.strip():
                        break
                except Exception:
                    pass
            seg = parse_segment_text(text, lap_counter)

        if seg:
            seg["y_top"] = y
            seg["x_left"] = x
            segments.append(seg)
            lap_counter += 1
        else:
            if text.strip():
                lap_match = re.search(r"\b(\d{1,3})\b", text)
                lap_num = int(lap_match.group(1)) if lap_match else lap_counter
                segments.append({
                    "lap": lap_num,
                    "stroke_type": "Freestyle",
                    "lap_length_m": 50,
                    "duration_sec": 90,
                    "strokes": 25,
                    "swolf": 115,
                    "pace_per_100m_sec": 120,
                    "y_top": y,
                    "x_left": x,
                })
                lap_counter += 1

    segments = _postprocess_and_sort(segments)
    for s in segments:
        s.pop("y_top", None)
        s.pop("x_left", None)

    return segments, debug_with_boxes


# =========================
# High-level extractor
# =========================

def extract_swimming_data_v2(image: np.ndarray) -> Tuple[List[Dict[str, Any]], np.ndarray]:
    from ..image_processing.preprocessing import preprocess_for_small_text

    processed, debug_img = preprocess_for_small_text(image)
    all_candidates: List[Tuple[str, List[Dict[str, Any]], np.ndarray]] = []

    try:
        segments, dbg = extract_by_regions(image, debug_img)
        if len(segments) >= 5:
            segments = _postprocess_and_sort(segments)
            return segments, dbg
        elif len(segments) > 0:
            all_candidates.append(("region", segments, dbg))
    except Exception as e:
        print(f"✗ Region extraction failed: {e}")

    variants = [
        ("processed", processed),
        ("original_gray", cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image),
        ("inverted", cv2.bitwise_not(processed)),
        ("enhanced", cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(processed)),
    ]

    for name, img in variants:
        for psm in (6, 4, 3, 11, 8, 13):
            try:
                data = pytesseract.image_to_data(img, output_type=Output.DICT, config=f'--psm {psm} --oem 3')
                segs = parse_ocr_data_structured(data)
                if len(segs) >= 5:
                    segs = _postprocess_and_sort(segs)
                    return segs, debug_img
                elif len(segs) > 0:
                    all_candidates.append((f"{name}_psm{psm}", segs, debug_img))
            except Exception as e:
                print(f"✗ {name} PSM {psm} failed: {e}")

    for psm in (6, 4, 3, 11, 8):
        try:
            text = pytesseract.image_to_string(processed, config=f'--psm {psm} --oem 3')
            segs = parse_text_simple(text)
            if len(segs) >= 5:
                segs = _postprocess_and_sort(segs)
                return segs, debug_img
            elif len(segs) > 0:
                all_candidates.append((f"simple_psm{psm}", segs, debug_img))
        except Exception as e:
            print(f"✗ Simple PSM {psm} failed: {e}")

    if all_candidates:
        best = max(all_candidates, key=lambda x: len(x[1]))
        _, segs, dbg = best

        known = {(s["lap"], s.get("duration_sec", 0), s.get("strokes", -1), s.get("swolf", -1)) for s in segs}
        merged = list(segs)
        for _, other, _ in all_candidates:
            for s in other:
                key = (s["lap"], s.get("duration_sec", 0), s.get("strokes", -1), s.get("swolf", -1))
                if key not in known:
                    merged.append(s)
                    known.add(key)

        merged = _postprocess_and_sort(merged)
        return merged, dbg

    return [], debug_img


# =========================
# Single segment OCR (one crop)
# =========================

def ocr_single_segment(segment_image: np.ndarray, segment_id: int, start_lap: int = 1) -> Dict[str, Any]:
    logger.info(f"🏊 Starting OCR for segment {segment_id}, start_lap={start_lap}")
    logger.debug(f"Image shape: {segment_image.shape}, dtype: {segment_image.dtype}")

    if len(segment_image.shape) == 3:
        gray = cv2.cvtColor(segment_image, cv2.COLOR_BGR2GRAY)
    else:
        gray = segment_image

    processed_variants: List[Tuple[str, np.ndarray]] = [("original", segment_image)]

    try:
        from ..image_processing.preprocessing import preprocess_for_small_text
        pre, _ = preprocess_for_small_text(segment_image)
        processed_variants.append(("preprocessed", pre))
        logger.debug("✅ Added preprocessed variant")
    except Exception as e:
        logger.warning(f"⚠️  Failed to preprocess: {e}")

    try:
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        processed_variants.append(("enhanced", enhanced))
        denoised = cv2.fastNlMeansDenoising(gray)
        processed_variants.append(("denoised", denoised))
        logger.debug(f"✅ Added enhanced and denoised variants (total: {len(processed_variants)})")
    except Exception as e:
        logger.warning(f"⚠️  Failed to create enhanced variants: {e}")

    all_laps: List[Dict[str, Any]] = []

    for variant_name, img in processed_variants:
        logger.debug(f"🔍 Trying variant: {variant_name}")
        for psm in (6, 4, 3, 11, 8):
            try:
                logger.debug(f"  → PSM {psm}: Running image_to_data...")
                data = pytesseract.image_to_data(img, output_type=Output.DICT, config=f'--psm {psm} --oem 3')
                segs = parse_ocr_data_structured(data)
                logger.debug(f"  → PSM {psm}: Structured parsing found {len(segs)} segments")

                if segs:
                    segs = _postprocess_and_sort(segs)
                    for i, s in enumerate(segs):
                        s["lap"] = start_lap + i
                        s["duration"] = seconds_to_mmss(s.pop("duration_sec", 90))
                        s["pace_per_100m"] = seconds_to_mmss(s.pop("pace_per_100m_sec", 120))
                        all_laps.append(s)
                    if all_laps:
                        logger.info(f"✅ SUCCESS with {variant_name} PSM {psm}: {len(all_laps)} laps found")
                        logger.debug(f"Laps data: {all_laps}")
                        return {"laps": all_laps, "total_laps": len(all_laps)}

                logger.debug(f"  → PSM {psm}: Running image_to_string...")
                text = pytesseract.image_to_string(img, config=f'--psm {psm} --oem 3')
                logger.debug(f"  → PSM {psm}: OCR text length: {len(text)} chars")
                logger.debug(f"  → PSM {psm}: OCR text preview: {text[:200]}")

                if text.strip():
                    lines = [l.strip() for l in text.splitlines() if l.strip()]
                    logger.debug(f"  → PSM {psm}: {len(lines)} lines after cleanup")
                    tmp: List[Dict[str, Any]] = []
                    for i, _line in enumerate(lines):
                        ctx = "\n".join(lines[max(0, i - 1):min(len(lines), i + 3)])
                        has_strokes = bool(re.search(r"\bStrokes?\b", ctx, re.IGNORECASE))
                        has_swolf = bool(re.search(r"\bSWOLF\b", ctx, re.IGNORECASE))

                        if not (has_strokes and has_swolf):
                            continue

                        logger.debug(f"    Line {i}: Found Strokes & SWOLF markers")
                        lap_m = re.search(r"^\s*(\d{1,3})\b", _line)
                        lap_num = int(lap_m.group(1)) if lap_m else (start_lap + len(tmp))
                        seg = parse_segment_text(ctx, lap_num)
                        if seg:
                            logger.debug(f"    Line {i}: Parsed segment - lap={seg.get('lap')}, stroke={seg.get('stroke_type')}")
                            tmp.append(seg)

                    if tmp:
                        logger.debug(f"  → PSM {psm}: Parsed {len(tmp)} segments from text")
                        tmp = _postprocess_and_sort(tmp)
                        for i, s in enumerate(tmp):
                            s["lap"] = start_lap + i
                            s["duration"] = seconds_to_mmss(s.pop("duration_sec", 90))
                            s["pace_per_100m"] = seconds_to_mmss(s.pop("pace_per_100m_sec", 120))
                            all_laps.append(s)
                        logger.info(f"✅ SUCCESS with {variant_name} PSM {psm} text parsing: {len(all_laps)} laps")
                        logger.debug(f"Laps data: {all_laps}")
                        return {"laps": all_laps, "total_laps": len(all_laps)}

                    logger.debug(f"  → PSM {psm}: Trying single segment parse...")
                    single = parse_segment_text(text, start_lap)
                    if single:
                        logger.info(f"✅ SUCCESS with {variant_name} PSM {psm} single parse")
                        single["duration"] = seconds_to_mmss(single.pop("duration_sec", 90))
                        single["pace_per_100m"] = seconds_to_mmss(single.pop("pace_per_100m_sec", 120))
                        logger.debug(f"Single lap data: {single}")
                        return {"laps": [single], "total_laps": 1}
                    else:
                        logger.debug(f"  → PSM {psm}: Single parse returned None (missing Strokes/SWOLF)")

            except Exception as e:
                logger.warning(f"  → PSM {psm}: Exception during OCR: {type(e).__name__}: {e}")
                continue

    logger.error(f"❌ FALLBACK: All OCR attempts failed for segment {segment_id}")
    logger.error(f"   Tried {len(processed_variants)} variants x 5 PSM modes = {len(processed_variants) * 5} attempts")
    fallback_segment = {
        "lap": start_lap,
        "stroke_type": "Freestyle",
        "lap_length_m": 50,
        "duration": "1:30",
        "strokes": 25,
        "swolf": 115,
        "pace_per_100m": "2:00",
    }
    logger.warning(f"   Returning default fallback: {fallback_segment}")
    return {"laps": [fallback_segment], "total_laps": 1}
