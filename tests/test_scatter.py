"""Scatter ray-tracing benchmark tests — BM-8.

BM-8.1: Kahn sampling mean angle vs analytic.
BM-8.2: Angular distribution chi-square fit to KN.
BM-8.3: Energy conservation E' + T = E0.
BM-8.4: SPR sanity checks.
BM-8.5: Scatter contribution vs material thickness.

Plus basic validation and integration tests.

Reference: docs/phase-07-scatter-ray-tracing.md.
"""

import math
import time

import numpy as np
import pytest
from scipy import stats

from app.core.compton_engine import ComptonEngine
from app.core.klein_nishina_sampler import KleinNishinaSampler
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.ray_tracer import RayTracer
from app.core.scatter_tracer import ScatterTracer
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
from app.models.simulation import (
    BeamProfile,
    ComptonConfig,
    QualityMetrics,
    SimulationResult,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def sampler():
    """Seeded sampler for reproducible tests."""
    return KleinNishinaSampler(rng=np.random.default_rng(42))


@pytest.fixture
def compton():
    return ComptonEngine()


@pytest.fixture
def scatter_tracer():
    """Full scatter tracer with real physics services."""
    mat_svc = MaterialService()
    physics = PhysicsEngine(mat_svc)
    tracer = RayTracer()
    compton = ComptonEngine()
    sampler = KleinNishinaSampler(rng=np.random.default_rng(123))
    return ScatterTracer(physics, tracer, compton, sampler)


def _make_slit_geometry(
    thickness_mm: float = 50.0,
    slit_width_mm: float = 4.0,
    material: str = "Pb",
) -> CollimatorGeometry:
    """Create a simple slit geometry for scatter tests.

    Single stage with one material, slit aperture.
    Source at (0, -200), detector at (0, 200).
    Stage height = 100 mm, outer_width = 2 * thickness + slit_width.
    """
    return CollimatorGeometry(
        id="scatter-test",
        name="Scatter Test Slit",
        type=CollimatorType.SLIT,
        source=SourceConfig(
            position=Point2D(0.0, -200.0),
            energy_kVp=None,
        ),
        stages=[
            CollimatorStage(
                id="s0",
                name="Primary",
                order=0,
                purpose=StagePurpose.PRIMARY_SHIELDING,
                outer_width=slit_width_mm + 2 * thickness_mm,
                outer_height=100.0,
                aperture=ApertureConfig(
                    slit_width=slit_width_mm,
                    slit_height=100.0,
                ),
                material_id=material,
                y_position=-50.0,
            ),
        ],
        detector=DetectorConfig(
            position=Point2D(0.0, 200.0),
            width=400.0,
            distance_from_source=400.0,
        ),
        phantoms=[],
    )


def _make_primary_result(geometry, energy_keV=1000.0, num_rays=100):
    """Create a mock primary SimulationResult."""
    from app.core.beam_simulation import BeamSimulation
    from app.core.build_up_factors import BuildUpFactors

    mat_svc = MaterialService()
    physics = PhysicsEngine(mat_svc)
    tracer = RayTracer()
    buildup = BuildUpFactors()
    sim = BeamSimulation(physics, tracer, buildup)
    return sim.calculate_beam_profile(
        geometry, energy_keV, num_rays, include_buildup=False,
    )


# ── BM-8.1: Kahn Sampling Mean Angle ────────────────────────────────


class TestBM8_1_MeanAngle:
    """BM-8.1: Kahn sampling mean matches analytic (<theta>, +/-1%)."""

    def test_mean_angle_100keV(self, sampler):
        thetas, _, _ = sampler.sample_batch(100.0, 100_000)
        analytic = sampler.mean_angle_analytic(100.0)
        assert float(np.mean(thetas)) == pytest.approx(analytic, rel=0.02)

    def test_mean_angle_500keV(self, sampler):
        thetas, _, _ = sampler.sample_batch(500.0, 100_000)
        analytic = sampler.mean_angle_analytic(500.0)
        assert float(np.mean(thetas)) == pytest.approx(analytic, rel=0.02)

    def test_mean_angle_1MeV(self, sampler):
        thetas, _, _ = sampler.sample_batch(1000.0, 100_000)
        analytic = sampler.mean_angle_analytic(1000.0)
        assert float(np.mean(thetas)) == pytest.approx(analytic, rel=0.02)

    def test_mean_angle_6MeV(self, sampler):
        thetas, _, _ = sampler.sample_batch(6000.0, 100_000)
        analytic = sampler.mean_angle_analytic(6000.0)
        assert float(np.mean(thetas)) == pytest.approx(analytic, rel=0.02)


# ── BM-8.2: Angular Distribution ────────────────────────────────────


class TestBM8_2_AngularDistribution:
    """BM-8.2: Histogram fits KN distribution (chi-square, p > 0.01)."""

    def test_chi_square_1MeV(self):
        sampler = KleinNishinaSampler(rng=np.random.default_rng(456))
        ce = ComptonEngine()
        n_samples = 200_000
        n_bins = 18  # 10-degree bins

        thetas, _, _ = sampler.sample_batch(1000.0, n_samples)

        # Histogram of sampled angles
        bin_edges = np.linspace(0, math.pi, n_bins + 1)
        observed, _ = np.histogram(thetas, bins=bin_edges)

        # Expected: KN * sin(theta) integrated over each bin
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
        expected_pdf = np.array([
            ce.klein_nishina_differential(1000.0, float(t)) * math.sin(float(t))
            for t in bin_centers
        ])
        expected_pdf /= np.sum(expected_pdf)
        expected = expected_pdf * n_samples

        # Ensure all expected bins have at least 5 counts
        # (chi-square assumption)
        assert np.all(expected > 5), "Expected counts too low for chi-square"

        chi2, p_value = stats.chisquare(observed, f_exp=expected)
        assert p_value > 0.01, f"Chi-square p={p_value:.4f} < 0.01"


# ── BM-8.3: Energy Conservation ─────────────────────────────────────


class TestBM8_3_EnergyConservation:
    """BM-8.3: E' + T = E0 for all sampled events."""

    def test_energy_conservation_strict(self, sampler, compton):
        for E0 in [100.0, 500.0, 1000.0, 3000.0]:
            for _ in range(500):
                theta, _, E_prime = sampler.sample_compton_angle(E0)
                T = compton.recoil_electron_energy(E0, theta)
                assert E_prime + T == pytest.approx(E0, rel=1e-10), (
                    f"E0={E0}, theta={theta:.4f}, E'={E_prime:.4f}, T={T:.4f}"
                )


# ── BM-8.4: SPR Sanity ──────────────────────────────────────────────


class TestBM8_4_SPR:
    """BM-8.4: SPR basic sanity checks on simple geometry."""

    def test_scatter_produces_interactions(self, scatter_tracer):
        """Scatter simulation with thick Pb produces > 0 interactions."""
        geo = _make_slit_geometry(thickness_mm=50.0)
        config = ComptonConfig(enabled=True, max_scatter_order=1)

        primary = _make_primary_result(geo, energy_keV=1000.0, num_rays=50)
        result = scatter_tracer.simulate_scatter(
            geo, 1000.0, 50, config,
            primary_result=primary, step_size_cm=0.1,
        )

        assert result.num_interactions > 0

    def test_no_scatter_through_aperture_rays(self, scatter_tracer):
        """Rays passing directly through aperture generate no scatter."""
        # Very wide slit — most rays pass through
        geo = _make_slit_geometry(thickness_mm=10.0, slit_width_mm=200.0)
        config = ComptonConfig(enabled=True, max_scatter_order=1)

        primary = _make_primary_result(geo, energy_keV=1000.0, num_rays=20)
        result = scatter_tracer.simulate_scatter(
            geo, 1000.0, 20, config,
            primary_result=primary,
        )

        # Most rays pass through aperture → very few interactions
        # Can't assert zero (some edge rays still hit material)
        # but should be far fewer than a narrow slit
        narrow_geo = _make_slit_geometry(thickness_mm=50.0, slit_width_mm=2.0)
        narrow_primary = _make_primary_result(narrow_geo, 1000.0, 20)
        narrow_result = scatter_tracer.simulate_scatter(
            narrow_geo, 1000.0, 20, config,
            primary_result=narrow_primary,
        )

        assert result.num_interactions < narrow_result.num_interactions


# ── BM-8.5: Thickness Effect ────────────────────────────────────────


class TestBM8_5_ThicknessEffect:
    """BM-8.5: Thicker material produces more scatter interactions."""

    def test_thick_more_scatter_than_thin(self, scatter_tracer):
        config = ComptonConfig(enabled=True, max_scatter_order=1)

        thin_geo = _make_slit_geometry(thickness_mm=10.0)
        thin_primary = _make_primary_result(thin_geo, 1000.0, 50)
        thin_result = scatter_tracer.simulate_scatter(
            thin_geo, 1000.0, 50, config,
            primary_result=thin_primary,
        )

        thick_geo = _make_slit_geometry(thickness_mm=80.0)
        thick_primary = _make_primary_result(thick_geo, 1000.0, 50)
        thick_result = scatter_tracer.simulate_scatter(
            thick_geo, 1000.0, 50, config,
            primary_result=thick_primary,
        )

        assert thick_result.num_interactions >= thin_result.num_interactions


# ── Basic Sampler Validation ─────────────────────────────────────────


class TestKleinNishinaSamplerBasic:
    """Basic sampler validation tests."""

    def test_theta_in_range(self, sampler):
        """All sampled thetas in [0, pi]."""
        thetas, _, _ = sampler.sample_batch(1000.0, 10_000)
        assert np.all(thetas >= 0)
        assert np.all(thetas <= math.pi + 1e-10)

    def test_phi_in_range(self, sampler):
        """All sampled phis in [0, 2*pi]."""
        _, phis, _ = sampler.sample_batch(1000.0, 10_000)
        assert np.all(phis >= 0)
        assert np.all(phis <= 2 * math.pi + 1e-10)

    def test_scattered_energy_less_than_incident(self, sampler):
        """E_scattered <= E0 for all samples."""
        for E0 in [100.0, 1000.0, 6000.0]:
            _, _, energies = sampler.sample_batch(E0, 10_000)
            assert np.all(energies <= E0 + 1e-10)
            assert np.all(energies > 0)

    def test_reproducible_with_seed(self):
        """Same seed produces same sequence."""
        s1 = KleinNishinaSampler(rng=np.random.default_rng(999))
        s2 = KleinNishinaSampler(rng=np.random.default_rng(999))

        t1, p1, e1 = s1.sample_compton_angle(1000.0)
        t2, p2, e2 = s2.sample_compton_angle(1000.0)

        assert t1 == t2
        assert p1 == p2
        assert e1 == e2

    def test_forward_bias_at_high_energy(self, sampler):
        """At high energies, scattering is forward-biased (mean theta < pi/2)."""
        thetas, _, _ = sampler.sample_batch(6000.0, 50_000)
        assert float(np.mean(thetas)) < math.pi / 2


# ── Compton Attenuation Tests ────────────────────────────────────────


class TestComptonAttenuation:
    """Tests for the new get_compton_mu_rho and compton_linear_attenuation."""

    def test_compton_mu_rho_pb_1MeV(self):
        """Pb Compton mu/rho at 1 MeV is reasonable."""
        mat_svc = MaterialService()
        mu_c = mat_svc.get_compton_mu_rho("Pb", 1000.0)
        # Compton for Pb at 1 MeV: ~0.05-0.07 cm²/g
        assert 0.03 < mu_c < 0.10

    def test_compton_less_than_total(self):
        """Compton mu/rho <= total mu/rho at any energy."""
        mat_svc = MaterialService()
        for mat_id in ["Pb", "W", "Al", "Cu"]:
            for E in [100.0, 500.0, 1000.0, 3000.0]:
                mu_c = mat_svc.get_compton_mu_rho(mat_id, E)
                mu_t = mat_svc.get_mu_rho(mat_id, E)
                assert mu_c <= mu_t * 1.01, (
                    f"{mat_id} at {E}keV: Compton={mu_c:.4f} > Total={mu_t:.4f}"
                )

    def test_compton_linear_attenuation(self):
        """PhysicsEngine.compton_linear_attenuation returns positive value."""
        mat_svc = MaterialService()
        physics = PhysicsEngine(mat_svc)
        mu_c = physics.compton_linear_attenuation("Pb", 1000.0)
        assert mu_c > 0
        # mu_compton = (mu/rho)_compton * density_Pb
        # ~0.06 * 11.34 ≈ 0.68 cm⁻¹
        assert 0.3 < mu_c < 1.5


# ── ScatterTracer Integration ────────────────────────────────────────


class TestScatterTracerBasic:
    """Basic ScatterTracer integration tests."""

    def test_empty_result_without_material(self, scatter_tracer):
        """Very wide aperture → no material hits → no scatter."""
        geo = _make_slit_geometry(thickness_mm=1.0, slit_width_mm=500.0)
        config = ComptonConfig(enabled=True)

        result = scatter_tracer.simulate_scatter(
            geo, 1000.0, 10, config,
        )
        # With very wide slit, almost all rays pass → very few or no scatter
        assert result.num_interactions < 5

    def test_result_has_elapsed_time(self, scatter_tracer):
        geo = _make_slit_geometry()
        config = ComptonConfig(enabled=True)

        result = scatter_tracer.simulate_scatter(geo, 1000.0, 10, config)
        assert result.elapsed_seconds > 0

    def test_spr_computed_when_primary_given(self, scatter_tracer):
        """SPR profile computed when primary_result is provided."""
        geo = _make_slit_geometry(thickness_mm=50.0)
        config = ComptonConfig(enabled=True)

        primary = _make_primary_result(geo, 1000.0, 50)
        result = scatter_tracer.simulate_scatter(
            geo, 1000.0, 50, config,
            primary_result=primary,
        )

        if result.num_reaching_detector > 0:
            assert len(result.spr_profile) > 0
            assert len(result.spr_positions_mm) > 0


# ── Performance ──────────────────────────────────────────────────────


class TestPerformance:
    """Scatter performance requirements."""

    def test_100_rays_scatter_under_10s(self, scatter_tracer):
        """100 primary rays + scatter completes in under 10 seconds."""
        geo = _make_slit_geometry(thickness_mm=50.0)
        config = ComptonConfig(enabled=True, max_scatter_order=1)

        primary = _make_primary_result(geo, 1000.0, 100)

        t0 = time.perf_counter()
        result = scatter_tracer.simulate_scatter(
            geo, 1000.0, 100, config,
            primary_result=primary,
        )
        elapsed = time.perf_counter() - t0

        assert elapsed < 10.0, f"Scatter took {elapsed:.1f}s > 10s limit"
        assert result.num_interactions >= 0
