"""Geometry controller — central mediator between data model and UI.

Owns the single CollimatorGeometry instance. All mutations go through
this controller, which emits Qt signals for canvas/panel refresh.

Reference: Phase-03 spec — Architecture.
"""

from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal

from app.constants import MAX_PHANTOMS, MAX_STAGES, MIN_STAGES, MATERIAL_IDS
from app.core.i18n import t
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    FocalSpotDistribution,
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
    # Source / detector
    source_changed = pyqtSignal()
    detector_changed = pyqtSignal()
    # Stage position from canvas drag (lightweight — no full rebuild)
    stage_position_changed = pyqtSignal(int)
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
            CollimatorGeometry, CollimatorStage,
            SourceConfig, DetectorConfig, Point2D,
        )
        geo = CollimatorGeometry(
            name=t("templates.custom_design", "Custom Design"),
            type=CollimatorType.FAN_BEAM,
            stages=[
                CollimatorStage(
                    name=t("templates.default_stage", "Stage {index}").format(index=0),
                    order=0,
                    outer_width=100.0,
                    outer_height=100.0,
                    material_id="Pb",
                    y_position=100.0,
                    x_offset=0.0,
                ),
            ],
            source=SourceConfig(position=Point2D(0, 0)),
            detector=DetectorConfig(
                position=Point2D(0, 500),
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
            import math
            # Default: 300mm wide, 10mm deep Pb stage with tapered slit
            taper = math.degrees(math.atan2(2.0, 10.0))

            if after_index < 0 or after_index >= len(self._geometry.stages):
                insert_idx = len(self._geometry.stages)
            else:
                insert_idx = after_index + 1

            # Compute Y position below the previous stage
            if insert_idx > 0:
                prev = self._geometry.stages[insert_idx - 1]
                new_y = prev.y_position + prev.outer_height + 10.0
            else:
                new_y = 50.0

            new_stage = CollimatorStage(
                name=t("templates.default_stage", "Stage {index}").format(index=len(self._geometry.stages)),
                order=len(self._geometry.stages),
                outer_width=300.0,
                outer_height=10.0,
                material_id="Pb",
                y_position=new_y,
                x_offset=0.0,
                aperture=ApertureConfig(
                    slit_width=6.0,
                    taper_angle=taper,
                ),
            )
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

    def set_stage_y_position(self, index: int, y: float) -> None:
        """Update stage Y position (top edge relative to source) [mm]."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].y_position = y
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    def set_stage_x_offset(self, index: int, x: float) -> None:
        """Update stage X offset from source axis [mm]."""
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].x_offset = x
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

    def set_stage_material(self, index: int, material_id: str) -> None:
        """Update stage shielding material."""
        if self._updating or not self._valid_stage(index):
            return
        if material_id not in MATERIAL_IDS:
            return
        self._updating = True
        try:
            self._geometry.stages[index].material_id = material_id
            self._touch()
            self.stage_changed.emit(index)
        finally:
            self._updating = False

    def update_stage_position_from_canvas(
        self, index: int, x_offset: float, y_position: float,
    ) -> None:
        """Update stage position from canvas drag (lightweight, no rebuild).

        Does NOT emit stage_changed (avoids full visual rebuild).
        Emits stage_position_changed for panel refresh only.
        """
        if self._updating or not self._valid_stage(index):
            return
        self._updating = True
        try:
            self._geometry.stages[index].x_offset = x_offset
            self._geometry.stages[index].y_position = y_position
            self._touch()
            self.stage_position_changed.emit(index)
        finally:
            self._updating = False

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

    def set_source_beam_angle(self, angle_deg: float) -> None:
        """Update X-ray beam spread angle [degree, full cone].

        0.0 means auto-calculate from geometry extent.
        """
        if self._updating:
            return
        if angle_deg < 0 or angle_deg > 180:
            return
        self._updating = True
        try:
            self._geometry.source.beam_angle = angle_deg
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Source dose parameters
    # ------------------------------------------------------------------

    def set_tube_current(self, mA: float) -> None:
        """Update X-ray tube current [mA]."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.source.tube_current_mA = mA
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    def set_tube_output_method(self, method: str) -> None:
        """Update tube output method ('empirical' or 'lookup')."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.source.tube_output_method = method
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    def set_linac_pps(self, pps: int) -> None:
        """Update LINAC pulse repetition rate [PPS]."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.source.linac_pps = pps
            self._touch()
            self.source_changed.emit()
        finally:
            self._updating = False

    def set_linac_dose_rate(self, gy_min: float, ref_pps: int | None = None) -> None:
        """Update LINAC dose rate [Gy/min] and optionally ref PPS."""
        if self._updating:
            return
        self._updating = True
        try:
            self._geometry.source.linac_dose_rate_Gy_min = gy_min
            if ref_pps is not None:
                self._geometry.source.linac_ref_pps = ref_pps
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
    # Private helpers
    # ------------------------------------------------------------------

    def _valid_phantom(self, index: int) -> bool:
        return 0 <= index < len(self._geometry.phantoms)

    def _auto_phantom_y(self) -> float:
        """Compute midpoint Y between last stage bottom and detector [mm]."""
        geo = self._geometry
        if not geo.stages:
            return geo.detector.position.y / 2.0
        last_stage_bottom_y = max(
            s.y_position + s.outer_height for s in geo.stages
        )
        det_y = geo.detector.position.y
        return (last_stage_bottom_y + det_y) / 2.0

    def _valid_stage(self, index: int) -> bool:
        return 0 <= index < len(self._geometry.stages)

    def _reorder_stages(self) -> None:
        for i, stage in enumerate(self._geometry.stages):
            stage.order = i

    def _update_sdd(self) -> None:
        src_y = self._geometry.source.position.y
        det_y = self._geometry.detector.position.y
        self._geometry.detector.distance_from_source = abs(det_y - src_y)

    def _touch(self) -> None:
        self._geometry.updated_at = datetime.now().isoformat()
