"""Gap graphics item — visual gap between collimator stages.

Rendered as a dashed-border region with a distance label.

Reference: Phase-03 spec — Scene Hierarchy.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from app.ui.styles.colors import PANEL_BG, TEXT_SECONDARY


class GapItem(QGraphicsItem):
    """Visual gap between two stages.

    Dashed-border rectangle, PANEL_BG background, centered distance label.
    """

    def __init__(
        self,
        gap_index: int,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._gap_index = gap_index
        self._rect = QRectF()
        self._gap_mm: float = 0.0
        self.setZValue(-5)

    def set_gap(self, rect: QRectF, gap_mm: float) -> None:
        """Set gap rectangle and distance value."""
        self.prepareGeometryChange()
        self._rect = rect
        self._gap_mm = gap_mm

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-2, -2, 2, 2)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        if self._rect.isEmpty() or self._gap_mm <= 0:
            return

        # Fill
        fill = QColor(PANEL_BG)
        fill.setAlpha(80)
        painter.fillRect(self._rect, fill)

        # Dashed border
        pen = QPen(QColor(PANEL_BG), 1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(self._rect)

        # Distance label
        painter.setPen(QColor(TEXT_SECONDARY))
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        label = f"{self._gap_mm:.1f} mm"
        painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, label)
