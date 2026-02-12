"""Test object (phantom) data models for image quality assessment.

Phantom types:
  - Wire (IQI): circular cross-section wire for resolution measurement.
  - LinePair: bar pattern for spatial frequency response / MTF.
  - Grid: wire mesh for 2D resolution assessment.

All UI-facing dimensions are in mm.
Core computations convert via app.core.units before use.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Union
import uuid


class PhantomType(Enum):
    """Type of test object."""
    WIRE = "wire"
    LINE_PAIR = "line_pair"
    GRID = "grid"


class ProjectionMethod(Enum):
    """Projection calculation method.

    ANALYTIC: Geometric projection with Beer-Lambert attenuation.
    RAY_TRACE: Monte Carlo ray-tracing (Phase 4).
    """
    ANALYTIC = "analytic"
    RAY_TRACE = "ray_trace"


@dataclass
class PhantomConfig:
    """Common configuration shared by all phantom types.

    Attributes:
        id: Unique phantom identifier.
        type: Phantom type discriminator.
        name: User-visible name (e.g. "Tel 0.5mm W").
        position_y: Y position on canvas [mm] (between last stage and detector).
        material_id: Material identifier (e.g. "W", "Pb").
        enabled: Whether phantom participates in projection.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: PhantomType = PhantomType.WIRE
    name: str = ""
    position_y: float = 300.0
    material_id: str = "W"
    enabled: bool = True


@dataclass
class WirePhantom:
    """Wire (IQI) test object — circular cross-section.

    Used for resolution measurement. The wire's projected image
    provides the Line Spread Function (LSF) from which the MTF
    can be derived via FFT.

    Attributes:
        config: Common phantom configuration.
        diameter: Wire diameter [mm].
    """
    config: PhantomConfig = field(default_factory=lambda: PhantomConfig(
        type=PhantomType.WIRE, name="Tel 0.5mm",
    ))
    diameter: float = 0.5


@dataclass
class LinePairPhantom:
    """Line-pair (bar pattern) test object.

    Alternating opaque/transparent bars at a given spatial frequency.
    Measures contrast transfer at specific frequencies.

    Attributes:
        config: Common phantom configuration.
        frequency: Spatial frequency at object plane [lp/mm].
        bar_thickness: Bar thickness in beam direction [mm].
        num_cycles: Number of bar-space cycles.
    """
    config: PhantomConfig = field(default_factory=lambda: PhantomConfig(
        type=PhantomType.LINE_PAIR, name="Cizgi Cifti 1 lp/mm",
    ))
    frequency: float = 1.0
    bar_thickness: float = 1.0
    num_cycles: int = 5


@dataclass
class GridPhantom:
    """Wire grid (mesh) test object.

    Periodic array of wires for 2D resolution assessment.

    Attributes:
        config: Common phantom configuration.
        pitch: Wire center-to-center spacing [mm].
        wire_diameter: Individual wire diameter [mm].
        size: Total grid extent [mm].
    """
    config: PhantomConfig = field(default_factory=lambda: PhantomConfig(
        type=PhantomType.GRID, name="Grid 1mm",
    ))
    pitch: float = 1.0
    wire_diameter: float = 0.1
    size: float = 50.0


# Union type for any phantom
AnyPhantom = Union[WirePhantom, LinePairPhantom, GridPhantom]
