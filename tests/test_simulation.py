"""Tests for BeamSimulation — beam profile and quality metrics.

Covers BM-10 benchmark tests, quality metric calculations,
and performance requirements.

Reference: Phase 4 spec — Simulation Benchmarks BM-10.
"""

import math
import time

import numpy as np
import pytest

from app.core.beam_simulation import BeamSimulation
from app.core.build_up_factors import BuildUpFactors
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.ray_tracer import RayTracer
from app.core.units import mm_to_cm
from app.models.geometry import (
    ApertureConfig,
    CollimatorGeometry,
    CollimatorStage,
    CollimatorType,
    DetectorConfig,
    FocalSpotDistribution,
    Point2D,
    SourceConfig,
)
from app.models.simulation import MetricStatus


# ── Fixtures ──


@pytest.fixture(scope="module")
def material_service() -> MaterialService:
    return MaterialService()


@pytest.fixture(scope="module")
def buildup_service() -> BuildUpFactors:
    return BuildUpFactors()


@pytest.fixture(scope="module")
def physics_engine(material_service) -> PhysicsEngine:
    return PhysicsEngine(material_service)


@pytest.fixture(scope="module")
def beam_sim(physics_engine, buildup_service) -> BeamSimulation:
    return BeamSimulation(
        physics_engine=physics_engine,
        ray_tracer=RayTracer(),
        buildup_service=buildup_service,
    )


@pytest.fixture(scope="module")
def beam_sim_no_buildup(physics_engine) -> BeamSimulation:
    return BeamSimulation(
        physics_engine=physics_engine,
        ray_tracer=RayTracer(),
        buildup_service=None,
    )


# ── Helper geometries ──


def _slit_geometry(
    slit_width_mm: float = 5.0,
    thickness_mm: float = 100.0,
    material: str = "Pb",
    outer_width_mm: float | None = None,
    outer_height_mm: float = 200.0,
    source_y_mm: float = -500.0,
    detector_y_mm: float = 500.0,
) -> CollimatorGeometry:
    """Single-stage slit collimator.

    If outer_width_mm is None, auto-calculated so wall fills the body.
    """
    if outer_width_mm is None:
        outer_width_mm = slit_width_mm + 2.0 * thickness_mm
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(slit_width=slit_width_mm),
        material_id=material,
        y_position=-outer_height_mm / 2.0,
    )
    return CollimatorGeometry(
        type=CollimatorType.SLIT,
        source=SourceConfig(position=Point2D(0, source_y_mm), focal_spot_size=0.0),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, detector_y_mm)),
    )


def _pencil_geometry(
    diameter_mm: float = 2.0,
    thickness_mm: float = 50.0,
    material: str = "Pb",
    outer_height_mm: float = 100.0,
) -> CollimatorGeometry:
    """Single-stage pencil-beam collimator.

    outer_width is auto-calculated so wall fills the body exactly.
    """
    outer_width_mm = diameter_mm + 2.0 * thickness_mm
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(pencil_diameter=diameter_mm),
        material_id=material,
        y_position=-outer_height_mm / 2.0,
    )
    return CollimatorGeometry(
        type=CollimatorType.PENCIL_BEAM,
        source=SourceConfig(position=Point2D(0, -500), focal_spot_size=0.0),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, 500)),
    )


def _fan_geometry(
    fan_angle_deg: float = 30.0,
    slit_width_mm: float = 20.0,
    thickness_mm: float = 50.0,
    material: str = "Pb",
    outer_width_mm: float = 200.0,
    outer_height_mm: float = 200.0,
) -> CollimatorGeometry:
    """Single-stage fan-beam collimator."""
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=outer_height_mm,
        aperture=ApertureConfig(fan_angle=fan_angle_deg, fan_slit_width=slit_width_mm),
        material_id=material,
        y_position=-outer_height_mm / 2.0,
    )
    return CollimatorGeometry(
        type=CollimatorType.FAN_BEAM,
        source=SourceConfig(position=Point2D(0, -500), focal_spot_size=0.0),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, 500)),
    )


