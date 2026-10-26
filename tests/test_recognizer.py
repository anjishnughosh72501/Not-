"""
tests/test_recognizer.py - Automated unit tests for gesture classification.
"""

import math
from recognizer import classify

def generate_box_points():
    pts = []
    # top: 0 to 100
    for x in range(0, 101, 10): pts.append((float(x), 0.0))
    # right: y 0 to 100
    for y in range(10, 101, 10): pts.append((100.0, float(y)))
    # bottom: x 100 to 0
    for x in range(90, -1, -10): pts.append((float(x), 100.0))
    # left: y 100 to 0
    for y in range(90, -1, -10): pts.append((0.0, float(y)))
    return pts

def generate_circle_points():
    pts = []
    cx, cy, r = 100.0, 100.0, 50.0
    for step in range(36):
        rad = 2 * math.pi * (step / 36.0)
        pts.append((cx + r * math.cos(rad), cy + r * math.sin(rad)))
    pts.append(pts[0])
    return pts

def generate_underline_points():
    return [(float(x), 50.0) for x in range(10, 200, 10)]

def generate_arrow_points():
    return [(float(i), float(i * 2)) for i in range(10, 120, 10)]

def test_box_recognition():
    pts = generate_box_points()
    res = classify(pts)
    assert res["shape"] == "box", f"Expected box, got {res['shape']}"

def test_circle_recognition():
    pts = generate_circle_points()
    res = classify(pts)
    assert res["shape"] == "circle", f"Expected circle, got {res['shape']}"

def test_underline_recognition():
    pts = generate_underline_points()
    res = classify(pts)
    assert res["shape"] == "underline", f"Expected underline, got {res['shape']}"

def test_arrow_recognition():
    pts = generate_arrow_points()
    res = classify(pts)
    assert res["shape"] == "arrow", f"Expected arrow, got {res['shape']}"
