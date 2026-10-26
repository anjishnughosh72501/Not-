"""
recognizer.py - Pure geometric gesture recognition for MarkSnap.

No GUI or OS imports here so it can be unit-tested and ported cleanly.
"""
from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any

Point = Tuple[float, float]


def bounding_box(points: List[Point]) -> Tuple[float, float, float, float]:
    """Returns (min_x, min_y, max_x, max_y)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def path_length(points: List[Point]) -> float:
    """Total length of the polyline."""
    total = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        total += math.hypot(dx, dy)
    return total


def classify(points: List[Point], sensitivity: int = 50) -> Dict[str, Any]:
    """
    Classify a gesture stroke given a list of (x, y) coordinates.

    sensitivity: 1 (strict) to 100 (loose), default 50.
    """
    if not points or len(points) < 5:
        return {
            "shape": "unknown",
            "bbox": (0, 0, 0, 0),
            "confidence": 0.0,
            "metrics": {"reason": "too_few_points"}
        }

    min_x, min_y, max_x, max_y = bounding_box(points)
    w = max(1.0, max_x - min_x)
    h = max(1.0, max_y - min_y)
    bbox = (min_x, min_y, max_x, max_y)

    total_len = path_length(points)
    if total_len < 20.0:
        return {
            "shape": "unknown",
            "bbox": bbox,
            "confidence": 0.0,
            "metrics": {"reason": "too_short", "path_length": total_len}
        }

    start_p = points[0]
    end_p = points[-1]
    closure_dist = math.hypot(end_p[0] - start_p[0], end_p[1] - start_p[1])
    closure_ratio = closure_dist / total_len
    diagonal = math.hypot(w, h)

    # Adjust thresholds based on sensitivity:
    # sensitivity 50 is base (closure_max = 0.28, box_threshold = 0.76)
    # sensitivity 100 makes loops easier to close (closure_max = 0.38, box_threshold = 0.65)
    # sensitivity 1 makes loops strict (closure_max = 0.18, box_threshold = 0.85)
    sens_factor = (sensitivity - 50.0) / 50.0
    closure_limit = 0.28 + (0.10 * sens_factor)
    box_req_ratio = 0.76 - (0.11 * sens_factor)

    # Check if closed loop
    is_closed = (closure_ratio < closure_limit) or (closure_dist < 55.0 and closure_dist / diagonal < closure_limit)

    if is_closed:
        box_tolerance = max(8.0, (0.12 + 0.04 * sens_factor) * min(w, h))
        near_edge_count = 0

        for px, py in points:
            dist_left = abs(px - min_x)
            dist_right = abs(px - max_x)
            dist_top = abs(py - min_y)
            dist_bottom = abs(py - max_y)

            near_top = dist_top <= box_tolerance and (min_x - box_tolerance <= px <= max_x + box_tolerance)
            near_bottom = dist_bottom <= box_tolerance and (min_x - box_tolerance <= px <= max_x + box_tolerance)
            near_left = dist_left <= box_tolerance and (min_y - box_tolerance <= py <= max_y + box_tolerance)
            near_right = dist_right <= box_tolerance and (min_y - box_tolerance <= py <= max_y + box_tolerance)

            if near_top or near_bottom or near_left or near_right:
                near_edge_count += 1

        box_ratio = near_edge_count / len(points)
        aspect_ratio = min(w, h) / max(w, h)

        if box_ratio >= box_req_ratio:
            return {
                "shape": "box",
                "bbox": bbox,
                "confidence": min(1.0, box_ratio),
                "metrics": {
                    "is_closed": True,
                    "box_ratio": box_ratio,
                    "closure_ratio": closure_ratio,
                    "aspect_ratio": aspect_ratio
                }
            }
        else:
            return {
                "shape": "circle",
                "bbox": bbox,
                "confidence": min(1.0, 1.0 - box_ratio + 0.3),
                "metrics": {
                    "is_closed": True,
                    "box_ratio": box_ratio,
                    "closure_ratio": closure_ratio,
                    "aspect_ratio": aspect_ratio
                }
            }

    # Open stroke: Underline vs Arrow
    efficiency = closure_dist / total_len
    underline_h_w_limit = 0.22 + (0.05 * sens_factor)

    if (h / w) < underline_h_w_limit and w > 35.0:
        return {
            "shape": "underline",
            "bbox": bbox,
            "confidence": min(1.0, 1.0 - (h / w)),
            "metrics": {
                "is_closed": False,
                "aspect_ratio": h / w,
                "efficiency": efficiency
            }
        }

    arrow_eff_limit = 0.58 - (0.10 * sens_factor)
    if efficiency > arrow_eff_limit:
        return {
            "shape": "arrow",
            "bbox": bbox,
            "confidence": efficiency,
            "metrics": {
                "is_closed": False,
                "aspect_ratio": h / w,
                "efficiency": efficiency
            }
        }

    return {
        "shape": "unknown",
        "bbox": bbox,
        "confidence": 0.0,
        "metrics": {
            "is_closed": False,
            "efficiency": efficiency,
            "h_to_w": h / w
        }
    }
