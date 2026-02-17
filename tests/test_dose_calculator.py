"""Tests for DoseCalculator — absolute dose rate at detector plane.

Benchmark tests: BM-D1 through BM-D10.
"""

import math
import pytest

import numpy as np

from app.core.dose_calculator import (
    DoseCalculator,
    _DEFAULT_TUBE_COEFFICIENTS,
    air_mu_en_rho,
    air_mu_en_rho_array,
)
from app.core.units import Gy_h_to_µSv_h, Gy_min_to_Gy_h
from app.models.geometry import SourceConfig


# ── Tube output empirical ──


class TestTubeOutputEmpirical:
    """BM-D1: Tube output Y(kVp) empirical formula validation."""

    def test_BM_D1_1_W_120kVp(self):
        """W target at 120 kVp → reasonable tube output range."""
        calc = DoseCalculator()
        Y = calc.tube_output_empirical(120.0, "W")
        # Expected: ~0.03-0.10 mGy/mAs @1m for industrial W tubes
        assert 0.01 < Y < 0.2

    def test_BM_D1_2_W_output_increases_with_kVp(self):
        """Higher kVp → higher tube output."""
        calc = DoseCalculator()
        Y_80 = calc.tube_output_empirical(80.0, "W")
        Y_120 = calc.tube_output_empirical(120.0, "W")
        Y_200 = calc.tube_output_empirical(200.0, "W")
        assert Y_80 < Y_120 < Y_200

    def test_BM_D1_3_power_law(self):
        """Verify Y ∝ kVp^n relationship."""
        calc = DoseCalculator()
        coeff = _DEFAULT_TUBE_COEFFICIENTS["W"]
        kVp = 150.0
        Y = calc.tube_output_empirical(kVp, "W")
        expected = coeff.C * (kVp ** coeff.n)
        assert abs(Y - expected) < 1e-12

    def test_BM_D1_4_different_targets(self):
        """Different targets produce different outputs."""
        calc = DoseCalculator()
        targets = ["W", "Mo", "Rh", "Cu", "Ag"]
        outputs = [calc.tube_output_empirical(120.0, t) for t in targets]
        # All positive
        assert all(y > 0 for y in outputs)
        # Not all identical
        assert len(set(round(y, 10) for y in outputs)) > 1

    def test_BM_D1_5_unknown_target_falls_back_to_W(self):
        """Unknown target uses W coefficients."""
        calc = DoseCalculator()
        Y_unknown = calc.tube_output_empirical(120.0, "Unobtanium")
        Y_W = calc.tube_output_empirical(120.0, "W")
        assert Y_unknown == Y_W


# ── Tube dose rate ──


class TestTubeDoseRate:
    """BM-D2: Tube mode dose rate at detector."""

    def test_BM_D2_1_basic_dose_rate(self):
        """8 mA, 120 kVp, SDD=1000mm → positive dose rate."""
        calc = DoseCalculator()
        dose = calc.tube_dose_rate_Gy_h(120.0, 8.0, 1000.0, "W")
        assert dose > 0

    def test_BM_D2_2_inverse_square_law(self):
        """Halving SDD → 4× dose rate."""
        calc = DoseCalculator()
        d_1000 = calc.tube_dose_rate_Gy_h(120.0, 8.0, 1000.0, "W")
        d_500 = calc.tube_dose_rate_Gy_h(120.0, 8.0, 500.0, "W")
        ratio = d_500 / d_1000
        assert abs(ratio - 4.0) < 0.01

    def test_BM_D2_3_linear_with_mA(self):
        """Doubling tube current → 2× dose rate."""
        calc = DoseCalculator()
        d_4 = calc.tube_dose_rate_Gy_h(120.0, 4.0, 1000.0, "W")
        d_8 = calc.tube_dose_rate_Gy_h(120.0, 8.0, 1000.0, "W")
        assert abs(d_8 / d_4 - 2.0) < 0.01

    def test_BM_D2_4_unit_consistency(self):
        """Verify mGy/s → Gy/h conversion: × 3.6."""
        calc = DoseCalculator()
        kVp, mA, sdd_mm = 100.0, 1.0, 1000.0
        Y = calc.tube_output_empirical(kVp, "W")
        sdd_m = sdd_mm / 1000.0
        expected_mGy_s = Y * mA / (sdd_m ** 2)
        expected_Gy_h = expected_mGy_s * 3.6
        result = calc.tube_dose_rate_Gy_h(kVp, mA, sdd_mm, "W")
        assert abs(result - expected_Gy_h) < 1e-10


