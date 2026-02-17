"""Beam simulation — orchestrates ray-tracing with attenuation.

Generates a beam intensity profile by tracing rays through the
collimator geometry and computing Beer-Lambert attenuation with
optional build-up factor correction.

All internal computations in core units: cm, radian, keV.
Results returned in UI units: mm, degree.

Reference: Phase 4 spec — Beam Simulation.
"""

from __future__ import annotations

import math
import time
from typing import Callable

import numpy as np

from app.core.i18n import t
from app.core.ray_tracer import Ray, RayTracer, compute_stage_layout
from app.core.units import cm_to_mm, thickness_to_mfp
from app.models.geometry import (
    CollimatorGeometry,
    CollimatorType,
    FocalSpotDistribution,
)
from app.models.simulation import (
    BeamProfile,
    MetricStatus,
    QualityMetric,
    QualityMetrics,
    SimulationResult,
)

# ── Quality metric thresholds ──

# Penumbra thresholds [mm] per collimator type
_PENUMBRA_THRESHOLDS: dict[CollimatorType, tuple[float, float]] = {
    CollimatorType.FAN_BEAM: (5.0, 10.0),       # excellent, acceptable
    CollimatorType.PENCIL_BEAM: (1.0, 3.0),
    CollimatorType.SLIT: (2.0, 5.0),
}

# Flatness [%]
_FLATNESS_EXCELLENT = 3.0
_FLATNESS_ACCEPTABLE = 10.0

# Leakage [%]
_LEAKAGE_EXCELLENT = 0.1
_LEAKAGE_ACCEPTABLE = 5.0

# Collimation ratio [dB]
_CR_EXCELLENT = 30.0
_CR_ACCEPTABLE = 10.0


