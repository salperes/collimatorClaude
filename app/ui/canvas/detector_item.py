"""Detector graphics item — draggable horizontal line.

Shows detector active width as a line segment, draggable along Y-axis.

Reference: Phase-03 spec — FR-1.5.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from app.ui.styles.colors import SUCCESS


class DetectorItem(QGraphicsItem):
    """Detector line — draggable horizontal bar with width label."""

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._width: float = 500.0  # mm
        self._on_moved: callable | None = None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setZValue(50)

    def set_move_callback(self, callback: callable) -> None:
        """Set callback for position changes from canvas drag."""
        self._on_moved = callback

    def set_width(self, width_mm: float) -> None:
        self.prepareGeometryChange()
        self._width = width_mm
        self.update()

    @property
    def detector_width(self) -> float:
        return self._width

    def boundingRect(self) -> QRectF:
        hw = self._width / 2.0
        return QRectF(-hw - 5, -10, self._width + 10, 25)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        color = QColor(SUCCESS)
        hw = self._width / 2.0

        # Detector line
        pen = QPen(color, 3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLine(QPointF(-hw, 0), QPointF(hw, 0))

        # End caps
        cap_pen = QPen(color, 2)
        cap_pen.setCosmetic(True)
        painter.setPen(cap_pen)
        painter.drawLine(QPointF(-hw, -5), QPointF(-hw, 5))
        painter.drawLine(QPointF(hw, -5), QPointF(hw, 5))

        # Label
        painter.setPen(QColor("#F8FAFC"))
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        painter.drawText(
            QRectF(-40, 5, 80, 12),
            Qt.AlignmentFlag.AlignCenter,
            f"Detektor ({self._width:.0f}mm)",
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return QPointF(self.pos().x(), value.y())
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved(value.x(), value.y())
        return super().itemChange(change, value)
