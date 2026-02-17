"""Collimator canvas scene — QGraphicsScene containing all visual items.

Manages the scene graph hierarchy, layout algorithm, and synchronization
with the GeometryController.

Scene hierarchy:
  GridItem -> StageItems + GapItems -> SourceItem -> DetectorItem ->
  BeamLinesItem -> DimensionItems

Coordinate system: 1 scene unit = 1 mm.
  X-axis = lateral (positive right), Y-axis = beam direction (positive down).
  Origin = source position (0, 0).

Each stage is independently draggable with snap-to-edge behavior.

Reference: Phase-03 spec — Canvas Implementation.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsSceneContextMenuEvent,
    QGraphicsSceneMouseEvent, QMenu,
)
from PyQt6.QtCore import QRectF, QPointF, QLineF, pyqtSignal
from PyQt6.QtGui import QColor, QAction

from app.core.i18n import t
from app.models.geometry import CollimatorType, ApertureConfig
from app.models.phantom import PhantomType
from app.constants import MIN_STAGES, MAX_STAGES, MAX_PHANTOMS
from app.ui.canvas.geometry_controller import GeometryController
from app.ui.canvas.grid_item import GridItem
from app.ui.canvas.stage_item import StageItem
from app.ui.canvas.source_item import SourceItem
from app.ui.canvas.detector_item import DetectorItem
from app.ui.canvas.beam_lines_item import BeamLinesItem
from app.ui.canvas.dimension_item import DimensionItem
from app.ui.canvas.phantom_item import PhantomItem
from app.ui.canvas.resize_handle import HandlePosition
from app.ui.canvas.isodose_overlay import IsodoseOverlayItem
from app.ui.canvas.scatter_overlay import ScatterOverlayItem
from app.ui.styles.colors import BACKGROUND

# Snap threshold in scene coordinates (mm)
SNAP_THRESHOLD = 8.0


class CollimatorScene(QGraphicsScene):
    """QGraphicsScene containing the complete collimator cross-section.

    Builds and maintains all visual items from GeometryController data.
    Stages are independently draggable with edge/corner snapping.
    """

    stage_clicked = pyqtSignal(int)
    show_properties_requested = pyqtSignal(str)  # "stage", "source", "detector", "phantom"

    def __init__(
        self,
        controller: GeometryController,
        parent=None,
    ):
        super().__init__(parent)
        self._controller = controller
        self.setBackgroundBrush(QColor(BACKGROUND))

        # Scene items
        self._grid_item = GridItem()
        self.addItem(self._grid_item)

        self._stage_items: list[StageItem] = []
        self._phantom_items: list[PhantomItem] = []
        self._source_item = SourceItem()
        self._detector_item = DetectorItem()
        self._beam_lines_item = BeamLinesItem()
        self._isodose_overlay = IsodoseOverlayItem()
        self._scatter_overlay = ScatterOverlayItem()
        self._dimension_items: list[DimensionItem] = []
        self._dimensions_visible: bool = True
        self._labels_visible: bool = True
        self._rebuilding: bool = False

        self.addItem(self._source_item)
        self.addItem(self._detector_item)
        self.addItem(self._beam_lines_item)
        self.addItem(self._isodose_overlay)
        self.addItem(self._scatter_overlay)

        self._connect_signals()
        self.rebuild()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        ctrl = self._controller

        # Full rebuilds
        ctrl.geometry_changed.connect(self.rebuild)
        ctrl.stage_added.connect(lambda _: self.rebuild())
        ctrl.stage_removed.connect(lambda _: self.rebuild())
        ctrl.collimator_type_changed.connect(lambda _: self.rebuild())

        # Partial updates
        ctrl.stage_changed.connect(self._on_stage_changed)
        ctrl.stage_selected.connect(self._on_stage_selected)
        ctrl.source_changed.connect(self._update_source)
        ctrl.detector_changed.connect(self._update_detector)

        # Lightweight position sync from panel spinners
        ctrl.stage_position_changed.connect(self._on_stage_position_signal)

        # Phantom signals
        ctrl.phantom_added.connect(lambda _: self.rebuild())
        ctrl.phantom_removed.connect(lambda _: self.rebuild())
        ctrl.phantom_changed.connect(self._on_phantom_changed)

        # Scene click signals -> controller
        self.stage_clicked.connect(ctrl.select_stage)

        # Draggable source/detector -> controller
        self._source_item.setFlag(
            SourceItem.GraphicsItemFlag.ItemSendsGeometryChanges, True,
        )
        self._detector_item.setFlag(
            DetectorItem.GraphicsItemFlag.ItemSendsGeometryChanges, True,
        )
        self._source_item.set_move_callback(
            lambda x, y: ctrl.set_source_position(x, 0)
        )
        self._detector_item.set_move_callback(
            lambda x, y: ctrl.set_detector_position(x, y)
        )

    # ------------------------------------------------------------------
    # Full rebuild
    # ------------------------------------------------------------------

    def rebuild(self) -> None:
        """Complete rebuild of all scene items from controller geometry."""
        self._rebuilding = True
        geo = self._controller.geometry

        # Remove old stage items
        for item in self._stage_items:
            self.removeItem(item)
        self._stage_items.clear()

        for item in self._dimension_items:
            self.removeItem(item)
        self._dimension_items.clear()

        # Create stage items
        for i, stage in enumerate(geo.stages):
            stage_item = StageItem(i)
            stage_item.set_handle_callback(self._on_handle_moved)
            stage_item.update_from_model(
                stage.outer_width, stage.outer_height,
                stage.material_id,
                stage.aperture, geo.type,
            )
            self.addItem(stage_item)
            self._stage_items.append(stage_item)

        # Remove old phantom items
        for item in self._phantom_items:
            self.removeItem(item)
        self._phantom_items.clear()

        # Create phantom items
        for i, phantom in enumerate(geo.phantoms):
            p_item = PhantomItem(i, phantom.config.type)
            p_item.set_label(phantom.config.name)
            p_item.set_enabled(phantom.config.enabled)
            p_item.setPos(0, phantom.config.position_y)
            self.addItem(p_item)
            self._phantom_items.append(p_item)

        # Layout stages and gaps (initial positions)
        self._layout_stages()
        self._rebuilding = False

        # Update source, detector, beams, dimensions
        self._update_source()
        self._update_detector()
        self._update_beam_lines()
        self._update_dimensions()

        # Highlight active stage
        active = self._controller.active_stage_index
        self._on_stage_selected(active)

    # ------------------------------------------------------------------
    # Layout (initial positioning from model)
    # ------------------------------------------------------------------

    def _layout_stages(self) -> None:
        """Position stages from their explicit y_position and x_offset.

        Scene coordinates: item pos = top-left corner.
        stage_x = x_offset - outer_width / 2  (center to top-left)
        stage_y = y_position                   (already top-edge)
        """
        geo = self._controller.geometry
        for i, stage in enumerate(geo.stages):
            stage_x = stage.x_offset - stage.outer_width / 2.0
            stage_y = stage.y_position
            self._stage_items[i].setPos(stage_x, stage_y)

    # ------------------------------------------------------------------
    # Stage snap logic (called from StageItem.itemChange)
    # ------------------------------------------------------------------

    def _snap_stage_position(self, moving: StageItem, new_pos: QPointF) -> QPointF:
        """Snap a moving stage to nearby edges/corners of other stages.

        Checks Y-axis snaps (top-bottom, bottom-top, top-top, bottom-bottom)
        and X-axis snaps (left-left, right-right, left-right, right-left,
        center-center). Returns the snapped position.

        Args:
            moving: The stage item being dragged.
            new_pos: Proposed new position (top-left corner).

        Returns:
            Possibly adjusted position with snap applied.
        """
        if self._rebuilding:
            return new_pos

        snap_x = new_pos.x()
        snap_y = new_pos.y()
        best_dx = SNAP_THRESHOLD
        best_dy = SNAP_THRESHOLD

        m_w = moving.width
        m_h = moving.height
        # Moving stage edges at proposed position
        m_left = new_pos.x()
        m_right = new_pos.x() + m_w
        m_top = new_pos.y()
        m_bottom = new_pos.y() + m_h
        m_cx = new_pos.x() + m_w / 2.0

        for other in self._stage_items:
            if other is moving:
                continue

            o_pos = other.pos()
            o_w = other.width
            o_h = other.height
            o_left = o_pos.x()
            o_right = o_pos.x() + o_w
            o_top = o_pos.y()
            o_bottom = o_pos.y() + o_h
            o_cx = o_pos.x() + o_w / 2.0

            # ── Y-axis snaps ──

            # Bottom of moving → Top of other (stack above)
            dy = abs(m_bottom - o_top)
            if dy < best_dy:
                best_dy = dy
                snap_y = o_top - m_h

            # Top of moving → Bottom of other (stack below)
            dy = abs(m_top - o_bottom)
            if dy < best_dy:
                best_dy = dy
                snap_y = o_bottom

            # Top-top alignment
            dy = abs(m_top - o_top)
            if dy < best_dy:
                best_dy = dy
                snap_y = o_top

            # Bottom-bottom alignment
            dy = abs(m_bottom - o_bottom)
            if dy < best_dy:
                best_dy = dy
                snap_y = o_bottom - m_h

            # ── X-axis snaps ──

            # Center-center alignment (most common for collimators)
            dx = abs(m_cx - o_cx)
            if dx < best_dx:
                best_dx = dx
                snap_x = o_cx - m_w / 2.0

            # Left-left alignment
            dx = abs(m_left - o_left)
            if dx < best_dx:
                best_dx = dx
                snap_x = o_left

            # Right-right alignment
            dx = abs(m_right - o_right)
            if dx < best_dx:
                best_dx = dx
                snap_x = o_right - m_w

            # Left of moving → Right of other (side by side)
            dx = abs(m_left - o_right)
            if dx < best_dx:
                best_dx = dx
                snap_x = o_right

            # Right of moving → Left of other (side by side)
            dx = abs(m_right - o_left)
            if dx < best_dx:
                best_dx = dx
                snap_x = o_left - m_w

        result_x = snap_x if best_dx < SNAP_THRESHOLD else new_pos.x()
        result_y = snap_y if best_dy < SNAP_THRESHOLD else new_pos.y()
        return QPointF(result_x, result_y)

    def _on_stage_position_changed(self, stage_item: StageItem) -> None:
        """Called after a stage has been dragged. Sync position to model."""
        if self._rebuilding:
            return
        idx = stage_item.stage_index
        pos = stage_item.pos()
        geo = self._controller.geometry
        if 0 <= idx < len(geo.stages):
            x_offset = pos.x() + geo.stages[idx].outer_width / 2.0
            y_position = pos.y()
            self._controller.update_stage_position_from_canvas(
                idx, x_offset, y_position,
            )
        self._update_beam_lines()
        self._update_dimensions()

    # ------------------------------------------------------------------
    # Source / Detector
    # ------------------------------------------------------------------

    def _update_source(self) -> None:
        """Position source item from geometry."""
        src = self._controller.geometry.source
        self._source_item.setPos(src.position.x, src.position.y)
        self._source_item.set_focal_spot(src.focal_spot_size)
        self._source_item.set_distribution(src.focal_spot_distribution)

    def _update_detector(self) -> None:
        """Position detector item from geometry."""
        det = self._controller.geometry.detector
        self._detector_item.setPos(det.position.x, det.position.y)
        self._detector_item.set_width(det.width)

    # ------------------------------------------------------------------
    # Beam lines (use actual stage item positions)
    # ------------------------------------------------------------------

    def _update_beam_lines(self) -> None:
        """Compute and set beam path lines using source beam_angle."""
        geo = self._controller.geometry
        src_pos = QPointF(geo.source.position.x, geo.source.position.y)
        det_pos = QPointF(geo.detector.position.x, geo.detector.position.y)

        lines: list[QLineF] = []

        if not geo.stages or not self._stage_items:
            self._beam_lines_item.set_lines(lines)
            return

        # Beam cone from source beam_angle (0 = auto from geometry extent)
        beam_angle = geo.source.beam_angle
        if beam_angle <= 0:
            # Auto: compute from widest stage extent
            max_hw = max(s.outer_width / 2.0 for s in geo.stages)
            first_y = min(s.y_position for s in geo.stages)
            dy = abs(first_y - src_pos.y()) or 1.0
            beam_angle = 2.0 * math.degrees(math.atan(max_hw / dy))
        half_angle_rad = math.radians(beam_angle / 2.0)
        det_dy = det_pos.y() - src_pos.y()

        # Edge lines of the beam cone: source → detector plane
        spread_at_det = abs(det_dy) * math.tan(half_angle_rad)
        left_det = QPointF(src_pos.x() - spread_at_det, det_pos.y())
        right_det = QPointF(src_pos.x() + spread_at_det, det_pos.y())
        lines.append(QLineF(src_pos, left_det))
        lines.append(QLineF(src_pos, right_det))

        # Center line
        lines.append(QLineF(src_pos, det_pos))

        self._beam_lines_item.set_lines(lines)


    # ------------------------------------------------------------------
    # Dimensions (use actual stage item positions)
    # ------------------------------------------------------------------

    def _update_dimensions(self) -> None:
        """Create/update dimension annotation items from actual positions."""
        for item in self._dimension_items:
            self.removeItem(item)
        self._dimension_items.clear()

        geo = self._controller.geometry
        max_width = max(
            (s.width for s in self._stage_items), default=100,
        )

        for i, stage_item in enumerate(self._stage_items):
            sx = stage_item.pos().x()
            sy = stage_item.pos().y()
            sw = stage_item.width
            sh = stage_item.height

            # Width dimension (below stage)
            w_dim = DimensionItem()
            w_dim.set_dimension(
                QPointF(sx, sy + sh),
                QPointF(sx + sw, sy + sh),
                f"{sw:.0f} mm",
                offset=10,
                horizontal=True,
            )
            self.addItem(w_dim)
            self._dimension_items.append(w_dim)

            # Height dimension (right of stage)
            h_dim = DimensionItem()
            h_dim.set_dimension(
                QPointF(sx + sw, sy),
                QPointF(sx + sw, sy + sh),
                f"{sh:.0f} mm",
                offset=10,
                horizontal=False,
            )
            self.addItem(h_dim)
            self._dimension_items.append(h_dim)

        # SDD dimension (far right)
        sdd_dim = DimensionItem()
        sdd_dim.set_dimension(
            QPointF(max_width / 2 + 30, geo.source.position.y),
            QPointF(max_width / 2 + 30, geo.detector.position.y),
            f"SDD {geo.detector.distance_from_source:.0f} mm",
            offset=15,
            horizontal=False,
        )
        self.addItem(sdd_dim)
        self._dimension_items.append(sdd_dim)

        # Respect current visibility setting
        if not self._dimensions_visible:
            for item in self._dimension_items:
                item.setVisible(False)

    # ------------------------------------------------------------------
    # Content bounds (excludes grid for fit-to-content)
    # ------------------------------------------------------------------

    def content_rect(self) -> QRectF:
        """Bounding rect of meaningful items (stages, source, detector, gaps).

        Excludes the background grid so fit-to-content can zoom properly.
        """
        rect = QRectF()
        for item in self._stage_items:
            rect = rect.united(item.mapRectToScene(item.boundingRect()))
        for item in self._phantom_items:
            rect = rect.united(item.mapRectToScene(item.boundingRect()))
        rect = rect.united(
            self._source_item.mapRectToScene(self._source_item.boundingRect())
        )
        rect = rect.united(
            self._detector_item.mapRectToScene(self._detector_item.boundingRect())
        )
        if self._dimensions_visible:
            for item in self._dimension_items:
                rect = rect.united(item.mapRectToScene(item.boundingRect()))
        return rect

    # ------------------------------------------------------------------
    # Dimension visibility toggle
    # ------------------------------------------------------------------

    def set_dimensions_visible(self, visible: bool) -> None:
        """Show or hide all dimension annotations."""
        self._dimensions_visible = visible
        for item in self._dimension_items:
            item.setVisible(visible)

    # ------------------------------------------------------------------
    # Label visibility toggle
    # ------------------------------------------------------------------

    def set_labels_visible(self, visible: bool) -> None:
        """Show or hide text labels on source, detector, and phantom items."""
        self._labels_visible = visible
        self._source_item.set_label_visible(visible)
        self._detector_item.set_label_visible(visible)
        for item in self._phantom_items:
            item.set_label_visible(visible)
        self.set_dimensions_visible(visible)

    # ------------------------------------------------------------------
    # Scatter overlay
    # ------------------------------------------------------------------

    def set_scatter_data(self, interactions: list, detector_y_mm: float) -> None:
        """Update scatter overlay with simulation results."""
        self._scatter_overlay.set_scatter_data(interactions, detector_y_mm)

    def clear_scatter(self) -> None:
        """Remove scatter overlay."""
        self._scatter_overlay.clear()

    def set_scatter_visible(self, visible: bool) -> None:
        """Toggle scatter overlay visibility."""
        self._scatter_overlay.setVisible(visible)

    # ------------------------------------------------------------------
    # Isodose overlay
    # ------------------------------------------------------------------

    def set_isodose_data(self, result) -> None:
        """Update isodose overlay with computation results."""
        self._isodose_overlay.set_isodose_data(result)

    def clear_isodose(self) -> None:
        """Remove isodose overlay."""
        self._isodose_overlay.clear()

    def set_isodose_visible(self, visible: bool) -> None:
        """Toggle isodose overlay visibility."""
        self._isodose_overlay.setVisible(visible)

    # ------------------------------------------------------------------
    # Partial updates (signal slots)
    # ------------------------------------------------------------------

    def _on_stage_changed(self, index: int) -> None:
        """Update a single stage's visual and position from model."""
        if not (0 <= index < len(self._stage_items)):
            return
        geo = self._controller.geometry
        stage = geo.stages[index]
        self._stage_items[index].update_from_model(
            stage.outer_width, stage.outer_height,
            stage.material_id,
            stage.aperture, geo.type,
        )
        # Reposition from model
        stage_x = stage.x_offset - stage.outer_width / 2.0
        self._stage_items[index].setPos(stage_x, stage.y_position)
        self._update_beam_lines()
        self._update_dimensions()

    def _on_stage_selected(self, index: int) -> None:
        """Highlight active stage, dim others."""
        for i, item in enumerate(self._stage_items):
            item.set_selected(i == index)

    # ------------------------------------------------------------------
    # Click selection (highlight clicked item, deselect others)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Select and highlight the clicked item; start undo batch for drag."""
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        target = self._resolve_target(item)

        if isinstance(target, StageItem):
            # Stage selection is handled by stage_clicked signal
            self._deselect_non_stage_items()
            # Start undo batch for drag
            self._controller.begin_undo_batch()
        elif isinstance(target, SourceItem):
            self._select_only(target)
            self._controller.begin_undo_batch()
        elif isinstance(target, DetectorItem):
            self._select_only(target)
            self._controller.begin_undo_batch()
        elif isinstance(target, PhantomItem):
            self._select_only(target)
            self._controller.begin_undo_batch()
        else:
            # Clicked empty canvas — deselect all
            self._deselect_all()

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """End undo batch after drag."""
        self._controller.end_undo_batch()
        super().mouseReleaseEvent(event)

    def _deselect_all(self) -> None:
        """Deselect every selectable item."""
        for item in self._stage_items:
            item.set_selected(False)
        self._source_item.set_selected(False)
        self._detector_item.set_selected(False)
        for item in self._phantom_items:
            item.set_selected(False)

    def _deselect_non_stage_items(self) -> None:
        """Deselect source, detector, phantoms (stage handles its own)."""
        self._source_item.set_selected(False)
        self._detector_item.set_selected(False)
        for item in self._phantom_items:
            item.set_selected(False)

    def _select_only(self, target) -> None:
        """Deselect everything, then select the given item."""
        self._deselect_all()
        target.set_selected(True)

    def get_selected_editable(self) -> tuple[str, int] | None:
        """Return ("stage", idx) or ("phantom", idx) if an editable item is selected.

        Source and detector are NOT editable (cut/copy/paste/delete).
        Returns None if nothing editable is selected.
        """
        # Check stages
        for item in self._stage_items:
            if item._selected:
                return ("stage", item.stage_index)
        # Check phantoms
        for item in self._phantom_items:
            if item._selected:
                return ("phantom", item.phantom_index)
        return None

    # ------------------------------------------------------------------
    # Phantom updates
    # ------------------------------------------------------------------

    def _on_phantom_changed(self, index: int) -> None:
        """Update a single phantom item from model."""
        if not (0 <= index < len(self._phantom_items)):
            return
        phantom = self._controller.geometry.phantoms[index]
        p_item = self._phantom_items[index]
        p_item.set_label(phantom.config.name)
        p_item.set_enabled(phantom.config.enabled)
        p_item.setPos(0, phantom.config.position_y)

    # ------------------------------------------------------------------
    # Stage position signal (from panel spinners, lightweight)
    # ------------------------------------------------------------------

    def _on_stage_position_signal(self, index: int) -> None:
        """Reposition a single stage after its position changed via panel."""
        if not (0 <= index < len(self._stage_items)):
            return
        geo = self._controller.geometry
        stage = geo.stages[index]
        stage_x = stage.x_offset - stage.outer_width / 2.0
        self._rebuilding = True
        self._stage_items[index].setPos(stage_x, stage.y_position)
        self._rebuilding = False
        self._update_beam_lines()
        self._update_dimensions()

    # ------------------------------------------------------------------
    # Handle resize callback
    # ------------------------------------------------------------------

    def _on_handle_moved(
        self, stage_idx: int, position: HandlePosition,
        dx: float, dy: float,
    ) -> None:
        """Resize handle was dragged on a stage."""
        geo = self._controller.geometry
        if not (0 <= stage_idx < len(geo.stages)):
            return

        stage = geo.stages[stage_idx]

        match position:
            case HandlePosition.RIGHT:
                new_w = stage.outer_width + dx
                self._controller.set_stage_dimensions(stage_idx, width=max(10, new_w))
            case HandlePosition.LEFT:
                new_w = stage.outer_width - dx
                self._controller.set_stage_dimensions(stage_idx, width=max(10, new_w))
            case HandlePosition.BOTTOM:
                new_h = stage.outer_height + dy
                self._controller.set_stage_dimensions(stage_idx, height=max(10, new_h))
            case HandlePosition.TOP:
                new_h = stage.outer_height - dy
                self._controller.set_stage_dimensions(stage_idx, height=max(10, new_h))
            case _:
                pass

    # ------------------------------------------------------------------
    # Context menu (right-click)
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event: QGraphicsSceneContextMenuEvent) -> None:
        """Show context menu based on clicked item type."""
        item = self.itemAt(event.scenePos(), self.views()[0].transform())
        target = self._resolve_target(item)

        # Highlight the right-clicked item
        if isinstance(target, StageItem):
            self._deselect_non_stage_items()
            self.stage_clicked.emit(target.stage_index)
            self._show_stage_menu(event, target)
        elif isinstance(target, PhantomItem):
            self._select_only(target)
            self._show_phantom_menu(event, target)
        elif target is self._source_item:
            self._select_only(target)
            self._show_source_menu(event)
        elif target is self._detector_item:
            self._select_only(target)
            self._show_detector_menu(event)
        else:
            self._show_canvas_menu(event)

    def _resolve_target(self, item) -> object | None:
        """Walk up the parent chain to find the actionable target item.

        Child items (LayerItem, ApertureItem, ResizeHandle) resolve to
        their parent StageItem.
        """
        while item is not None:
            if isinstance(item, (StageItem, PhantomItem, SourceItem, DetectorItem)):
                return item
            item = item.parentItem()
        return None

    # -- Stage context menu --

    def _show_stage_menu(
        self, event: QGraphicsSceneContextMenuEvent, stage_item: StageItem,
    ) -> None:
        idx = stage_item.stage_index
        geo = self._controller.geometry
        menu = QMenu()

        # Show properties
        act_props = menu.addAction(t("context.show_properties", "\u2699  Show Properties"))

        menu.addSeparator()

        # Add stage after this one
        act_add = menu.addAction(t("context.add_stage_after", "Add Stage (After)"))
        act_add.setEnabled(len(geo.stages) < MAX_STAGES)

        # Delete this stage
        act_del = menu.addAction(t("context.delete_stage", "Delete Stage"))
        act_del.setEnabled(len(geo.stages) > MIN_STAGES)

        menu.addSeparator()

        # Lock / unlock position (checkable)
        act_lock = menu.addAction(t("context.lock", "Lock"))
        act_lock.setCheckable(True)
        act_lock.setChecked(stage_item.locked)

        # X-axis lock toggle (checkable)
        act_x_lock = menu.addAction(t("context.x_lock", "X-Axis Lock"))
        act_x_lock.setCheckable(True)
        act_x_lock.setChecked(stage_item.x_locked)

        menu.addSeparator()

        act_hide_labels = menu.addAction(t("context.hide_labels", "Hide Labels"))
        act_hide_labels.setCheckable(True)
        act_hide_labels.setChecked(not self._labels_visible)

        chosen = menu.exec(event.screenPos())
        if chosen is act_props:
            self._controller.select_stage(idx)
            self.show_properties_requested.emit("stage")
        elif chosen is act_add:
            self._controller.add_stage(after_index=idx)
        elif chosen is act_del:
            self._controller.remove_stage(idx)
        elif chosen is act_lock:
            stage_item.set_locked(act_lock.isChecked())
        elif chosen is act_x_lock:
            stage_item.set_x_locked(act_x_lock.isChecked())
        elif chosen is act_hide_labels:
            self.set_labels_visible(not act_hide_labels.isChecked())

    # -- Phantom context menu --

    def _show_phantom_menu(
        self, event: QGraphicsSceneContextMenuEvent, phantom_item: PhantomItem,
    ) -> None:
        idx = phantom_item.phantom_index
        menu = QMenu()

        # Show properties
        act_props = menu.addAction(t("context.show_properties", "\u2699  Show Properties"))

        menu.addSeparator()

        act_del = menu.addAction(t("context.delete_phantom", "Delete Phantom"))

        menu.addSeparator()

        act_lock = menu.addAction(t("context.lock", "Lock"))
        act_lock.setCheckable(True)
        act_lock.setChecked(phantom_item.locked)

        act_x_lock = menu.addAction(t("context.x_lock", "X-Axis Lock"))
        act_x_lock.setCheckable(True)
        act_x_lock.setChecked(phantom_item.x_locked)

        menu.addSeparator()

        act_hide_labels = menu.addAction(t("context.hide_labels", "Hide Labels"))
        act_hide_labels.setCheckable(True)
        act_hide_labels.setChecked(not self._labels_visible)

        chosen = menu.exec(event.screenPos())
        if chosen is act_props:
            self.show_properties_requested.emit("phantom")
        elif chosen is act_del:
            self._controller.remove_phantom(idx)
        elif chosen is act_lock:
            phantom_item.set_locked(act_lock.isChecked())
        elif chosen is act_x_lock:
            phantom_item.set_x_locked(act_x_lock.isChecked())
        elif chosen is act_hide_labels:
            self.set_labels_visible(not act_hide_labels.isChecked())

    # -- Source context menu --

    def _show_source_menu(self, event: QGraphicsSceneContextMenuEvent) -> None:
        menu = QMenu()

        # Show properties
        act_props = menu.addAction(t("context.show_properties", "\u2699  Show Properties"))

        menu.addSeparator()

        act_lock = menu.addAction(t("context.lock", "Lock"))
        act_lock.setCheckable(True)
        act_lock.setChecked(self._source_item.locked)

        act_x_lock = menu.addAction(t("context.x_lock", "X-Axis Lock"))
        act_x_lock.setCheckable(True)
        act_x_lock.setChecked(self._source_item.x_locked)

        menu.addSeparator()

        act_hide_labels = menu.addAction(t("context.hide_labels", "Hide Labels"))
        act_hide_labels.setCheckable(True)
        act_hide_labels.setChecked(not self._labels_visible)

        chosen = menu.exec(event.screenPos())
        if chosen is act_props:
            self.show_properties_requested.emit("source")
        elif chosen is act_lock:
            self._source_item.set_locked(act_lock.isChecked())
        elif chosen is act_x_lock:
            self._source_item.set_x_locked(act_x_lock.isChecked())
        elif chosen is act_hide_labels:
            self.set_labels_visible(not act_hide_labels.isChecked())

    # -- Detector context menu --

    def _show_detector_menu(self, event: QGraphicsSceneContextMenuEvent) -> None:
        menu = QMenu()

        # Show properties
        act_props = menu.addAction(t("context.show_properties", "\u2699  Show Properties"))

        menu.addSeparator()

        act_lock = menu.addAction(t("context.lock", "Lock"))
        act_lock.setCheckable(True)
        act_lock.setChecked(self._detector_item.locked)

        act_x_lock = menu.addAction(t("context.x_lock", "X-Axis Lock"))
        act_x_lock.setCheckable(True)
        act_x_lock.setChecked(self._detector_item.x_locked)

        menu.addSeparator()

        act_hide_labels = menu.addAction(t("context.hide_labels", "Hide Labels"))
        act_hide_labels.setCheckable(True)
        act_hide_labels.setChecked(not self._labels_visible)

        chosen = menu.exec(event.screenPos())
        if chosen is act_props:
            self.show_properties_requested.emit("detector")
        elif chosen is act_lock:
            self._detector_item.set_locked(act_lock.isChecked())
        elif chosen is act_x_lock:
            self._detector_item.set_x_locked(act_x_lock.isChecked())
        elif chosen is act_hide_labels:
            self.set_labels_visible(not act_hide_labels.isChecked())

    # -- Empty canvas context menu --

    def _show_canvas_menu(self, event: QGraphicsSceneContextMenuEvent) -> None:
        geo = self._controller.geometry
        menu = QMenu()

        # Add stage
        act_add_stage = menu.addAction(t("context.add_stage", "Add Stage"))
        act_add_stage.setEnabled(len(geo.stages) < MAX_STAGES)

        # Add phantom submenu
        phantom_menu = menu.addMenu(t("context.add_phantom", "Add Phantom"))
        can_add = len(geo.phantoms) < MAX_PHANTOMS
        act_wire = phantom_menu.addAction(t("context.wire", "Wire"))
        act_wire.setEnabled(can_add)
        act_lp = phantom_menu.addAction(t("context.line_pair", "Line Pair"))
        act_lp.setEnabled(can_add)
        act_grid = phantom_menu.addAction(t("context.grid", "Grid"))
        act_grid.setEnabled(can_add)

        menu.addSeparator()

        # Lock all (checkable — checked when ALL items are locked)
        all_locked = self._all_locked()
        act_lock_all = menu.addAction(t("context.lock", "Lock"))
        act_lock_all.setCheckable(True)
        act_lock_all.setChecked(all_locked)

        # X-axis lock all (checkable)
        all_x_locked = self._all_x_locked()
        act_x_lock_all = menu.addAction(t("context.x_lock", "X-Axis Lock"))
        act_x_lock_all.setCheckable(True)
        act_x_lock_all.setChecked(all_x_locked)

        menu.addSeparator()

        act_hide_labels = menu.addAction(t("context.hide_labels", "Hide Labels"))
        act_hide_labels.setCheckable(True)
        act_hide_labels.setChecked(not self._labels_visible)

        chosen = menu.exec(event.screenPos())
        if chosen is act_add_stage:
            self._controller.add_stage()
        elif chosen is act_wire:
            self._controller.add_phantom(PhantomType.WIRE)
        elif chosen is act_lp:
            self._controller.add_phantom(PhantomType.LINE_PAIR)
        elif chosen is act_grid:
            self._controller.add_phantom(PhantomType.GRID)
        elif chosen is act_lock_all:
            self._lock_all(act_lock_all.isChecked())
        elif chosen is act_x_lock_all:
            self._x_lock_all(act_x_lock_all.isChecked())
        elif chosen is act_hide_labels:
            self.set_labels_visible(not act_hide_labels.isChecked())

    # -- Lock helpers --

    def _lock_all(self, locked: bool) -> None:
        """Lock or unlock all movable items."""
        self._source_item.set_locked(locked)
        self._detector_item.set_locked(locked)
        for item in self._stage_items:
            item.set_locked(locked)
        for item in self._phantom_items:
            item.set_locked(locked)

    def _x_lock_all(self, locked: bool) -> None:
        """Lock or unlock X-axis movement for all movable items."""
        self._source_item.set_x_locked(locked)
        self._detector_item.set_x_locked(locked)
        for item in self._stage_items:
            item.set_x_locked(locked)
        for item in self._phantom_items:
            item.set_x_locked(locked)

    def _all_locked(self) -> bool:
        """Return True if every movable item is position-locked."""
        items: list = [self._source_item, self._detector_item]
        items.extend(self._stage_items)
        items.extend(self._phantom_items)
        return all(item.locked for item in items) if items else False

    def _all_x_locked(self) -> bool:
        """Return True if every movable item has X-axis locked."""
        items: list = [self._source_item, self._detector_item]
        items.extend(self._stage_items)
        items.extend(self._phantom_items)
        return all(item.x_locked for item in items) if items else False