class BeamSimulation:
    """Orchestrates full beam profile simulation.

    Args:
        physics_engine: For μ lookups (linear_attenuation).
        ray_tracer: Geometric ray-tracing engine.
        buildup_service: Optional build-up factor calculator.
    """

    def __init__(
        self,
        physics_engine,
        ray_tracer: RayTracer | None = None,
        buildup_service=None,
    ) -> None:
        self._physics = physics_engine
        self._tracer = ray_tracer or RayTracer()
        self._buildup = buildup_service
        self._custom_thresholds: dict[str, float] | None = None

    def set_custom_thresholds(self, thresholds: dict[str, float] | None) -> None:
        """Set custom quality metric thresholds.

        Args:
            thresholds: Dict with keys like 'penumbra_excellent', 'flatness_acceptable', etc.
                        Pass None to reset to defaults.
        """
        self._custom_thresholds = thresholds

    def calculate_beam_profile(
        self,
        geometry: CollimatorGeometry,
        energy_keV: float,
        num_rays: int = 5000,
        include_buildup: bool = True,
        include_air: bool = False,
        include_inverse_sq: bool = False,
        progress_callback: Callable[[int], None] | None = None,
    ) -> SimulationResult:
        """Run full beam profile simulation.

        1. Generate ray angles spanning FOV + leakage region.
        2. Trace each ray through the collimator.
        3. Compute Beer-Lambert transmission per ray.
        4. Optionally apply build-up factor.
        5. Optionally apply air attenuation and 1/r².
        6. Calculate quality metrics.

        Args:
            geometry: Collimator geometry [mm, degree].
            energy_keV: Photon energy [keV].
            num_rays: Number of rays (default 5000).
            include_buildup: Apply build-up factor correction.
            include_air: Apply air attenuation along ray path.
            include_inverse_sq: Apply 1/r² geometric divergence.
            progress_callback: Called with progress 0-100.

        Returns:
            SimulationResult with beam profile and quality metrics.
        """
        t0 = time.perf_counter()

        # Source position in core units [cm]
        src_x_cm = geometry.source.position.x / 10.0  # mm→cm
        src_y_cm = geometry.source.position.y / 10.0
        det_y_cm = geometry.detector.position.y / 10.0

        # Pre-compute air linear attenuation [cm^-1]
        mu_air = 0.0
        if include_air:
            mu_air = self._physics.linear_attenuation("Air", energy_keV)

        # Reference distance for 1/r² [cm]
        r_ref_sq = 1.0
        if include_inverse_sq:
            layouts = compute_stage_layout(geometry)
            if layouts:
                dy_ref = layouts[0].y_top - src_y_cm
            else:
                dy_ref = det_y_cm - src_y_cm
            r_ref_sq = max(dy_ref ** 2, 0.01)

        # Total source-to-detector vertical distance [cm]
        total_dy_cm = abs(det_y_cm - src_y_cm)

        # Generate ray angles
        angles = self._tracer.compute_ray_angles(num_rays, geometry)

        positions_cm = np.empty(num_rays)
        intensities = np.empty(num_rays)

        for i, angle in enumerate(angles):
            ray = Ray(
                origin_x=src_x_cm,
                origin_y=src_y_cm,
                angle=float(angle),
                energy_keV=energy_keV,
            )

            # Trace through geometry
            stage_results = self._tracer.trace_ray(ray, geometry)

            # Check if passes all apertures
            all_pass = all(sr.passes_aperture for sr in stage_results)

            # Accumulate μ × path_length per material
            total_mu_x = 0.0
            material_path_cm = 0.0
            layers_mfp: list[tuple[str, float]] = []

            if not all_pass:
                for sr in stage_results:
                    if sr.passes_aperture:
                        continue
                    for ix in sr.layer_intersections:
                        mu = self._physics.linear_attenuation(
                            ix.material_id, energy_keV,
                        )
                        mu_x = mu * ix.path_length
                        total_mu_x += mu_x
                        material_path_cm += ix.path_length

                        # For build-up: convert to mfp
                        mfp = thickness_to_mfp(ix.path_length, mu)
                        layers_mfp.append((ix.material_id, mfp))

            transmission = math.exp(-total_mu_x) if total_mu_x > 0 else 1.0

            # Build-up correction
            if include_buildup and self._buildup and layers_mfp:
                B = self._buildup.get_multilayer_buildup(
                    layers_mfp, energy_keV,
                )
                transmission *= B

            # Air attenuation
            if include_air and mu_air > 1e-15:
                cos_a = math.cos(float(angle))
                total_ray_path = total_dy_cm / cos_a if abs(cos_a) > 1e-10 else total_dy_cm
                air_path = max(total_ray_path - material_path_cm, 0.0)
                transmission *= math.exp(-mu_air * air_path)

            # Inverse-square law
            if include_inverse_sq:
                cos_a = math.cos(float(angle))
                det_dx = total_dy_cm * math.tan(float(angle))
                r_sq = det_dx**2 + total_dy_cm**2
                r_sq = max(r_sq, 0.01)
                transmission *= r_ref_sq / r_sq

            intensities[i] = min(transmission, 1.0)

            # Detector position
            positions_cm[i] = self._tracer.compute_detector_position(ray, geometry)

            if progress_callback and (i + 1) % max(1, num_rays // 100) == 0:
                progress_callback(int((i + 1) / num_rays * 100))

        # Sort by detector position
        sort_idx = np.argsort(positions_cm)
        positions_cm = positions_cm[sort_idx]
        intensities = intensities[sort_idx]
        angles_sorted = angles[sort_idx]

        # Convert positions to mm (UI units)
        positions_mm = positions_cm * 10.0

        # ── Focal spot PSF blur ──
        focal_mm = geometry.source.focal_spot_size
        if focal_mm > 0.01 and len(positions_mm) > 2:
            focal_cm = focal_mm * 0.1
            det_y_cm = geometry.detector.position.y / 10.0

            # Object = last stage midpoint (defines beam edges)
            last_stage = geometry.stages[-1]
            stage_mid_y_cm = (
                last_stage.y_position + last_stage.outer_height / 2.0
            ) / 10.0

            sod = abs(stage_mid_y_cm - src_y_cm)
            odd = abs(det_y_cm - stage_mid_y_cm)

            if sod > 1e-6:
                ug_cm = focal_cm * odd / sod

                # Resample onto uniform detector grid for convolution
                n_grid = len(positions_mm)
                grid_mm = np.linspace(
                    float(positions_mm[0]), float(positions_mm[-1]), n_grid,
                )
                grid_intensities = np.interp(grid_mm, positions_mm, intensities)
                grid_angles = np.interp(grid_mm, positions_mm, angles_sorted)

                dx_cm = abs(grid_mm[1] - grid_mm[0]) * 0.1

                if ug_cm > dx_cm and dx_cm > 0:
                    from scipy.ndimage import gaussian_filter1d, uniform_filter1d

                    dist = geometry.source.focal_spot_distribution
                    if dist == FocalSpotDistribution.GAUSSIAN:
                        sigma_cm = ug_cm / 2.355
                        sigma_samples = sigma_cm / dx_cm
                        if sigma_samples > 0.5:
                            grid_intensities = gaussian_filter1d(
                                grid_intensities,
                                sigma=sigma_samples,
                                mode="nearest",
                            )
                    else:
                        width_samples = int(round(ug_cm / dx_cm))
                        if width_samples >= 2:
                            grid_intensities = uniform_filter1d(
                                grid_intensities,
                                size=width_samples,
                                mode="nearest",
                            )

                positions_mm = grid_mm
                intensities = grid_intensities
                angles_sorted = grid_angles

        beam_profile = BeamProfile(
            positions_mm=positions_mm,
            intensities=intensities,
            angles_rad=angles_sorted,
        )

        # Quality metrics
        quality = self._calculate_quality_metrics(beam_profile, geometry.type)

        elapsed = time.perf_counter() - t0

        return SimulationResult(
            energy_keV=energy_keV,
            num_rays=num_rays,
            beam_profile=beam_profile,
            quality_metrics=quality,
            elapsed_seconds=elapsed,
            include_buildup=include_buildup,
        )

    def _calculate_quality_metrics(
        self,
        profile: BeamProfile,
        ctype: CollimatorType,
    ) -> QualityMetrics:
        """Calculate beam quality metrics from intensity profile.

        Args:
            profile: Beam intensity profile [mm, 0-1].
            ctype: Collimator type (for penumbra thresholds).

        Returns:
            QualityMetrics with penumbra, flatness, leakage, CR.
        """
        pos = profile.positions_mm
        ints = profile.intensities

        if len(pos) < 3:
            return QualityMetrics()

        i_max = float(np.max(ints))
        if i_max < 1e-12:
            return QualityMetrics()

        # ── FWHM ──
        half_max = i_max / 2.0
        fwhm_left, fwhm_right = self._find_edges(pos, ints, half_max)
        fwhm_mm = fwhm_right - fwhm_left

        # ── Penumbra (20%-80%) ──
        level_20 = 0.2 * i_max
        level_80 = 0.8 * i_max

        left_20, _ = self._find_edges(pos, ints, level_20)
        left_80, _ = self._find_edges(pos, ints, level_80)
        _, right_80 = self._find_edges(pos, ints, level_80)
        _, right_20 = self._find_edges(pos, ints, level_20)

        penumbra_left = abs(left_80 - left_20)
        penumbra_right = abs(right_20 - right_80)
        penumbra_max = max(penumbra_left, penumbra_right)

        # ── Flatness ──
        # Useful beam = central 80% of FWHM
        trim = 0.1 * fwhm_mm  # 10% from each edge
        useful_left = fwhm_left + trim
        useful_right = fwhm_right - trim

        mask_useful = (pos >= useful_left) & (pos <= useful_right)
        if np.any(mask_useful):
            i_useful = ints[mask_useful]
            i_min_u = float(np.min(i_useful))
            i_max_u = float(np.max(i_useful))
            denom = i_max_u + i_min_u
            flatness_pct = 100.0 * (i_max_u - i_min_u) / denom if denom > 0 else 0.0
        else:
            flatness_pct = 0.0

        # ── Leakage ──
        # Outside FWHM region (excluding penumbra transition)
        margin = penumbra_max
        mask_leak = (pos < (fwhm_left - margin)) | (pos > (fwhm_right + margin))
        mask_primary = (pos >= fwhm_left) & (pos <= fwhm_right)

        if np.any(mask_leak) and np.any(mask_primary):
            leak_mean = float(np.mean(ints[mask_leak]))
            leak_max_val = float(np.max(ints[mask_leak]))
            primary_mean = float(np.mean(ints[mask_primary]))
            if primary_mean > 1e-12:
                leakage_avg_pct = 100.0 * leak_mean / primary_mean
                leakage_max_pct = 100.0 * leak_max_val / primary_mean
                cr = primary_mean / max(leak_mean, 1e-30)
                cr_dB = 10.0 * math.log10(cr) if cr > 0 else 0.0
            else:
                leakage_avg_pct = 0.0
                leakage_max_pct = 0.0
                cr = 0.0
                cr_dB = 0.0
        else:
            leakage_avg_pct = 0.0
            leakage_max_pct = 0.0
            cr = 1e6  # no leakage region
            cr_dB = 60.0

        # ── Build metric list for UI ──
        ct = self._custom_thresholds
        pen_exc, pen_acc = _PENUMBRA_THRESHOLDS.get(
            ctype, (5.0, 10.0),
        )
        if ct:
            pen_exc = ct.get("penumbra_excellent", pen_exc)
            pen_acc = ct.get("penumbra_acceptable", pen_acc)

        flat_exc = ct.get("flatness_excellent", _FLATNESS_EXCELLENT) if ct else _FLATNESS_EXCELLENT
        flat_acc = ct.get("flatness_acceptable", _FLATNESS_ACCEPTABLE) if ct else _FLATNESS_ACCEPTABLE
        leak_exc = ct.get("leakage_excellent", _LEAKAGE_EXCELLENT) if ct else _LEAKAGE_EXCELLENT
        leak_acc = ct.get("leakage_acceptable", _LEAKAGE_ACCEPTABLE) if ct else _LEAKAGE_ACCEPTABLE
        cr_exc = ct.get("cr_excellent", _CR_EXCELLENT) if ct else _CR_EXCELLENT
        cr_acc = ct.get("cr_acceptable", _CR_ACCEPTABLE) if ct else _CR_ACCEPTABLE

        metrics: list[QualityMetric] = [
            QualityMetric(
                name=t("metrics.penumbra", "Penumbra (max)"),
                value=penumbra_max,
                unit="mm",
                status=_classify_lower_better(penumbra_max, pen_exc, pen_acc),
                threshold_excellent=pen_exc,
                threshold_acceptable=pen_acc,
            ),
            QualityMetric(
                name=t("metrics.flatness", "Flatness"),
                value=flatness_pct,
                unit="%",
                status=_classify_lower_better(flatness_pct, flat_exc, flat_acc),
                threshold_excellent=flat_exc,
                threshold_acceptable=flat_acc,
            ),
            QualityMetric(
                name=t("metrics.leakage", "Leakage (avg)"),
                value=leakage_avg_pct,
                unit="%",
                status=_classify_lower_better(leakage_avg_pct, leak_exc, leak_acc),
                threshold_excellent=leak_exc,
                threshold_acceptable=leak_acc,
            ),
            QualityMetric(
                name=t("metrics.collimation_ratio", "Collim. Ratio"),
                value=cr_dB,
                unit="dB",
                status=_classify_higher_better(cr_dB, cr_exc, cr_acc),
                threshold_excellent=cr_exc,
                threshold_acceptable=cr_acc,
            ),
        ]

        all_pass = all(m.status != MetricStatus.POOR for m in metrics)

        return QualityMetrics(
            penumbra_left_mm=penumbra_left,
            penumbra_right_mm=penumbra_right,
            penumbra_max_mm=penumbra_max,
            flatness_pct=flatness_pct,
            leakage_avg_pct=leakage_avg_pct,
            leakage_max_pct=leakage_max_pct,
            collimation_ratio=cr,
            collimation_ratio_dB=cr_dB,
            fwhm_mm=fwhm_mm,
            metrics=metrics,
            all_pass=all_pass,
        )

    def compare_energies(
        self,
        geometry: CollimatorGeometry,
        energies_keV: list[float],
        num_rays: int = 5000,
        include_buildup: bool = True,
        include_air: bool = False,
        include_inverse_sq: bool = False,
        progress_callback: Callable[[int], None] | None = None,
    ) -> dict[float, SimulationResult]:
        """Run beam profile at multiple energies for overlay comparison.

        FRD §5.3 — compare_energies interface.

        Args:
            geometry: Collimator geometry [mm, degree].
            energies_keV: List of photon energies [keV].
            num_rays: Number of rays per simulation.
            include_buildup: Apply build-up factor correction.
            include_air: Apply air attenuation along ray path.
            include_inverse_sq: Apply 1/r² geometric divergence.
            progress_callback: Called with progress 0-100 (total).

        Returns:
            Dict mapping energy_keV → SimulationResult.
        """
        results: dict[float, SimulationResult] = {}
        n = len(energies_keV)
        for idx, e in enumerate(energies_keV):
            def _sub(pct: int, _idx=idx) -> None:
                if progress_callback:
                    progress_callback(int((_idx * 100 + pct) / n))

            results[e] = self.calculate_beam_profile(
                geometry, e, num_rays, include_buildup,
                include_air, include_inverse_sq, _sub,
            )
        return results

    @staticmethod
    def _find_edges(
        pos: np.ndarray,
        ints: np.ndarray,
        level: float,
    ) -> tuple[float, float]:
        """Find left and right edge positions at given intensity level.

        Linear interpolation at crossings.

        Args:
            pos: Sorted positions [mm].
            ints: Intensities [0-1].
            level: Threshold intensity.

        Returns:
            (left_edge_mm, right_edge_mm).
        """
        above = ints >= level

        # Left edge: first crossing from below to above
        left_edge = float(pos[0])
        for i in range(1, len(above)):
            if above[i] and not above[i - 1]:
                # Linear interpolation
                frac = (level - ints[i - 1]) / max(ints[i] - ints[i - 1], 1e-30)
                left_edge = pos[i - 1] + frac * (pos[i] - pos[i - 1])
                break

        # Right edge: last crossing from above to below
        right_edge = float(pos[-1])
        for i in range(len(above) - 1, 0, -1):
            if above[i - 1] and not above[i]:
                frac = (level - ints[i]) / max(ints[i - 1] - ints[i], 1e-30)
                right_edge = pos[i] + frac * (pos[i - 1] - pos[i])
                break

        return left_edge, right_edge


# ── Helpers ──


def _classify_lower_better(
    value: float, excellent: float, acceptable: float,
) -> MetricStatus:
    """Classify metric where lower is better."""
    if value <= excellent:
        return MetricStatus.EXCELLENT
    elif value <= acceptable:
        return MetricStatus.ACCEPTABLE
    return MetricStatus.POOR


def _classify_higher_better(
    value: float, excellent: float, acceptable: float,
) -> MetricStatus:
    """Classify metric where higher is better."""
    if value >= excellent:
        return MetricStatus.EXCELLENT
    elif value >= acceptable:
        return MetricStatus.ACCEPTABLE
    return MetricStatus.POOR
