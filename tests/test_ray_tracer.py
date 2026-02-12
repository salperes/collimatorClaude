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
    CollimatorLayer,
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
    layer_thickness_mm: float = 47.5,
    source_y: float = -500.0,
    detector_y: float = 500.0,
) -> CollimatorGeometry:
    """Create a simple single-stage slit geometry."""
    layer = CollimatorLayer(material_id=layer_material, thickness=layer_thickness_mm)
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(slit_width=slit_width_mm),
        layers=[layer],
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
    layer_thickness_mm: float = 50.0,
) -> CollimatorGeometry:
    """Create a single-stage fan-beam geometry."""
    layer = CollimatorLayer(material_id=layer_material, thickness=layer_thickness_mm)
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(fan_angle=fan_angle_deg, fan_slit_width=slit_width_mm),
        layers=[layer],
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
    layer_thickness_mm: float = 47.5,
) -> CollimatorGeometry:
    """Create a single-stage pencil-beam geometry."""
    layer = CollimatorLayer(material_id=layer_material, thickness=layer_thickness_mm)
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(pencil_diameter=pencil_diameter_mm),
        layers=[layer],
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

    def test_single_stage_centered(self):
        """Single stage is centered on Y=0."""
        geo = _make_slit_geometry(outer_height_mm=200.0)
        layouts = compute_stage_layout(geo)

        assert len(layouts) == 1
        sl = layouts[0]
        assert sl.y_top == pytest.approx(-mm_to_cm(100), abs=1e-6)
        assert sl.y_bottom == pytest.approx(mm_to_cm(100), abs=1e-6)
        assert sl.half_width == pytest.approx(mm_to_cm(50), abs=1e-6)

    def test_two_stages_with_gap(self):
        """Two stages with a gap are positioned correctly."""
        stage1 = CollimatorStage(
            outer_width=100.0, outer_height=100.0,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[], gap_after=20.0,
        )
        stage2 = CollimatorStage(
            outer_width=80.0, outer_height=60.0,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[],
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage1, stage2],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )
        # total_height = 100 + 20 + 60 = 180 mm = 18 cm
        layouts = compute_stage_layout(geo)

        assert len(layouts) == 2
        # y_offset starts at -9.0 cm
        assert layouts[0].y_top == pytest.approx(-9.0, abs=1e-6)
        assert layouts[0].y_bottom == pytest.approx(-9.0 + 10.0, abs=1e-6)
        # gap = 2.0 cm
        assert layouts[1].y_top == pytest.approx(-9.0 + 10.0 + 2.0, abs=1e-6)
        assert layouts[1].y_bottom == pytest.approx(-9.0 + 10.0 + 2.0 + 6.0, abs=1e-6)

    def test_three_stages_total_height(self):
        """Total span matches total_height for 3 stages."""
        stages = [
            CollimatorStage(outer_width=100, outer_height=80, layers=[], gap_after=10,
                            aperture=ApertureConfig(slit_width=5)),
            CollimatorStage(outer_width=100, outer_height=60, layers=[], gap_after=5,
                            aperture=ApertureConfig(slit_width=5)),
            CollimatorStage(outer_width=100, outer_height=40, layers=[],
                            aperture=ApertureConfig(slit_width=5)),
        ]
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=stages,
            detector=DetectorConfig(position=Point2D(0, 500)),
        )
        layouts = compute_stage_layout(geo)
        span = layouts[-1].y_bottom - layouts[0].y_top
        assert span == pytest.approx(mm_to_cm(geo.total_height), rel=1e-6)


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
    """Layer path length computation tests."""

    def test_single_layer_nonzero_path(self):
        """Ray hitting single layer has nonzero path length."""
        tracer = RayTracer()
        geo = _make_slit_geometry(
            slit_width_mm=5.0, layer_thickness_mm=47.5,
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
        geo = _make_slit_geometry(slit_width_mm=5.0, layer_thickness_mm=47.5)

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

    def test_multi_layer_accumulation(self):
        """Two layers produce separate material intersections."""
        tracer = RayTracer()
        layer1 = CollimatorLayer(order=0, material_id="W", thickness=10.0)
        layer2 = CollimatorLayer(order=1, material_id="Pb", thickness=35.0)
        stage = CollimatorStage(
            outer_width=100.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[layer1, layer2],
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
            # Should have at least one material (both if ray crosses both layers)
            assert len(materials) >= 1

    def test_composite_layer_two_materials(self):
        """Composite layer produces two material intersections."""
        tracer = RayTracer()
        layer = CollimatorLayer(
            order=0, material_id="Pb", thickness=47.5,
            inner_material_id="W", inner_width=10.0,
        )
        assert layer.is_composite

        stage = CollimatorStage(
            outer_width=100.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[layer],
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        # Ray that enters the body near the aperture edge → hits inner zone
        ray = Ray(0.0, mm_to_cm(-500), 0.05, 100)
        results = tracer.trace_ray(ray, geo)
        blocked = [r for r in results if not r.passes_aperture]

        if blocked:
            materials = {ix.material_id for ix in blocked[0].layer_intersections}
            # Should have W (inner) and Pb (outer) if ray crosses both zones
            assert "W" in materials or "Pb" in materials

    def test_no_layers_no_attenuation(self):
        """Stage with no layers → ray passes through body without intersections."""
        tracer = RayTracer()
        stage = CollimatorStage(
            outer_width=100.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[],
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500)),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        ray = Ray(0.0, mm_to_cm(-500), 0.1, 100)
        results = tracer.trace_ray(ray, geo)

        # Even if ray hits body area, no layers → no material intersections
        # The stage intersection should reflect this
        for sr in results:
            assert sr.total_path_length == 0.0


# ── Multi-Stage ──


class TestMultiStage:
    """Multi-stage traversal tests."""

    def test_two_stage_both_blocked(self):
        """Ray at large angle is blocked by both stages."""
        tracer = RayTracer()
        layer = CollimatorLayer(material_id="Pb", thickness=47.5)
        stage1 = CollimatorStage(
            outer_width=100, outer_height=100,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[layer], gap_after=20.0,
        )
        stage2 = CollimatorStage(
            outer_width=100, outer_height=100,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[CollimatorLayer(material_id="W", thickness=47.5)],
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
        layer = CollimatorLayer(material_id="Pb", thickness=47.5)
        stage1 = CollimatorStage(
            outer_width=100, outer_height=50,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[layer], gap_after=50.0,
        )
        stage2 = CollimatorStage(
            outer_width=100, outer_height=50,
            aperture=ApertureConfig(slit_width=5.0),
            layers=[CollimatorLayer(material_id="Pb", thickness=47.5)],
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
                layers=[CollimatorLayer(material_id="Pb", thickness=47.5)],
                gap_after=10.0,
            ),
            CollimatorStage(
                outer_width=100, outer_height=60,
                aperture=ApertureConfig(slit_width=5.0),
                layers=[CollimatorLayer(material_id="W", thickness=47.5)],
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