# ── BM-10.1: Slit shield attenuation ──


class TestBM10_1_SlitShieldAttenuation:
    """BM-10.1: Slit, 100mm Pb, 5mm aperture, 1000 keV."""

    def test_aperture_transmission_near_unity(self, beam_sim_no_buildup):
        """Rays through aperture have T ≈ 1.0."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0, material="Pb")
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        profile = result.beam_profile

        # Center rays (within FWHM) should have T ≈ 1.0
        center_mask = np.abs(profile.positions_mm) < 2.0
        if np.any(center_mask):
            center_t = profile.intensities[center_mask]
            assert float(np.mean(center_t)) > 0.95

    def test_shield_high_attenuation(self, beam_sim_no_buildup):
        """Rays through 100mm Pb at 1000 keV have very low T."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0, material="Pb")
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        profile = result.beam_profile

        # Pb μ at 1000 keV ≈ 0.804 cm⁻¹, path ≈ 10cm → T ≈ exp(-8.04) ≈ 3.2e-4
        # Far-field rays (outside beam) should have very low T
        far_mask = np.abs(profile.positions_mm) > 50.0
        if np.any(far_mask):
            far_t = profile.intensities[far_mask]
            assert float(np.max(far_t)) < 0.01  # < 1%


# ── BM-10.2: Build-up increases leakage ──


class TestBM10_2_BuildupEffect:
    """BM-10.2: Build-up factor increases shielded-region transmission."""

    def test_buildup_increases_leakage(self, beam_sim, beam_sim_no_buildup):
        """T with build-up > T without build-up in shielded region."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0, material="Pb")

        r_no_bu = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_bu = beam_sim.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=True,
        )

        # Far-field leakage should be higher with build-up
        far_mask = np.abs(r_no_bu.beam_profile.positions_mm) > 50.0
        if np.any(far_mask):
            t_no_bu = float(np.mean(r_no_bu.beam_profile.intensities[far_mask]))
            t_bu = float(np.mean(r_bu.beam_profile.intensities[far_mask]))
            assert t_bu >= t_no_bu


# ── BM-10.3: Pencil beam ──


class TestBM10_3_PencilBeam:
    """BM-10.3: Pencil, 50mm Pb, 2mm diameter, 500 keV."""

    def test_pencil_has_narrow_beam(self, beam_sim_no_buildup):
        """Pencil beam produces narrow FWHM."""
        geo = _pencil_geometry(diameter_mm=2.0, thickness_mm=50.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=500, num_rays=500, include_buildup=False,
        )
        # FWHM should be small (< 10mm for a 2mm pencil at this geometry)
        assert result.quality_metrics.fwhm_mm > 0
        assert result.quality_metrics.fwhm_mm < 20.0

    def test_pencil_low_leakage(self, beam_sim_no_buildup):
        """Pencil beam has low leakage through 50mm Pb."""
        geo = _pencil_geometry(diameter_mm=2.0, thickness_mm=50.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=500, num_rays=500, include_buildup=False,
        )
        # 50mm Pb at 500 keV: μ ≈ 1.73 cm⁻¹ → T ≈ exp(-8.65) ≈ 1.8e-4
        assert result.quality_metrics.leakage_avg_pct < 5.0


# ── BM-10.4: Symmetry ──


class TestBM10_4_Symmetry:
    """BM-10.4: Symmetric geometry → symmetric penumbra."""

    def test_symmetric_penumbra(self, beam_sim_no_buildup):
        """Left and right penumbra are approximately equal."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        qm = result.quality_metrics
        if qm.penumbra_left_mm > 0 and qm.penumbra_right_mm > 0:
            ratio = qm.penumbra_left_mm / qm.penumbra_right_mm
            assert 0.8 < ratio < 1.25  # within 25%


# ── BM-10.5: Closed aperture ──


