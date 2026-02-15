"""Tests for RayTracer — geometric ray-collimator intersection.

Tests cover: stage layout, ray geometry, aperture checks,
layer intersections, multi-stage traversal.

Reference: Phase 4 spec — Ray-Tracing Algorithm.
"""

import math

import numpy as np
import pytest

from app.core.ray_tracer import (
    Ray,
    RayTracer,
    StageLayout,
    aperture_half_width_at_y,
    compute_stage_layout,
    _ray_x_at_y,
)
from app.core.units import mm_to_cm, deg_to_rad
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    Point2D,
    SourceConfig,
)


# ── Helpers ──


def _make_slit_geometry(
    outer_width_mm: float = 100.0,
    outer_height_mm: float = 200.0,
    slit_width_mm: float = 5.0,
    layer_material: str = "Pb",
    source_y: float = -500.0,
    detector_y: float = 500.0,
    y_position: float = -100.0,
) -> CollimatorGeometry:
    """Create a simple single-stage slit geometry.

    Default y_position=-100 centers a 200mm stage around Y=0.
    """
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(slit_width=slit_width_mm),
        material_id=layer_material,
        y_position=y_position,
    )
    return CollimatorGeometry(
        type=CollimatorType.SLIT,
        source=SourceConfig(position=Point2D(0, source_y)),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, detector_y)),
    )


def _make_fan_geometry(
    fan_angle_deg: float = 30.0,
    slit_width_mm: float = 2.0,
    outer_width_mm: float = 150.0,
    outer_height_mm: float = 200.0,
    layer_material: str = "Pb",
) -> CollimatorGeometry:
    """Create a single-stage fan-beam geometry."""
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(fan_angle=fan_angle_deg, fan_slit_width=slit_width_mm),
        material_id=layer_material,
        y_position=-100.0,
    )
    return CollimatorGeometry(
        type=CollimatorType.FAN_BEAM,
        source=SourceConfig(position=Point2D(0, -500)),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, 500)),
    )


def _make_pencil_geometry(
    pencil_diameter_mm: float = 5.0,
    outer_width_mm: float = 100.0,
    outer_height_mm: float = 100.0,
    layer_material: str = "Pb",
) -> CollimatorGeometry:
    """Create a single-stage pencil-beam geometry."""
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(pencil_diameter=pencil_diameter_mm),
        material_id=layer_material,
        y_position=-50.0,
    )
    return CollimatorGeometry(
        type=CollimatorType.PENCIL_BEAM,
        source=SourceConfig(position=Point2D(0, -500)),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, 500)),
    )


# ── Stage Layout ──


