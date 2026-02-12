"""Projection result data models.

Stores the output of analytic (or future ray-trace) projection
calculations: geometric parameters, detector intensity profile,
and MTF (Modulation Transfer Function) curves.

All result dimensions use the unit system convention:
  - Core internal: cm, keV
  - UI-facing arrays: mm (positions), lp/mm (frequencies)
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from app.models.phantom import ProjectionMethod


def _empty_array() -> NDArray[np.float64]:
    return np.array([], dtype=np.float64)


@dataclass
class GeometricParams:
    """Projection geometry parameters.

    Attributes:
        sod_cm: Source-to-Object Distance [cm].
        odd_cm: Object-to-Detector Distance [cm].
        sdd_cm: Source-to-Detector Distance [cm].
        magnification: Geometric magnification M = SDD / SOD.
        geometric_unsharpness_cm: Ug = f * ODD / SOD [cm],
            where f = focal spot diameter.
    """
    sod_cm: float = 0.0
    odd_cm: float = 0.0
    sdd_cm: float = 0.0
    magnification: float = 1.0
    geometric_unsharpness_cm: float = 0.0


@dataclass
class DetectorProfile:
    """Intensity profile at the detector plane.

    Attributes:
        positions_mm: Lateral detector coordinates [mm].
        intensities: Normalized intensity values [0–1].
        contrast: Michelson contrast (Imax - Imin) / (Imax + Imin).
    """
    positions_mm: NDArray[np.float64] = field(default_factory=_empty_array)
    intensities: NDArray[np.float64] = field(default_factory=_empty_array)
    contrast: float = 0.0


@dataclass
class MTFResult:
    """Modulation Transfer Function result.

    Attributes:
        frequencies_lpmm: Spatial frequency axis [lp/mm].
        mtf_values: MTF magnitude [0–1].
        mtf_50_freq: Frequency where MTF = 0.5 [lp/mm], 0 if not reached.
        mtf_10_freq: Frequency where MTF = 0.1 [lp/mm], 0 if not reached.
    """
    frequencies_lpmm: NDArray[np.float64] = field(default_factory=_empty_array)
    mtf_values: NDArray[np.float64] = field(default_factory=_empty_array)
    mtf_50_freq: float = 0.0
    mtf_10_freq: float = 0.0


@dataclass
class ProjectionResult:
    """Complete projection calculation result.

    Attributes:
        phantom_id: ID of the phantom that was projected.
        method: Projection method used.
        geometry: Geometric projection parameters.
        profile: Detector intensity profile.
        mtf: MTF analysis (None if not computed).
    """
    phantom_id: str = ""
    method: ProjectionMethod = ProjectionMethod.ANALYTIC
    geometry: GeometricParams = None  # type: ignore[assignment]
    profile: DetectorProfile = None  # type: ignore[assignment]
    mtf: Optional[MTFResult] = None

    def __post_init__(self):
        if self.geometry is None:
            self.geometry = GeometricParams()
        if self.profile is None:
            self.profile = DetectorProfile()
