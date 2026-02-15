"""Stage graphics item — represents a single CollimatorStage.

Contains a single material LayerItem and ApertureItem. Manages resize handles.
Coordinate system: item's local (0,0) = top-left of stage rect.
Each stage is independently draggable with snap-to-edge behavior.

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
    and height=outer_height. A single LayerItem fills the wall area.
    ApertureItem sits at the center.

    Independently draggable — snaps to nearby stage edges via scene callback.
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
        self._material_item: LayerItem | None = None
        self._aperture_item: ApertureItem | None = None
        self._handles: list[ResizeHandle] = []
        self._handle_callback = None  # set by scene
        self._locked: bool = False
        self._x_locked: bool = True  # X-axis locked by default
        self._dragging: bool = False

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

    @property
    def stage_index(self) -> int:
        return self._stage_index

    @stage_index.setter
    def stage_index(self, value: int) -> None:
        self._stage_index = value

    @property
    def width(self) -> float:
        return self._width

    @property
    def height(self) -> float:
        return self._height

    def set_handle_callback(self, callback) -> None:
        """Set callback for resize handle drags: fn(stage_idx, pos, dx, dy)."""
        self._handle_callback = callback

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

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._update_handle_visibility()
        self.update()

    def update_from_model(
        self,
        width: float,
        height: float,
        material_id: str,
        aperture_config,
        collimator_type,
    ) -> None:
        """Rebuild visual from model data.

        Args:
            width: Stage outer width [mm].
            height: Stage outer height [mm].
            material_id: Shielding material identifier.
            aperture_config: ApertureConfig for this stage.
            collimator_type: CollimatorType enum.
        """
        self.prepareGeometryChange()
        self._width = width
        self._height = height

        # Remove old material item
        if self._material_item and self._material_item.scene():
            self._material_item.scene().removeItem(self._material_item)
        self._material_item = None

        if self._aperture_item and self._aperture_item.scene():
            self._aperture_item.scene().removeItem(self._aperture_item)
        self._aperture_item = None

        # Solid material fill: entire stage rect (no inner void)
        if material_id:
            outer_rect = QRectF(0, 0, width, height)
            if outer_rect.width() > 0 and outer_rect.height() > 0:
                self._material_item = LayerItem(
                    self._stage_index, material_id, parent=self,
                )
                self._material_item.set_geometry(outer_rect, QRectF())

        # Aperture (drawn on top of material)
        self._aperture_item = ApertureItem(self._stage_index, parent=self)
        self._aperture_item.update_shape(
            aperture_config, collimator_type,
            width, height,
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
        if self._locked:
            return
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
        pen = QPen(pen_color, 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, self._width, self._height))

    # ------------------------------------------------------------------
    # Qt item change — snap + notification
    # ------------------------------------------------------------------

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Constrain X-axis during user drag only (not programmatic setPos)
            if self._x_locked and self._dragging:
                value = QPointF(self.pos().x(), value.y())
            # Snap to nearby stage edges via scene callback
            scene = self.scene()
            if scene and hasattr(scene, '_snap_stage_position'):
                return scene._snap_stage_position(self, value)
            return value

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Notify scene to update beam lines, gaps, dimensions
            scene = self.scene()
            if scene and hasattr(scene, '_on_stage_position_changed'):
                scene._on_stage_position_changed(self)

        return super().itemChange(change, value)

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        self._dragging = True
        # Emit stage_clicked for selection
        scene = self.scene()
        if scene and hasattr(scene, 'stage_clicked'):
            scene.stage_clicked.emit(self._stage_index)
        # Let Qt handle drag via ItemIsMovable
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        super().mouseReleaseEvent(event)