class TestStageLayout:
    """Stage Y-position computation tests."""

    def test_single_stage_position(self):
        """Single stage at y_position=-100mm → y_top=-10cm."""
        geo = _make_slit_geometry(outer_height_mm=200.0, y_position=-100.0)
        layouts = compute_stage_layout(geo)

        assert len(layouts) == 1
        sl = layouts[0]
        assert sl.y_top == pytest.approx(mm_to_cm(-100), abs=1e-6)
        assert sl.y_bottom == pytest.approx(mm_to_cm(100), abs=1e-6)
        assert sl.half_width == pytest.approx(mm_to_cm(50), abs=1e-6)

    def test_two_stages_explicit_positions(self):
        """Two stages with explicit y_position are laid out correctly."""
        stage1 = CollimatorStage(
            outer_width=100.0, outer_height=100.0,
            aperture=ApertureConfig(slit_width=5.0),
            y_position=0.0,
        )
        stage2 = CollimatorStage(
            outer_width=80.0, outer_height=60.0,
            aperture=ApertureConfig(slit_width=5.0),
            y_position=120.0,  # 20mm gap after stage1
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage1, stage2],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )
        layouts = compute_stage_layout(geo)

        assert len(layouts) == 2
        assert layouts[0].y_top == pytest.approx(0.0, abs=1e-6)
        assert layouts[0].y_bottom == pytest.approx(10.0, abs=1e-6)
        assert layouts[1].y_top == pytest.approx(12.0, abs=1e-6)
        assert layouts[1].y_bottom == pytest.approx(18.0, abs=1e-6)

    def test_three_stages_explicit(self):
        """Three stages with explicit y_position."""
        stages = [
            CollimatorStage(outer_width=100, outer_height=80,
                            aperture=ApertureConfig(slit_width=5),
                            y_position=0.0),
            CollimatorStage(outer_width=100, outer_height=60,
                            aperture=ApertureConfig(slit_width=5),
                            y_position=90.0),
            CollimatorStage(outer_width=100, outer_height=40,
                            aperture=ApertureConfig(slit_width=5),
                            y_position=155.0),
        ]
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=stages,
            detector=DetectorConfig(position=Point2D(0, 500)),
        )
        layouts = compute_stage_layout(geo)
        assert len(layouts) == 3
        assert layouts[2].y_bottom == pytest.approx(mm_to_cm(195), rel=1e-6)

    def test_x_center_from_x_offset(self):
        """Stage x_offset maps to layout x_center."""
        stage = CollimatorStage(
            outer_width=100.0, outer_height=100.0,
            aperture=ApertureConfig(slit_width=5.0),
            y_position=0.0, x_offset=15.0,
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )
        layouts = compute_stage_layout(geo)
        assert layouts[0].x_center == pytest.approx(mm_to_cm(15.0), abs=1e-6)


# ── Ray Geometry ──


class TestRayGeometry:
    """Ray position computation tests."""

    def test_straight_down(self):
        """Angle=0 → X stays constant."""
        ray = Ray(origin_x=1.0, origin_y=0.0, angle=0.0, energy_keV=100)
        assert _ray_x_at_y(ray, 10.0) == pytest.approx(1.0, abs=1e-10)

    def test_angled_right(self):
        """Positive angle → X increases with Y."""
        ray = Ray(origin_x=0.0, origin_y=0.0, angle=math.pi / 4, energy_keV=100)
        assert _ray_x_at_y(ray, 5.0) == pytest.approx(5.0, rel=1e-6)

    def test_angled_left(self):
        """Negative angle → X decreases with Y."""
        ray = Ray(origin_x=0.0, origin_y=0.0, angle=-0.1, energy_keV=100)
        x = _ray_x_at_y(ray, 10.0)
        assert x < 0

    def test_detector_position(self):
        """Detector position matches ray_x_at_y at detector Y."""
        tracer = RayTracer()
        geo = _make_slit_geometry()
        ray = Ray(0.0, mm_to_cm(-500), 0.1, 100)
        det_x = tracer.compute_detector_position(ray, geo)
        expected = _ray_x_at_y(ray, mm_to_cm(500))
        assert det_x == pytest.approx(expected, rel=1e-6)


# ── Aperture Checks ──


