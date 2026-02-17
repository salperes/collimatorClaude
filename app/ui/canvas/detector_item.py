"""Detector graphics item — draggable horizontal line.

Shows detector active width as a line segment, draggable along Y-axis.

Reference: Phase-03 spec — FR-1.5.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from app.ui.styles.colors import ACCENT, SUCCESS


class DetectorItem(QGraphicsItem):
    """Detector line — draggable horizontal bar with width label."""

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._width: float = 500.0  # mm
        self._selected: bool = False
        self._on_moved: callable | None = None
        self._locked: bool = True
        self._x_locked: bool = True
        self._label_visible: bool = True
        self._dragging: bool = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.ForbiddenCursor)
        self.setZValue(50)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_move_callback(self, callback: callable) -> None:
        """Set callback for position changes from canvas drag."""
        self._on_moved = callback

    @property
    def locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        self.setCursor(
            Qt.CursorShape.ForbiddenCursor if locked
            else Qt.CursorShape.SizeVerCursor
        )

    @property
    def x_locked(self) -> bool:
        return self._x_locked

    def set_x_locked(self, locked: bool) -> None:
        self._x_locked = locked

    def set_label_visible(self, visible: bool) -> None:
        self._label_visible = visible
        self.update()

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

        # Selection highlight
        if self._selected:
            sel_pen = QPen(QColor(ACCENT), 2)
            sel_pen.setCosmetic(True)
            sel_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(-hw - 3, -8, self._width + 6, 16))

        # Label
        if self._label_visible:
            painter.setPen(QColor("#F8FAFC"))
            font = QFont("Segoe UI", 7)
            painter.setFont(font)
            painter.drawText(
                QRectF(-40, 5, 80, 12),
                Qt.AlignmentFlag.AlignCenter,
                f"Detektor ({self._width:.0f}mm)",
            )

    def mousePressEvent(self, event) -> None:
        self._dragging = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._x_locked and self._dragging:
                return QPointF(self.pos().x(), value.y())
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._on_moved:
                self._on_moved(value.x(), value.y())
        return super().itemChange(change, value)