# ── LINAC dose rate ──


class TestLinacDoseRate:
    """BM-D3: LINAC mode dose rate at detector."""

    def test_BM_D3_1_reference_at_1m(self):
        """260 PPS, 0.8 Gy/min ref @1m, SDD=1000mm → 48 Gy/h."""
        calc = DoseCalculator()
        dose = calc.linac_dose_rate_Gy_h(260, 0.8, 260, 1000.0, 1.0)
        # 0.8 Gy/min × 60 = 48 Gy/h at 1m, SDD=1m → no scaling
        assert abs(dose - 48.0) < 0.01

    def test_BM_D3_2_inverse_square(self):
        """SDD=2000mm vs SDD=1000mm → 4× reduction."""
        calc = DoseCalculator()
        d1 = calc.linac_dose_rate_Gy_h(260, 0.8, 260, 1000.0, 1.0)
        d2 = calc.linac_dose_rate_Gy_h(260, 0.8, 260, 2000.0, 1.0)
        assert abs(d1 / d2 - 4.0) < 0.01

    def test_BM_D3_3_pps_linearity(self):
        """Doubling PPS → 2× dose rate."""
        calc = DoseCalculator()
        d260 = calc.linac_dose_rate_Gy_h(260, 0.8, 260, 1000.0)
        d520 = calc.linac_dose_rate_Gy_h(520, 0.8, 260, 1000.0)
        assert abs(d520 / d260 - 2.0) < 0.01

    def test_BM_D3_4_dose_per_pulse(self):
        """Verify dose_per_pulse = ref_Gy_min / ref_PPS."""
        calc = DoseCalculator()
        # 0.8 Gy/min at 260 PPS → dose_per_pulse = 0.8/260 Gy/min
        # At 100 PPS: dose = (0.8/260)*100 = 0.3077 Gy/min = 18.46 Gy/h @1m
        dose = calc.linac_dose_rate_Gy_h(100, 0.8, 260, 1000.0, 1.0)
        expected = (0.8 / 260) * 100 * 60.0
        assert abs(dose - expected) < 0.01


# ── Edge cases ──


class TestEdgeCases:
    """BM-D4: Zero and boundary conditions."""

    def test_BM_D4_1_zero_sdd_tube(self):
        """SDD=0 → 0 dose (avoid division by zero)."""
        calc = DoseCalculator()
        assert calc.tube_dose_rate_Gy_h(120.0, 8.0, 0.0) == 0.0

    def test_BM_D4_2_zero_sdd_linac(self):
        calc = DoseCalculator()
        assert calc.linac_dose_rate_Gy_h(260, 0.8, 260, 0.0) == 0.0

    def test_BM_D4_3_zero_mA(self):
        calc = DoseCalculator()
        assert calc.tube_dose_rate_Gy_h(120.0, 0.0, 1000.0) == 0.0

    def test_BM_D4_4_zero_pps(self):
        calc = DoseCalculator()
        assert calc.linac_dose_rate_Gy_h(0, 0.8, 260, 1000.0) == 0.0

    def test_BM_D4_5_zero_ref_pps(self):
        calc = DoseCalculator()
        assert calc.linac_dose_rate_Gy_h(260, 0.8, 0, 1000.0) == 0.0

    def test_BM_D4_6_negative_kVp(self):
        calc = DoseCalculator()
        assert calc.tube_dose_rate_Gy_h(-120.0, 8.0, 1000.0) == 0.0


# ── Dispatcher ──


class TestDispatcher:
    """BM-D5: calculate_unattenuated_dose dispatcher."""

    def test_BM_D5_1_tube_mode(self):
        """energy_kVp set → tube calculation."""
        calc = DoseCalculator()
        src = SourceConfig(energy_kVp=120.0, tube_current_mA=8.0)
        dose = calc.calculate_unattenuated_dose(src, 1000.0)
        expected = calc.tube_dose_rate_Gy_h(120.0, 8.0, 1000.0, "W")
        assert abs(dose - expected) < 1e-10

    def test_BM_D5_2_linac_mode(self):
        """energy_MeV set → LINAC calculation."""
        calc = DoseCalculator()
        src = SourceConfig(
            energy_MeV=6.0,
            linac_pps=260,
            linac_dose_rate_Gy_min=0.8,
            linac_ref_pps=260,
        )
        dose = calc.calculate_unattenuated_dose(src, 1000.0)
        expected = calc.linac_dose_rate_Gy_h(260, 0.8, 260, 1000.0)
        assert abs(dose - expected) < 1e-10

    def test_BM_D5_3_no_energy(self):
        """Neither kVp nor MeV → 0 dose."""
        calc = DoseCalculator()
        src = SourceConfig()
        dose = calc.calculate_unattenuated_dose(src, 1000.0)
        assert dose == 0.0


