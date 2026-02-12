"""Geometry data models for collimator design.

Multi-Stage architecture (v2.0): A collimator consists of one or more
stages arranged along the beam axis, separated by gaps (air/vacuum).
Each stage has its own aperture, layers, and outer dimensions.

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


class LayerPurpose(Enum):
    PRIMARY_SHIELDING = "primary_shielding"
    SECONDARY_SHIELDING = "secondary_shielding"
    STRUCTURAL = "structural"
    FILTER = "filter"


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
    """
    position: Point2D = field(default_factory=Point2D)
    energy_kVp: Optional[float] = None
    energy_MeV: Optional[float] = None
    focal_spot_size: float = 1.0
    focal_spot_distribution: FocalSpotDistribution = FocalSpotDistribution.UNIFORM


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
class CollimatorLayer:
    """Single material layer in a collimator stage.

    Supports optional composite (İç/Dış) zones: when inner_material_id
    is set and inner_width > 0, the layer has two lateral zones:
      - Inner zone (aperture side, width = inner_width): inner_material_id
      - Outer zone (remaining thickness): material_id

    Attributes:
        id: Unique layer identifier.
        order: Stacking order (0 = innermost).
        material_id: Primary (outer zone) material reference.
        thickness: Total layer thickness [mm].
        purpose: Layer functional purpose.
        inner_material_id: Composite inner zone material (None = not composite).
        inner_width: Inner zone width [mm] (0 = not composite).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order: int = 0
    material_id: str = ""
    thickness: float = 0.0
    purpose: LayerPurpose = LayerPurpose.PRIMARY_SHIELDING
    inner_material_id: str | None = None
    inner_width: float = 0.0

    @property
    def is_composite(self) -> bool:
        """True if this layer has İç/Dış zones."""
        return self.inner_material_id is not None and self.inner_width > 0


@dataclass
class CollimatorStage:
    """A single collimator stage (body) in the beam path.

    Each stage is an independent collimator body with its own aperture,
    layers, and physical dimensions. Stages are ordered along the beam
    axis from source to detector.

    Example 3-stage layout:
        Source → [Internal] → (gap) → [Fan] → (gap) → [Penumbra] → Detector

    Attributes:
        id: Unique stage identifier.
        name: User-given stage name (e.g. "Internal", "Fan", "Penumbra").
        order: Position along beam axis (0 = closest to source).
        purpose: Functional purpose of this stage.
        outer_width: Total outer width [mm].
        outer_height: Total outer height along beam axis [mm].
        aperture: Aperture configuration for this stage.
        layers: Material layers (inner to outer).
        gap_after: Gap distance to next stage [mm]. Ignored for last stage.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    order: int = 0
    purpose: StagePurpose = StagePurpose.PRIMARY_SHIELDING
    outer_width: float = 100.0
    outer_height: float = 200.0
    aperture: ApertureConfig = field(default_factory=ApertureConfig)
    layers: list[CollimatorLayer] = field(default_factory=list)
    gap_after: float = 0.0


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
    axis from source to detector. Each stage is an independent body
    with its own aperture and layers. Stages are separated by gaps.

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
        """Total height of all stages plus inter-stage gaps [mm]."""
        if not self.stages:
            return 0.0
        height = sum(s.outer_height for s in self.stages)
        # Add gaps between stages (last stage's gap_after is ignored)
        if len(self.stages) > 1:
            height += sum(s.gap_after for s in self.stages[:-1])
        return height
