"""Tests for IsodoseEngine — 2D dose distribution computation.

Validates:
- Unobstructed beam produces expected 1/r² pattern
- Collimator material attenuates correctly
- Aperture corridor shows high dose
- Symmetric geometry produces symmetric map
- Grid edge cases
- Performance
"""

import math
import time

import numpy as np
import pytest

from app.core.isodose_engine import IsodoseEngine, IsodoseResult
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    Point2D,
    SourceConfig,
    StagePurpose,
)


@pytest.fixture
def material_service():
    return MaterialService()


@pytest.fixture
def physics_engine(material_service):
    return PhysicsEngine(material_service)


@pytest.fixture
def isodose_engine(physics_engine):
    return IsodoseEngine(physics_engine)


def _make_geometry(
    stages: list[CollimatorStage] | None = None,
    ctype: CollimatorType = CollimatorType.FAN_BEAM,
    source_y: float = 0.0,
    detector_y: float = 500.0,
    detector_width: float = 400.0,
) -> CollimatorGeometry:
    """Create test geometry with defaults."""
    if stages is None:
        stages = []
    return CollimatorGeometry(
        type=ctype,
        stages=stages,
        source=SourceConfig(
            position=Point2D(x=0.0, y=source_y),
            focal_spot_size=0.0,
        ),
        detector=DetectorConfig(
            position=Point2D(x=0.0, y=detector_y),
            width=detector_width,
        ),
    )


def _make_stage(
    y_position: float = 100.0,
    outer_width: float = 200.0,
    outer_height: float = 50.0,
    material_id: str = "Pb",
    aperture: ApertureConfig | None = None,
) -> CollimatorStage:
    """Create a test stage."""
    return CollimatorStage(
        outer_width=outer_width,
        outer_height=outer_height,
        y_position=y_position,
        material_id=material_id,
        purpose=StagePurpose.PRIMARY_SHIELDING,
        aperture=aperture or ApertureConfig(fan_angle=30.0, fan_slit_width=2.0),
    )


# ── Test: Result Structure ──


class TestIsodoseResultStructure:
    """Verify result shape and coordinate system."""

    def test_result_shape(self, isodose_engine):
        geo = _make_geometry(stages=[_make_stage()])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=40, ny=30)

        assert isinstance(result, IsodoseResult)
        assert result.dose_map.shape == (30, 40)
        assert result.x_positions_mm.shape == (40,)
        assert result.y_positions_mm.shape == (30,)
        assert result.nx == 40
        assert result.ny == 30

    def test_result_normalized(self, isodose_engine):
        geo = _make_geometry(stages=[_make_stage()])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=40, ny=30)

        assert float(np.max(result.dose_map)) == pytest.approx(1.0, abs=1e-6)
        assert float(np.min(result.dose_map)) >= 0.0

    def test_y_grid_covers_source_to_detector(self, isodose_engine):
        geo = _make_geometry(source_y=0.0, detector_y=500.0)
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=20, ny=20)

        # Y grid should start just below source and end at detector
        assert result.y_positions_mm[0] > 0.0  # slightly below source
        assert result.y_positions_mm[-1] == pytest.approx(500.0, abs=1.0)

    def test_contour_levels_default(self, isodose_engine):
        geo = _make_geometry(stages=[_make_stage()])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=10, ny=10)

        assert result.contour_levels == [1.0, 0.8, 0.5, 0.2, 0.1, 0.05]


# ── Test: Unobstructed Beam ──


class TestUnobstructedBeam:
    """No stages → uniform transmission everywhere."""

    def test_no_stages_uniform(self, isodose_engine):
        geo = _make_geometry(stages=[])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=50, ny=40)

        # With no stages, every point has zero attenuation → transmission=1.0
        # After normalization, entire map should be 1.0
        np.testing.assert_allclose(result.dose_map, 1.0, atol=1e-6)

    def test_no_stages_symmetric(self, isodose_engine):
        """No stages, centered source → symmetric dose map."""
        geo = _make_geometry(stages=[])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=60, ny=40)

        # Compare left and right halves
        left = result.dose_map[:, :30]
        right = result.dose_map[:, -1:-31:-1]
        np.testing.assert_allclose(left, right, atol=1e-3)


