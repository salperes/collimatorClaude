"""Geometry controller — central mediator between data model and UI.

Owns the single CollimatorGeometry instance. All mutations go through
this controller, which emits Qt signals for canvas/panel refresh.

Reference: Phase-03 spec — Architecture.
"""

from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from app.constants import MAX_PHANTOMS, MAX_STAGES, MIN_STAGES, MATERIAL_IDS
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorLayer,
    CollimatorStage,
    CollimatorType,
    FocalSpotDistribution,
    LayerPurpose,
    Point2D,
    StagePurpose,
)
from app.models.phantom import (
    AnyPhantom,
    GridPhantom,
    LinePairPhantom,
    PhantomConfig,
    PhantomType,
    WirePhantom,
)
from app.ui.canvas.geometry_templates import create_template


class GeometryController(QObject):
    """Central mediator between CollimatorGeometry data model and UI views.

    Owns the geometry instance. All mutations update the model and emit
    the appropriate signal so that the canvas scene and side panels stay
    in sync.

    Signals use int indices (not UUIDs) for simplicity.
    """

    # Full geometry rebuild needed
    geometry_changed = pyqtSignal()
    # Single stage changed (index)
    stage_changed = pyqtSignal(int)
    stage_added = pyqtSignal(int)
    stage_removed = pyqtSignal(int)
    stage_selected = pyqtSignal(int)
    # Layer within a stage changed (stage_idx, layer_idx)
    layer_changed = pyqtSignal(int, int)
    layer_added = pyqtSignal(int, int)
    layer_removed = pyqtSignal(int, int)
    layer_selected = pyqtSignal(int, int)
    # Source / detector
    source_changed = pyqtSignal()
    detector_changed = pyqtSignal()
    # Collimator type
    collimator_type_changed = pyqtSignal(object)  # CollimatorType
    # Phantom signals
    phantom_added = pyqtSignal(int)
    phantom_removed = pyqtSignal(int)
    phantom_changed = pyqtSignal(int)
    phantom_selected = pyqtSignal(int)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._geometry = create_template(CollimatorType.SLIT)
        self._active_stage_index: int = 0
        self._active_layer_index: int = -1  # -1 = no selection
        self._active_phantom_index: int = -1  # -1 = no selection
        self._updating: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def geometry(self) -> CollimatorGeometry:
        """Current geometry (read-only reference)."""
        return self._geometry

    @property
    def active_stage_index(self) -> int:
        return self._active_stage_index

    @property
    def active_stage(self) -> CollimatorStage | None:
        if 0 <= self._active_stage_index < len(self._geometry.stages):
            return self._geometry.stages[self._active_stage_index]
        return None

    @property
    def active_layer_index(self) -> int:
        return self._active_layer_index

    @property
    def active_phantom_index(self) -> int:
        return self._active_phantom_index

    @property
    def active_phantom(self) -> AnyPhantom | None:
        phantoms = self._geometry.phantoms
        if 0 <= self._active_phantom_index < len(phantoms):
            return phantoms[self._active_phantom_index]
        return None

    # ------------------------------------------------------------------
    # Geometry-level mutations
    # ------------------------------------------------------------------

    def set_geometry(self, geometry: CollimatorGeometry) -> None:
        """Replace the entire geometry and trigger full rebuild."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry = geometry
            self._active_stage_index = 0
            self._active_layer_index = -1
            self.geometry_changed.emit()
        finally:
            self._updating = False

    def load_template(self, ctype: CollimatorType) -> None:
        """Load a fresh template for the given collimator type."""
        geo = create_template(ctype)
        self.set_geometry(geo)

    def set_collimator_type(self, ctype: CollimatorType) -> None:
        """Switch collimator type by loading its default template."""
        if self._updating:
            return
        self.load_template(ctype)
        self.collimator_type_changed.emit(ctype)

    def create_blank_geometry(self) -> None:
        """Create a minimal blank geometry for free-form editing."""
        from app.models.geometry import (
            CollimatorGeometry, CollimatorStage, CollimatorLayer,
            SourceConfig, DetectorConfig, Point2D,
        )
        geo = CollimatorGeometry(
            name="Özel Tasarım",
            type=CollimatorType.FAN_BEAM,
            stages=[
                CollimatorStage(
                    name="Stage 0",
                    order=0,
                    outer_width=100.0,
                    outer_height=100.0,
                    layers=[
                        CollimatorLayer(
                            order=0, material_id="Pb", thickness=20.0,
                            purpose=LayerPurpose.PRIMARY_SHIELDING,
                        ),
                    ],
                ),
            ],
            source=SourceConfig(position=Point2D(0, -150)),
            detector=DetectorConfig(
                position=Point2D(0, 350),
                width=500.0,
                distance_from_source=500.0,
            ),
        )
        self.set_geometry(geo)

    # ------------------------------------------------------------------
    # Stage mutations
    # ------------------------------------------------------------------

    def add_stage(self, after_index: int = -1) -> None:
        """Insert a new default stage after *after_index* (-1 = append)."""
        if self._updating:
            return
        if len(self._geometry.stages) >= MAX_STAGES:
            return
        self._updating = True
        try:
            new_stage = CollimatorStage(
                name=f"Stage {len(self._geometry.stages)}",
                order=len(self._geometry.stages),
                outer_width=80.0,
                outer_height=60.0,
                layers=[
                    CollimatorLayer(
                        order=0, material_id="Pb", thickness=10.0,
                        purpose=LayerPurpose.PRIMARY_SHIELDING,
                    ),
                ],
            )
            if after_index < 0 or after_index >= len(self._geometry.stages):
                insert_idx = len(self._geometry.stages)
            else:
                insert_idx = after_index + 1
            self._geometry.stages.insert(insert_idx, new_stage)
            self._reorder_stages()
            self._touch()
            self.stage_added.emit(insert_idx)
        finally:
            self._updating = False

    def remove_stage(self, index: int) -> None:
        """Remove stage at *index*. Minimum 1 stage enforced."""
        if self._updating:
            return
        if len(self._geometry.stages) <= MIN_STAGES:
            return
        if not (0 <= index < len(self._geometry.stages)):
            return
        self._updating = True
        try:
            self._geometry.stages.pop(index)
            self._reorder_stages()
            if self._active_stage_index >= len(self._geometry.stages):
                self._active_stage_index = len(self._geometry.stages) - 1
            self._active_layer_index = -1
            self._touch()
            self.stage_removed.emit(index)
        finally:
            self._updating = False

    def select_stage(self, index: int) -> None:
        """Set active stage selection."""
        if self._updating:
            return
        if not (0 <= index < len(self._geometry.stages)):
            return
        self._active_stage_index = index
        self._active_layer_index = -1
        self.stage_selected.emit(index)

    def move_stage(self, from_index: int, to_index: int) -> None:
        """Move a stage from one position to another."""
        if self._updating:
            return
        n = len(self._geometry.stages)
        if not (0 <= from_index < n and 0 <= to_index < n):
            return
        if from_index == to_index:
            return
        self._updating = True
        try:
            stage = self._geometry.stages.pop(from_index)
            self._geometry.stages.insert(to_index, stage)
            self._reorder_stages()
            self._active_stage_index = to_index
            self._touch()
            self.geometry_changed.emit()
        finally:
            self._updating = False

    def set_stage_name(self, index: int, name: str) -> None:
        """Update stage name."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].name = name
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    def set_stage_purpose(self, index: int, purpose: StagePurpose) -> None:
        """Update stage purpose."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].purpose = purpose
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    def set_stage_dimensions(
        self, index: int, *, width: float | None = None, height: float | None = None
    ) -> None:
        """Update stage outer dimensions [mm]."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            stage = self._geometry.stages[index]
            if width is not None and width > 0:
                stage.outer_width = width
            if height is not None and height > 0:
                stage.outer_height = height
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    def set_stage_gap_after(self, index: int, gap: float) -> None:
        """Update gap after stage [mm]."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].gap_after = max(0.0, gap)
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    def set_stage_aperture(self, index: int, aperture: ApertureConfig) -> None:
        """Replace the aperture config for a stage."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].aperture = aperture
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Layer mutations
    # ------------------------------------------------------------------

    def add_layer(self, stage_index: int) -> None:
        """Add a new default layer to a stage (outermost position)."""
        if self._updating or not self._valid_stage(stage_index):
            return
        self._updating = True
        try:
            stage = self._geometry.stages[stage_index]
            new_order = max((l.order for l in stage.layers), default=-1) + 1
            layer = CollimatorLayer(
                order=new_order,
                material_id="Pb",
                thickness=10.0,
                purpose=LayerPurpose.PRIMARY_SHIELDING,
            )
            stage.layers.append(layer)
            layer_idx = len(stage.layers) - 1
            self._touch()
            self.layer_added.emit(stage_index, layer_idx)
        finally:
            self._updating = False

    def remove_layer(self, stage_index: int, layer_index: int) -> None:
        """Remove a layer from a stage."""
        if self._updating or not self._valid_layer(stage_index, layer_index):
            return
        self._updating = True
        try:
            stage = self._geometry.stages[stage_index]
            stage.layers.pop(layer_index)
            # Re-order remaining
            for i, layer in enumerate(stage.layers):
                layer.order = i
            if self._active_layer_index >= len(stage.layers):
                self._active_layer_index = len(stage.layers) - 1
            self._touch()
            self.layer_removed.emit(stage_index, layer_index)
        finally:
            self._updating = False

    def move_layer(self, stage_index: int, from_idx: int, to_idx: int) -> None:
        """Reorder a layer within a stage."""
        if self._updating or not self._valid_stage(stage_index):
            return
        stage = self._geometry.stages[stage_index]
        n = len(stage.layers)
        if not (0 <= from_idx < n and 0 <= to_idx < n):
            return
        if from_idx == to_idx:
            return
        self._updating = True
        try:
            layer = stage.layers.pop(from_idx)
            stage.layers.insert(to_idx, layer)
            for i, l in enumerate(stage.layers):
                l.order = i
            self._touch()
            self.layer_changed.emit(stage_index, to_idx)
        finally:
            self._updating = False

    def set_layer_material(
        self, stage_index: int, layer_index: int, material_id: str
    ) -> None:
        """Update layer material."""
        if self._updating or not self._valid_layer(stage_index, layer_index):
            return
        if material_id not in MATERIAL_IDS:
            return
        self._updating = True
        try:
            self._geometry.stages[stage_index].layers[layer_index].material_id = material_id
            self._touch()
            self.layer_changed.emit(stage_index, layer_index)
        finally:
            self._updating = False

    def set_layer_thickness(
        self, stage_index: int, layer_index: int, thickness: float
    ) -> None:
        """Update layer thickness [mm]."""
        if self._updating or not self._valid_layer(stage_index, layer_index):
            return
        if thickness <= 0:
            return
        self._updating = True
        try:
            self._geometry.stages[stage_index].layers[layer_index].thickness = thickness
            self._touch()
            self.layer_changed.emit(stage_index, layer_index)
        finally:
            self._updating = False

    def set_layer_purpose(
        self, stage_index: int, layer_index: int, purpose: LayerPurpose
    ) -> None:
        """Update layer purpose."""
        if self._updating or not self._valid_layer(stage_index, layer_index):
            return
        self._updating = True
        try:
            self._geometry.stages[stage_index].layers[layer_index].purpose = purpose
            self._touch()
            self.layer_changed.emit(stage_index, layer_index)
        finally:
            self._updating = False

    def select_layer(self, stage_index: int, layer_index: int) -> None:
        """Set active layer selection."""
        if self._updating:
            return
        if not self._valid_stage(stage_index):
            return
        stage = self._geometry.stages[stage_index]
        if not (0 <= layer_index < len(stage.layers)):
            return
        self._active_stage_index = stage_index
        self._active_layer_index = layer_index
        self.layer_selected.emit(stage_index, layer_index)

    # ------------------------------------------------------------------
    # Source / Detector mutations
    # ------------------------------------------------------------------

    def set_source_position(self, x: float, y: float) -> None:
        """Update source position [mm]."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.source.position = Point2D(x, y)
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    def set_source_focal_spot(self, size: float) -> None:
        """Update focal spot diameter [mm]."""
        if self._updating:
            return
        if size <= 0:
            return
        self._updating = True
        try:
            self._geometry.source.focal_spot_size = size
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    def set_source_focal_spot_distribution(
        self, dist: FocalSpotDistribution
    ) -> None:
        """Update focal spot spatial intensity distribution."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.source.focal_spot_distribution = dist
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    def set_detector_position(self, x: float, y: float) -> None:
        """Update detector position [mm]."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.detector.position = Point2D(x, y)
            self._update_sdd()
            self._touch()
            self.detector_changed.emit()
        finally:
            self._updating = False

    def set_detector_width(self, width: float) -> None:
        """Update detector active width [mm]."""
        if self._updating:
            return
        if width <= 0:
            return
        self._updating = True
        try:
            self._geometry.detector.width = width
            self._touch()
            self.detector_changed.emit()
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Phantom mutations
    # ------------------------------------------------------------------

    def add_phantom(
        self, phantom_type: PhantomType, position_y: float | None = None,
    ) -> None:
        """Add a new phantom. Auto-positions at midpoint if position_y is None."""
        if self._updating:
            return
        if len(self._geometry.phantoms) >= MAX_PHANTOMS:
            return
        self._updating = True
        try:
            if position_y is None:
                position_y = self._auto_phantom_y()

            match phantom_type:
                case PhantomType.WIRE:
                    phantom: AnyPhantom = WirePhantom(
                        config=PhantomConfig(
                            type=PhantomType.WIRE,
                            name=f"Tel {0.5}mm",
                            position_y=position_y,
                            material_id="W",
                        ),
                    )
                case PhantomType.LINE_PAIR:
                    phantom = LinePairPhantom(
                        config=PhantomConfig(
                            type=PhantomType.LINE_PAIR,
                            name="Cizgi Cifti 1 lp/mm",
                            position_y=position_y,
                            material_id="Pb",
                        ),
                    )
                case PhantomType.GRID:
                    phantom = GridPhantom(
                        config=PhantomConfig(
                            type=PhantomType.GRID,
                            name="Grid 1mm",
                            position_y=position_y,
                            material_id="W",
                        ),
                    )

            self._geometry.phantoms.append(phantom)
            idx = len(self._geometry.phantoms) - 1
            self._active_phantom_index = idx
            self._touch()
            self.phantom_added.emit(idx)
        finally:
            self._updating = False

    def remove_phantom(self, index: int) -> None:
        """Remove phantom at index."""
        if self._updating or not self._valid_phantom(index):
            return
        self._updating = True
        try:
            self._geometry.phantoms.pop(index)
            if self._active_phantom_index >= len(self._geometry.phantoms):
                self._active_phantom_index = len(self._geometry.phantoms) - 1
            self._touch()
            self.phantom_removed.emit(index)
        finally:
            self._updating = False

    def select_phantom(self, index: int) -> None:
        """Set active phantom selection."""
        if self._updating:
            return
        if not self._valid_phantom(index):
            return
        self._active_phantom_index = index
        self.phantom_selected.emit(index)

    def set_phantom_position(self, index: int, y_mm: float) -> None:
        """Update phantom Y position [mm]."""
        if self._updating or not self._valid_phantom(index):
            return
        self._updating = True
        try:
            self._geometry.phantoms[index].config.position_y = y_mm
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_phantom_material(self, index: int, material_id: str) -> None:
        """Update phantom material."""
        if self._updating or not self._valid_phantom(index):
            return
        if material_id not in MATERIAL_IDS:
            return
        self._updating = True
        try:
            self._geometry.phantoms[index].config.material_id = material_id
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_phantom_enabled(self, index: int, enabled: bool) -> None:
        """Enable/disable phantom."""
        if self._updating or not self._valid_phantom(index):
            return
        self._updating = True
        try:
            self._geometry.phantoms[index].config.enabled = enabled
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_phantom_name(self, index: int, name: str) -> None:
        """Update phantom display name."""
        if self._updating or not self._valid_phantom(index):
            return
        self._updating = True
        try:
            self._geometry.phantoms[index].config.name = name
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_wire_diameter(self, index: int, diameter_mm: float) -> None:
        """Update wire phantom diameter [mm]."""
        if self._updating or not self._valid_phantom(index):
            return
        phantom = self._geometry.phantoms[index]
        if not isinstance(phantom, WirePhantom):
            return
        if diameter_mm <= 0:
            return
        self._updating = True
        try:
            phantom.diameter = diameter_mm
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_line_pair_frequency(self, index: int, freq_lpmm: float) -> None:
        """Update line-pair spatial frequency [lp/mm]."""
        if self._updating or not self._valid_phantom(index):
            return
        phantom = self._geometry.phantoms[index]
        if not isinstance(phantom, LinePairPhantom):
            return
        if freq_lpmm <= 0:
            return
        self._updating = True
        try:
            phantom.frequency = freq_lpmm
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_line_pair_thickness(self, index: int, thickness_mm: float) -> None:
        """Update line-pair bar thickness [mm]."""
        if self._updating or not self._valid_phantom(index):
            return
        phantom = self._geometry.phantoms[index]
        if not isinstance(phantom, LinePairPhantom):
            return
        if thickness_mm <= 0:
            return
        self._updating = True
        try:
            phantom.bar_thickness = thickness_mm
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_line_pair_num_cycles(self, index: int, num_cycles: int) -> None:
        """Update line-pair number of cycles."""
        if self._updating or not self._valid_phantom(index):
            return
        phantom = self._geometry.phantoms[index]
        if not isinstance(phantom, LinePairPhantom):
            return
        if num_cycles < 1:
            return
        self._updating = True
        try:
            phantom.num_cycles = num_cycles
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_grid_pitch(self, index: int, pitch_mm: float) -> None:
        """Update grid wire pitch [mm]."""
        if self._updating or not self._valid_phantom(index):
            return
        phantom = self._geometry.phantoms[index]
        if not isinstance(phantom, GridPhantom):
            return
        if pitch_mm <= 0:
            return
        self._updating = True
        try:
            phantom.pitch = pitch_mm
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    def set_grid_wire_diameter(self, index: int, diameter_mm: float) -> None:
        """Update grid wire diameter [mm]."""
        if self._updating or not self._valid_phantom(index):
            return
        phantom = self._geometry.phantoms[index]
        if not isinstance(phantom, GridPhantom):
            return
        if diameter_mm <= 0:
            return
        self._updating = True
        try:
            phantom.wire_diameter = diameter_mm
            self._touch()
            self.phantom_changed.emit(index)
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Composite layer mutations
    # ------------------------------------------------------------------

    def set_layer_composite(
        self, stage_idx: int, layer_idx: int, enabled: bool,
    ) -> None:
        """Toggle composite mode for a layer.

        When enabled, sets inner_material_id to 'W' and inner_width
        to half the layer thickness. When disabled, clears both fields.
        """
        if self._updating or not self._valid_layer(stage_idx, layer_idx):
            return
        self._updating = True
        try:
            layer = self._geometry.stages[stage_idx].layers[layer_idx]
            if enabled:
                layer.inner_material_id = "W"
                layer.inner_width = layer.thickness / 2.0
            else:
                layer.inner_material_id = None
                layer.inner_width = 0.0
            self._touch()
            self.layer_changed.emit(stage_idx, layer_idx)
        finally:
            self._updating = False

    def set_layer_inner_material(
        self, stage_idx: int, layer_idx: int, material_id: str,
    ) -> None:
        """Update composite layer inner zone material."""
        if self._updating or not self._valid_layer(stage_idx, layer_idx):
            return
        if material_id not in MATERIAL_IDS:
            return
        self._updating = True
        try:
            layer = self._geometry.stages[stage_idx].layers[layer_idx]
            layer.inner_material_id = material_id
            self._touch()
            self.layer_changed.emit(stage_idx, layer_idx)
        finally:
            self._updating = False

    def set_layer_inner_width(
        self, stage_idx: int, layer_idx: int, width_mm: float,
    ) -> None:
        """Update composite layer inner zone width [mm]."""
        if self._updating or not self._valid_layer(stage_idx, layer_idx):
            return
        layer = self._geometry.stages[stage_idx].layers[layer_idx]
        if width_mm <= 0 or width_mm >= layer.thickness:
            return
        self._updating = True
        try:
            layer.inner_width = width_mm
            self._touch()
            self.layer_changed.emit(stage_idx, layer_idx)
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _valid_phantom(self, index: int) -> bool:
        return 0 <= index < len(self._geometry.phantoms)

    def _auto_phantom_y(self) -> float:
        """Compute midpoint Y between last stage bottom and detector [mm]."""
        geo = self._geometry
        if not geo.stages:
            return geo.detector.position.y / 2.0
        total_h = geo.total_height
        last_stage_bottom_y = total_h / 2.0  # centered layout
        det_y = geo.detector.position.y
        return (last_stage_bottom_y + det_y) / 2.0

    def _valid_stage(self, index: int) -> bool:
        return 0 <= index < len(self._geometry.stages)

    def _valid_layer(self, stage_index: int, layer_index: int) -> bool:
        if not self._valid_stage(stage_index):
            return False
        return 0 <= layer_index < len(self._geometry.stages[stage_index].layers)

    def _reorder_stages(self) -> None:
        for i, stage in enumerate(self._geometry.stages):
            stage.order = i

    def _update_sdd(self) -> None:
        src_y = self._geometry.source.position.y
        det_y = self._geometry.detector.position.y
        self._geometry.detector.distance_from_source = abs(det_y - src_y)

    def _touch(self) -> None:
        self._geometry.updated_at = datetime.now().isoformat()