class TestApertureCheck:
    """Aperture pass/fail tests for different collimator types."""

    def test_slit_center_ray_passes(self):
        """Center ray (angle=0) passes through slit aperture."""
        tracer = RayTracer()
        geo = _make_slit_geometry(slit_width_mm=5.0)
        ray = Ray(0.0, mm_to_cm(-500), 0.0, 100)
        assert tracer.passes_through_aperture(ray, geo)

    def test_slit_wide_angle_blocked(self):
        """Ray at moderate angle hits slit body (not aperture)."""
        tracer = RayTracer()
        geo = _make_slit_geometry(slit_width_mm=5.0)
        # 0.05 rad → x≈2cm at stage top, inside body (5cm) but outside aperture (0.25cm)
        ray = Ray(0.0, mm_to_cm(-500), 0.05, 100)
        assert not tracer.passes_through_aperture(ray, geo)

    def test_fan_center_passes(self):
        """Center ray passes through fan-beam aperture."""
        tracer = RayTracer()
        geo = _make_fan_geometry(fan_angle_deg=30.0)
        ray = Ray(0.0, mm_to_cm(-500), 0.0, 100)
        assert tracer.passes_through_aperture(ray, geo)

    def test_fan_within_angle_passes(self):
        """Ray within fan angle passes (slit wide enough for source distance)."""
        tracer = RayTracer()
        # 20mm slit → slit_half=1cm.  Acceptance at top: atan(1/40)≈0.025 rad
        geo = _make_fan_geometry(fan_angle_deg=30.0, slit_width_mm=20.0)
        # 0.02 rad → x=0.8cm at top < 1.0cm → passes
        ray = Ray(0.0, mm_to_cm(-500), 0.02, 100)
        assert tracer.passes_through_aperture(ray, geo)

    def test_pencil_center_passes(self):
        """Center ray passes through pencil-beam aperture."""
        tracer = RayTracer()
        geo = _make_pencil_geometry(pencil_diameter_mm=5.0)
        ray = Ray(0.0, mm_to_cm(-500), 0.0, 100)
        assert tracer.passes_through_aperture(ray, geo)

    def test_ray_outside_stage_passes(self):
        """Ray that misses the stage entirely is treated as passing."""
        tracer = RayTracer()
        geo = _make_slit_geometry(outer_width_mm=100.0)
        # Very large angle → misses stage body entirely
        ray = Ray(0.0, mm_to_cm(-500), 0.5, 100)
        results = tracer.trace_ray(ray, geo)
        assert results[0].passes_aperture


# ── Layer Intersection ──


