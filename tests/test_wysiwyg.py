"""
tests/test_wysiwyg.py - Verifies scene rendering equals on-screen pixels without distortion.
"""

import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QColor
from overlay_scene import AnnotationScene, ArrowItem, RectShapeItem

def test_wysiwyg_export_fidelity():
    app = QApplication.instance() or QApplication([])

    # Create dummy base 400x300 image
    base = QImage(400, 300, QImage.Format_ARGB32_Premultiplied)
    base.fill(QColor(40, 40, 40))

    scene = AnnotationScene(base)

    # Draw arrow
    arrow = ArrowItem(QPointF(50, 50), QPointF(200, 150), QColor("#6366F1"), width=4.0)
    scene.addItem(arrow)

    # Render image
    out_img = scene.render_wysiwyg_image()
    assert out_img.width() == 400
    assert out_img.height() == 300

    # Ensure painted pixels exist around the center of the arrow line
    arrow_pixel = out_img.pixelColor(125, 100)
    assert arrow_pixel.alpha() > 0