# ── Unit conversions ──


class TestUnitConversions:
    """BM-D6: Dose unit conversion functions."""

    def test_BM_D6_1_Gy_to_uSv(self):
        assert Gy_h_to_µSv_h(1.0) == 1_000_000.0

    def test_BM_D6_2_Gy_to_uSv_small(self):
        assert Gy_h_to_µSv_h(0.001) == 1000.0

    def test_BM_D6_3_Gy_min_to_Gy_h(self):
        assert Gy_min_to_Gy_h(1.0) == 60.0

    def test_BM_D6_4_Gy_min_to_Gy_h_default_linac(self):
        assert abs(Gy_min_to_Gy_h(0.8) - 48.0) < 1e-10


# ── Lookup table ──


class TestLookupTable:
    """BM-D7: Lookup table tube output."""

    def test_BM_D7_1_no_table_falls_back(self):
        """No lookup table → empirical fallback."""
        calc = DoseCalculator()
        Y_lookup = calc.tube_output_lookup(120.0, "W")
        Y_empirical = calc.tube_output_empirical(120.0, "W")
        assert Y_lookup == Y_empirical

    def test_BM_D7_2_invalid_path_falls_back(self):
        """Invalid file path → empirical fallback."""
        calc = DoseCalculator(lookup_table_path="/nonexistent/path.json")
        Y = calc.tube_output_lookup(120.0, "W")
        Y_emp = calc.tube_output_empirical(120.0, "W")
        assert Y == Y_emp

    def test_BM_D7_3_lookup_interpolation(self, tmp_path):
        """Lookup table with linear interpolation."""
        table_file = tmp_path / "tube_output.json"
        table_file.write_text(
            '{"entries": ['
            '{"target": "W", "filtration": "1mm Al", "kVp": 100, "Y_mGy_mAs_1m": 0.047},'
            '{"target": "W", "filtration": "1mm Al", "kVp": 120, "Y_mGy_mAs_1m": 0.070}'
            ']}'
        )
        calc = DoseCalculator(lookup_table_path=str(table_file))
        # Midpoint: 110 kVp → (0.047 + 0.070) / 2 = 0.0585
        Y = calc.tube_output_lookup(110.0, "W", "1mm Al")
        assert abs(Y - 0.0585) < 1e-6

    def test_BM_D7_4_lookup_clamp_below(self, tmp_path):
        """kVp below table minimum → use minimum value."""
        table_file = tmp_path / "tube_output.json"
        table_file.write_text(
            '{"entries": ['
            '{"target": "W", "filtration": "1mm Al", "kVp": 100, "Y_mGy_mAs_1m": 0.047}'
            ']}'
        )
        calc = DoseCalculator(lookup_table_path=str(table_file))
        Y = calc.tube_output_lookup(50.0, "W", "1mm Al")
        assert Y == 0.047


# ── Air μ_en/ρ ──


