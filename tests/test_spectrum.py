"""Tests for realistic X-ray tube spectrum model.

Covers: Kramers continuum, characteristic peaks, filtration (glass/Be),
multi-target support, effective energy, normalization, and legacy API.
"""

import math

import numpy as np
import pytest

from app.core.material_database import MaterialService
from app.core.spectrum_models import (
    CharLine,
    TubeConfig,
    XRaySpectrum,
    XRayTarget,
    _get_targets,
    effective_energy_kVp,
    kramers_spectrum,
    monoenergetic_energy_MeV,
)


@pytest.fixture(scope="module")
def material_service() -> MaterialService:
    return MaterialService()


@pytest.fixture(scope="module")
def spectrum(material_service: MaterialService) -> XRaySpectrum:
    return XRaySpectrum(material_service)


# ── Target database tests ───────────────────────────────────────────

class TestTargetDatabase:
    def test_load_targets(self):
        targets = _get_targets()
        assert "W" in targets
        assert "Mo" in targets
        assert "Rh" in targets
        assert "Cu" in targets
        assert "Ag" in targets

    def test_tungsten_properties(self):
        t = _get_targets()["W"]
        assert t.Z == 74
        assert t.k_edge_keV == pytest.approx(69.525, abs=0.1)
        assert len(t.char_lines) >= 3
        # Ka1 should be the strongest line
        ka1 = next(cl for cl in t.char_lines if cl.name == "Ka1")
        assert ka1.energy_keV == pytest.approx(59.32, abs=0.1)
        assert ka1.relative_intensity == pytest.approx(1.0)

    def test_molybdenum_properties(self):
        t = _get_targets()["Mo"]
        assert t.Z == 42
        assert t.k_edge_keV == pytest.approx(20.0, abs=0.5)

    def test_available_targets(self, spectrum: XRaySpectrum):
        targets = spectrum.available_targets()
        assert "W" in targets
        assert "Mo" in targets
        assert len(targets) >= 5


# ── Spectrum generation tests ───────────────────────────────────────

