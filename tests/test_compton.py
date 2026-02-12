"""Compton engine benchmark tests.

BM-7: Klein-Nishina analytical validation.

Reference: docs/phase-02-physics-engine.md §Benchmark Tests.
"""

import math

import pytest

from app.core.compton_engine import ComptonEngine


@pytest.fixture(scope="module")
def ce() -> ComptonEngine:
    return ComptonEngine()


# -----------------------------------------------------------------------
# BM-7: Klein-Nishina total cross-section
# -----------------------------------------------------------------------

class TestBM7_TotalCrossSection:
    """BM-7.1–7.4: σ_KN at key energies."""

    def test_bm7_1_thomson_limit(self, ce: ComptonEngine):
        """BM-7.1: σ_KN(E→0) ≈ σ_Thomson = 6.6524e-25 cm²."""
        sigma = ce.total_cross_section(0.001)  # 1 eV, effectively zero
        assert sigma == pytest.approx(6.6524e-25, rel=0.001)

    def test_bm7_2_sigma_511keV(self, ce: ComptonEngine):
        """BM-7.2: σ_KN(511 keV) = 2.716e-25 cm²."""
        sigma = ce.total_cross_section(511.0)
        assert sigma == pytest.approx(2.716e-25, rel=0.005)

    def test_bm7_3_sigma_1MeV(self, ce: ComptonEngine):
        """BM-7.3: σ_KN(1 MeV) = 1.772e-25 cm²."""
        sigma = ce.total_cross_section(1000.0)
        assert sigma == pytest.approx(1.772e-25, rel=0.005)

    def test_bm7_4_sigma_6MeV(self, ce: ComptonEngine):
        """BM-7.4: σ_KN(6 MeV) = 0.494e-25 cm²."""
        sigma = ce.total_cross_section(6000.0)
        assert sigma == pytest.approx(0.494e-25, rel=0.005)

    def test_sigma_decreases_with_energy(self, ce: ComptonEngine):
        """σ_KN should decrease monotonically with energy."""
        energies = [10, 100, 511, 1000, 6000]
        sigmas = [ce.total_cross_section(E) for E in energies]
        for i in range(len(sigmas) - 1):
            assert sigmas[i] > sigmas[i + 1], (
                f"σ({energies[i]}) = {sigmas[i]:.3e} should be > "
                f"σ({energies[i+1]}) = {sigmas[i+1]:.3e}"
            )


# -----------------------------------------------------------------------
# BM-7: Klein-Nishina differential cross-section
# -----------------------------------------------------------------------

class TestBM7_DifferentialCrossSection:
    """BM-7.5–7.6: dσ/dΩ Thomson limit checks."""

    def test_bm7_5_forward_scattering_thomson(self, ce: ComptonEngine):
        """BM-7.5: dσ/dΩ(0°, 10 keV) ≈ r₀² (Thomson limit)."""
        r0 = ce.CLASSICAL_ELECTRON_RADIUS
        dsigma = ce.klein_nishina_differential(10.0, 0.0)
        # Thomson at 0°: dσ/dΩ = r₀² (since (1+cos²0)/2 × r₀² = r₀²)
        assert dsigma == pytest.approx(r0 ** 2, rel=0.02)

    def test_bm7_6_90deg_scattering_thomson(self, ce: ComptonEngine):
        """BM-7.6: dσ/dΩ(90°, 10 keV) ≈ r₀²/2 (Thomson limit)."""
        r0 = ce.CLASSICAL_ELECTRON_RADIUS
        dsigma = ce.klein_nishina_differential(10.0, math.pi / 2)
        # Thomson at 90°: sin²(90°)=1, cos²(90°)=0
        # dσ/dΩ = (r₀²/2)(1 + 0 - 1) ... wait, let me recalculate.
        # KN: dσ/dΩ = (r₀²/2)(E'/E₀)²(E'/E₀ + E₀/E' - sin²θ)
        # At low energy, E'/E₀ ≈ 1, so: (r₀²/2)(1 + 1 - 1) = r₀²/2
        assert dsigma == pytest.approx(r0 ** 2 / 2, rel=0.02)

    def test_forward_scattering_maximum(self, ce: ComptonEngine):
        """Forward scattering (0°) should have maximum dσ/dΩ."""
        dsigma_0 = ce.klein_nishina_differential(1000.0, 0.0)
        dsigma_90 = ce.klein_nishina_differential(1000.0, math.pi / 2)
        dsigma_180 = ce.klein_nishina_differential(1000.0, math.pi)
        assert dsigma_0 > dsigma_90
        assert dsigma_0 > dsigma_180


