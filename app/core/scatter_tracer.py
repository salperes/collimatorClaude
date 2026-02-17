"""Compton scatter ray-tracing engine — single-scatter Monte Carlo.

Walks primary rays through collimator material in discrete steps,
generates scatter events via Klein-Nishina sampling, traces scattered
photons through remaining geometry, and computes detector scatter
contributions and SPR (Scatter-to-Primary Ratio) profiles.

All internal computations in core units: cm, radian, keV.

Reference: Phase-07 spec — Scatter Ray-Tracing Algorithm.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from app.core.compton_engine import ComptonEngine
from app.core.klein_nishina_sampler import KleinNishinaSampler
from app.core.physics_engine import PhysicsEngine
from app.core.ray_tracer import (
    Ray,
    RayTracer,
    StageLayout,
    _ray_x_at_y,
    compute_stage_layout,
)
from app.core.units import mm_to_cm
from app.models.geometry import CollimatorGeometry
from app.models.simulation import ComptonConfig, SimulationResult


# ── Data Models ──────────────────────────────────────────────────────


def _empty_float_array() -> NDArray[np.float64]:
    return np.array([], dtype=np.float64)


@dataclass
class ScatterInteraction:
    """A single Compton scatter event in collimator material.

    All positions in cm (core units), angles in radian, energies in keV.

    Attributes:
        x: Interaction point X [cm].
        y: Interaction point Y [cm].
        stage_index: Index of the stage where scatter occurred.
        material_id: Material where scatter occurred.
        incident_energy_keV: Photon energy before scatter [keV].
        scattered_energy_keV: Photon energy after scatter [keV].
        scatter_angle_rad: Scattering angle theta [radian].
        reaches_detector: Whether scattered photon reaches detector.
        detector_x_cm: X position on detector plane [cm], or NaN.
        weight: Attenuation weight of scattered photon [0-1].
    """
    x: float = 0.0
    y: float = 0.0
    stage_index: int = 0
    material_id: str = ""
    incident_energy_keV: float = 0.0
    scattered_energy_keV: float = 0.0
    scatter_angle_rad: float = 0.0
    reaches_detector: bool = False
    detector_x_cm: float = float("nan")
    weight: float = 0.0


@dataclass
class ScatterResult:
    """Complete scatter simulation result.

    Attributes:
        interactions: All scatter interaction events.
        scatter_profile_mm: Detector positions of scatter contributions [mm].
        scatter_intensities: Scatter weight at each contribution.
        spr_profile: Scatter-to-primary ratio per spatial bin.
        spr_positions_mm: Bin center positions for SPR [mm].
        total_scatter_fraction: Fraction of total signal from scatter.
        mean_scattered_energy_keV: Mean energy of scattered photons reaching detector.
        num_interactions: Total scatter events generated.
        num_reaching_detector: Scatter events that reach detector.
        elapsed_seconds: Wall-clock time [s].
    """
    interactions: list[ScatterInteraction] = field(default_factory=list)
    scatter_profile_mm: NDArray[np.float64] = field(default_factory=_empty_float_array)
    scatter_intensities: NDArray[np.float64] = field(default_factory=_empty_float_array)
    spr_profile: NDArray[np.float64] = field(default_factory=_empty_float_array)
    spr_positions_mm: NDArray[np.float64] = field(default_factory=_empty_float_array)
    total_scatter_fraction: float = 0.0
    mean_scattered_energy_keV: float = 0.0
    num_interactions: int = 0
    num_reaching_detector: int = 0
    elapsed_seconds: float = 0.0


# ── ScatterTracer ────────────────────────────────────────────────────


class ScatterTracer:
    """Single-scatter Compton ray-tracing engine.

    Composition-based design: uses existing RayTracer for geometry
    intersection, PhysicsEngine for attenuation coefficients, and
    KleinNishinaSampler for angle sampling.

    Args:
        physics_engine: For mu lookups (total and Compton).
        ray_tracer: Geometric ray-tracing engine.
        compton_engine: Compton kinematics (scattered_energy, etc.).
        sampler: Klein-Nishina angle sampler.
    """

    def __init__(
        self,
        physics_engine: PhysicsEngine,
        ray_tracer: RayTracer,
        compton_engine: ComptonEngine,
        sampler: KleinNishinaSampler,
    ) -> None:
        self._physics = physics_engine
        self._tracer = ray_tracer
        self._compton = compton_engine
        self._sampler = sampler

    def simulate_scatter(
        self,
        geometry: CollimatorGeometry,
        energy_keV: float,
        num_primary_rays: int,
        config: ComptonConfig,
        primary_result: SimulationResult | None = None,
        step_size_cm: float = 0.1,
        progress_callback: Callable[[int], None] | None = None,
    ) -> ScatterResult:
        """Run single-scatter Compton simulation through multi-stage geometry.

        For each primary ray that hits material, walks along the
        material path in discrete steps and probabilistically generates
        Compton scatter events. Scattered rays are traced through the
        full geometry to determine if they reach the detector.

        Args:
            geometry: Collimator geometry [mm, degree].
            energy_keV: Primary photon energy [keV].
            num_primary_rays: Number of primary rays to trace.
            config: Compton configuration parameters.
            primary_result: Pre-computed primary simulation for SPR.
            step_size_cm: Step size for walking along ray paths [cm].
            progress_callback: Called with progress 0-100.

        Returns:
            ScatterResult with scatter profile and SPR.
        """
        t0 = time.perf_counter()

        src_x_cm = mm_to_cm(geometry.source.position.x)
        src_y_cm = mm_to_cm(geometry.source.position.y)
        det_y_cm = mm_to_cm(geometry.detector.position.y)
        det_half_cm = mm_to_cm(geometry.detector.width / 2.0)
        rng = self._sampler.rng

        # Generate primary ray angles
        angles = self._tracer.compute_ray_angles(num_primary_rays, geometry)

        # Precompute stage layouts for position interpolation
        layouts = compute_stage_layout(geometry)

        interactions: list[ScatterInteraction] = []
        scatter_detector_x: list[float] = []  # cm
        scatter_weights: list[float] = []

        progress_step = max(1, num_primary_rays // 100)

        for ray_idx, angle in enumerate(angles):
            ray = Ray(
                origin_x=src_x_cm,
                origin_y=src_y_cm,
                angle=float(angle),
                energy_keV=energy_keV,
            )

            # Trace primary ray through geometry
            stage_results = self._tracer.trace_ray(ray, geometry)

            # Only process rays that hit material
            if all(sr.passes_aperture for sr in stage_results):
                continue

            # Walk through each stage's material intersections
            for sr in stage_results:
                if sr.passes_aperture:
                    continue

                layout = layouts[sr.stage_index]

                for layer_ix in sr.layer_intersections:
                    if layer_ix.path_length < 1e-8:
                        continue

                    mat_id = layer_ix.material_id
                    mu_total = self._physics.linear_attenuation(mat_id, energy_keV)
                    mu_compton = self._physics.compton_linear_attenuation(
                        mat_id, energy_keV,
                    )

                    if mu_total < 1e-12:
                        continue

                    # Number of steps through this layer segment
                    n_steps = max(1, int(layer_ix.path_length / step_size_cm))
                    actual_step = layer_ix.path_length / n_steps

                    # Compton interaction probability per step
                    P_compton = (mu_compton / mu_total) * (
                        1.0 - math.exp(-mu_total * actual_step)
                    )

                    # Vectorized random draw for all steps
                    draws = rng.random(n_steps)
                    scatter_indices = np.where(draws < P_compton)[0]

                    for step_i in scatter_indices:
                        # Interaction position: interpolate along ray in stage
                        frac = (step_i + 0.5) / n_steps
                        iy = layout.y_top + frac * (layout.y_bottom - layout.y_top)
                        ix = _ray_x_at_y(ray, iy)

                        # Sample scattering angle
                        theta, phi, E_scattered = (
                            self._sampler.sample_compton_angle(energy_keV)
                        )

                        if E_scattered < config.min_energy_cutoff_keV:
                            continue

                        # 2D projection: project 3D scatter cone onto 2D plane.
                        # The polar angle theta defines the cone half-angle,
                        # and cos(phi) gives the lateral component in the
                        # collimator cross-section plane.
                        scatter_angle = float(angle) + theta * math.cos(phi)

                        # Check if scatter ray direction reaches detector
                        # Detector is below stages (larger Y). The ray must
                        # travel in a direction that increases Y to reach it.
                        # For our coordinate system: ray angle near 0 means
                        # moving in +Y direction. Very large |angle| > π/2
                        # would mean backward travel.
                        if abs(scatter_angle) > math.pi / 2:
                            # Ray travels sideways/backward — won't reach detector
                            interaction = ScatterInteraction(
                                x=ix, y=iy,
                                stage_index=sr.stage_index,
                                material_id=mat_id,
                                incident_energy_keV=energy_keV,
                                scattered_energy_keV=E_scattered,
                                scatter_angle_rad=theta,
                                reaches_detector=False,
                            )
                            interactions.append(interaction)
                            continue

                        # Create scatter ray and trace through all geometry
                        scatter_ray = Ray(
                            origin_x=ix,
                            origin_y=iy,
                            angle=scatter_angle,
                            energy_keV=E_scattered,
                        )

                        scatter_stage_results = self._tracer.trace_ray(
                            scatter_ray, geometry,
                        )

                        # Compute attenuation of scattered ray
                        scatter_mu_x = 0.0
                        for s_sr in scatter_stage_results:
                            if not s_sr.passes_aperture:
                                for s_ix in s_sr.layer_intersections:
                                    s_mu = self._physics.linear_attenuation(
                                        s_ix.material_id, E_scattered,
                                    )
                                    scatter_mu_x += s_mu * s_ix.path_length

                        scatter_transmission = math.exp(-scatter_mu_x)

                        # Compute detector position
                        det_x = _ray_x_at_y(scatter_ray, det_y_cm)

                        # Filter: only count scatter landing on detector
                        lands_on_detector = abs(det_x) <= det_half_cm

                        interaction = ScatterInteraction(
                            x=ix,
                            y=iy,
                            stage_index=sr.stage_index,
                            material_id=mat_id,
                            incident_energy_keV=energy_keV,
                            scattered_energy_keV=E_scattered,
                            scatter_angle_rad=theta,
                            reaches_detector=lands_on_detector,
                            detector_x_cm=det_x if lands_on_detector else float("nan"),
                            weight=scatter_transmission if lands_on_detector else 0.0,
                        )
                        interactions.append(interaction)
                        if lands_on_detector:
                            scatter_detector_x.append(det_x)
                            scatter_weights.append(scatter_transmission)

            # Progress reporting
            if progress_callback and (ray_idx + 1) % progress_step == 0:
                pct = int((ray_idx + 1) / num_primary_rays * 100)
                progress_callback(min(pct, 100))

        # Build final result with SPR computation
        result = self._build_result(
            interactions,
            scatter_detector_x,
            scatter_weights,
            primary_result,
            num_primary_rays,
        )
        result.elapsed_seconds = time.perf_counter() - t0
        return result

    def _build_result(
        self,
        interactions: list[ScatterInteraction],
        scatter_x_cm: list[float],
        scatter_weights: list[float],
        primary_result: SimulationResult | None,
        num_primary_rays: int,
    ) -> ScatterResult:
        """Aggregate scatter events into detector profile and SPR.

        Bins scatter contributions spatially, computes SPR per bin
        as scatter_intensity / primary_intensity.

        Args:
            interactions: All scatter events.
            scatter_x_cm: Detector X positions of scatter hits [cm].
            scatter_weights: Attenuation weights of scatter hits.
            primary_result: Primary simulation for SPR computation.
            num_primary_rays: Total primary rays traced.

        Returns:
            Populated ScatterResult.
        """
        result = ScatterResult()
        result.interactions = interactions
        result.num_interactions = len(interactions)
        result.num_reaching_detector = len(scatter_x_cm)

        if not scatter_x_cm:
            return result

        scatter_x_mm = np.array(scatter_x_cm) * 10.0  # cm → mm
        weights = np.array(scatter_weights)

        result.scatter_profile_mm = scatter_x_mm
        result.scatter_intensities = weights

        # Mean scattered energy of photons reaching detector
        reaching = [i for i in interactions if i.reaches_detector]
        if reaching:
            result.mean_scattered_energy_keV = float(np.mean(
                [i.scattered_energy_keV for i in reaching]
            ))

        # SPR computation — histogram scatter + interpolated primary
        if primary_result is not None:
            prim_pos = primary_result.beam_profile.positions_mm
            prim_int = primary_result.beam_profile.intensities

            if len(prim_pos) > 1 and len(scatter_x_mm) > 0:
                n_bins = 200
                pos_min = float(np.min(prim_pos))
                pos_max = float(np.max(prim_pos))
                bin_edges = np.linspace(pos_min, pos_max, n_bins + 1)
                bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
                bin_width = bin_edges[1] - bin_edges[0]

                # Primary: clean interpolation from beam profile
                prim_at_bins = np.interp(bin_centers, prim_pos, prim_int)

                # Scatter: histogram + Gaussian smoothing
                scat_hist, _ = np.histogram(
                    scatter_x_mm, bins=bin_edges, weights=weights,
                )
                # Normalize: scatter weight per primary ray per bin
                denom = max(num_primary_rays, 1)
                scat_per_ray = scat_hist / denom

                # Smooth scatter to reduce Monte Carlo noise.
                # Kernel sigma ~4 bins ≈ 2% of detector width.
                from scipy.ndimage import gaussian_filter1d
                sigma_bins = max(2.0, n_bins / 50.0)
                scat_smooth = gaussian_filter1d(
                    scat_per_ray, sigma=sigma_bins, mode="nearest",
                )

                # Primary per ray per bin (how many primary rays land
                # in each bin × their intensity, divided by N)
                prim_hist, _ = np.histogram(
                    prim_pos, bins=bin_edges, weights=prim_int,
                )
                prim_per_ray = prim_hist / denom
                prim_smooth = gaussian_filter1d(
                    prim_per_ray, sigma=sigma_bins, mode="nearest",
                )

                # SPR = scatter / primary (both smoothed, same units)
                with np.errstate(divide="ignore", invalid="ignore"):
                    spr = np.where(
                        prim_smooth > 1e-12,
                        scat_smooth / prim_smooth,
                        0.0,
                    )

                result.spr_profile = spr
                result.spr_positions_mm = bin_centers

                # Total scatter fraction (from raw sums, not smoothed)
                total_scat = float(np.sum(scat_per_ray))
                total_prim = float(np.sum(prim_per_ray))
                total_signal = total_prim + total_scat
                if total_signal > 0:
                    result.total_scatter_fraction = total_scat / total_signal

        return result
