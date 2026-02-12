"""Geometric ray-tracing engine for collimator analysis.

Traces rays from source through multi-stage collimator geometry,
computing per-layer material intersections for Beer-Lambert attenuation.

All internal computations in core units: cm, radian, keV.
Geometry model values (mm, degree) are converted at the boundary.

Reference: Phase 4 spec — Ray-Tracing Algorithm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.core.units import mm_to_cm, deg_to_rad
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorType,
)

# Y-sampling resolution per stage for layer intersection
_SAMPLES_PER_STAGE = 100


# ── Data Structures ──


@dataclass
class Ray:
    """A single ray in 2D space.

    Attributes:
        origin_x: Origin X position [cm].
        origin_y: Origin Y position [cm].
        angle: Angle from vertical (+Y axis). 0 = straight down [radian].
        energy_keV: Photon energy [keV].
    """
    origin_x: float
    origin_y: float
    angle: float
    energy_keV: float


@dataclass
class LayerIntersection:
    """Ray-layer intersection with accumulated path length.

    Attributes:
        path_length: Total path through this material segment [cm].
        material_id: Material identifier.
        layer_index: Layer index in the stage (-1 if aggregated).
    """
    path_length: float
    material_id: str
    layer_index: int = -1


@dataclass
class StageIntersection:
    """Per-stage ray intersection results.

    Attributes:
        stage_index: Index in geometry.stages.
        passes_aperture: True if ray passes entirely through aperture.
        layer_intersections: Material segments the ray traverses.
        total_path_length: Sum of all intersection path lengths [cm].
    """
    stage_index: int
    passes_aperture: bool
    layer_intersections: list[LayerIntersection] = field(default_factory=list)
    total_path_length: float = 0.0


@dataclass
class StageLayout:
    """Computed Y position and dimensions of a stage in core units.

    Attributes:
        y_top: Top edge (entry) Y position [cm].
        y_bottom: Bottom edge (exit) Y position [cm].
        half_width: Half the outer width [cm].
    """
    y_top: float
    y_bottom: float
    half_width: float


# ── Geometry Helpers ──


def compute_stage_layout(geometry: CollimatorGeometry) -> list[StageLayout]:
    """Compute Y positions for each stage in core units [cm].

    Stages are centered vertically on Y=0. The layout replicates
    the algorithm used by CollimatorScene._layout_stages().

    Args:
        geometry: Collimator geometry (dimensions in mm).
    Returns:
        List of StageLayout, one per stage, in core units [cm].
    """
    total_h_cm = mm_to_cm(geometry.total_height)
    y_offset = -total_h_cm / 2.0

    layouts: list[StageLayout] = []
    for i, stage in enumerate(geometry.stages):
        h_cm = mm_to_cm(stage.outer_height)
        w_cm = mm_to_cm(stage.outer_width)

        layouts.append(StageLayout(
            y_top=y_offset,
            y_bottom=y_offset + h_cm,
            half_width=w_cm / 2.0,
        ))
        y_offset += h_cm

        if i < len(geometry.stages) - 1:
            y_offset += mm_to_cm(stage.gap_after)

    return layouts


def aperture_half_width_at_y(
    aperture: ApertureConfig,
    ctype: CollimatorType,
    y_local_cm: float,
    stage_height_cm: float,
) -> float:
    """Aperture half-width at a given Y position within a stage [cm].

    Args:
        aperture: Aperture configuration (values in mm/degree).
        ctype: Collimator type.
        y_local_cm: Local Y within stage [cm], 0 = top (entry).
        stage_height_cm: Total stage height [cm].
    Returns:
        Aperture half-width at this Y [cm]. 0 means aperture is closed
        at this Y position.
    """
    if ctype == CollimatorType.FAN_BEAM:
        half_angle_rad = deg_to_rad((aperture.fan_angle or 30.0) / 2.0)
        slit_half_cm = mm_to_cm((aperture.fan_slit_width or 2.0) / 2.0)
        return slit_half_cm + y_local_cm * math.tan(half_angle_rad)

    elif ctype == CollimatorType.SLIT:
        slit_half_cm = mm_to_cm((aperture.slit_width or 2.0) / 2.0)
        if aperture.taper_angle and aperture.taper_angle != 0.0:
            # slit_width = narrow end (exit/detector side, y=stage_height).
            # Aperture widens toward source: hw(y) = slit_half + (H-y)*tan(α)
            taper_rad = deg_to_rad(aperture.taper_angle)
            slit_half_cm += (stage_height_cm - y_local_cm) * math.tan(taper_rad)
        return slit_half_cm

    elif ctype == CollimatorType.PENCIL_BEAM:
        # Cylindrical hole → constant width in 2D cross-section
        radius_cm = mm_to_cm((aperture.pencil_diameter or 5.0) / 2.0)
        return radius_cm

    return 0.0


def _ray_x_at_y(ray: Ray, y: float) -> float:
    """X coordinate where ray reaches a given Y.

    Ray travels from origin at angle from vertical.
    angle=0 → straight down. Positive angle → rightward.

    Args:
        ray: The ray.
        y: Target Y coordinate [cm].
    Returns:
        X coordinate [cm].
    """
    dy = y - ray.origin_y
    return ray.origin_x + dy * math.tan(ray.angle)


# ── RayTracer ──


class RayTracer:
    """Geometric ray-tracing engine for collimator analysis.

    Traces rays through multi-stage collimator geometry using
    Y-sampling to compute material intersections.
    """

    def trace_ray(
        self,
        ray: Ray,
        geometry: CollimatorGeometry,
    ) -> list[StageIntersection]:
        """Trace a single ray through the multi-stage collimator.

        For each stage:
          1. Check if ray misses the stage body entirely → pass.
          2. Check if ray passes through the aperture → pass.
          3. Otherwise, sample Y positions through the stage
             and accumulate per-material path lengths.

        Args:
            ray: Ray in core units [cm, radian, keV].
            geometry: Collimator geometry [mm, degree].
        Returns:
            List of StageIntersection, one per stage.
        """
        layouts = compute_stage_layout(geometry)
        results: list[StageIntersection] = []

        for i, stage in enumerate(geometry.stages):
            layout = layouts[i]
            stage_h_cm = layout.y_bottom - layout.y_top

            # Ray X at stage entry and exit
            x_top = _ray_x_at_y(ray, layout.y_top)
            x_bot = _ray_x_at_y(ray, layout.y_bottom)

            # If ray misses stage body entirely → passes through air
            if abs(x_top) > layout.half_width and abs(x_bot) > layout.half_width:
                results.append(StageIntersection(
                    stage_index=i, passes_aperture=True,
                ))
                continue

            # Check aperture passage at entry and exit
            ap_half_top = aperture_half_width_at_y(
                stage.aperture, geometry.type, 0.0, stage_h_cm)
            ap_half_bot = aperture_half_width_at_y(
                stage.aperture, geometry.type, stage_h_cm, stage_h_cm)

            if abs(x_top) < ap_half_top and abs(x_bot) < ap_half_bot:
                # For fan-beam with linear taper, checking endpoints suffices
                # because both ray path and aperture boundary are linear in Y
                results.append(StageIntersection(
                    stage_index=i, passes_aperture=True,
                ))
                continue

            # Ray hits shielding → compute layer intersections via sampling
            intersections = self._compute_layer_intersections(
                ray, stage, layout, geometry.type,
            )
            total_path = sum(ix.path_length for ix in intersections)

            results.append(StageIntersection(
                stage_index=i,
                passes_aperture=False,
                layer_intersections=intersections,
                total_path_length=total_path,
            ))

        return results

    def passes_through_aperture(
        self,
        ray: Ray,
        geometry: CollimatorGeometry,
    ) -> bool:
        """Check if ray passes through all apertures without hitting material.

        Args:
            ray: Ray in core units [cm, radian, keV].
            geometry: Collimator geometry [mm, degree].
        Returns:
            True if ray passes through all stage apertures.
        """
        stage_results = self.trace_ray(ray, geometry)
        return all(sr.passes_aperture for sr in stage_results)

    def compute_ray_angles(
        self,
        num_rays: int,
        geometry: CollimatorGeometry,
    ) -> np.ndarray:
        """Compute ray angles spanning the collimator body.

        All generated rays are guaranteed to intersect at least one
        stage body.  The angle range uses the farthest body extent
        to ensure no ray misses the body entirely.

        Args:
            num_rays: Number of rays to generate.
            geometry: Collimator geometry [mm, degree].
        Returns:
            Array of angles [radian], shape (num_rays,).
        """
        src_x_cm = mm_to_cm(geometry.source.position.x)
        src_y_cm = mm_to_cm(geometry.source.position.y)

        layouts = compute_stage_layout(geometry)
        if not layouts:
            return np.zeros(num_rays)

        # Max half-width of any stage
        max_half_w = max(sl.half_width for sl in layouts)

        # Use the farthest body boundary (bottom of last stage) so that
        # rays at max_angle still intersect the body at the far end.
        dy_max = max(abs(sl.y_bottom - src_y_cm) for sl in layouts)
        if dy_max < 1e-10:
            dy_max = 1e-10

        max_angle = math.atan2(max_half_w - abs(src_x_cm), dy_max)

        return np.linspace(-max_angle, max_angle, num_rays)

    def compute_detector_position(
        self,
        ray: Ray,
        geometry: CollimatorGeometry,
    ) -> float:
        """Compute ray's X position at the detector plane [cm].

        Args:
            ray: Ray in core units [cm, radian, keV].
            geometry: Collimator geometry [mm, degree].
        Returns:
            Detector X position [cm].
        """
        det_y_cm = mm_to_cm(geometry.detector.position.y)
        return _ray_x_at_y(ray, det_y_cm)

    def _compute_layer_intersections(
        self,
        ray: Ray,
        stage,
        layout: StageLayout,
        ctype: CollimatorType,
    ) -> list[LayerIntersection]:
        """Compute per-material path lengths via Y-sampling.

        Samples _SAMPLES_PER_STAGE Y positions through the stage.
        At each Y, determines lateral distance from aperture edge,
        identifies which layer the ray is in, and accumulates path length.

        Args:
            ray: Ray in core units.
            stage: CollimatorStage (mm units).
            layout: Precomputed stage layout (cm units).
            ctype: Collimator type.
        Returns:
            List of LayerIntersection with per-material path lengths [cm].
        """
        stage_h_cm = layout.y_bottom - layout.y_top
        dy = stage_h_cm / _SAMPLES_PER_STAGE
        cos_angle = math.cos(ray.angle)
        path_per_step = dy / cos_angle if abs(cos_angle) > 1e-12 else dy

        # Build layer boundary table: sorted by order (inner → outer)
        # Each entry: (cumulative_start_cm, cumulative_end_cm, material_id, layer_idx)
        sorted_layers = sorted(stage.layers, key=lambda l: l.order)
        boundaries: list[tuple[float, float, str, int]] = []
        cumulative = 0.0
        for li, layer in enumerate(sorted_layers):
            t_cm = mm_to_cm(layer.thickness)
            if layer.is_composite:
                inner_w_cm = mm_to_cm(layer.inner_width)
                # Inner zone (aperture side)
                boundaries.append((
                    cumulative, cumulative + inner_w_cm,
                    layer.inner_material_id, li,
                ))
                # Outer zone
                boundaries.append((
                    cumulative + inner_w_cm, cumulative + t_cm,
                    layer.material_id, li,
                ))
            else:
                boundaries.append((
                    cumulative, cumulative + t_cm,
                    layer.material_id, li,
                ))
            cumulative += t_cm

        # Accumulate path per material
        material_paths: dict[str, float] = {}

        for step in range(_SAMPLES_PER_STAGE):
            y = layout.y_top + (step + 0.5) * dy
            x = _ray_x_at_y(ray, y)
            y_local = y - layout.y_top

            ap_half = aperture_half_width_at_y(
                stage.aperture, ctype, y_local, stage_h_cm,
            )

            dist_from_aperture = abs(x) - ap_half
            if dist_from_aperture <= 0:
                continue  # in aperture

            if abs(x) > layout.half_width:
                continue  # outside stage body

            # Find which layer/zone
            for inner_off, outer_off, mat_id, _ in boundaries:
                if inner_off <= dist_from_aperture < outer_off:
                    material_paths[mat_id] = (
                        material_paths.get(mat_id, 0.0) + path_per_step
                    )
                    break

        return [
            LayerIntersection(
                path_length=path,
                material_id=mat_id,
            )
            for mat_id, path in material_paths.items()
            if path > 0
        ]