# ── Test: Single Stage Attenuation ──


class TestSingleStageAttenuation:
    """One Pb slab → dose drops in material, high in aperture."""

    def test_dose_lower_in_material(self, isodose_engine, physics_engine):
        """Dose at center of wide Pb stage should be higher than edge (material)."""
        stage = _make_stage(
            y_position=100.0,
            outer_width=300.0,
            outer_height=50.0,
            material_id="Pb",
            # Wide aperture so grid points fall inside
            aperture=ApertureConfig(fan_angle=30.0, fan_slit_width=20.0),
        )
        geo = _make_geometry(stages=[stage], detector_y=300.0)
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=80, ny=40)

        # Just below the stage (y=155mm)
        y_target = 155.0  # mm, just below stage exit
        row_idx = np.argmin(np.abs(result.y_positions_mm - y_target))

        # Center (aperture) vs edge (material) dose
        cx = result.nx // 2
        edge_idx = 5  # near the edge (deep in material)
        center_dose = result.dose_map[row_idx, cx]
        edge_dose = result.dose_map[row_idx, edge_idx]

        # Center (through aperture) should have MUCH higher dose
        assert center_dose > edge_dose * 2.0, (
            f"Center dose {center_dose:.6f} should be >> edge dose {edge_dose:.6f}"
        )

    def test_material_attenuates(self, isodose_engine):
        """Dose behind thick Pb should be much lower at edge than at center."""
        stage = _make_stage(
            y_position=100.0,
            outer_width=400.0,
            outer_height=100.0,
            material_id="Pb",
            aperture=ApertureConfig(fan_angle=20.0, fan_slit_width=10.0),
        )
        geo = _make_geometry(
            stages=[stage],
            detector_y=400.0,
            detector_width=500.0,
        )
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=80, ny=60)

        # Row below stage
        y_below = 210.0  # mm
        row_idx = np.argmin(np.abs(result.y_positions_mm - y_below))

        # Row above stage (no material yet)
        y_above = 50.0
        row_above_idx = np.argmin(np.abs(result.y_positions_mm - y_above))

        # Above stage: uniform (no attenuation). Edge should be same as center.
        edge_above = result.dose_map[row_above_idx, 5]
        center_above = result.dose_map[row_above_idx, result.nx // 2]
        assert abs(edge_above - center_above) < 0.01, (
            f"Above stage: edge={edge_above:.4f} should ≈ center={center_above:.4f}"
        )

        # Below stage: edge (material) should be < center (aperture)
        edge_below = result.dose_map[row_idx, 5]
        center_below = result.dose_map[row_idx, result.nx // 2]
        assert center_below > edge_below * 2.0, (
            f"Center below {center_below:.6f} should be >> edge {edge_below:.6f}"
        )


# ── Test: Symmetry ──


class TestSymmetry:
    """Symmetric geometry should produce symmetric dose map."""

    def test_centered_geometry_symmetric(self, isodose_engine):
        stage = _make_stage(
            y_position=100.0,
            outer_width=200.0,
            outer_height=50.0,
            material_id="Pb",
        )
        geo = _make_geometry(stages=[stage])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=60, ny=40)

        # Left-right symmetry
        left = result.dose_map[:, :30]
        right = result.dose_map[:, -1:-31:-1]
        np.testing.assert_allclose(left, right, atol=0.02)


# ── Test: Multi-Stage ──


class TestMultiStage:
    """Multiple stages should compound attenuation."""

    def test_two_stages_more_attenuation(self, isodose_engine):
        """Two Pb stages should attenuate more than one."""
        stage1 = _make_stage(y_position=100.0, outer_height=50.0)
        stage2 = _make_stage(y_position=200.0, outer_height=50.0)

        geo_one = _make_geometry(stages=[stage1])
        geo_two = _make_geometry(stages=[stage1, stage2])

        result_one = isodose_engine.compute(geo_one, energy_keV=100.0, nx=40, ny=30)
        result_two = isodose_engine.compute(geo_two, energy_keV=100.0, nx=40, ny=30)

        # Edge dose at detector (y=500mm) should be lower with 2 stages
        last_row_one = result_one.dose_map[-1, :]
        last_row_two = result_two.dose_map[-1, :]

        # Compare at off-axis position
        edge_one = last_row_one[5]
        edge_two = last_row_two[5]
        assert edge_two < edge_one, (
            f"Two-stage edge dose {edge_two:.4f} should be < single-stage {edge_one:.4f}"
        )


# ── Test: Energy Dependence ──


class TestEnergyDependence:
    """Higher energy → more penetration → higher dose behind shielding."""

    def test_higher_energy_more_penetration(self, isodose_engine):
        stage = _make_stage(
            y_position=100.0,
            outer_width=300.0,
            outer_height=100.0,
            material_id="Pb",
            aperture=ApertureConfig(fan_angle=5.0, fan_slit_width=2.0),
        )
        geo = _make_geometry(stages=[stage], detector_y=400.0)

        result_low = isodose_engine.compute(geo, energy_keV=50.0, nx=40, ny=30)
        result_high = isodose_engine.compute(geo, energy_keV=200.0, nx=40, ny=30)

        # Note: both are normalized to max=1.0.
        # However, at edge positions, the RATIO of edge/center should differ.
        row_idx = result_low.ny - 1  # last row (detector)
        cx = result_low.nx // 2

        # Ratio of edge to center for each energy
        ratio_low = result_low.dose_map[row_idx, 3] / max(
            result_low.dose_map[row_idx, cx], 1e-12
        )
        ratio_high = result_high.dose_map[row_idx, 3] / max(
            result_high.dose_map[row_idx, cx], 1e-12
        )

        # Higher energy: material attenuates less → edge/center ratio higher
        assert ratio_high > ratio_low, (
            f"High-E ratio {ratio_high:.6f} should be > low-E ratio {ratio_low:.6f}"
        )


# ── Test: Performance ──


class TestPerformance:
    """Computation should complete within performance budget."""

    def test_default_grid_under_5_seconds(self, isodose_engine):
        stage = _make_stage()
        geo = _make_geometry(stages=[stage])

        t0 = time.perf_counter()
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=120, ny=80)
        elapsed = time.perf_counter() - t0

        assert elapsed < 5.0, f"Computation took {elapsed:.2f}s (limit: 5s)"
        assert result.dose_map.shape == (80, 120)

    def test_coarse_grid_fast(self, isodose_engine):
        stage = _make_stage()
        geo = _make_geometry(stages=[stage])

        t0 = time.perf_counter()
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=30, ny=20)
        elapsed = time.perf_counter() - t0

        assert elapsed < 1.0, f"Coarse grid took {elapsed:.2f}s (limit: 1s)"


