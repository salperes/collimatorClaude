"""Phase 5 chart data tests — verify physics data feeds for visualization.

Non-GUI tests: validate that data sources produce correct inputs
for the chart widgets (attenuation, HVL, transmission, Compton).

Reference: docs/phase-05-visualization.md.
"""

import math

import numpy as np
import pytest

from app.core.compton_engine import ComptonEngine
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.units import cm_to_mm


@pytest.fixture(scope="module")
def ms() -> MaterialService:
    return MaterialService()


@pytest.fixture(scope="module")
def pe(ms: MaterialService) -> PhysicsEngine:
    return PhysicsEngine(ms)


@pytest.fixture(scope="module")
def ce() -> ComptonEngine:
    return ComptonEngine()


# -----------------------------------------------------------------------
# Attenuation data (mu/rho vs energy)
# -----------------------------------------------------------------------


class TestAttenuationData:
    """Data source for AttenuationChartWidget."""

    def test_pb_has_nist_data(self, ms: MaterialService):
        """Pb should have NIST XCOM data in 10–6000 keV range."""
        data = ms.get_attenuation_data("Pb", min_energy_keV=10, max_energy_keV=6000)
        assert len(data) > 10

    def test_w_has_nist_data(self, ms: MaterialService):
        """W should have NIST XCOM data."""
        data = ms.get_attenuation_data("W", min_energy_keV=10, max_energy_keV=6000)
        assert len(data) > 10

    def test_energy_range(self, ms: MaterialService):
        """Data points should be within requested energy range."""
        data = ms.get_attenuation_data("Pb", min_energy_keV=10, max_energy_keV=6000)
        energies = [d.energy_keV for d in data]
        assert min(energies) >= 10
        assert max(energies) <= 6000

    def test_mu_rho_positive(self, ms: MaterialService):
        """All mu/rho values should be positive."""
        data = ms.get_attenuation_data("Pb", min_energy_keV=10, max_energy_keV=6000)
        for d in data:
            assert d.mass_attenuation > 0


# -----------------------------------------------------------------------
# HVL computation
# -----------------------------------------------------------------------


class TestHvlComputation:
    """Data source for HvlChartWidget."""

    @pytest.mark.parametrize("mat_id", ["Pb", "W", "Cu", "Al"])
    def test_hvl_positive(self, pe: PhysicsEngine, mat_id: str):
        """HVL should be positive at 1000 keV for all materials."""
        result = pe.calculate_hvl_tvl(mat_id, 1000.0)
        assert result.hvl_cm > 0

    def test_hvl_pb_less_than_al(self, pe: PhysicsEngine):
        """At 100 keV, Pb HVL should be much smaller than Al."""
        hvl_pb = pe.calculate_hvl_tvl("Pb", 100.0).hvl_cm
        hvl_al = pe.calculate_hvl_tvl("Al", 100.0).hvl_cm
        assert hvl_pb < hvl_al

    def test_hvl_energy_sweep(self, pe: PhysicsEngine):
        """HVL sweep over energy should produce valid values."""
        energies = np.logspace(np.log10(30), np.log10(6000), 20)
        for e in energies:
            result = pe.calculate_hvl_tvl("Pb", float(e))
            hvl_mm = float(cm_to_mm(result.hvl_cm))
            assert hvl_mm > 0


# -----------------------------------------------------------------------
# Transmission sweep
# -----------------------------------------------------------------------


class TestTransmissionSweep:
    """Data source for TransmissionChartWidget."""

    def test_transmission_at_zero_thickness(self, pe: PhysicsEngine):
        """T(0) should be 1.0 (no material = full transmission)."""
        pts = pe.thickness_sweep("Pb", 1000.0, max_thickness_mm=10.0, steps=50)
        assert pts[0].transmission == pytest.approx(1.0, abs=1e-6)

    def test_transmission_decreasing(self, pe: PhysicsEngine):
        """Transmission should decrease monotonically with thickness."""
        pts = pe.thickness_sweep("Pb", 1000.0, max_thickness_mm=50.0, steps=100)
        transmissions = [p.transmission for p in pts]
        for i in range(1, len(transmissions)):
            assert transmissions[i] <= transmissions[i - 1] + 1e-10

    def test_transmission_less_than_one(self, pe: PhysicsEngine):
        """T > 0 for any finite thickness (exponential never reaches zero)."""
        pts = pe.thickness_sweep("Pb", 1000.0, max_thickness_mm=100.0, steps=50)
        for p in pts:
            assert p.transmission >= 0
            assert p.transmission <= 1.0