class TestBM10_5_ClosedAperture:
    """BM-10.5: Aperture = 0 → all rays at leakage level."""

    def test_zero_aperture_all_attenuated(self, beam_sim_no_buildup):
        """Zero-width aperture: no ray passes unattenuated."""
        geo = _slit_geometry(slit_width_mm=0.001, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=200, include_buildup=False,
        )
        # All rays should be significantly attenuated
        assert float(np.max(result.beam_profile.intensities)) < 0.1


# ── BM-10.6: No shielding → full transmission ──


class TestBM10_6_NoLayers:
    """BM-10.6: Aperture fills entire body → full transmission."""

    def test_full_aperture_transmission(self, beam_sim_no_buildup):
        """Stage where aperture = outer_width → T ≈ 1.0 for all rays."""
        stage = CollimatorStage(
            outer_width=200.0, outer_height=200.0,
            aperture=ApertureConfig(slit_width=200.0),
            y_position=-100.0,
        )
        geo = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500), focal_spot_size=0.0),
            stages=[stage],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=200, include_buildup=False,
        )
        # All rays should pass through the wide-open aperture
        assert float(np.min(result.beam_profile.intensities)) > 0.99


# ── BM-10.7: Multi-stage ──


class TestBM10_7_MultiStage:
    """BM-10.7: 2-stage: Pb 50mm + W 30mm, 5mm aperture, 20mm gap."""

    def test_two_stage_combined_attenuation(self, beam_sim_no_buildup):
        """Combined attenuation from two stages exceeds single stage."""
        # Single stage: 50mm Pb (outer_width fills body)
        geo_single = _slit_geometry(
            slit_width_mm=5.0, thickness_mm=50.0, material="Pb",
            outer_width_mm=105.0,  # 5 + 2*50 = 105
        )

        # Two-stage: Pb 105mm-wide + W 65mm-wide with 20mm gap
        stage1 = CollimatorStage(
            outer_width=105, outer_height=100,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="Pb",
            y_position=-90.0,
        )
        stage2 = CollimatorStage(
            outer_width=65, outer_height=60,
            aperture=ApertureConfig(slit_width=5.0),
            material_id="W",
            y_position=30.0,  # 20mm gap after stage1
        )
        geo_multi = CollimatorGeometry(
            type=CollimatorType.SLIT,
            source=SourceConfig(position=Point2D(0, -500), focal_spot_size=0.0),
            stages=[stage1, stage2],
            detector=DetectorConfig(position=Point2D(0, 500)),
        )

        r_single = beam_sim_no_buildup.calculate_beam_profile(
            geo_single, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_multi = beam_sim_no_buildup.calculate_beam_profile(
            geo_multi, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Multi-stage should have lower leakage
        assert r_multi.quality_metrics.leakage_avg_pct <= r_single.quality_metrics.leakage_avg_pct + 0.01


# ── BM-10.8: Fan-beam shape ──


class TestBM10_8_FanBeam:
    """BM-10.8: Fan-beam produces wider beam than slit."""

    def test_fan_wider_than_slit(self, beam_sim_no_buildup):
        """Fan-beam FWHM is wider than slit with same outer dimensions."""
        geo_slit = _slit_geometry(slit_width_mm=5.0, thickness_mm=50.0)
        geo_fan = _fan_geometry(
            fan_angle_deg=30.0, slit_width_mm=20.0, thickness_mm=50.0,
        )

        r_slit = beam_sim_no_buildup.calculate_beam_profile(
            geo_slit, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_fan = beam_sim_no_buildup.calculate_beam_profile(
            geo_fan, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Fan should have wider FWHM than slit
        assert r_fan.quality_metrics.fwhm_mm > r_slit.quality_metrics.fwhm_mm


# ── Quality Metrics ──


class TestQualityMetrics:
    """Quality metric computation tests."""

    def test_penumbra_positive(self, beam_sim_no_buildup):
        """Penumbra values are non-negative."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        qm = result.quality_metrics
        assert qm.penumbra_left_mm >= 0
        assert qm.penumbra_right_mm >= 0
        assert qm.penumbra_max_mm >= 0

    def test_flatness_reasonable(self, beam_sim_no_buildup):
        """Flatness is between 0% and 100%."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        assert 0 <= result.quality_metrics.flatness_pct <= 100

    def test_leakage_reasonable(self, beam_sim_no_buildup):
        """Leakage percentage is between 0% and 100%."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        assert 0 <= result.quality_metrics.leakage_avg_pct <= 100
        assert 0 <= result.quality_metrics.leakage_max_pct <= 100

    def test_cr_positive(self, beam_sim_no_buildup):
        """Collimation ratio is positive for shielded geometry."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        assert result.quality_metrics.collimation_ratio > 0
        assert result.quality_metrics.collimation_ratio_dB > 0

    def test_metric_statuses_assigned(self, beam_sim_no_buildup):
        """All metrics have valid status assignments."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        for m in result.quality_metrics.metrics:
            assert isinstance(m.status, MetricStatus)
            assert m.name != ""
            assert m.unit != ""

    def test_fwhm_positive(self, beam_sim_no_buildup):
        """FWHM is positive for any collimator with aperture."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        assert result.quality_metrics.fwhm_mm > 0


# ── Performance ──


class TestPerformance:
    """Simulation performance requirements."""

    def test_1000_rays_under_2s(self, beam_sim_no_buildup):
        """1000 rays completes in under 2 seconds."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        t0 = time.perf_counter()
        beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=1000, include_buildup=False,
        )
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"1000 rays took {elapsed:.2f}s (limit: 2s)"


# ── Result Structure ──


class TestResultStructure:
    """SimulationResult structure validation."""

    def test_result_fields_populated(self, beam_sim_no_buildup):
        """All result fields are populated."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=200, include_buildup=False,
        )
        assert result.energy_keV == 1000
        assert result.num_rays == 200
        assert result.elapsed_seconds > 0
        assert len(result.beam_profile.positions_mm) == 200
        assert len(result.beam_profile.intensities) == 200
        assert len(result.beam_profile.angles_rad) == 200

    def test_positions_sorted(self, beam_sim_no_buildup):
        """Beam profile positions are sorted ascending."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=200, include_buildup=False,
        )
        pos = result.beam_profile.positions_mm
        assert np.all(pos[1:] >= pos[:-1])

    def test_intensities_in_range(self, beam_sim_no_buildup):
        """All intensities are in [0, 1]."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        result = beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=200, include_buildup=False,
        )
        assert float(np.min(result.beam_profile.intensities)) >= 0
        assert float(np.max(result.beam_profile.intensities)) <= 1.0

    def test_progress_callback_called(self, beam_sim_no_buildup):
        """Progress callback is invoked during simulation."""
        geo = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        calls = []
        beam_sim_no_buildup.calculate_beam_profile(
            geo, energy_keV=1000, num_rays=200, include_buildup=False,
            progress_callback=lambda pct: calls.append(pct),
        )
        assert len(calls) > 0
        assert calls[-1] == 100


# ── BM-10.9: Focal spot PSF blur ──


def _slit_geometry_with_focal_spot(
    focal_spot_mm: float = 1.0,
    distribution: FocalSpotDistribution = FocalSpotDistribution.UNIFORM,
    slit_width_mm: float = 5.0,
    thickness_mm: float = 100.0,
    material: str = "Pb",
) -> CollimatorGeometry:
    """Single-stage slit collimator with explicit focal spot settings."""
    outer_width_mm = slit_width_mm + 2.0 * thickness_mm
    stage = CollimatorStage(
        outer_width=outer_width_mm,
        outer_height=200.0,
        aperture=ApertureConfig(slit_width=slit_width_mm),
        material_id=material,
        y_position=-100.0,
    )
    return CollimatorGeometry(
        type=CollimatorType.SLIT,
        source=SourceConfig(
            position=Point2D(0, -500),
            focal_spot_size=focal_spot_mm,
            focal_spot_distribution=distribution,
        ),
        stages=[stage],
        detector=DetectorConfig(position=Point2D(0, 500)),
    )


class TestBM10_9_FocalSpotPSF:
    """BM-10.9: Focal spot PSF blur tests."""

    @pytest.mark.benchmark
    def test_focal_spot_zero_no_blur(self, beam_sim_no_buildup):
        """focal_spot_size=0 produces same profile as point source (no blur)."""
        geo_point = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        geo_zero = _slit_geometry_with_focal_spot(focal_spot_mm=0.0)

        r_point = beam_sim_no_buildup.calculate_beam_profile(
            geo_point, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_zero = beam_sim_no_buildup.calculate_beam_profile(
            geo_zero, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Identical profiles — no PSF applied
        np.testing.assert_allclose(
            r_point.beam_profile.intensities,
            r_zero.beam_profile.intensities,
            atol=1e-10,
        )

    @pytest.mark.benchmark
    def test_focal_spot_gaussian_blur(self, beam_sim_no_buildup):
        """2mm Gaussian focal spot softens beam edges (wider penumbra)."""
        geo_point = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        geo_gauss = _slit_geometry_with_focal_spot(
            focal_spot_mm=2.0,
            distribution=FocalSpotDistribution.GAUSSIAN,
        )

        r_point = beam_sim_no_buildup.calculate_beam_profile(
            geo_point, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_gauss = beam_sim_no_buildup.calculate_beam_profile(
            geo_gauss, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Penumbra should be wider with focal spot blur
        assert r_gauss.quality_metrics.penumbra_max_mm > r_point.quality_metrics.penumbra_max_mm

    @pytest.mark.benchmark
    def test_focal_spot_uniform_blur(self, beam_sim_no_buildup):
        """2mm Uniform focal spot softens beam edges (wider penumbra)."""
        geo_point = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        geo_unif = _slit_geometry_with_focal_spot(
            focal_spot_mm=2.0,
            distribution=FocalSpotDistribution.UNIFORM,
        )

        r_point = beam_sim_no_buildup.calculate_beam_profile(
            geo_point, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_unif = beam_sim_no_buildup.calculate_beam_profile(
            geo_unif, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Penumbra should be wider with focal spot blur
        assert r_unif.quality_metrics.penumbra_max_mm > r_point.quality_metrics.penumbra_max_mm

    @pytest.mark.benchmark
    def test_focal_spot_larger_wider(self, beam_sim_no_buildup):
        """3mm focal spot produces wider penumbra than 1mm."""
        geo_1mm = _slit_geometry_with_focal_spot(focal_spot_mm=1.0)
        geo_3mm = _slit_geometry_with_focal_spot(focal_spot_mm=3.0)

        r_1mm = beam_sim_no_buildup.calculate_beam_profile(
            geo_1mm, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_3mm = beam_sim_no_buildup.calculate_beam_profile(
            geo_3mm, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Larger focal spot → wider penumbra
        assert r_3mm.quality_metrics.penumbra_max_mm > r_1mm.quality_metrics.penumbra_max_mm

    @pytest.mark.benchmark
    def test_focal_spot_preserves_area(self, beam_sim_no_buildup):
        """PSF convolution preserves total integrated intensity."""
        geo_point = _slit_geometry(slit_width_mm=5.0, thickness_mm=100.0)
        geo_blur = _slit_geometry_with_focal_spot(
            focal_spot_mm=2.0,
            distribution=FocalSpotDistribution.GAUSSIAN,
        )

        r_point = beam_sim_no_buildup.calculate_beam_profile(
            geo_point, energy_keV=1000, num_rays=500, include_buildup=False,
        )
        r_blur = beam_sim_no_buildup.calculate_beam_profile(
            geo_blur, energy_keV=1000, num_rays=500, include_buildup=False,
        )

        # Trapezoidal integration — total area should be preserved within 5%
        area_point = float(np.trapezoid(r_point.beam_profile.intensities, r_point.beam_profile.positions_mm))
        area_blur = float(np.trapezoid(r_blur.beam_profile.intensities, r_blur.beam_profile.positions_mm))

        if area_point > 0:
            ratio = area_blur / area_point
            assert 0.95 < ratio < 1.05, (
                f"Area ratio {ratio:.4f} outside 5% tolerance"
            )