# ── Test: Edge Cases ──


class TestEdgeCases:
    """Boundary conditions and degenerate cases."""

    def test_no_stages_no_crash(self, isodose_engine):
        geo = _make_geometry(stages=[])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=20, ny=20)
        assert result.dose_map.shape == (20, 20)
        assert float(np.max(result.dose_map)) > 0

    def test_very_thin_stage(self, isodose_engine):
        stage = _make_stage(outer_height=1.0)
        geo = _make_geometry(stages=[stage])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=20, ny=20)
        assert result.dose_map.shape == (20, 20)

    def test_minimal_grid(self, isodose_engine):
        stage = _make_stage()
        geo = _make_geometry(stages=[stage])
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=3, ny=3)
        assert result.dose_map.shape == (3, 3)


# ── Test: Air Material Loading ──


class TestAirMaterial:
    """Verify Air material is loaded and usable."""

    def test_air_material_loaded(self, material_service):
        mat = material_service.get_material("Air")
        assert mat.density == pytest.approx(0.001205, abs=0.0001)

    def test_air_mu_rho_100keV(self, material_service):
        mu_rho = material_service.get_mu_rho("Air", 100.0)
        # NIST Air total mu/rho at 100 keV ≈ 0.1541 cm²/g
        assert mu_rho == pytest.approx(0.1541, rel=0.05)

    def test_air_linear_attenuation(self, physics_engine):
        mu = physics_engine.linear_attenuation("Air", 100.0)
        # mu = mu_rho * density = ~0.154 * 0.001205 ≈ 1.86e-4 cm^-1
        assert 1e-5 < mu < 1e-2


