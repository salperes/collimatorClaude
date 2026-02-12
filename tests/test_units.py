"""BM-9: End-to-end unit conversion chain validation.

Reference: FRD §11.6 — Unit conversion benchmarks.
"""

import math
import pytest

from app.core.units import (
    mm_to_cm, cm_to_mm,
    MeV_to_keV, keV_to_MeV,
    deg_to_rad, rad_to_deg,
    thickness_to_mfp, mfp_to_thickness,
    transmission_to_dB, dB_to_transmission,
)


class TestLengthConversion:
    def test_mm_to_cm(self):
        assert mm_to_cm(10.0) == pytest.approx(1.0)
        assert mm_to_cm(0.0) == pytest.approx(0.0)
        assert mm_to_cm(1.0) == pytest.approx(0.1)

    def test_cm_to_mm(self):
        assert cm_to_mm(1.0) == pytest.approx(10.0)
        assert cm_to_mm(0.0) == pytest.approx(0.0)
        assert cm_to_mm(0.1) == pytest.approx(1.0)

    def test_roundtrip(self):
        assert cm_to_mm(mm_to_cm(42.5)) == pytest.approx(42.5)


class TestEnergyConversion:
    def test_MeV_to_keV(self):
        assert MeV_to_keV(3.5) == pytest.approx(3500.0)
        assert MeV_to_keV(1.0) == pytest.approx(1000.0)
        assert MeV_to_keV(6.0) == pytest.approx(6000.0)

    def test_keV_to_MeV(self):
        assert keV_to_MeV(1000.0) == pytest.approx(1.0)
        assert keV_to_MeV(3500.0) == pytest.approx(3.5)

    def test_roundtrip(self):
        assert keV_to_MeV(MeV_to_keV(2.5)) == pytest.approx(2.5)


class TestAngleConversion:
    def test_deg_to_rad(self):
        assert deg_to_rad(180.0) == pytest.approx(math.pi)
        assert deg_to_rad(90.0) == pytest.approx(math.pi / 2)
        assert deg_to_rad(0.0) == pytest.approx(0.0)

    def test_rad_to_deg(self):
        assert rad_to_deg(math.pi) == pytest.approx(180.0)
        assert rad_to_deg(math.pi / 2) == pytest.approx(90.0)

    def test_roundtrip(self):
        assert rad_to_deg(deg_to_rad(45.0)) == pytest.approx(45.0)


class TestOpticalThickness:
    def test_thickness_to_mfp(self):
        # Pb, 1 MeV: μ = 0.8036 cm⁻¹, 1 cm → 0.8036 mfp
        assert thickness_to_mfp(1.0, 0.8036) == pytest.approx(0.8036)

    def test_mfp_to_thickness(self):
        assert mfp_to_thickness(0.8036, 0.8036) == pytest.approx(1.0)

    def test_roundtrip(self):
        mu = 0.8036
        t = 2.5
        mfp = thickness_to_mfp(t, mu)
        assert mfp_to_thickness(mfp, mu) == pytest.approx(t)


class TestAttenuationConversion:
    def test_transmission_to_dB(self):
        assert transmission_to_dB(1.0) == pytest.approx(0.0)
        assert transmission_to_dB(0.1) == pytest.approx(10.0)
        assert transmission_to_dB(0.01) == pytest.approx(20.0)

    def test_dB_to_transmission(self):
        assert dB_to_transmission(0.0) == pytest.approx(1.0)
        assert dB_to_transmission(10.0) == pytest.approx(0.1)
        assert dB_to_transmission(20.0) == pytest.approx(0.01)

    def test_roundtrip(self):
        assert dB_to_transmission(transmission_to_dB(0.4478)) == pytest.approx(0.4478, rel=1e-6)

    def test_very_small_transmission(self):
        # Should not raise even for effectively zero transmission
        result = transmission_to_dB(1e-30)
        assert result > 0


# ---------------------------------------------------------------------------
# BM-9: End-to-end unit chain validation (FRD §11.6)
# ---------------------------------------------------------------------------

@pytest.mark.benchmark
class TestBM9:
    """BM-9: End-to-end unit conversion chain — Pb reference values."""

    def test_BM_9_1_pb_10mm_1MeV_transmission(self):
        """BM-9.1: Pb 10mm, 1 MeV → T = 0.4478.

        Chain: 10 mm → 1.0 cm, μ = 0.0708×11.34 = 0.8036 cm⁻¹,
               μx = 0.8036, T = exp(-0.8036) ≈ 0.4478.
        """
        thickness_mm = 10.0
        mu_rho = 0.0708       # cm²/g (Pb, 1 MeV, NIST XCOM)
        density = 11.34       # g/cm³

        thickness_cm = mm_to_cm(thickness_mm)
        assert thickness_cm == pytest.approx(1.0)

        mu = mu_rho * density  # cm⁻¹
        assert mu == pytest.approx(0.8036, rel=0.01)

        mu_x = thickness_to_mfp(thickness_cm, mu)
        assert mu_x == pytest.approx(0.8036, rel=0.01)

        transmission = math.exp(-mu_x)
        assert transmission == pytest.approx(0.4478, rel=0.01)

    def test_BM_9_2_pb_1MeV_HVL(self):
        """BM-9.2: Pb, 1 MeV → HVL = 8.62 mm.

        Chain: μ/ρ → μ → ln(2)/μ [cm] → ×10 [mm].
        """
        mu_rho = 0.0708
        density = 11.34
        mu = mu_rho * density  # 0.8036 cm⁻¹

        hvl_cm = math.log(2) / mu
        hvl_mm = cm_to_mm(hvl_cm)
        assert hvl_mm == pytest.approx(8.62, rel=0.02)

    def test_BM_9_3_pb_10mm_buildup_mfp(self):
        """BM-9.3: Pb 10mm, 1 MeV → mfp ≈ 0.8036.

        Chain: 10mm → 1cm → 0.8036 mfp.
        Build-up factor at ~1 mfp ≈ 1.37 (reference only, not tested here).
        """
        thickness_cm = mm_to_cm(10.0)
        mu = 0.0708 * 11.34
        mfp = thickness_to_mfp(thickness_cm, mu)
        assert mfp == pytest.approx(0.8036, rel=0.01)

    def test_BM_9_4_MeV_to_keV(self):
        """BM-9.4: 3.5 MeV → 3500 keV."""
        assert MeV_to_keV(3.5) == pytest.approx(3500.0)
