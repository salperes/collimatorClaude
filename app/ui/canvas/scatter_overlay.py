"""Scatter overlay graphics item — Compton interaction visualization.

Draws scatter interaction points as colored circles and scattered
ray paths as dashed lines on the collimator canvas.

Limited to max_display interactions for performance (default: 50).
All positions received in cm (core units), converted to mm (scene units).

Reference: Phase-07 spec — Canvas Visualization.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import QRectF, QPointF, QLineF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

from app.core.units import cm_to_mm

# Scatter display colors
_SCATTER_POINT_COLOR = "#FFA726"     # orange — interaction in material
_SCATTER_HIT_COLOR = "#FF1744"       # bright red — reaches detector
_SCATTER_RAY_COLOR = "#EF4444"       # red — scattered ray path


class ScatterOverlayItem(QGraphicsItem):
    """Visualizes Compton scatter interactions on the canvas.

    Draws:
    - Orange circles at scatter interaction points.
    - Red dashed lines from interaction to detector for photons that
      reach the detector.
    - Bright red circles for scatter that reaches the detector.
    """

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._points: list[tuple[float, float, bool]] = []  # (x_mm, y_mm, reaches_det)
        self._ray_lines: list[tuple[QLineF, bool]] = []     # (line, reaches_det)
        self._bounding = QRectF()
        self._max_display: int = 50
        self.setZValue(5)  # above beam lines

    def set_max_display(self, n: int) -> None:
        """Set maximum number of interactions to display."""
        self._max_display = max(1, n)

    def set_scatter_data(
        self,
        interactions: list,
        detector_y_mm: float,
    ) -> None:
        """Set scatter interaction data for visualization.

        Args:
            interactions: ScatterInteraction list (core units: cm, radian).
            detector_y_mm: Detector Y position in scene units [mm].
        """
        self.prepareGeometryChange()
        self._points.clear()
        self._ray_lines.clear()

        # Limit display count
        display = interactions[: self._max_display]

        xs: list[float] = []
        ys: list[float] = []

        for si in display:
            x_mm = float(cm_to_mm(si.x))
            y_mm = float(cm_to_mm(si.y))
            self._points.append((x_mm, y_mm, si.reaches_detector))
            xs.append(x_mm)
            ys.append(y_mm)

            if si.reaches_detector:
                det_x_mm = float(cm_to_mm(si.detector_x_cm))
                line = QLineF(
                    QPointF(x_mm, y_mm),
                    QPointF(det_x_mm, detector_y_mm),
                )
                self._ray_lines.append((line, True))
                xs.append(det_x_mm)
                ys.append(detector_y_mm)

        if xs and ys:
            margin = 10.0
            self._bounding = QRectF(
                min(xs) - margin,
                min(ys) - margin,
                max(xs) - min(xs) + 2 * margin,
                max(ys) - min(ys) + 2 * margin,
            )
        else:
            self._bounding = QRectF()

        self.update()

    def clear(self) -> None:
        """Remove all scatter visualization."""
        self.prepareGeometryChange()
        self._points.clear()
        self._ray_lines.clear()
        self._bounding = QRectF()
        self.update()

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._bounding

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        if not self._points:
            return

        # Draw scattered ray paths (dashed, semi-transparent)
        for line, reaches in self._ray_lines:
            color = QColor(_SCATTER_HIT_COLOR if reaches else _SCATTER_RAY_COLOR)
            color.setAlpha(80)
            pen = QPen(color, 1.0, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(line)

        # Draw interaction points
        radius = 2.5
        for x_mm, y_mm, reaches in self._points:
            color = QColor(_SCATTER_HIT_COLOR if reaches else _SCATTER_POINT_COLOR)
            color.setAlpha(180)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x_mm, y_mm), radius, radius)
