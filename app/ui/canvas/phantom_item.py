"""Phantom graphics item — draggable test object icon on canvas.

Renders wire, line-pair, or grid phantom icons with labels.
Draggable along Y-axis (constrained), reports position changes.

Reference: Phase-03.5 spec — Phantom Visualization.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from app.models.phantom import PhantomType
from app.ui.styles.colors import ACCENT, PHANTOM_WIRE, PHANTOM_LINE_PAIR, PHANTOM_GRID


ICON_HALF = 10.0  # half-size of icon area [scene units = mm]

_TYPE_COLORS = {
    PhantomType.WIRE: PHANTOM_WIRE,
    PhantomType.LINE_PAIR: PHANTOM_LINE_PAIR,
    PhantomType.GRID: PHANTOM_GRID,
}


class PhantomItem(QGraphicsItem):
    """Canvas item for a test object (phantom).

    Renders type-specific icon and label. Draggable along Y-axis.

    Args:
        phantom_index: Index into geometry.phantoms list.
        phantom_type: Type of phantom for icon selection.
    """

    def __init__(
        self,
        phantom_index: int,
        phantom_type: PhantomType,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._index = phantom_index
        self._type = phantom_type
        self._label = ""
        self._enabled = True
        self._selected: bool = False
        self._locked: bool = True
        self._x_locked: bool = True
        self._label_visible: bool = True
        self._dragging: bool = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.ForbiddenCursor)
        self.setZValue(45)

    @property
    def phantom_index(self) -> int:
        return self._index

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_label(self, label: str) -> None:
        self._label = label
        self.update()

    @property
    def locked(self) -> bool:
        return self._locked

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)

    @property
    def x_locked(self) -> bool:
        return self._x_locked

    def set_x_locked(self, locked: bool) -> None:
        self._x_locked = locked
        self.setCursor(
            Qt.CursorShape.ForbiddenCursor if locked
            else Qt.CursorShape.SizeVerCursor
        )

    def set_label_visible(self, visible: bool) -> None:
        self._label_visible = visible
        self.update()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.setOpacity(1.0 if enabled else 0.3)
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(-40, -ICON_HALF - 2, 80, ICON_HALF * 2 + 18)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        color = QColor(_TYPE_COLORS.get(self._type, PHANTOM_WIRE))

        pen = QPen(color, 2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        match self._type:
            case PhantomType.WIRE:
                self._paint_wire(painter, color)
            case PhantomType.LINE_PAIR:
                self._paint_line_pair(painter, color)
            case PhantomType.GRID:
                self._paint_grid(painter, color)

        # Selection highlight
        if self._selected:
            sel_pen = QPen(QColor(ACCENT), 2)
            sel_pen.setCosmetic(True)
            sel_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(-ICON_HALF - 4, -ICON_HALF - 4,
                                    ICON_HALF * 2 + 8, ICON_HALF * 2 + 8))

        # Label
        if self._label_visible:
            painter.setPen(QColor("#F8FAFC"))
            font = QFont("Segoe UI", 7)
            painter.setFont(font)
            painter.drawText(
                QRectF(-35, ICON_HALF, 70, 14),
                Qt.AlignmentFlag.AlignCenter,
                self._label,
            )

    def _paint_wire(self, painter: QPainter, color: QColor) -> None:
        """Wire: horizontal line with dots at ends."""
        w = ICON_HALF * 1.5
        painter.drawLine(QPointF(-w, 0), QPointF(w, 0))
        # End dots
        painter.setBrush(color)
        painter.drawEllipse(QPointF(-w, 0), 2, 2)
        painter.drawEllipse(QPointF(w, 0), 2, 2)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_line_pair(self, painter: QPainter, color: QColor) -> None:
        """Line-pair: 3 vertical bars."""
        bar_w = 3.0
        spacing = 5.0
        h = ICON_HALF * 0.8
        painter.setBrush(color)
        for i in range(3):
            x = -spacing + i * spacing
            painter.drawRect(QRectF(x - bar_w / 2, -h, bar_w, h * 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_grid(self, painter: QPainter, color: QColor) -> None:
        """Grid: crosshatch pattern."""
        s = ICON_HALF * 0.7
        # Horizontal lines
        for i in range(-2, 3):
            y = i * s / 2
            painter.drawLine(QPointF(-s, y), QPointF(s, y))
        # Vertical lines
        for i in range(-2, 3):
            x = i * s / 2
            painter.drawLine(QPointF(x, -s), QPointF(x, s))

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
        return super().itemChange(change, value)
