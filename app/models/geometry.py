"""Geometry data models for collimator design.

Multi-Stage architecture (v3.0): A collimator consists of one or more
stages arranged along the beam axis. Each stage is a solid body with
a single material and an aperture cut. Stage positions are explicit
(y_position, x_offset) relative to the source focal spot.

All UI-facing dimensions are in mm, angles in degrees.
Core computations convert via app.core.units before use.
Reference: FRD §3 — Data Models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
import uuid

if TYPE_CHECKING:
    from app.models.phantom import AnyPhantom, ProjectionMethod


class CollimatorType(Enum):
    FAN_BEAM = "fan_beam"
    PENCIL_BEAM = "pencil_beam"
    SLIT = "slit"


class FocalSpotDistribution(Enum):
    """Spatial intensity distribution across the focal spot.

    UNIFORM:  Equal intensity at all points.
    GAUSSIAN: Intensity peaks at center, falls off as Gaussian
              (sigma = focal_spot_size / 4, so FWHM ≈ 0.59 * diameter).
    """
    UNIFORM = "uniform"
    GAUSSIAN = "gaussian"



class StagePurpose(Enum):
    """Functional purpose of a collimator stage in the beam path."""
    PRIMARY_SHIELDING = "primary_shielding"
    SECONDARY_SHIELDING = "secondary_shielding"
    FAN_DEFINITION = "fan_definition"
    PENUMBRA_TRIMMER = "penumbra_trimmer"
    FILTER = "filter"
    CUSTOM = "custom"


@dataclass
class Point2D:
    """2D point in UI coordinates [mm]."""
    x: float = 0.0
    y: float = 0.0


@dataclass
class SourceConfig:
    """X-ray source configuration.

    Attributes:
        position: Source position [mm].
        energy_kVp: Tube voltage [kVp] (bremsstrahlung sources).
        energy_MeV: Monoenergetic energy [MeV] (isotope sources).
        focal_spot_size: Focal spot diameter [mm].
        focal_spot_distribution: Spatial intensity profile (uniform / gaussian).
        beam_angle: X-ray beam spread full cone angle [degree].
            0.0 means auto-calculate from geometry extent.
    """
    position: Point2D = field(default_factory=Point2D)
    energy_kVp: Optional[float] = None
    energy_MeV: Optional[float] = None
    focal_spot_size: float = 1.0
    focal_spot_distribution: FocalSpotDistribution = FocalSpotDistribution.UNIFORM
    beam_angle: float = 0.0
    # Dose / intensity parameters
    tube_current_mA: float = 8.0
    tube_output_method: str = "empirical"     # "empirical" or "lookup"
    linac_pps: int = 260
    linac_dose_rate_Gy_min: float = 0.8
    linac_ref_pps: int = 260


@dataclass
class ApertureConfig:
    """Collimator aperture configuration.

    Only relevant fields are used depending on CollimatorType.

    Attributes:
        fan_angle: Fan beam opening angle [degree].
        fan_slit_width: Fan beam slit width [mm].
        pencil_diameter: Pencil beam diameter [mm].
        slit_width: Slit width [mm].
        slit_height: Slit height [mm].
        taper_angle: Aperture taper angle [degree].
    """
    fan_angle: Optional[float] = None
    fan_slit_width: Optional[float] = None
    pencil_diameter: Optional[float] = None
    slit_width: Optional[float] = None
    slit_height: Optional[float] = None
    taper_angle: float = 0.0


@dataclass
class CollimatorStage:
    """A single collimator stage (body) in the beam path.

    The stage body is SOLID: material fills the entire outer rectangle
    except for the aperture cut. No inner void or wall thickness concept.

    Stage position is explicit: y_position is the top edge Y relative
    to source focal spot (Y=0), x_offset is the center X offset from
    source axis (X=0).

    Attributes:
        id: Unique stage identifier.
        name: User-given stage name (e.g. "Internal", "Fan", "Penumbra").
        order: Position along beam axis (0 = closest to source).
        purpose: Functional purpose of this stage.
        outer_width: Total outer width (G) [mm].
        outer_height: Total outer height / thickness along beam axis (T) [mm].
        aperture: Aperture configuration for this stage.
        material_id: Shielding material identifier (e.g. "Pb", "W").
        y_position: Y position of stage top edge relative to source [mm].
        x_offset: X offset of stage center from source axis [mm].
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    order: int = 0
    purpose: StagePurpose = StagePurpose.PRIMARY_SHIELDING
    outer_width: float = 100.0
    outer_height: float = 200.0
    aperture: ApertureConfig = field(default_factory=ApertureConfig)
    material_id: str = "Pb"
    y_position: float = 0.0
    x_offset: float = 0.0


# Deprecated alias — use CollimatorStage instead.
CollimatorBody = CollimatorStage


@dataclass
class DetectorConfig:
    """Detector configuration.

    Attributes:
        position: Detector center position [mm].
        width: Detector active width [mm].
        distance_from_source: Source-to-detector distance (SDD) [mm].
    """
    position: Point2D = field(default_factory=lambda: Point2D(0, 500))
    width: float = 500.0
    distance_from_source: float = 1000.0


@dataclass
class CollimatorGeometry:
    """Complete collimator design geometry.

    The design consists of one or more stages arranged along the beam
    axis from source to detector. Each stage is a solid body with its
    own aperture and material. Stage positions are explicit.

    For single-stage designs, ``stages`` contains exactly one element.

    Attributes:
        id: Unique design identifier.
        name: User-given design name.
        type: Collimator beam type.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last-modified timestamp.
        source: X-ray source configuration.
        stages: Ordered list of collimator stages (source → detector).
        detector: Detector configuration.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Yeni Tasarim"
    type: CollimatorType = CollimatorType.FAN_BEAM
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source: SourceConfig = field(default_factory=SourceConfig)
    stages: list[CollimatorStage] = field(default_factory=lambda: [CollimatorStage()])
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    phantoms: list[AnyPhantom] = field(default_factory=list)

    @property
    def body(self) -> CollimatorStage:
        """Legacy accessor — returns the first (or only) stage.

        Deprecated: use ``stages[0]`` instead.
        """
        return self.stages[0] if self.stages else CollimatorStage()

    @property
    def stage_count(self) -> int:
        """Number of stages in the design."""
        return len(self.stages)

    @property
    def total_height(self) -> float:
        """Total span from topmost stage top to bottommost stage bottom [mm]."""
        if not self.stages:
            return 0.0
        top = min(s.y_position for s in self.stages)
        bottom = max(s.y_position + s.outer_height for s in self.stages)
        return bottom - top