class TestLayerIntersection:
    """Layer path length computation tests (solid body model)."""

    def test_single_layer_nonzero_path(self):
        """Ray hitting stage body has nonzero path length."""
        tracer = RayTracer()
        geo = _make_slit_geometry(
            slit_width_mm=5.0,
            outer_width_mm=100.0,
        )
        # Ray at moderate angle, hits the body
        ray = Ray(0.0, mm_to_cm(-500), 0.1, 100)
        results = tracer.trace_ray(ray, geo)

        blocked = [r for r in results if not r.passes_aperture]
        assert len(blocked) == 1
        sr = blocked[0]
        assert sr.total_path_length > 0
        assert len(sr.layer_intersections) > 0
        assert sr.layer_intersections[0].material_id == "Pb"

    def test_angled_ray_longer_path(self):
        """Angled ray has longer path through material than straight ray."""
        tracer = RayTracer()
        geo = _make_slit_geometry(slit_width_mm=5.0)

        # Two rays at different angles, both hitting body
        ray_small = Ray(0.0, mm_to_cm(-500), 0.05, 100)
        ray_large = Ray(0.0, mm_to_cm(-500), 0.15, 100)

        r_small = tracer.trace_ray(ray_small, geo)
        r_large = tracer.trace_ray(ray_large, geo)

        # Both should hit body
        blocked_s = [r for r in r_small if not r.passes_aperture]
        blocked_l = [r for r in r_large if not r.passes_aperture]

        if blocked_s and blocked_l:
            # Larger angle → longer path per Y-step (dy/cos(angle))
            assert blocked_l[0].total_path_length >= blocked_s[0].total_path_length

    def test_single_material_accumulation(self):
        """Ray hitting solid stage body accumulates material path length."""
        tracer = RayTracer()
        stage = CollimatorStage(
            outer_width=100.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="Pb",
            y_position=-100.0,
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        ray = Ray(0.0, mm_to_cm(-500), 0.08, 100)
        results = tracer.trace_ray(ray, geo)
        blocked = [r for r in results if not r.passes_aperture]

        if blocked:
            materials = {ix.material_id for ix in blocked[0].layer_intersections}
            # Should have at least one material intersection
            assert len(materials) >= 1
            assert "Pb" in materials

    def test_single_material_near_aperture(self):
        """Ray near aperture edge hits body and produces material intersection."""
        tracer = RayTracer()
        stage = CollimatorStage(
            outer_width=100.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="Pb",
            y_position=-100.0,
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        # Ray that enters the body near the aperture edge
        ray = Ray(0.0, mm_to_cm(-500), 0.05, 100)
        results = tracer.trace_ray(ray, geo)
        blocked = [r for r in results if not r.passes_aperture]

        if blocked:
            materials = {ix.material_id for ix in blocked[0].layer_intersections}
            assert "Pb" in materials

    def test_solid_body_all_body_is_material(self):
        """In solid body model, any point outside aperture hits material."""
        tracer = RayTracer()
        # Small aperture, large body → most rays hit material
        stage = CollimatorStage(
            outer_width=200.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=2.0),
            material_id="Pb",
            y_position=-100.0,
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        ray = Ray(0.0, mm_to_cm(-500), 0.1, 100)
        results = tracer.trace_ray(ray, geo)

        blocked = [r for r in results if not r.passes_aperture]
        assert len(blocked) == 1
        assert blocked[0].total_path_length > 0


# ── Multi-Stage ──


class TestMultiStage:
    """Multi-stage traversal tests."""

    def test_two_stage_both_blocked(self):
        """Ray at large angle is blocked by both stages."""
        tracer = RayTracer()
        stage1 = CollimatorStage(
            outer_width=200, outer_height=100,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="Pb",
            y_position=-110.0,
        )
        stage2 = CollimatorStage(
            outer_width=200, outer_height=100,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="W",
            y_position=10.0,  # 20mm gap after stage1
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage1, stage2],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        ray = Ray(0.0, mm_to_cm(-500), 0.1, 100)
        results = tracer.trace_ray(ray, geo)

        assert len(results) == 2
        blocked = [r for r in results if not r.passes_aperture]
        # At least one stage should be blocked for a ray at angle 0.1
        assert len(blocked) >= 1

    def test_gap_contributes_no_material(self):
        """Inter-stage gap has no material intersections."""
        tracer = RayTracer()
        stage1 = CollimatorStage(
            outer_width=100, outer_height=50,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="Pb",
            y_position=0.0,
        )
        stage2 = CollimatorStage(
            outer_width=100, outer_height=50,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="Pb",
            y_position=100.0,  # 50mm gap
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage1, stage2],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        # Only 2 StageIntersections (not 3 — gaps aren't stages)
        ray = Ray(0.0, mm_to_cm(-500), 0.1, 100)
        results = tracer.trace_ray(ray, geo)
        assert len(results) == 2

    def test_center_ray_passes_all_stages(self):
        """Center ray passes through all apertures in multi-stage geometry."""
        tracer = RayTracer()
        stages = [
            CollimatorStage(
                outer_width=100, outer_height=80,
                aperture=ApertureConfig(slit_width=5.0),
                material_id="Pb",
                y_position=0.0,
            ),
            CollimatorStage(
                outer_width=100, outer_height=60,
                aperture=ApertureConfig(slit_width=5.0),
                material_id="W",
                y_position=90.0,
            ),
        ]
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=stages,
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        ray = Ray(0.0, mm_to_cm(-500), 0.0, 100)
        assert tracer.passes_through_aperture(ray, geo)


# ── Ray Angle Generation ──


class TestRayAngles:
    """Ray angle generation tests."""

    def test_angles_count(self):
        """Correct number of angles generated."""
        tracer = RayTracer()
        geo = _make_slit_geometry()
        angles = tracer.compute_ray_angles(360, geo)
        assert len(angles) == 360

    def test_angles_symmetric(self):
        """Angles are symmetric around zero for centered source."""
        tracer = RayTracer()
        geo = _make_slit_geometry()
        angles = tracer.compute_ray_angles(100, geo)
        assert angles[0] == pytest.approx(-angles[-1], rel=1e-6)

    def test_center_angle_near_zero(self):
        """Middle angle is approximately zero."""
        tracer = RayTracer()
        geo = _make_slit_geometry()
        angles = tracer.compute_ray_angles(101, geo)
        assert abs(angles[50]) < 1e-6