class TestAirMuEnRho:
    """BM-D8: NIST dry air mass energy-absorption coefficient."""

    def test_BM_D8_1_known_100keV(self):
        """100 keV → 0.02325 cm²/g (exact NIST table point)."""
        val = air_mu_en_rho(100.0)
        assert abs(val - 0.02325) / 0.02325 < 0.001  # <0.1% tolerance

    def test_BM_D8_2_known_10keV(self):
        """10 keV → 4.742 cm²/g (exact table point)."""
        val = air_mu_en_rho(10.0)
        assert abs(val - 4.742) / 4.742 < 0.001

    def test_BM_D8_3_known_1MeV(self):
        """1000 keV → 0.02789 cm²/g (exact table point)."""
        val = air_mu_en_rho(1000.0)
        assert abs(val - 0.02789) / 0.02789 < 0.001

    def test_BM_D8_4_interpolation_50keV(self):
        """50 keV → between 40 keV (0.06833) and 60 keV (0.03041)."""
        val = air_mu_en_rho(50.0)
        assert 0.03041 < val < 0.06833

    def test_BM_D8_5_decreasing_at_low_energy(self):
        """μ_en/ρ decreases with energy in 10-80 keV range."""
        val_10 = air_mu_en_rho(10.0)
        val_40 = air_mu_en_rho(40.0)
        val_80 = air_mu_en_rho(80.0)
        assert val_10 > val_40 > val_80

    def test_BM_D8_6_array_matches_scalar(self):
        """Vectorized version matches scalar for known points."""
        energies = np.array([10.0, 50.0, 100.0, 500.0, 1000.0])
        arr = air_mu_en_rho_array(energies)
        for i, E in enumerate(energies):
            scalar = air_mu_en_rho(E)
            assert abs(arr[i] - scalar) / scalar < 0.01

    def test_BM_D8_7_zero_energy(self):
        """E=0 → returns 0 (safety guard)."""
        assert air_mu_en_rho(0.0) == 0.0

    def test_BM_D8_8_clamp_above(self):
        """E=25 MeV (above table max) → clamp to last value."""
        val = air_mu_en_rho(25000.0)
        assert abs(val - 0.01311) / 0.01311 < 0.001


# ── Spectral dose rate ──


@pytest.fixture
def spectrum_gen():
    """Create XRaySpectrum with real MaterialService."""
    from app.core.material_database import MaterialService
    from app.core.spectrum_models import XRaySpectrum
    mat_svc = MaterialService()
    return XRaySpectrum(mat_svc)


