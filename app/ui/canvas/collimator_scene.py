"""Collimator canvas scene — QGraphicsScene containing all visual items.

Manages the scene graph hierarchy, layout algorithm, and synchronization
with the GeometryController.

Scene hierarchy:
  GridItem -> StageItems + GapItems -> SourceItem -> DetectorItem ->
  BeamLinesItem -> DimensionItems

Coordinate system: 1 scene unit = 1 mm.
  X-axis = lateral (positive right), Y-axis = beam direction (positive down).
  Origin = center of collimator assembly.

Reference: Phase-03 spec — Canvas Implementation.
"""

from __future__ import annotations

import math

from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import QRectF, QPointF, QLineF, pyqtSignal
from PyQt6.QtGui import QColor

from app.models.geometry import CollimatorType, ApertureConfig
from app.ui.canvas.geometry_controller import GeometryController
from app.ui.canvas.grid_item import GridItem
from app.ui.canvas.stage_item import StageItem
from app.ui.canvas.gap_item import GapItem
from app.ui.canvas.source_item import SourceItem
from app.ui.canvas.detector_item import DetectorItem
from app.ui.canvas.beam_lines_item import BeamLinesItem
from app.ui.canvas.dimension_item import DimensionItem
from app.ui.canvas.phantom_item import PhantomItem
from app.ui.canvas.resize_handle import HandlePosition
from app.ui.canvas.scatter_overlay import ScatterOverlayItem
from app.ui.styles.colors import BACKGROUND