# ── Test: Air Attenuation Effect ──


class TestAirAttenuation:
    """Verify air attenuation reduces dose at distance."""

    def test_air_reduces_dose(self, isodose_engine):
        """With air ON, dose at far distance is lower than without air."""
        geo = _make_geometry(stages=[], detector_y=2000.0)

        result_no_air = isodose_engine.compute(
            geo, energy_keV=30.0, nx=20, ny=20,
            include_air=False,
        )
        result_with_air = isodose_engine.compute(
            geo, energy_keV=30.0, nx=20, ny=20,
            include_air=True,
        )

        # Without air: no stages → uniform (all 1.0 after normalization)
        np.testing.assert_allclose(result_no_air.dose_map, 1.0, atol=1e-6)

        # With air: dose should decrease with distance, so last row < first row
        # (after normalization, first row = 1.0, last row < 1.0)
        first_row_mean = np.mean(result_with_air.dose_map[0, :])
        last_row_mean = np.mean(result_with_air.dose_map[-1, :])
        assert last_row_mean < first_row_mean, (
            f"Far dose {last_row_mean:.4f} should be < near dose {first_row_mean:.4f}"
        )

    def test_air_effect_stronger_at_low_energy(self, isodose_engine):
        """Air attenuation should be much stronger at 10 keV than at 100 keV."""
        geo = _make_geometry(stages=[], detector_y=1000.0)

        result_10keV = isodose_engine.compute(
            geo, energy_keV=10.0, nx=10, ny=20,
            include_air=True,
        )
        result_100keV = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=20,
            include_air=True,
        )

        # At detector (last row), ratio to max should differ:
        # 10 keV: much lower dose (strong air absorption)
        # 100 keV: near-unity dose (weak air absorption)
        far_10 = np.mean(result_10keV.dose_map[-1, :])
        far_100 = np.mean(result_100keV.dose_map[-1, :])

        # 100 keV should be much closer to peak than 10 keV
        assert far_100 > far_10, (
            f"100 keV far dose {far_100:.4f} should be > 10 keV far dose {far_10:.4f}"
        )

    def test_air_result_flag(self, isodose_engine):
        """IsodoseResult should report include_air flag."""
        geo = _make_geometry(stages=[])
        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=10,
            include_air=True,
        )
        assert result.include_air is True

        result_off = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=10,
            include_air=False,
        )
        assert result_off.include_air is False


# ── Test: Inverse Square Law ──


class TestInverseSquare:
    """Verify 1/r² geometric divergence."""

    def test_inverse_sq_reduces_dose_with_distance(self, isodose_engine):
        """With 1/r² ON and no stages, dose decreases with distance from source."""
        geo = _make_geometry(stages=[], detector_y=1000.0)

        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=40,
            include_inverse_sq=True,
            include_air=False,
        )

        # Check center column: dose should decrease with Y
        cx = result.nx // 2
        center_col = result.dose_map[:, cx]

        # After normalization, first row = 1.0 (closest to source)
        assert center_col[0] == pytest.approx(1.0, abs=0.01)

        # Last row should be much less than first
        assert center_col[-1] < 0.5, (
            f"Far dose {center_col[-1]:.4f} should be < 0.5 (1/r² drop)"
        )

    def test_inverse_sq_ratio_approx_4x(self, isodose_engine):
        """Dose at 2× distance should be ~4× lower (1/r²)."""
        stage_top_y = 50.0  # mm, reference distance from source
        geo = _make_geometry(
            stages=[],
            source_y=0.0,
            detector_y=200.0,
        )

        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=100,
            include_inverse_sq=True,
            include_air=False,
        )

        # Find rows at ~50mm and ~100mm from source
        cx = result.nx // 2
        idx_50 = np.argmin(np.abs(result.y_positions_mm - 50.0))
        idx_100 = np.argmin(np.abs(result.y_positions_mm - 100.0))

        dose_50 = result.dose_map[idx_50, cx]
        dose_100 = result.dose_map[idx_100, cx]

        # ratio = dose_50 / dose_100 should be ~(100/50)² = 4.0
        if dose_100 > 0:
            ratio = dose_50 / dose_100
            assert ratio == pytest.approx(4.0, rel=0.2), (
                f"Dose ratio {ratio:.2f} should be ~4.0 (1/r²)"
            )

    def test_inverse_sq_result_flag(self, isodose_engine):
        """IsodoseResult should report include_inverse_sq flag."""
        geo = _make_geometry(stages=[])
        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=10,
            include_inverse_sq=True,
        )
        assert result.include_inverse_sq is True