# -----------------------------------------------------------------------
# Compton KN distribution
# -----------------------------------------------------------------------


class TestComptonKnDistribution:
    """Data source for KleinNishinaChart."""

    def test_kn_bin_count(self, ce: ComptonEngine):
        """KN distribution with angular_bins=360 returns 361 points (0 to pi inclusive)."""
        kn = ce.klein_nishina_distribution(1000.0, angular_bins=360)
        assert len(kn.angles_rad) == 361
        assert len(kn.dsigma_domega) == 361

    def test_kn_dsigma_positive(self, ce: ComptonEngine):
        """All dsigma/dOmega values should be positive."""
        kn = ce.klein_nishina_distribution(1000.0, angular_bins=180)
        for val in kn.dsigma_domega:
            assert val > 0

    def test_kn_forward_greater_at_high_energy(self, ce: ComptonEngine):
        """At high energy, forward scattering (0°) > backward (180°)."""
        kn = ce.klein_nishina_distribution(6000.0, angular_bins=180)
        # First bin ≈ near 0°, last bin ≈ near π
        assert kn.dsigma_domega[0] > kn.dsigma_domega[-1]


# -----------------------------------------------------------------------
# Compton energy spectrum
# -----------------------------------------------------------------------


class TestComptonSpectrum:
    """Data source for ComptonEnergyChart."""

    def test_spectrum_energy_range(self, ce: ComptonEngine):
        """Spectrum energies should be within [E'_min, E0]."""
        E0 = 1000.0
        spectrum = ce.scattered_energy_spectrum(E0, num_bins=200)
        e_min, _ = ce.compton_edge(E0)
        energies = np.array(spectrum.energy_bins_keV)
        assert np.all(energies >= e_min - 1.0)  # small tolerance
        assert np.all(energies <= E0 + 1.0)

    def test_spectrum_weights_positive(self, ce: ComptonEngine):
        """Spectrum weights should be non-negative."""
        spectrum = ce.scattered_energy_spectrum(1000.0, num_bins=200)
        weights = np.array(spectrum.weights)
        assert np.all(weights >= 0)


# -----------------------------------------------------------------------
# Angle-energy map
# -----------------------------------------------------------------------


class TestAngleEnergyMap:
    """Data source for AngleEnergyChart."""

    def test_forward_scatter_equals_E0(self, ce: ComptonEngine):
        """At theta=0, scattered energy E' should equal E0."""
        data = ce.angle_energy_map(1000.0, angular_steps=361)
        # First angle is 0 rad
        assert data.scattered_energies_keV[0] == pytest.approx(1000.0, rel=1e-3)

    def test_backward_scatter_equals_compton_edge(self, ce: ComptonEngine):
        """At theta=180°, scattered energy E' = Compton edge."""
        E0 = 1000.0
        data = ce.angle_energy_map(E0, angular_steps=181)
        e_min, _ = ce.compton_edge(E0)
        # Last angle is π
        assert data.scattered_energies_keV[-1] == pytest.approx(e_min, rel=1e-3)

    def test_recoil_energy_conservation(self, ce: ComptonEngine):
        """E' + T = E0 (energy conservation at each angle)."""
        E0 = 1000.0
        data = ce.angle_energy_map(E0, angular_steps=100)
        for e_prime, t_recoil in zip(
            data.scattered_energies_keV, data.recoil_energies_keV
        ):
            assert e_prime + t_recoil == pytest.approx(E0, rel=1e-3)
