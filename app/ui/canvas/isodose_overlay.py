"""Isodose overlay graphics item — semi-transparent heatmap on canvas.

Renders 2D dose distribution as a colored overlay on the collimator
geometry canvas, with optional contour lines.

All positions in scene units (1 unit = 1 mm).

Reference: Phase 8 — Isodose Map Feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QImage, QColor, QPen, QPainterPath

if TYPE_CHECKING:
    from app.core.isodose_engine import IsodoseResult


# Colormap: dose level → RGBA (hot-style)
def _dose_to_rgba(dose_map: np.ndarray) -> np.ndarray:
    """Convert normalized dose [0-1] to RGBA uint8 array.

    Uses a hot-style colormap: black → red → orange → yellow → white.
    Returns array of shape (ny, nx, 4).
    """
    h, w = dose_map.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    d = np.clip(dose_map, 0.0, 1.0)

    # Red channel: ramps from 0 at d=0 to 255 at d=0.4, stays 255
    rgba[:, :, 0] = np.clip(d * (255 / 0.4), 0, 255).astype(np.uint8)

    # Green channel: ramps from 0 at d=0.4 to 255 at d=0.8
    g = np.clip((d - 0.4) * (255 / 0.4), 0, 255)
    rgba[:, :, 1] = g.astype(np.uint8)

    # Blue channel: ramps from 0 at d=0.8 to 255 at d=1.0
    b = np.clip((d - 0.8) * (255 / 0.2), 0, 255)
    rgba[:, :, 2] = b.astype(np.uint8)

    # Alpha: transparent where dose is very low, opaque where high
    alpha = np.clip(d * 200, 0, 180).astype(np.uint8)
    # Very low dose → fully transparent
    alpha[d < 0.01] = 0
    rgba[:, :, 3] = alpha

    return rgba


class IsodoseOverlayItem(QGraphicsItem):
    """Semi-transparent isodose heatmap overlay on the canvas.

    Renders a 2D dose distribution as a colored overlay,
    positioned to match the collimator scene coordinates.
    """

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._image: QImage | None = None
        self._bounding = QRectF()
        self._x_min: float = 0.0
        self._y_min: float = 0.0
        self._x_range: float = 0.0
        self._y_range: float = 0.0
        self.setZValue(4)  # between beam lines (3) and scatter (5)

    def set_isodose_data(self, result: IsodoseResult) -> None:
        """Set isodose data for visualization.

        Args:
            result: IsodoseResult with dose_map and coordinates in mm.
        """
        self.prepareGeometryChange()

        x_mm = result.x_positions_mm
        y_mm = result.y_positions_mm
        self._x_min = float(x_mm[0])
        self._y_min = float(y_mm[0])
        self._x_range = float(x_mm[-1] - x_mm[0])
        self._y_range = float(y_mm[-1] - y_mm[0])

        # Convert dose_map to RGBA image
        rgba = _dose_to_rgba(result.dose_map)
        h, w = result.dose_map.shape

        # Create QImage from RGBA data
        # QImage expects data to persist, so we keep a copy
        self._rgba_data = rgba.copy()
        self._image = QImage(
            self._rgba_data.data,
            w, h,
            w * 4,
            QImage.Format.Format_RGBA8888,
        )

        margin = 5.0
        self._bounding = QRectF(
            self._x_min - margin,
            self._y_min - margin,
            self._x_range + 2 * margin,
            self._y_range + 2 * margin,
        )

        self.update()

    def clear(self) -> None:
        """Remove isodose visualization."""
        self.prepareGeometryChange()
        self._image = None
        self._rgba_data = None
        self._bounding = QRectF()
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bounding

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if self._image is None:
            return

        # Draw the heatmap image scaled to scene coordinates
        target_rect = QRectF(
            self._x_min, self._y_min,
            self._x_range, self._y_range,
        )
        painter.drawImage(target_rect, self._image)
