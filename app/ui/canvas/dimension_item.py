"""Dimension annotation item — measurement lines with labels.

Extension lines + arrowheads + centered mm-value label.
Color: TEXT_SECONDARY (#94A3B8).

Reference: Phase-03 spec — FR-1.3.4.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPolygonF

from app.ui.styles.colors import TEXT_SECONDARY


class DimensionItem(QGraphicsItem):
    """Dimension annotation with extension lines, arrows, and label.

    Supports horizontal and vertical orientations.
    """

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._start = QPointF()
        self._end = QPointF()
        self._label: str = ""
        self._offset: float = 15.0  # offset from geometry edge (scene units)
        self._horizontal: bool = True
        self.setZValue(40)

    def set_dimension(
        self,
        start: QPointF,
        end: QPointF,
        label: str,
        offset: float = 15.0,
        horizontal: bool = True,
    ) -> None:
        """Configure the dimension annotation.

        Args:
            start: Start point in scene coordinates.
            end: End point in scene coordinates.
            label: Text label (e.g. "120.0 mm").
            offset: Perpendicular offset from the measured edge.
            horizontal: True for width dims, False for height dims.
        """
        self.prepareGeometryChange()
        self._start = start
        self._end = end
        self._label = label
        self._offset = offset
        self._horizontal = horizontal

    def boundingRect(self) -> QRectF:
        x1 = min(self._start.x(), self._end.x()) - 30
        y1 = min(self._start.y(), self._end.y()) - 30
        x2 = max(self._start.x(), self._end.x()) + 30
        y2 = max(self._start.y(), self._end.y()) + 30
        return QRectF(x1, y1, x2 - x1, y2 - y1)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        if self._label == "":
            return

        color = QColor(TEXT_SECONDARY)
        pen = QPen(color, 1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        if self._horizontal:
            self._draw_horizontal(painter, color)
        else:
            self._draw_vertical(painter, color)

    def _draw_horizontal(self, painter: QPainter, color: QColor) -> None:
        """Draw a horizontal dimension (measures width)."""
        y = self._start.y() + self._offset
        x1 = self._start.x()
        x2 = self._end.x()

        # Extension lines
        painter.drawLine(QPointF(x1, self._start.y()), QPointF(x1, y + 3))
        painter.drawLine(QPointF(x2, self._end.y()), QPointF(x2, y + 3))

        # Dimension line
        painter.drawLine(QPointF(x1, y), QPointF(x2, y))

        # Arrows
        arrow_size = 4
        painter.drawLine(QPointF(x1, y), QPointF(x1 + arrow_size, y - arrow_size))
        painter.drawLine(QPointF(x1, y), QPointF(x1 + arrow_size, y + arrow_size))
        painter.drawLine(QPointF(x2, y), QPointF(x2 - arrow_size, y - arrow_size))
        painter.drawLine(QPointF(x2, y), QPointF(x2 - arrow_size, y + arrow_size))

        # Label
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        mid_x = (x1 + x2) / 2
        painter.drawText(
            QRectF(mid_x - 50, y - 16, 100, 14),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )

    def _draw_vertical(self, painter: QPainter, color: QColor) -> None:
        """Draw a vertical dimension (measures height)."""
        x = self._start.x() + self._offset
        y1 = self._start.y()
        y2 = self._end.y()

        # Extension lines
        painter.drawLine(QPointF(self._start.x(), y1), QPointF(x + 3, y1))
        painter.drawLine(QPointF(self._end.x(), y2), QPointF(x + 3, y2))

        # Dimension line
        painter.drawLine(QPointF(x, y1), QPointF(x, y2))

        # Arrows
        arrow_size = 4
        painter.drawLine(QPointF(x, y1), QPointF(x - arrow_size, y1 + arrow_size))
        painter.drawLine(QPointF(x, y1), QPointF(x + arrow_size, y1 + arrow_size))
        painter.drawLine(QPointF(x, y2), QPointF(x - arrow_size, y2 - arrow_size))
        painter.drawLine(QPointF(x, y2), QPointF(x + arrow_size, y2 - arrow_size))

        # Label
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        mid_y = (y1 + y2) / 2
        painter.save()
        painter.translate(x - 2, mid_y)
        painter.rotate(-90)
        painter.drawText(
            QRectF(-50, -14, 100, 14),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )
        painter.restore()
