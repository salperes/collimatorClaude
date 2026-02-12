"""Background grid item for the collimator canvas.

Draws a scaled grid with thin/thick line hierarchy.
Paints only within the visible viewport for performance.

Reference: Phase-03 spec — FR-1.1.2.
"""

import math

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget
from PyQt6.QtCore import QRectF, QPointF, QLineF
from PyQt6.QtGui import QPainter, QPen, QColor

from app.ui.styles.colors import PANEL_BG, SURFACE
from app.constants import DEFAULT_GRID_SPACING


class GridItem(QGraphicsItem):
    """Background grid with thin/thick line hierarchy.

    Colors:
        Thin lines:  PANEL_BG (#1E293B)
        Thick lines: SURFACE (#334155)

    Grid adapts to current view — only draws lines within visible area.
    Uses cosmetic pen widths (do not scale with zoom).
    """

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._grid_spacing: float = DEFAULT_GRID_SPACING  # mm
        self._visible_rect: QRectF = QRectF(-2000, -2000, 4000, 4000)
        self.setZValue(-100)  # behind everything

    def set_grid_spacing(self, spacing_mm: float) -> None:
        """Update grid spacing [mm]."""
        if spacing_mm > 0:
            self._grid_spacing = spacing_mm
            self.update()

    def set_visible_rect(self, rect: QRectF) -> None:
        """Update the visible area for optimized painting."""
        self._visible_rect = rect
        self.update()

    @property
    def grid_spacing(self) -> float:
        return self._grid_spacing

    def boundingRect(self) -> QRectF:
        return QRectF(-5000, -5000, 10000, 10000)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        rect = self._visible_rect
        spacing = self._grid_spacing

        # Thin lines (slightly brighter for visibility)
        thin_pen = QPen(QColor("#253248"))
        thin_pen.setWidthF(0)  # cosmetic (1px regardless of zoom)
        thin_pen.setCosmetic(True)

        # Thick lines (every 5th — brighter)
        thick_pen = QPen(QColor("#3D5068"))
        thick_pen.setWidthF(0)
        thick_pen.setCosmetic(True)

        major_spacing = spacing * 5.0

        # Vertical lines
        x_start = math.floor(rect.left() / spacing) * spacing
        x = x_start
        while x <= rect.right():
            is_major = abs(x % major_spacing) < 0.01 * spacing
            painter.setPen(thick_pen if is_major else thin_pen)
            painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            x += spacing

        # Horizontal lines
        y_start = math.floor(rect.top() / spacing) * spacing
        y = y_start
        while y <= rect.bottom():
            is_major = abs(y % major_spacing) < 0.01 * spacing
            painter.setPen(thick_pen if is_major else thin_pen)
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
            y += spacing
