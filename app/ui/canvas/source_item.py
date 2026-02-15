"""Source graphics item — draggable X-ray source icon.

Star/crosshair icon with focal spot size label.
Draggable along Y-axis, reports position changes to controller.

Reference: Phase-03 spec — FR-1.5.1.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QFont, QRadialGradient, QBrush,
)

from app.models.geometry import FocalSpotDistribution
from app.ui.styles.colors import WARNING


ICON_SIZE = 12.0  # scene units (mm)


class SourceItem(QGraphicsItem):
    """X-ray source icon — draggable star with focal spot label.

    Gaussian distribution renders a radial gradient around the center;
    uniform distribution renders a solid circle.
    """

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._focal_spot_size: float = 1.0  # mm
        self._distribution = FocalSpotDistribution.UNIFORM
        self._on_moved: callable | None = None
        self._locked: bool = False
        self._x_locked: bool = True
        self._dragging: bool = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setZValue(50)

    def set_focal_spot(self, size_mm: float) -> None:
        self._focal_spot_size = size_mm
        self.update()

    def set_distribution(self, dist: FocalSpotDistribution) -> None:
        self._distribution = dist
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

    def boundingRect(self) -> QRectF:
        s = ICON_SIZE
        return QRectF(-s, -s, s * 2, s * 2 + 15)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        color = QColor(WARNING)

        # Focal spot glow — shows distribution type
        glow_r = ICON_SIZE * 0.45
        if self._distribution == FocalSpotDistribution.GAUSSIAN:
            grad = QRadialGradient(QPointF(0, 0), glow_r)
            c_center = QColor(color)
            c_center.setAlpha(120)
            c_edge = QColor(color)
            c_edge.setAlpha(0)
            grad.setColorAt(0.0, c_center)
            grad.setColorAt(0.5, QColor(color.red(), color.green(), color.blue(), 50))
            grad.setColorAt(1.0, c_edge)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawEllipse(QPointF(0, 0), glow_r, glow_r)
        else:
            c_fill = QColor(color)
            c_fill.setAlpha(50)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c_fill)
            painter.drawEllipse(QPointF(0, 0), glow_r, glow_r)

        # Star shape
        pen = QPen(color, 2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        s = ICON_SIZE * 0.6
        # Crosshair
        painter.drawLine(QPointF(0, -s), QPointF(0, s))
        painter.drawLine(QPointF(-s, 0), QPointF(s, 0))
        # Diagonals
        d = s * 0.6
        painter.drawLine(QPointF(-d, -d), QPointF(d, d))
        painter.drawLine(QPointF(-d, d), QPointF(d, -d))

        # Center dot
        painter.setBrush(color)
        painter.setPen(QPen(color, 1))
        painter.drawEllipse(QPointF(0, 0), 2, 2)

        # Label
        painter.setPen(QColor("#F8FAFC"))
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        dist_tag = "G" if self._distribution == FocalSpotDistribution.GAUSSIAN else "U"
        painter.drawText(
            QRectF(-35, s + 2, 70, 12),
            Qt.AlignmentFlag.AlignCenter,
            f"Kaynak ({self._focal_spot_size:.1f}mm {dist_tag})",
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
