"""Resize handle for interactive geometry editing.

Small cosmetic squares on edges/corners of stages and apertures.
Drag callback reports delta to parent item.

Reference: Phase-03 spec — FR-1.3, Handle System.
"""

from enum import Enum
from typing import Callable

from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor

from app.constants import HANDLE_SIZE
from app.ui.styles.colors import ACCENT


HANDLE_NORMAL = QColor("#64748B")
HANDLE_HOVER = QColor(ACCENT)


class HandlePosition(Enum):
    """Edge or corner position of a resize handle."""
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


# Cursor map
_CURSORS = {
    HandlePosition.TOP: Qt.CursorShape.SizeVerCursor,
    HandlePosition.BOTTOM: Qt.CursorShape.SizeVerCursor,
    HandlePosition.LEFT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.RIGHT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    HandlePosition.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
}


class ResizeHandle(QGraphicsRectItem):
    """Draggable handle for resizing geometry elements.

    Cosmetic 6x6px square that stays fixed-size at all zoom levels.
    Normal: #64748B, Hover: #3B82F6.
    Reports drag deltas via callback(position, dx_scene, dy_scene).
    """

    def __init__(
        self,
        position: HandlePosition,
        callback: Callable[[HandlePosition, float, float], None],
        parent: QGraphicsItem | None = None,
    ):
        hs = HANDLE_SIZE
        super().__init__(-hs / 2, -hs / 2, hs, hs, parent)
        self._position = position
        self._callback = callback
        self._hovered = False
        self._drag_start: QPointF | None = None

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(_CURSORS.get(position, Qt.CursorShape.ArrowCursor))
        self.setZValue(100)

        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(HANDLE_NORMAL)

    @property
    def handle_position(self) -> HandlePosition:
        return self._position

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        color = HANDLE_HOVER if self._hovered else HANDLE_NORMAL
        painter.setBrush(color)
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawRect(self.rect())

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.scenePos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None:
            current = event.scenePos()
            dx = current.x() - self._drag_start.x()
            dy = current.y() - self._drag_start.y()
            self._drag_start = current
            self._callback(self._position, dx, dy)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