class CollimatorScene(QGraphicsScene):
    """QGraphicsScene containing the complete collimator cross-section.

    Builds and maintains all visual items from GeometryController data.
    """

    stage_clicked = pyqtSignal(int)
    layer_clicked = pyqtSignal(int, int)

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
        self._gap_items: list[GapItem] = []
        self._phantom_items: list[PhantomItem] = []
        self._source_item = SourceItem()
        self._detector_item = DetectorItem()
        self._beam_lines_item = BeamLinesItem()
        self._scatter_overlay = ScatterOverlayItem()
        self._dimension_items: list[DimensionItem] = []
        self._dimensions_visible: bool = True

        self.addItem(self._source_item)
        self.addItem(self._detector_item)
        self.addItem(self._beam_lines_item)
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
        ctrl.layer_changed.connect(self._on_layer_changed)
        ctrl.layer_added.connect(self._on_layer_in_stage_changed)
        ctrl.layer_removed.connect(self._on_layer_in_stage_changed)
        ctrl.layer_selected.connect(self._on_layer_selected)
        ctrl.source_changed.connect(self._update_source)
        ctrl.detector_changed.connect(self._update_detector)

        # Phantom signals
        ctrl.phantom_added.connect(lambda _: self.rebuild())
        ctrl.phantom_removed.connect(lambda _: self.rebuild())
        ctrl.phantom_changed.connect(self._on_phantom_changed)

        # Scene click signals -> controller
        self.stage_clicked.connect(ctrl.select_stage)
        self.layer_clicked.connect(ctrl.select_layer)

        # Draggable source/detector -> controller
        self._source_item.setFlag(
            SourceItem.GraphicsItemFlag.ItemSendsGeometryChanges, True,
        )
        self._detector_item.setFlag(
            DetectorItem.GraphicsItemFlag.ItemSendsGeometryChanges, True,
        )
        self._source_item.set_move_callback(
            lambda x, y: ctrl.set_source_position(x, y)
        )
        self._detector_item.set_move_callback(
            lambda x, y: ctrl.set_detector_position(x, y)
        )

    # ------------------------------------------------------------------
    # Full rebuild
    # ------------------------------------------------------------------

    def rebuild(self) -> None:
        """Complete rebuild of all scene items from controller geometry."""
        geo = self._controller.geometry

        # Remove old stage/gap items
        for item in self._stage_items:
            self.removeItem(item)
        self._stage_items.clear()

        for item in self._gap_items:
            self.removeItem(item)
        self._gap_items.clear()

        for item in self._dimension_items:
            self.removeItem(item)
        self._dimension_items.clear()

        # Create stage items
        for i, stage in enumerate(geo.stages):
            stage_item = StageItem(i)
            stage_item.set_handle_callback(self._on_handle_moved)
            layers = [
                (l.material_id, l.thickness, l.inner_material_id, l.inner_width)
                for l in stage.layers
            ]
            stage_item.update_from_model(
                stage.outer_width, stage.outer_height,
                layers, stage.aperture, geo.type,
            )
            self.addItem(stage_item)
            self._stage_items.append(stage_item)

        # Create gap items
        for i in range(len(geo.stages) - 1):
            gap_item = GapItem(i)
            self.addItem(gap_item)
            self._gap_items.append(gap_item)

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

        # Layout stages and gaps
        self._layout_stages()

        # Update source, detector, beams, dimensions
        self._update_source()
        self._update_detector()
        self._update_beam_lines()
        self._update_dimensions()

        # Highlight active stage
        active = self._controller.active_stage_index
        self._on_stage_selected(active)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _layout_stages(self) -> None:
        """Position stages vertically, centered on X=0."""
        geo = self._controller.geometry
        total_h = geo.total_height
        y_offset = -total_h / 2.0

        for i, stage in enumerate(geo.stages):
            stage_x = -stage.outer_width / 2.0
            self._stage_items[i].setPos(stage_x, y_offset)
            y_offset += stage.outer_height

            # Gap after (if not last)
            if i < len(geo.stages) - 1 and i < len(self._gap_items):
                gap = stage.gap_after
                if gap > 0:
                    # Gap rect spans the wider of adjacent stages
                    max_w = max(stage.outer_width,
                                geo.stages[i + 1].outer_width)
                    gap_rect = QRectF(-max_w / 2, y_offset, max_w, gap)
                    self._gap_items[i].set_gap(gap_rect, gap)
                else:
                    self._gap_items[i].set_gap(QRectF(), 0)
                y_offset += gap

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

    def _update_beam_lines(self) -> None:
        """Compute and set beam path lines."""
        geo = self._controller.geometry
        src_pos = QPointF(geo.source.position.x, geo.source.position.y)
        det_pos = QPointF(geo.detector.position.x, geo.detector.position.y)

        lines: list[QLineF] = []

        if not geo.stages:
            self._beam_lines_item.set_lines(lines)
            return

        # Find aperture edges of the first and last stages
        first = geo.stages[0]
        last = geo.stages[-1]
        total_h = geo.total_height
        top_y = -total_h / 2.0

        match geo.type:
            case CollimatorType.FAN_BEAM:
                lines = self._compute_fan_beam_lines(geo, src_pos, det_pos, top_y)
            case CollimatorType.PENCIL_BEAM:
                lines = self._compute_pencil_beam_lines(geo, src_pos, det_pos, top_y)
            case CollimatorType.SLIT:
                lines = self._compute_slit_beam_lines(geo, src_pos, det_pos, top_y)

        self._beam_lines_item.set_lines(lines)

    def _compute_fan_beam_lines(self, geo, src_pos, det_pos, top_y):
        """Fan beam: two diverging edge lines from source through apertures."""
        lines = []
        first = geo.stages[0]
        angle_rad = math.radians((first.aperture.fan_angle or 30) / 2)
        slit_w = first.aperture.fan_slit_width or 2.0

        # Top of first stage aperture
        top_half = slit_w / 2.0
        bottom_half = top_half + first.outer_height * math.tan(angle_rad)

        # Left edge: source -> left aperture top -> detector left
        lines.append(QLineF(src_pos, QPointF(-top_half, top_y)))
        lines.append(QLineF(src_pos, QPointF(top_half, top_y)))
        # Bottom of first stage
        bot_y = top_y + first.outer_height
        lines.append(QLineF(QPointF(-bottom_half, bot_y), det_pos))
        lines.append(QLineF(QPointF(bottom_half, bot_y), det_pos))

        # Center line
        lines.append(QLineF(src_pos, det_pos))
        return lines

    def _compute_pencil_beam_lines(self, geo, src_pos, det_pos, top_y):
        """Pencil beam: parallel lines through the aperture."""
        lines = []
        first = geo.stages[0]
        d = (first.aperture.pencil_diameter or 5.0) / 2.0

        bot_y = top_y + first.outer_height
        # Two parallel lines
        lines.append(QLineF(QPointF(-d, src_pos.y()), QPointF(-d, det_pos.y())))
        lines.append(QLineF(QPointF(d, src_pos.y()), QPointF(d, det_pos.y())))
        # Center
        lines.append(QLineF(src_pos, det_pos))
        return lines

    def _compute_slit_beam_lines(self, geo, src_pos, det_pos, top_y):
        """Slit: lines through the slit entry and exit edges."""
        lines = []
        first = geo.stages[0]
        sw = (first.aperture.slit_width or 2.0) / 2.0  # exit (narrow) half

        entry_y = top_y
        exit_y = top_y + first.outer_height

        # Compute entry half-width (source side)
        if first.aperture.taper_angle and first.aperture.taper_angle != 0.0:
            taper_rad = math.radians(first.aperture.taper_angle)
            entry_hw = sw + first.outer_height * math.tan(taper_rad)
        else:
            entry_hw = sw

        # Source → entry edges → exit edges → detector
        lines.append(QLineF(src_pos, QPointF(-entry_hw, entry_y)))
        lines.append(QLineF(src_pos, QPointF(entry_hw, entry_y)))
        lines.append(QLineF(QPointF(-sw, exit_y), det_pos))
        lines.append(QLineF(QPointF(sw, exit_y), det_pos))
        # Entry-to-exit slit walls
        lines.append(QLineF(QPointF(-entry_hw, entry_y), QPointF(-sw, exit_y)))
        lines.append(QLineF(QPointF(entry_hw, entry_y), QPointF(sw, exit_y)))
        # Center
        lines.append(QLineF(src_pos, det_pos))
        return lines

    def _update_dimensions(self) -> None:
        """Create/update dimension annotation items."""
        for item in self._dimension_items:
            self.removeItem(item)
        self._dimension_items.clear()

        geo = self._controller.geometry
        total_h = geo.total_height
        y_offset = -total_h / 2.0

        max_width = max((s.outer_width for s in geo.stages), default=100)

        for i, stage in enumerate(geo.stages):
            sx = -stage.outer_width / 2.0
            sy = y_offset

            # Width dimension (below stage)
            w_dim = DimensionItem()
            w_dim.set_dimension(
                QPointF(sx, sy + stage.outer_height),
                QPointF(sx + stage.outer_width, sy + stage.outer_height),
                f"{stage.outer_width:.0f} mm",
                offset=10,
                horizontal=True,
            )
            self.addItem(w_dim)
            self._dimension_items.append(w_dim)

            # Height dimension (right of stage)
            h_dim = DimensionItem()
            h_dim.set_dimension(
                QPointF(sx + stage.outer_width, sy),
                QPointF(sx + stage.outer_width, sy + stage.outer_height),
                f"{stage.outer_height:.0f} mm",
                offset=10,
                horizontal=False,
            )
            self.addItem(h_dim)
            self._dimension_items.append(h_dim)

            y_offset += stage.outer_height
            if i < len(geo.stages) - 1:
                y_offset += stage.gap_after

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
        for item in self._gap_items:
            rect = rect.united(item.mapRectToScene(item.boundingRect()))
        for item in self._phantom_items:
            rect = rect.united(item.mapRectToScene(item.boundingRect()))
        # Source and detector
        rect = rect.united(
            self._source_item.mapRectToScene(self._source_item.boundingRect())
        )
        rect = rect.united(
            self._detector_item.mapRectToScene(self._detector_item.boundingRect())
        )
        # Dimension items (if visible)
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
    # Partial updates (signal slots)
    # ------------------------------------------------------------------

    def _on_stage_changed(self, index: int) -> None:
        """Update a single stage's visual from model."""
        if not (0 <= index < len(self._stage_items)):
            return
        geo = self._controller.geometry
        stage = geo.stages[index]
        layers = [
            (l.material_id, l.thickness, l.inner_material_id, l.inner_width)
            for l in stage.layers
        ]
        self._stage_items[index].update_from_model(
            stage.outer_width, stage.outer_height,
            layers, stage.aperture, geo.type,
        )
        self._layout_stages()
        self._update_beam_lines()
        self._update_dimensions()

    def _on_stage_selected(self, index: int) -> None:
        """Highlight active stage, dim others."""
        for i, item in enumerate(self._stage_items):
            item.set_selected(i == index)

    def _on_layer_changed(self, stage_idx: int, layer_idx: int) -> None:
        """A layer's material or thickness changed."""
        self._on_stage_changed(stage_idx)

    def _on_layer_in_stage_changed(self, stage_idx: int, layer_idx: int) -> None:
        """Layer added or removed — rebuild that stage."""
        self._on_stage_changed(stage_idx)

    def _on_layer_selected(self, stage_idx: int, layer_idx: int) -> None:
        """Highlight the selected layer."""
        for si, stage_item in enumerate(self._stage_items):
            for li_item in stage_item._layer_items:
                li_item.set_highlighted(
                    si == stage_idx and li_item.layer_index == layer_idx
                )

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
