"""Layer graphics item — material layer rendered as filled ring.

Each layer is a concentric rectangle within its parent StageItem.
Fill: material color @ 70% opacity. Dashed borders between layers.

Reference: Phase-03 spec — FR-1.4.5, Layer Visualization.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath

from app.constants import LAYER_OPACITY, LAYER_BORDER_OPACITY
from app.ui.styles.colors import MATERIAL_COLORS


class LayerItem(QGraphicsItem):
    """Material layer rendered as a filled ring (outer_rect minus inner_rect).

    Fill: material color at 70% opacity.
    Inner border: white dashed line at 30% opacity.
    Highlighted state: brighter fill + solid accent border.
    """

    def __init__(
        self,
        stage_index: int,
        layer_index: int,
        material_id: str,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._stage_index = stage_index
        self._layer_index = layer_index
        self._material_id = material_id
        self._outer_rect = QRectF()
        self._inner_rect = QRectF()
        self._highlighted = False
        self._inner_material_id: str | None = None
        self._inner_width: float = 0.0

        self.setAcceptHoverEvents(True)

    @property
    def stage_index(self) -> int:
        return self._stage_index

    @property
    def layer_index(self) -> int:
        return self._layer_index

    def set_geometry(self, outer_rect: QRectF, inner_rect: QRectF) -> None:
        """Set layer outer and inner rectangles (in parent coords)."""
        self.prepareGeometryChange()
        self._outer_rect = outer_rect
        self._inner_rect = inner_rect

    def set_material(self, material_id: str) -> None:
        self._material_id = material_id
        self.update()

    def set_composite(
        self, inner_material_id: str | None, inner_width: float,
    ) -> None:
        """Set composite zone data for İç/Dış rendering."""
        self._inner_material_id = inner_material_id
        self._inner_width = inner_width
        self.update()

    def set_highlighted(self, highlighted: bool) -> None:
        self._highlighted = highlighted
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

        alpha = 220 if self._highlighted else int(255 * LAYER_OPACITY)
        is_composite = (
            self._inner_material_id is not None and self._inner_width > 0
        )

        if is_composite and not self._inner_rect.isEmpty():
            # Composite layer: split into inner zone + outer zone
            iw = self._inner_width
            mid_rect = self._inner_rect.adjusted(-iw, -iw, iw, iw)
            # Clamp mid_rect to outer_rect
            mid_rect = mid_rect.intersected(self._outer_rect)

            # Inner zone (aperture side): inner_rect → mid_rect
            inner_path = QPainterPath()
            inner_path.addRect(mid_rect)
            ir_path = QPainterPath()
            ir_path.addRect(self._inner_rect)
            inner_path = inner_path.subtracted(ir_path)

            inner_color = QColor(
                MATERIAL_COLORS.get(self._inner_material_id, "#64748B")
            )
            inner_color.setAlpha(alpha)
            painter.fillPath(inner_path, inner_color)

            # Outer zone (outside): mid_rect → outer_rect
            outer_path = QPainterPath()
            outer_path.addRect(self._outer_rect)
            mid_sub = QPainterPath()
            mid_sub.addRect(mid_rect)
            outer_path = outer_path.subtracted(mid_sub)

            outer_color = QColor(
                MATERIAL_COLORS.get(self._material_id, "#64748B")
            )
            outer_color.setAlpha(alpha)
            painter.fillPath(outer_path, outer_color)

            # Dashed border at zone boundary
            zone_pen = QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DotLine)
            zone_pen.setCosmetic(True)
            painter.setPen(zone_pen)
            painter.drawRect(mid_rect)
        else:
            # Non-composite: single material fill
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
            border_color.setAlpha(int(255 * LAYER_BORDER_OPACITY))
            pen = QPen(border_color, 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawRect(self._inner_rect)

        # Highlight border
        if self._highlighted:
            highlight_pen = QPen(QColor("#3B82F6"), 2, Qt.PenStyle.SolidLine)
            highlight_pen.setCosmetic(True)
            painter.setPen(highlight_pen)
            painter.drawRect(self._outer_rect)

    def mousePressEvent(self, event) -> None:
        # Propagate to scene for layer selection
        event.accept()
        scene = self.scene()
        if scene and hasattr(scene, 'layer_clicked'):
            scene.layer_clicked.emit(self._stage_index, self._layer_index)