# -----------------------------------------------------------------------
# BM-7: Compton kinematics
# -----------------------------------------------------------------------

class TestBM7_ComptonKinematics:
    """BM-7.7–7.10: Compton energy and wavelength shift."""

    def test_bm7_7_compton_edge_1MeV(self, ce: ComptonEngine):
        """BM-7.7: E'(1 MeV, 180°) = 203.5 keV (Compton edge).

        E' = 1000 / (1 + 2*1000/511) = 1000/4.914 = 203.5 keV.
        """
        E_prime = ce.scattered_energy(1000.0, math.pi)
        assert E_prime == pytest.approx(203.5, rel=0.001)

    def test_bm7_8_scattered_energy_6MeV_90deg(self, ce: ComptonEngine):
        """BM-7.8: E'(6 MeV, 90°) = 470.9 keV.

        E' = 6000 / (1 + 6000/511) = 6000/12.742 = 470.9 keV.
        """
        E_prime = ce.scattered_energy(6000.0, math.pi / 2)
        assert E_prime == pytest.approx(470.9, rel=0.001)

    def test_bm7_9_wavelength_shift_90deg(self, ce: ComptonEngine):
        """BM-7.9: Δλ(90°) = 0.02426 Å (exactly λ_C)."""
        delta_lambda = ce.wavelength_shift(math.pi / 2)
        assert delta_lambda == pytest.approx(0.02426, rel=0.001)

    def test_bm7_10_wavelength_shift_180deg(self, ce: ComptonEngine):
        """BM-7.10: Δλ(180°) = 0.04852 Å (2 × λ_C)."""
        delta_lambda = ce.wavelength_shift(math.pi)
        assert delta_lambda == pytest.approx(0.04852, rel=0.001)

    def test_forward_scattering_no_energy_loss(self, ce: ComptonEngine):
        """At θ=0, scattered energy equals incident energy."""
        E_prime = ce.scattered_energy(1000.0, 0.0)
        assert E_prime == pytest.approx(1000.0, rel=0.001)

    def test_wavelength_shift_zero_at_forward(self, ce: ComptonEngine):
        """At θ=0, wavelength shift is zero."""
        assert ce.wavelength_shift(0.0) == pytest.approx(0.0, abs=1e-10)

    def test_compton_edge_values(self, ce: ComptonEngine):
        """Compton edge: E'_min + T_max = E₀."""
        E0 = 1000.0
        E_prime_min, T_max = ce.compton_edge(E0)
        assert E_prime_min + T_max == pytest.approx(E0, rel=1e-6)

    def test_recoil_energy_conservation(self, ce: ComptonEngine):
        """E' + T = E₀ for any angle."""
        E0 = 2000.0
        for theta_deg in [30, 60, 90, 120, 150, 180]:
            theta_rad = math.radians(theta_deg)
            E_prime = ce.scattered_energy(E0, theta_rad)
            T = ce.recoil_electron_energy(E0, theta_rad)
            assert E_prime + T == pytest.approx(E0, rel=1e-6), (
                f"Energy not conserved at {theta_deg}°"
            )


# -----------------------------------------------------------------------
# Distribution and map methods
# -----------------------------------------------------------------------

class TestDistributions:
    def test_kn_distribution_shape(self, ce: ComptonEngine):
        result = ce.klein_nishina_distribution(1000.0, angular_bins=180)
        assert len(result.angles_rad) == 181
        assert len(result.dsigma_domega) == 181
        assert len(result.scattered_energies_keV) == 181
        assert result.angles_rad[0] == pytest.approx(0.0)
        assert result.angles_rad[-1] == pytest.approx(math.pi)

    def test_scattered_spectrum_shape(self, ce: ComptonEngine):
        result = ce.scattered_energy_spectrum(1000.0, num_bins=50)
        assert len(result.energy_bins_keV) == 50
        assert len(result.weights) == 50
        # Weights should sum to ~1 (normalized)
        assert sum(result.weights) == pytest.approx(1.0, rel=0.01)

    def test_angle_energy_map_shape(self, ce: ComptonEngine):
        result = ce.angle_energy_map(1000.0, angular_steps=91)
        assert len(result.angles_rad) == 91
        assert len(result.scattered_energies_keV) == 91
        assert len(result.recoil_energies_keV) == 91
        assert len(result.wavelength_shifts_angstrom) == 91

    def test_cross_section_vs_energy_shape(self, ce: ComptonEngine):
        result = ce.cross_section_vs_energy(10.0, 10000.0, 50)
        assert len(result.energies_keV) == 50
        assert len(result.sigma_kn) == 50
        # Should decrease with energy
        assert result.sigma_kn[0] > result.sigma_kn[-1]
