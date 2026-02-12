"""Simulation configuration and result data models.

Reference: FRD §3 — Data Models, Phase 4 spec.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from numpy.typing import NDArray


@dataclass
class ComptonConfig:
    """Compton scatter simulation parameters.

    Attributes:
        enabled: Whether Compton scatter is active.
        max_scatter_order: Maximum scatter generation (1 = single).
        scatter_rays_per_interaction: Sub-rays spawned per interaction.
        min_energy_cutoff_keV: Energy threshold to stop tracking [keV].
        include_klein_nishina: Use Klein-Nishina differential cross-section.
        angular_bins: Number of angular bins for scatter distribution.
    """
    enabled: bool = False
    max_scatter_order: int = 1
    scatter_rays_per_interaction: int = 10
    min_energy_cutoff_keV: float = 10.0
    include_klein_nishina: bool = True
    angular_bins: int = 180


@dataclass
class SimulationConfig:
    """Ray-tracing simulation configuration.

    Attributes:
        id: Unique simulation identifier.
        geometry_id: Reference to CollimatorGeometry.id.
        energy_points: Photon energies to simulate [keV].
        num_rays: Number of rays to trace.
        include_buildup: Apply build-up factor correction.
        include_scatter: Enable scatter simulation.
        angular_resolution: Angular step between rays [degree].
        compton_config: Compton scatter parameters.
    """
    id: str = ""
    geometry_id: str = ""
    energy_points: list[float] = field(default_factory=list)
    num_rays: int = 360
    include_buildup: bool = True
    include_scatter: bool = False
    angular_resolution: float = 1.0
    compton_config: ComptonConfig = field(default_factory=ComptonConfig)


# ── Phase 4: Ray-tracing results ──


class MetricStatus(Enum):
    """Traffic-light status for quality metrics."""
    EXCELLENT = "excellent"
    ACCEPTABLE = "acceptable"
    POOR = "poor"


@dataclass
class QualityMetric:
    """Single quality metric with value and pass/fail status.

    Attributes:
        name: Display name (e.g. "Penumbra").
        value: Numeric value.
        unit: Display unit (e.g. "mm", "%", "dB").
        status: Traffic-light status.
        threshold_excellent: Upper bound for EXCELLENT (lower-is-better metrics).
        threshold_acceptable: Upper bound for ACCEPTABLE.
    """
    name: str = ""
    value: float = 0.0
    unit: str = ""
    status: MetricStatus = MetricStatus.POOR
    threshold_excellent: float = 0.0
    threshold_acceptable: float = 0.0


@dataclass
class QualityMetrics:
    """Aggregate quality metrics for a beam simulation.

    All positions in mm (UI units), percentages as 0-100.

    Attributes:
        penumbra_left_mm: Left edge 20%-80% penumbra width [mm].
        penumbra_right_mm: Right edge 20%-80% penumbra width [mm].
        penumbra_max_mm: max(left, right) [mm].
        flatness_pct: (Imax-Imin)/(Imax+Imin) in useful beam [%].
        leakage_avg_pct: Mean leakage in shielded region [%].
        leakage_max_pct: Max leakage in shielded region [%].
        collimation_ratio: Primary/leakage ratio [linear].
        collimation_ratio_dB: 10*log10(CR) [dB].
        fwhm_mm: Full width at half maximum [mm].
        metrics: List of QualityMetric for UI rendering.
        all_pass: True if no metric is POOR.
    """
    penumbra_left_mm: float = 0.0
    penumbra_right_mm: float = 0.0
    penumbra_max_mm: float = 0.0
    flatness_pct: float = 0.0
    leakage_avg_pct: float = 0.0
    leakage_max_pct: float = 0.0
    collimation_ratio: float = 0.0
    collimation_ratio_dB: float = 0.0
    fwhm_mm: float = 0.0
    metrics: list[QualityMetric] = field(default_factory=list)
    all_pass: bool = False


def _empty_float_array() -> NDArray[np.float64]:
    return np.array([], dtype=np.float64)


@dataclass
class BeamProfile:
    """Detector intensity profile from ray-tracing simulation.

    Attributes:
        positions_mm: Detector lateral positions [mm].
        intensities: Normalized transmission at each position [0-1].
        angles_rad: Ray angles corresponding to each position [radian].
    """
    positions_mm: NDArray[np.float64] = field(default_factory=_empty_float_array)
    intensities: NDArray[np.float64] = field(default_factory=_empty_float_array)
    angles_rad: NDArray[np.float64] = field(default_factory=_empty_float_array)


@dataclass
class SimulationResult:
    """Complete ray-tracing simulation result.

    Attributes:
        energy_keV: Photon energy [keV].
        num_rays: Number of rays traced.
        beam_profile: Detector intensity profile.
        quality_metrics: Quality analysis.
        elapsed_seconds: Wall-clock time [s].
        include_buildup: Whether build-up was applied.
    """
    energy_keV: float = 0.0
    num_rays: int = 0
    beam_profile: BeamProfile = field(default_factory=BeamProfile)
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)
    elapsed_seconds: float = 0.0
    include_buildup: bool = False
    scatter_result: object | None = None  # ScatterResult (Phase 7, optional)
