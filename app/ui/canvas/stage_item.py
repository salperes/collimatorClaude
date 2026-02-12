"""Stage graphics item — represents a single CollimatorStage.

Contains child LayerItems and ApertureItem. Manages resize handles.
Coordinate system: item's local (0,0) = top-left of stage rect.

Reference: Phase-03 spec — Scene Hierarchy, FR-1.3.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QColor, QPen

from app.ui.canvas.layer_item import LayerItem
from app.ui.canvas.aperture_item import ApertureItem
from app.ui.canvas.resize_handle import ResizeHandle, HandlePosition
from app.ui.styles.colors import ACCENT


class StageItem(QGraphicsItem):
    """Visual representation of a CollimatorStage.

    The stage body is a rectangle at local (0,0) with width=outer_width
    and height=outer_height. Child LayerItems fill concentrically.
    ApertureItem sits at the center.
    """

    def __init__(
        self,
        stage_index: int,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._stage_index = stage_index
        self._width: float = 100.0
        self._height: float = 200.0
        self._selected: bool = False
        self._layer_items: list[LayerItem] = []
        self._aperture_item: ApertureItem | None = None
        self._handles: list[ResizeHandle] = []
        self._handle_callback = None  # set by scene

        self.setAcceptHoverEvents(True)

    @property
    def stage_index(self) -> int:
        return self._stage_index

    @stage_index.setter
    def stage_index(self, value: int) -> None:
        self._stage_index = value

    def set_handle_callback(self, callback) -> None:
        """Set callback for resize handle drags: fn(stage_idx, pos, dx, dy)."""
        self._handle_callback = callback

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._update_handle_visibility()
        self.update()

    def update_from_model(
        self,
        width: float,
        height: float,
        layers: list[tuple[str, float, str | None, float]],
        aperture_config,
        collimator_type,
    ) -> None:
        """Rebuild visual from model data.

        Args:
            width: Stage outer width [mm].
            height: Stage outer height [mm].
            layers: List of (material_id, thickness_mm, inner_material_id,
                    inner_width) from inner to outer.
            aperture_config: ApertureConfig for this stage.
            collimator_type: CollimatorType enum.
        """
        self.prepareGeometryChange()
        self._width = width
        self._height = height

        # Remove old children
        for item in self._layer_items:
            if item.scene():
                item.scene().removeItem(item)
        self._layer_items.clear()

        if self._aperture_item and self._aperture_item.scene():
            self._aperture_item.scene().removeItem(self._aperture_item)
        self._aperture_item = None

        # Build layer rects concentrically (outermost first)
        total_thickness = sum(t for _, t, *_ in layers)
        accumulated = 0.0

        # Iterate outer to inner (reverse order)
        for idx, (mat_id, thickness, inner_mat, inner_w) in enumerate(
            reversed(layers)
        ):
            outer_offset = accumulated
            accumulated += thickness
            inner_offset = accumulated

            outer_rect = QRectF(
                outer_offset, outer_offset,
                width - 2 * outer_offset,
                height - 2 * outer_offset,
            )
            inner_rect = QRectF(
                inner_offset, inner_offset,
                width - 2 * inner_offset,
                height - 2 * inner_offset,
            )

            # Ensure rects are valid
            if outer_rect.width() <= 0 or outer_rect.height() <= 0:
                continue

            layer_idx = len(layers) - 1 - idx  # original order index
            layer_item = LayerItem(
                self._stage_index, layer_idx, mat_id, parent=self,
            )
            layer_item.set_geometry(outer_rect, inner_rect)
            layer_item.set_composite(inner_mat, inner_w)
            self._layer_items.append(layer_item)

        # Aperture
        self._aperture_item = ApertureItem(self._stage_index, parent=self)
        self._aperture_item.update_shape(
            aperture_config, collimator_type,
            width, height, total_thickness,
        )

        # Rebuild handles
        self._rebuild_handles()

    def _rebuild_handles(self) -> None:
        """Create resize handles on edges."""
        for h in self._handles:
            if h.scene():
                h.scene().removeItem(h)
        self._handles.clear()

        positions = [
            (HandlePosition.RIGHT, QPointF(self._width, self._height / 2)),
            (HandlePosition.LEFT, QPointF(0, self._height / 2)),
            (HandlePosition.BOTTOM, QPointF(self._width / 2, self._height)),
            (HandlePosition.TOP, QPointF(self._width / 2, 0)),
        ]

        for pos, point in positions:
            handle = ResizeHandle(pos, self._on_handle_moved, parent=self)
            handle.setPos(point)
            handle.setVisible(self._selected)
            self._handles.append(handle)

    def _on_handle_moved(self, position: HandlePosition, dx: float, dy: float) -> None:
        """Handle drag -> report to scene via callback."""
        if self._handle_callback:
            self._handle_callback(self._stage_index, position, dx, dy)

    def _update_handle_visibility(self) -> None:
        for h in self._handles:
            h.setVisible(self._selected)

    def boundingRect(self) -> QRectF:
        return QRectF(-2, -2, self._width + 4, self._height + 4)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        # Stage outline
        pen_color = QColor(ACCENT) if self._selected else QColor("#78909C")
        pen_width = 2 if self._selected else 1
        pen = QPen(pen_color, pen_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, self._width, self._height))

    def mousePressEvent(self, event) -> None:
        event.accept()
        scene = self.scene()
        if scene and hasattr(scene, 'stage_clicked'):
            scene.stage_clicked.emit(self._stage_index)

    def get_layer_item(self, layer_index: int) -> LayerItem | None:
        """Find LayerItem by layer index."""
        for item in self._layer_items:
            if item.layer_index == layer_index:
                return item
        return None
