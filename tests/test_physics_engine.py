"""Physics engine benchmark tests.

BM-1: Pb attenuation (NIST XCOM)
BM-2: W attenuation
BM-3: SS304 attenuation
BM-4: Multi-layer attenuation

Reference: docs/phase-02-physics-engine.md §Benchmark Tests.
"""

import math

import pytest

from app.core.material_database import MaterialService
from app.core.build_up_factors import BuildUpFactors
from app.core.physics_engine import PhysicsEngine
from app.core.units import cm_to_mm
from app.models.geometry import CollimatorStage


@pytest.fixture(scope="module")
def svc() -> MaterialService:
    return MaterialService()


@pytest.fixture(scope="module")
def buildup() -> BuildUpFactors:
    return BuildUpFactors()


@pytest.fixture(scope="module")
def engine(svc: MaterialService, buildup: BuildUpFactors) -> PhysicsEngine:
    return PhysicsEngine(svc, buildup)


# -----------------------------------------------------------------------
# BM-1: Lead (Pb) attenuation — NIST XCOM reference
# -----------------------------------------------------------------------

class TestBM1_LeadAttenuation:
    """BM-1: Pb μ/ρ and HVL/TVL benchmarks."""

    # (energy_keV, expected_mu_rho, hvl_mm, tvl_mm, tolerance)
    # HVL/TVL values computed from JSON μ/ρ × density.
    # Pb density = 11.34 g/cm³

    def test_bm1_1_pb_88keV(self, engine: PhysicsEngine):
        """BM-1.1: Pb @ 88 keV (K-edge above)."""
        # Just above K-edge, μ/ρ jumps. JSON value at 88.005 keV above edge = 7.841
        r = engine.calculate_hvl_tvl("Pb", 88.005)
        mu = r.mu_per_cm
        # μ = 7.841 * 11.34 = 88.92 cm⁻¹ → HVL = 0.693/88.92 = 0.0078 cm = 0.078 mm
        assert mu == pytest.approx(7.841 * 11.34, rel=0.02)

    def test_bm1_2_pb_100keV(self, engine: PhysicsEngine):
        """BM-1.2: Pb @ 100 keV — μ/ρ = 5.549."""
        r = engine.calculate_hvl_tvl("Pb", 100.0)
        mu = r.mu_per_cm
        expected_mu = 5.549 * 11.34  # 62.93
        assert mu == pytest.approx(expected_mu, rel=0.01)
        # HVL = ln(2)/μ
        expected_hvl_cm = math.log(2) / expected_mu
        assert r.hvl_cm == pytest.approx(expected_hvl_cm, rel=0.02)

    def test_bm1_3_pb_200keV(self, engine: PhysicsEngine):
        """BM-1.3: Pb @ 200 keV — μ/ρ = 0.999."""
        r = engine.calculate_hvl_tvl("Pb", 200.0)
        expected_mu = 0.9985 * 11.34
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm1_4_pb_500keV(self, engine: PhysicsEngine):
        """BM-1.4: Pb @ 500 keV — μ/ρ = 0.1614."""
        r = engine.calculate_hvl_tvl("Pb", 500.0)
        expected_mu = 0.1614 * 11.34
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm1_5_pb_662keV(self, engine: PhysicsEngine):
        """BM-1.5: Pb @ 662 keV (Cs-137) — interpolated."""
        r = engine.calculate_hvl_tvl("Pb", 662.0)
        # Interpolation between 600 and 800 keV
        assert r.mu_per_cm > 0
        assert r.hvl_cm > 0

    def test_bm1_6_pb_1000keV(self, engine: PhysicsEngine):
        """BM-1.6: Pb @ 1000 keV — μ/ρ = 0.0708."""
        r = engine.calculate_hvl_tvl("Pb", 1000.0)
        expected_mu = 0.0708 * 11.34  # 0.803 cm⁻¹
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)
        # HVL ≈ 0.863 cm = 8.63 mm
        assert r.hvl_cm == pytest.approx(0.863, rel=0.02)

    def test_bm1_7_pb_1250keV(self, engine: PhysicsEngine):
        """BM-1.7: Pb @ 1250 keV (Co-60 avg)."""
        r = engine.calculate_hvl_tvl("Pb", 1250.0)
        expected_mu = 0.0578 * 11.34
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm1_8_pb_2000keV(self, engine: PhysicsEngine):
        """BM-1.8: Pb @ 2000 keV."""
        r = engine.calculate_hvl_tvl("Pb", 2000.0)
        expected_mu = 0.0426 * 11.34  # from JSON
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.02)

    def test_bm1_9_pb_6000keV(self, engine: PhysicsEngine):
        """BM-1.9: Pb @ 6000 keV."""
        r = engine.calculate_hvl_tvl("Pb", 6000.0)
        expected_mu = 0.0396 * 11.34  # from JSON
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.02)