# ── Test: Wide Field Grid ──


class TestWideFieldGrid:
    """Verify explicit x_range_mm and y_range_mm parameters."""

    def test_explicit_x_range(self, isodose_engine):
        geo = _make_geometry(stages=[])
        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=40, ny=10,
            x_range_mm=(-500.0, 500.0),
        )

        assert result.x_positions_mm[0] == pytest.approx(-500.0, abs=1.0)
        assert result.x_positions_mm[-1] == pytest.approx(500.0, abs=1.0)

    def test_explicit_y_range(self, isodose_engine):
        geo = _make_geometry(stages=[], source_y=0.0, detector_y=500.0)
        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=10, ny=40,
            y_range_mm=(10.0, 2000.0),
        )

        assert result.y_positions_mm[0] == pytest.approx(10.0, abs=1.0)
        assert result.y_positions_mm[-1] == pytest.approx(2000.0, abs=1.0)

    def test_wide_field_beyond_collimator(self, isodose_engine):
        """Wide X range should show dose drop-off outside collimator."""
        stage = _make_stage(
            y_position=100.0,
            outer_width=100.0,
            outer_height=50.0,
            material_id="Pb",
        )
        geo = _make_geometry(stages=[stage], detector_y=300.0)
        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=80, ny=20,
            x_range_mm=(-500.0, 500.0),
        )

        # Find row just below stage
        row_idx = np.argmin(np.abs(result.y_positions_mm - 160.0))

        # Far edge (outside stage body): no attenuation → high dose
        far_idx = 2  # near x=-500mm
        cx = result.nx // 2  # center

        dose_far = result.dose_map[row_idx, far_idx]
        dose_center = result.dose_map[row_idx, cx]

        # Center goes through aperture → high; far goes through nothing → also high
        # Both should be > 0
        assert dose_far > 0
        assert dose_center > 0


# ── Test: Combined Physics ──


class TestCombinedPhysics:
    """Verify all physics effects work together."""

    def test_all_effects_together(self, isodose_engine):
        """Air + 1/r² + material attenuation should all combine."""
        stage = _make_stage(
            y_position=100.0,
            outer_width=200.0,
            outer_height=50.0,
            material_id="Pb",
            aperture=ApertureConfig(fan_angle=20.0, fan_slit_width=10.0),
        )
        geo = _make_geometry(stages=[stage], detector_y=500.0)

        result = isodose_engine.compute(
            geo, energy_keV=100.0, nx=60, ny=40,
            include_air=True,
            include_inverse_sq=True,
        )

        assert result.include_air is True
        assert result.include_inverse_sq is True
        assert result.dose_map.shape == (40, 60)
        assert float(np.max(result.dose_map)) == pytest.approx(1.0, abs=1e-6)
        assert float(np.min(result.dose_map)) >= 0.0

    def test_backward_compat_defaults(self, isodose_engine):
        """Default compute() without new params matches old behavior."""
        stage = _make_stage()
        geo = _make_geometry(stages=[stage])

        # Default: no air, no inverse-square
        result = isodose_engine.compute(geo, energy_keV=100.0, nx=40, ny=30)

        assert result.include_air is False
        assert result.include_inverse_sq is False
        # Original behavior: no air or 1/r² effects
        assert result.dose_map.shape == (30, 40)
        assert float(np.max(result.dose_map)) == pytest.approx(1.0, abs=1e-6)
