"""Isodose map engine — 2D dose distribution computation.

Computes a 2D grid of radiation dose/intensity values through the
collimator geometry using vectorized ray-tracing per Y-plane.

Physics model:
  - Beer-Lambert material attenuation through collimator stages
  - Air attenuation along the full ray path (optional)
  - Inverse-square law geometric divergence (optional)

All internal computations in core units: cm, radian, keV.
Results returned in UI units: mm.

Reference: Phase 8 — Isodose Map Feature.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from app.core.ray_tracer import (
    StageLayout,
    aperture_half_width_at_y,
    compute_stage_layout,
)
from app.core.units import cm_to_mm, mm_to_cm
from app.models.geometry import CollimatorGeometry, CollimatorType


def _empty_float_array() -> NDArray[np.float64]:
    return np.array([], dtype=np.float64)


# Standard isodose contour levels (fraction of max)
DEFAULT_CONTOUR_LEVELS = [1.0, 0.8, 0.5, 0.2, 0.1, 0.05]


@dataclass
class IsodoseResult:
    """2D dose distribution through the collimator field.

    All spatial coordinates in UI units (mm).

    Attributes:
        dose_map: 2D array [ny, nx] of relative dose values [0-1].
        x_positions_mm: X grid positions [mm], shape (nx,).
        y_positions_mm: Y grid positions [mm], shape (ny,).
        contour_levels: Standard isodose levels as fractions [0-1].
        energy_keV: Photon energy [keV].
        nx: X grid resolution.
        ny: Y grid resolution.
        elapsed_seconds: Computation time [s].
        include_air: Whether air attenuation was applied.
        include_inverse_sq: Whether 1/r^2 was applied.
    """

    dose_map: NDArray[np.float64] = field(default_factory=_empty_float_array)
    x_positions_mm: NDArray[np.float64] = field(default_factory=_empty_float_array)
    y_positions_mm: NDArray[np.float64] = field(default_factory=_empty_float_array)
    contour_levels: list[float] = field(
        default_factory=lambda: list(DEFAULT_CONTOUR_LEVELS)
    )
    energy_keV: float = 0.0
    nx: int = 0
    ny: int = 0
    elapsed_seconds: float = 0.0
    include_air: bool = False
    include_inverse_sq: bool = False


class IsodoseEngine:
    """Computes 2D dose distribution through collimator geometry.

    Uses vectorized per-Y-plane ray-tracing for performance.

    Args:
        physics_engine: For linear attenuation lookups.
    """

    def __init__(self, physics_engine) -> None:
        self._physics = physics_engine

    def compute(
        self,
        geometry: CollimatorGeometry,
        energy_keV: float,
        nx: int = 120,
        ny: int = 80,
        include_buildup: bool = False,
        include_air: bool = False,
        include_inverse_sq: bool = False,
        x_range_mm: tuple[float, float] | None = None,
        y_range_mm: tuple[float, float] | None = None,
        progress_callback: Callable[[int], None] | None = None,
    ) -> IsodoseResult:
        """Compute 2D dose map through the collimator field.

        For each Y-plane, traces rays to all X grid positions and computes:
          1. Beer-Lambert attenuation through stage materials
          2. Air attenuation along the full ray path (if include_air)
          3. Inverse-square geometric factor (if include_inverse_sq)

        Args:
            geometry: Collimator geometry [mm, degree].
            energy_keV: Photon energy [keV].
            nx: Number of X grid points.
            ny: Number of Y grid points.
            include_buildup: Apply build-up factor (not yet implemented).
            include_air: Apply air attenuation along ray path.
            include_inverse_sq: Apply 1/r^2 geometric divergence.
            x_range_mm: Optional (x_min, x_max) in mm. None = auto.
            y_range_mm: Optional (y_min, y_max) in mm. None = auto.
            progress_callback: Called with progress 0-100.

        Returns:
            IsodoseResult with 2D dose grid in mm coordinates.
        """
        t0 = time.perf_counter()

        # Source and detector positions in cm
        src_x_cm = mm_to_cm(geometry.source.position.x)
        src_y_cm = mm_to_cm(geometry.source.position.y)
        det_y_cm = mm_to_cm(geometry.detector.position.y)

        # Stage layouts in cm
        layouts = compute_stage_layout(geometry)

        # ── Grid ranges ──────────────────────────────────────────────
        if x_range_mm is not None:
            x_min_cm = mm_to_cm(x_range_mm[0])
            x_max_cm = mm_to_cm(x_range_mm[1])
        else:
            # Auto: 1.5x widest stage (or detector half-width)
            if layouts:
                max_hw_cm = max(sl.half_width for sl in layouts) * 1.5
            else:
                max_hw_cm = mm_to_cm(geometry.detector.width / 2.0)
            max_hw_cm = max(max_hw_cm, 1.0)
            x_min_cm = src_x_cm - max_hw_cm
            x_max_cm = src_x_cm + max_hw_cm

        if y_range_mm is not None:
            y_start_cm = mm_to_cm(y_range_mm[0])
            y_end_cm = mm_to_cm(y_range_mm[1])
        else:
            # Auto: source to detector
            y_start_cm = src_y_cm + 0.1  # just below source
            y_end_cm = det_y_cm

        x_grid_cm = np.linspace(x_min_cm, x_max_cm, nx)
        y_grid_cm = np.linspace(y_start_cm, y_end_cm, ny)

        # ── Pre-compute attenuation coefficients [cm^-1] ─────────────
        stage_mu: list[float] = []
        for stage in geometry.stages:
            mu = self._physics.linear_attenuation(stage.material_id, energy_keV)
            stage_mu.append(mu)

        # Air linear attenuation [cm^-1]
        mu_air = 0.0
        if include_air:
            mu_air = self._physics.linear_attenuation("Air", energy_keV)

        # Reference distance for inverse-square (source → first stage top)
        r_ref_sq = 1.0  # cm^2
        if include_inverse_sq and layouts:
            dy_ref = layouts[0].y_top - src_y_cm
            r_ref_sq = max(dy_ref ** 2, 0.01)  # avoid division by zero

        # Initialize dose map [ny, nx]
        dose_map = np.zeros((ny, nx), dtype=np.float64)

        # Y-sampling resolution within each stage
        samples_per_stage = 50

        for j, y_cm in enumerate(y_grid_cm):
            # Distance from source
            dy_cm = y_cm - src_y_cm
            if abs(dy_cm) < 1e-10:
                dose_map[j, :] = 1.0
                continue

            # Angles from source to each X grid position
            dx_cm = x_grid_cm - src_x_cm
            tan_angles = dx_cm / dy_cm

            # Accumulate material attenuation from source to this Y-plane
            cumulative_mu_x = np.zeros(nx, dtype=np.float64)
            # Track total material path length per ray for air calculation
            material_path_total = np.zeros(nx, dtype=np.float64)

            for si, stage in enumerate(geometry.stages):
                layout = layouts[si]
                mu = stage_mu[si]

                if mu < 1e-12:
                    continue

                # Stage Y extent
                stage_y_top = layout.y_top
                stage_y_bot = layout.y_bottom
                stage_h_cm = stage_y_bot - stage_y_top
                src_dist_cm = max(stage_y_top - src_y_cm, 0.0)

                # Skip stages entirely below this Y-plane
                if stage_y_top >= y_cm:
                    continue

                # Effective bottom for this Y-plane
                y_bot_eff = min(stage_y_bot, y_cm)
                h_eff = y_bot_eff - stage_y_top

                # Y-sample steps within the effective stage region
                n_samples = max(1, int(samples_per_stage * h_eff / stage_h_cm))
                dy_step = h_eff / n_samples
                cos_angles = 1.0 / np.sqrt(1.0 + tan_angles**2)
                path_per_step = dy_step / cos_angles

                for s in range(n_samples):
                    y_sample = stage_y_top + (s + 0.5) * dy_step
                    y_local = y_sample - stage_y_top

                    # Ray X at this Y-sample for all grid points
                    dy_from_src = y_sample - src_y_cm
                    x_at_sample = src_x_cm + tan_angles * dy_from_src

                    # X position relative to stage center
                    x_local = x_at_sample - layout.x_center

                    # Aperture half-width at this Y
                    ap_half = aperture_half_width_at_y(
                        stage.aperture, geometry.type,
                        y_local, stage_h_cm, src_dist_cm,
                    )

                    # Material mask: inside stage body AND outside aperture
                    abs_x = np.abs(x_local)
                    in_body = abs_x <= layout.half_width
                    in_aperture = abs_x <= ap_half
                    in_material = in_body & ~in_aperture

                    # Accumulate mu * path for material positions
                    cumulative_mu_x += np.where(
                        in_material, mu * path_per_step, 0.0,
                    )

                    # Track material path for air subtraction
                    if include_air:
                        material_path_total += np.where(
                            in_material, path_per_step, 0.0,
                        )

            # Total ray path length from source to this Y-plane [cm]
            cos_angles = 1.0 / np.sqrt(1.0 + tan_angles**2)
            total_ray_path = dy_cm / cos_angles  # slant distance

            # ── Air attenuation ──────────────────────────────────────
            if include_air and mu_air > 1e-15:
                air_path = total_ray_path - material_path_total
                air_path = np.maximum(air_path, 0.0)
                cumulative_mu_x += mu_air * air_path

            # Transmission = exp(-cumulative_mu_x)
            transmission = np.exp(-cumulative_mu_x)

            # ── Inverse-square law ───────────────────────────────────
            if include_inverse_sq:
                r_sq = dx_cm**2 + dy_cm**2
                r_sq = np.maximum(r_sq, 0.01)  # clamp
                inv_sq_factor = r_ref_sq / r_sq
                transmission *= inv_sq_factor

            dose_map[j, :] = transmission

            if progress_callback and (j + 1) % max(1, ny // 100) == 0:
                progress_callback(int((j + 1) / ny * 100))

        # Normalize to [0, 1]
        max_dose = np.max(dose_map)
        if max_dose > 0:
            dose_map /= max_dose

        # Convert grid to mm for UI
        x_positions_mm = cm_to_mm(x_grid_cm)
        y_positions_mm = cm_to_mm(y_grid_cm)

        elapsed = time.perf_counter() - t0

        return IsodoseResult(
            dose_map=dose_map,
            x_positions_mm=x_positions_mm,
            y_positions_mm=y_positions_mm,
            energy_keV=energy_keV,
            nx=nx,
            ny=ny,
            elapsed_seconds=elapsed,
            include_air=include_air,
            include_inverse_sq=include_inverse_sq,
        )