# -----------------------------------------------------------------------
# BM-2: Tungsten (W) attenuation
# -----------------------------------------------------------------------

class TestBM2_TungstenAttenuation:
    """BM-2: W μ/ρ and HVL benchmarks (from NIST JSON data)."""

    def test_bm2_1_w_80keV(self, engine: PhysicsEngine):
        """BM-2.1: W @ 80 keV (just above K-edge 69.5) — μ/ρ = 4.027."""
        r = engine.calculate_hvl_tvl("W", 80.0)
        expected_mu = 4.027 * 19.30
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm2_2_w_100keV(self, engine: PhysicsEngine):
        """BM-2.2: W @ 100 keV — μ/ρ = 2.271."""
        r = engine.calculate_hvl_tvl("W", 100.0)
        expected_mu = 2.271 * 19.30
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm2_3_w_500keV(self, engine: PhysicsEngine):
        """BM-2.3: W @ 500 keV — μ/ρ = 0.1085."""
        r = engine.calculate_hvl_tvl("W", 500.0)
        expected_mu = 0.1085 * 19.30
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm2_4_w_1000keV(self, engine: PhysicsEngine):
        """BM-2.4: W @ 1000 keV — μ/ρ = 0.0596."""
        r = engine.calculate_hvl_tvl("W", 1000.0)
        expected_mu = 0.0596 * 19.30
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.01)

    def test_bm2_5_w_6000keV(self, engine: PhysicsEngine):
        """BM-2.5: W @ 6000 keV — μ/ρ = 0.0333."""
        r = engine.calculate_hvl_tvl("W", 6000.0)
        expected_mu = 0.0333 * 19.30
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.02)


# -----------------------------------------------------------------------
# BM-3: SS304 attenuation
# -----------------------------------------------------------------------

class TestBM3_SteelAttenuation:
    """BM-3: SS304 attenuation from pre-computed NIST JSON."""

    def test_bm3_4_ss304_at_500keV(self, engine: PhysicsEngine):
        """SS304 @ 500 keV — μ/ρ = 0.0616 from JSON."""
        r = engine.calculate_hvl_tvl("SS304", 500.0)
        expected_mu = 0.0616 * 8.00  # 0.4928 cm⁻¹
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.02)

    def test_bm3_5_ss304_at_1000keV(self, engine: PhysicsEngine):
        """SS304 @ 1000 keV — μ/ρ = 0.0365 from JSON."""
        r = engine.calculate_hvl_tvl("SS304", 1000.0)
        expected_mu = 0.0365 * 8.00  # 0.292 cm⁻¹
        assert r.mu_per_cm == pytest.approx(expected_mu, rel=0.02)


# -----------------------------------------------------------------------
# BM-4: Multi-layer attenuation
# -----------------------------------------------------------------------