class TestSpectralDoseRate:
    """BM-D9: Spectral air kerma dose rate calculation."""

    def test_BM_D9_1_glass_window_matches_empirical(self, spectrum_gen):
        """Glass window only → spectral ≈ empirical (correction ≈ 1.0).

        The reference baseline in the spectral method uses a 1mm glass
        window, matching what the empirical formula was calibrated against.
        """
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA, sdd = 120.0, 8.0, 1000.0
        # Standard glass window config (matches empirical reference)
        tc = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[],
        )
        d_spectral = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc, "W",
        )
        d_empirical = calc.tube_dose_rate_Gy_h(kVp, mA, sdd, "W")
        # With standard glass window the correction factor should be ~1.0
        ratio = d_spectral / d_empirical
        assert 0.95 <= ratio <= 1.05, f"ratio={ratio:.4f}"

    def test_BM_D9_2_Cu_filter_reduces_dose(self, spectrum_gen):
        """1mm Cu filter → dose decreases significantly vs glass-only."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA, sdd = 120.0, 8.0, 1000.0
        # Standard glass window only
        tc_glass = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[],
        )
        # Glass window + 1mm Cu filter
        tc_cu = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[("Cu", 1.0)],
        )
        d_glass = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_glass, "W",
        )
        d_cu = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_cu, "W",
        )
        # Cu filter should reduce dose by 30-80%
        ratio = d_cu / d_glass
        assert 0.05 < ratio < 0.70, f"Cu/glass ratio={ratio:.4f}"

    def test_BM_D9_3_Al_filter_reduces_dose(self, spectrum_gen):
        """2.5mm Al added filter → dose decreases moderately."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA, sdd = 80.0, 10.0, 1000.0
        tc_glass = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[],
        )
        tc_al = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[("Al", 2.5)],
        )
        d_glass = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_glass, "W",
        )
        d_al = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_al, "W",
        )
        # Al filter: moderate attenuation
        ratio = d_al / d_glass
        assert 0.10 < ratio < 0.90, f"Al/glass ratio={ratio:.4f}"

    def test_BM_D9_4_thicker_filter_less_dose(self, spectrum_gen):
        """Thicker Cu filter → lower dose."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA, sdd = 150.0, 5.0, 1000.0
        doses = []
        for cu_mm in [0.5, 1.0, 2.0]:
            tc = TubeConfig(
                target_id="W", kVp=kVp,
                window_type="glass", window_thickness_mm=1.0,
                added_filtration=[("Cu", cu_mm)],
            )
            d = calc.tube_dose_rate_spectral_Gy_h(
                kVp, mA, sdd, spectrum_gen, tc, "W",
            )
            doses.append(d)
        assert doses[0] > doses[1] > doses[2], f"doses={doses}"

    def test_BM_D9_5_inverse_square(self, spectrum_gen):
        """Spectral dose follows inverse-square law."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA = 120.0, 8.0
        tc = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[("Al", 1.0)],
        )
        d_1000 = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, 1000.0, spectrum_gen, tc, "W",
        )
        d_500 = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, 500.0, spectrum_gen, tc, "W",
        )
        ratio = d_500 / d_1000
        assert abs(ratio - 4.0) < 0.01

    def test_BM_D9_6_linear_with_mA(self, spectrum_gen):
        """Spectral dose scales linearly with tube current."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, sdd = 120.0, 1000.0
        tc = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[],
        )
        d_4 = calc.tube_dose_rate_spectral_Gy_h(
            kVp, 4.0, sdd, spectrum_gen, tc, "W",
        )
        d_8 = calc.tube_dose_rate_spectral_Gy_h(
            kVp, 8.0, sdd, spectrum_gen, tc, "W",
        )
        assert abs(d_8 / d_4 - 2.0) < 0.01

    def test_BM_D9_7_edge_zero_kVp(self, spectrum_gen):
        """kVp=0 → 0 dose."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        tc = TubeConfig(target_id="W", kVp=0.0)
        d = calc.tube_dose_rate_spectral_Gy_h(
            0.0, 8.0, 1000.0, spectrum_gen, tc, "W",
        )
        assert d == 0.0

    def test_BM_D9_8_Cu_less_than_Al_attenuation(self, spectrum_gen):
        """At same thickness, Cu attenuates more than Al."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA, sdd = 120.0, 8.0, 1000.0
        tc_al = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[("Al", 1.0)],
        )
        tc_cu = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[("Cu", 1.0)],
        )
        d_al = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_al, "W",
        )
        d_cu = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_cu, "W",
        )
        # Cu (Z=29) should attenuate more than Al (Z=13) at same thickness
        assert d_cu < d_al


# ── Spectral dispatcher ──


class TestSpectralDispatcher:
    """BM-D10: Dispatcher routes spectral method correctly."""

    def test_BM_D10_1_spectral_via_dispatcher(self, spectrum_gen):
        """tube_output_method='spectral' → spectral calculation."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        src = SourceConfig(
            energy_kVp=120.0,
            tube_current_mA=8.0,
            tube_output_method="spectral",
        )
        tc = TubeConfig(
            target_id="W", kVp=120.0,
            window_type="glass", window_thickness_mm=1.0,
            added_filtration=[("Cu", 0.5)],
        )
        dose = calc.calculate_unattenuated_dose(
            src, 1000.0, spectrum_gen=spectrum_gen, tube_config=tc,
        )
        # Should be positive and less than bare empirical (Cu filter)
        d_emp = calc.tube_dose_rate_Gy_h(120.0, 8.0, 1000.0, "W")
        assert dose > 0
        assert dose < d_emp

    def test_BM_D10_2_spectral_without_gen_falls_back(self):
        """spectral method without spectrum_gen → empirical fallback."""
        calc = DoseCalculator()
        src = SourceConfig(
            energy_kVp=120.0,
            tube_current_mA=8.0,
            tube_output_method="spectral",
        )
        dose = calc.calculate_unattenuated_dose(src, 1000.0)
        d_emp = calc.tube_dose_rate_Gy_h(120.0, 8.0, 1000.0, "W")
        # Falls back to empirical when spectrum_gen is None
        assert abs(dose - d_emp) < 1e-10

    def test_BM_D10_3_glass_window_reduces_vs_bare(self, spectrum_gen):
        """Glass window filtration measurably reduces dose vs bare."""
        from app.core.spectrum_models import TubeConfig
        calc = DoseCalculator()
        kVp, mA, sdd = 80.0, 10.0, 1000.0
        tc_bare = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="none", window_thickness_mm=0.0,
            added_filtration=[],
        )
        tc_glass = TubeConfig(
            target_id="W", kVp=kVp,
            window_type="glass", window_thickness_mm=2.0,
            added_filtration=[],
        )
        d_bare = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_bare, "W",
        )
        d_glass = calc.tube_dose_rate_spectral_Gy_h(
            kVp, mA, sdd, spectrum_gen, tc_glass, "W",
        )
        # Glass window should reduce dose
        assert d_glass < d_bare