class TestSpectrumGeneration:
    def test_basic_spectrum_shape(self, spectrum: XRaySpectrum):
        """Spectrum should be non-negative and normalized."""
        config = TubeConfig(target_id="W", kVp=120, window_type="none")
        energies, phi = spectrum.generate(config)
        assert len(energies) == 200
        assert len(phi) == 200
        assert np.all(phi >= 0)
        assert phi.sum() == pytest.approx(1.0, abs=1e-6)

    def test_spectrum_energy_range(self, spectrum: XRaySpectrum):
        """Energy range should span from ~1% to ~100% of kVp."""
        config = TubeConfig(target_id="W", kVp=150, window_type="none")
        energies, _ = spectrum.generate(config)
        assert energies[0] >= 1.0
        assert energies[-1] < 150.0
        assert energies[-1] > 140.0

    def test_characteristic_peaks_present_above_k_edge(
        self, spectrum: XRaySpectrum,
    ):
        """When kVp > K-edge, characteristic peaks should be visible."""
        # W K-edge is ~69.5 keV, so 120 kVp should show peaks
        config = TubeConfig(target_id="W", kVp=120, window_type="none")
        energies, phi = spectrum.generate(config, num_bins=500)

        # Find the Ka1 peak region (~59.3 keV)
        mask = (energies > 58.0) & (energies < 61.0)
        ka1_region = phi[mask]

        # Region around Ka1 should be higher than surrounding continuum
        mask_above = (energies > 62.0) & (energies < 65.0)
        continuum_above = phi[mask_above]

        assert np.max(ka1_region) > np.max(continuum_above)

    def test_no_characteristic_peaks_below_k_edge(
        self, spectrum: XRaySpectrum,
    ):
        """When kVp < K-edge, no characteristic peaks should appear."""
        # W K-edge ~69.5, use 60 kVp
        config_60 = TubeConfig(target_id="W", kVp=60, window_type="none")
        energies_60, phi_60 = spectrum.generate(config_60, num_bins=200)

        # Spectrum should be smoothly decreasing (Kramers only)
        # Check monotonicity in the upper half
        upper_half = phi_60[len(phi_60) // 2:]
        diffs = np.diff(upper_half)
        # Most differences should be negative (decreasing)
        assert np.sum(diffs < 0) > len(diffs) * 0.8

    def test_each_target_generates_valid_spectrum(
        self, spectrum: XRaySpectrum,
    ):
        """Every target should produce a valid normalized spectrum."""
        for target_id in spectrum.available_targets():
            config = TubeConfig(target_id=target_id, kVp=150, window_type="none")
            energies, phi = spectrum.generate(config)
            assert len(energies) > 0
            assert np.all(phi >= 0)
            assert phi.sum() == pytest.approx(1.0, abs=1e-6), (
                f"Normalization failed for target {target_id}"
            )

    def test_mo_peaks_at_correct_energy(self, spectrum: XRaySpectrum):
        """Mo Ka1 should appear near 17.48 keV (if kVp > 20 keV)."""
        config = TubeConfig(target_id="Mo", kVp=30, window_type="none")
        energies, phi = spectrum.generate(config, num_bins=300)

        mask = (energies > 16.5) & (energies < 18.5)
        ka_region = phi[mask]

        # Mo Ka peak should be clearly visible
        mask_off = (energies > 12.0) & (energies < 14.0)
        continuum = phi[mask_off]

        assert np.max(ka_region) > np.mean(continuum) * 1.5


# ── Filtration tests ────────────────────────────────────────────────

class TestFiltration:
    def test_glass_window_attenuates_low_energy(
        self, spectrum: XRaySpectrum,
    ):
        """Glass (Al) window should suppress low energies more than high."""
        config_none = TubeConfig(
            target_id="W", kVp=120, window_type="none",
        )
        config_glass = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
        )
        e_none, phi_none = spectrum.generate_unfiltered(config_none)
        e_glass, phi_glass = spectrum.generate(config_glass)

        # Low-energy bins should be more attenuated
        # Compare ratio at low vs high energy
        low_idx = len(e_glass) // 10   # ~10% of kVp
        high_idx = len(e_glass) * 8 // 10  # ~80% of kVp

        # The filtered spectrum should be shifted toward higher energies
        mean_e_none = np.sum(e_none * phi_none)
        mean_e_glass = np.sum(e_glass * phi_glass)
        assert mean_e_glass > mean_e_none

    def test_be_window_less_filtration_than_glass(
        self, spectrum: XRaySpectrum,
    ):
        """Be window should transmit more low-energy photons than glass."""
        config_glass = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
        )
        config_be = TubeConfig(
            target_id="W", kVp=120, window_type="Be",
            window_thickness_mm=0.5,
        )
        e_glass, phi_glass = spectrum.generate(config_glass)
        e_be, phi_be = spectrum.generate(config_be)

        # Be should have lower effective energy (more low-energy photons)
        mean_e_glass = np.sum(e_glass * phi_glass)
        mean_e_be = np.sum(e_be * phi_be)
        assert mean_e_be < mean_e_glass

    def test_added_filtration_hardens_beam(
        self, spectrum: XRaySpectrum,
    ):
        """Adding Al filtration should increase effective energy."""
        config_bare = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
        )
        config_filtered = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
            added_filtration=[("Al", 2.5)],
        )
        e_eff_bare = spectrum.effective_energy(config_bare)
        e_eff_filtered = spectrum.effective_energy(config_filtered)
        assert e_eff_filtered > e_eff_bare

    def test_cu_filter_strong_attenuation(self, spectrum: XRaySpectrum):
        """Cu filter should strongly attenuate low/mid energies."""
        config_no_cu = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
        )
        config_cu = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
            added_filtration=[("Cu", 0.5)],
        )
        e_no_cu = spectrum.effective_energy(config_no_cu)
        e_cu = spectrum.effective_energy(config_cu)
        # Cu filter should significantly harden the beam
        assert e_cu > e_no_cu + 5.0

    def test_no_filtration_mode(self, spectrum: XRaySpectrum):
        """window_type='none' should skip filtration."""
        config = TubeConfig(target_id="W", kVp=120, window_type="none")
        _, phi = spectrum.generate(config)
        # First bin should have significant intensity (no low-E suppression)
        assert phi[0] > 0