class TestBM4_MultiLayerAttenuation:
    """BM-4: Multi-layer Beer-Lambert attenuation (slab-based)."""

    def test_bm4_1_10mm_pb_1000keV(self, engine: PhysicsEngine):
        """BM-4.1: 10mm Pb @ 1000 keV → T = exp(-μ×x)."""
        result = engine.calculate_slab_attenuation("Pb", 10.0, 1000.0)
        # μ = 0.0708 * 11.34 = 0.8029 cm⁻¹, x = 1.0 cm
        # T = exp(-0.8029) ≈ 0.448
        assert result.transmission == pytest.approx(0.448, rel=0.02)
        assert result.total_mfp == pytest.approx(0.803, rel=0.02)

    def test_bm4_2_5mm_pb_5mm_w_1000keV(self, engine: PhysicsEngine):
        """BM-4.2: 5mm Pb + 5mm W @ 1000 keV."""
        r_pb = engine.calculate_slab_attenuation("Pb", 5.0, 1000.0)
        r_w = engine.calculate_slab_attenuation("W", 5.0, 1000.0)
        combined_t = r_pb.transmission * r_w.transmission
        # Pb: μ=0.0708*11.34=0.8029, x=0.5cm → mfp=0.4015
        # W: μ=0.0596*19.30=1.1503, x=0.5cm → mfp=0.5751
        # total_mfp ≈ 0.977, T = exp(-0.977) ≈ 0.376
        assert combined_t == pytest.approx(
            math.exp(-0.4015 - 0.5751), rel=0.03
        )

    def test_bm4_3_20mm_w_500keV(self, engine: PhysicsEngine):
        """BM-4.3: 20mm W @ 500 keV → very high attenuation."""
        result = engine.calculate_slab_attenuation("W", 20.0, 500.0)
        # μ = 0.1085 * 19.30 = 2.094 cm⁻¹, x = 2.0 cm
        # T = exp(-4.188) ≈ 0.015
        assert result.transmission < 0.02
        assert result.total_mfp > 4.0

    def test_bm4_4_empty_slab(self, engine: PhysicsEngine):
        """BM-4.4: Zero thickness → T = 1.0 (no attenuation)."""
        result = engine.calculate_slab_attenuation("Pb", 0.0, 1000.0)
        assert result.transmission == 1.0

    def test_bm4_5_100mm_pb_100keV(self, engine: PhysicsEngine):
        """BM-4.5: 100mm Pb @ 100 keV → effectively zero transmission."""
        result = engine.calculate_slab_attenuation("Pb", 100.0, 100.0)
        # μ = 5.549 * 11.34 = 62.93 cm⁻¹, x = 10 cm
        # T = exp(-629.3) ≈ 0 (essentially zero)
        assert result.transmission < 1e-20

    def test_zero_thickness_ignored(self, engine: PhysicsEngine):
        """Slab with zero thickness should return T=1."""
        result = engine.calculate_slab_attenuation("Pb", 0.0, 1000.0)
        assert result.transmission == 1.0


# -----------------------------------------------------------------------
# Energy sweep and thickness sweep
# -----------------------------------------------------------------------

class TestSweeps:
    def test_energy_sweep_returns_correct_count(self, engine: PhysicsEngine):
        # outer_width=20 + slit_width=0 → effective_wall=10mm per side
        stages = [CollimatorStage(material_id="Pb", outer_width=20.0)]
        results = engine.energy_sweep(stages, 100, 1000, 10)
        assert len(results) == 10

    def test_energy_sweep_transmission_increases_with_energy(
        self, engine: PhysicsEngine
    ):
        """Higher energy → less attenuation → higher transmission (above K-edge)."""
        stages = [CollimatorStage(material_id="Pb", outer_width=20.0)]
        results = engine.energy_sweep(stages, 200, 2000, 5)
        transmissions = [r.transmission for r in results]
        # Generally increasing (above K-edge, μ decreases with energy)
        assert transmissions[-1] > transmissions[0]

    def test_thickness_sweep_returns_correct_count(self, engine: PhysicsEngine):
        results = engine.thickness_sweep("Pb", 1000.0, 100.0, 20)
        assert len(results) == 20

    def test_thickness_sweep_starts_at_full_transmission(
        self, engine: PhysicsEngine
    ):
        results = engine.thickness_sweep("Pb", 1000.0, 100.0, 20)
        assert results[0].transmission == pytest.approx(1.0, abs=1e-10)
        assert results[0].thickness_cm == pytest.approx(0.0)

    def test_thickness_sweep_transmission_decreases(self, engine: PhysicsEngine):
        results = engine.thickness_sweep("Pb", 1000.0, 100.0, 20)
        assert results[-1].transmission < results[0].transmission
