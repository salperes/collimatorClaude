"""Layer graphics item — material layer rendered as filled ring.

Each stage has a single material layer rendered as a concentric rectangle.
Fill: material color @ 70% opacity.

Reference: Phase-03 spec — FR-1.4.5, Layer Visualization.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath

from app.constants import LAYER_OPACITY
from app.ui.styles.colors import MATERIAL_COLORS


class LayerItem(QGraphicsItem):
    """Material layer rendered as a filled ring (outer_rect minus inner_rect).

    Fill: material color at LAYER_OPACITY.
    Inner border: white dashed line at 40% opacity.
    Mouse-transparent — events pass through to parent StageItem.
    """

    def __init__(
        self,
        stage_index: int,
        material_id: str,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._stage_index = stage_index
        self._material_id = material_id
        self._outer_rect = QRectF()
        self._inner_rect = QRectF()

        # Let mouse events pass through to parent StageItem
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(True)

    @property
    def stage_index(self) -> int:
        return self._stage_index

    def set_geometry(self, outer_rect: QRectF, inner_rect: QRectF) -> None:
        """Set layer outer and inner rectangles (in parent coords)."""
        self.prepareGeometryChange()
        self._outer_rect = outer_rect
        self._inner_rect = inner_rect

    def set_material(self, material_id: str) -> None:
        self._material_id = material_id
        self.update()

    def boundingRect(self) -> QRectF:
        return self._outer_rect.adjusted(-2, -2, 2, 2)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        if self._outer_rect.isEmpty():
            return

        alpha = int(255 * LAYER_OPACITY)

        # Single material fill
        path = QPainterPath()
        path.addRect(self._outer_rect)
        if not self._inner_rect.isEmpty():
            inner_path = QPainterPath()
            inner_path.addRect(self._inner_rect)
            path = path.subtracted(inner_path)

        hex_color = MATERIAL_COLORS.get(self._material_id, "#64748B")
        color = QColor(hex_color)
        color.setAlpha(alpha)
        painter.fillPath(path, color)

        # Dashed border at inner edge
        if not self._inner_rect.isEmpty():
            border_color = QColor("#FFFFFF")
            border_color.setAlpha(100)
            pen = QPen(border_color, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawRect(self._inner_rect)