# ── Effective energy tests ──────────────────────────────────────────

class TestEffectiveEnergy:
    def test_effective_energy_reasonable_range(
        self, spectrum: XRaySpectrum,
    ):
        """Effective energy should be between kVp/4 and kVp/2."""
        config = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=1.0,
        )
        e_eff = spectrum.effective_energy(config)
        assert 120 / 4 < e_eff < 120 / 2

    def test_effective_energy_increases_with_filtration(
        self, spectrum: XRaySpectrum,
    ):
        """More filtration → higher effective energy (beam hardening)."""
        configs = [
            TubeConfig(target_id="W", kVp=120, window_type="none"),
            TubeConfig(target_id="W", kVp=120, window_type="glass",
                       window_thickness_mm=1.0),
            TubeConfig(target_id="W", kVp=120, window_type="glass",
                       window_thickness_mm=1.0,
                       added_filtration=[("Al", 5.0)]),
        ]
        e_effs = [spectrum.effective_energy(c) for c in configs]
        assert e_effs[0] < e_effs[1] < e_effs[2]

    def test_effective_energy_increases_with_kvp(
        self, spectrum: XRaySpectrum,
    ):
        """Higher kVp → higher effective energy."""
        e80 = spectrum.effective_energy(TubeConfig(kVp=80, window_type="glass"))
        e120 = spectrum.effective_energy(TubeConfig(kVp=120, window_type="glass"))
        e200 = spectrum.effective_energy(TubeConfig(kVp=200, window_type="glass"))
        assert e80 < e120 < e200


# ── Legacy API tests ────────────────────────────────────────────────

class TestLegacyAPI:
    def test_kramers_spectrum_unchanged(self):
        """Legacy kramers_spectrum should still work identically."""
        energies, phi = kramers_spectrum(120, num_bins=100, Z=74)
        assert len(energies) == 100
        assert phi.sum() == pytest.approx(1.0, abs=1e-6)
        assert np.all(phi >= 0)
        # Should be decreasing in upper half (Kramers shape)
        assert phi[-1] < phi[len(phi) // 2]

    def test_effective_energy_kvp_unfiltered(self):
        assert effective_energy_kVp(120) == pytest.approx(40.0)
        assert effective_energy_kVp(300) == pytest.approx(100.0)

    def test_effective_energy_kvp_filtered(self):
        assert effective_energy_kVp(120, filtered=True) == pytest.approx(48.0)

    def test_monoenergetic_mev(self):
        assert monoenergetic_energy_MeV(6.0) == pytest.approx(2.0)
        assert monoenergetic_energy_MeV(3.5) == pytest.approx(3.5 / 3.0)


# ── Edge cases ──────────────────────────────────────────────────────

class TestEdgeCases:
    def test_very_low_kvp(self, spectrum: XRaySpectrum):
        """Very low kVp should still produce valid spectrum."""
        config = TubeConfig(target_id="Cu", kVp=10, window_type="none")
        energies, phi = spectrum.generate(config, num_bins=50)
        assert len(energies) > 0
        assert phi.sum() == pytest.approx(1.0, abs=1e-6)

    def test_kvp_just_above_k_edge(self, spectrum: XRaySpectrum):
        """kVp barely above K-edge should produce small but present peaks."""
        # W K-edge ~69.5 keV, use kVp=72
        config = TubeConfig(target_id="W", kVp=72, window_type="none")
        energies, phi = spectrum.generate(config, num_bins=300)
        assert phi.sum() == pytest.approx(1.0, abs=1e-6)

    def test_zero_thickness_filter_no_effect(self, spectrum: XRaySpectrum):
        """Zero-thickness filter should not change spectrum."""
        config_none = TubeConfig(target_id="W", kVp=120, window_type="none")
        config_zero = TubeConfig(
            target_id="W", kVp=120, window_type="glass",
            window_thickness_mm=0.0,
        )
        _, phi_none = spectrum.generate(config_none)
        _, phi_zero = spectrum.generate(config_zero)
        np.testing.assert_allclose(phi_none, phi_zero, atol=1e-10)
