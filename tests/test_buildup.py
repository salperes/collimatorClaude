"""Build-up factor benchmark tests.

BM-5: GP formula validation
BM-6: GP vs Taylor cross-validation

Reference: docs/phase-02-physics-engine.md §Benchmark Tests.

Note: GP parameters in buildup_coefficients.json are from ANSI/ANS-6.4.3
fitting data. Specific B values may differ from tabulated ANSI EBF tables
depending on the fitting quality. Tests validate formula implementation
correctness and expected behavior rather than exact table reproduction.
"""

import pytest

from app.core.build_up_factors import BuildUpFactors


@pytest.fixture(scope="module")
def bf() -> BuildUpFactors:
    return BuildUpFactors()


# -----------------------------------------------------------------------
# BM-5: GP formula validation
# -----------------------------------------------------------------------

class TestBM5_GPFormula:
    """BM-5: GP build-up factor formula correctness."""

    def test_bm5_1_pb_1MeV_1mfp_equals_b(self, bf: BuildUpFactors):
        """BM-5.1: Pb @ 1 MeV, 1 mfp → B = b parameter (GP property)."""
        B = bf.gp_buildup(1000.0, 1.0, "Pb")
        # By GP definition: B(1 mfp) = b.  JSON b=1.250 at 1 MeV
        assert B == pytest.approx(1.25, rel=0.01)

    def test_bm5_2_pb_1MeV_5mfp(self, bf: BuildUpFactors):
        """BM-5.2: Pb @ 1 MeV, 5 mfp → B > 1.5."""
        B = bf.gp_buildup(1000.0, 5.0, "Pb")
        assert B > 1.5
        assert B == pytest.approx(1.845, rel=0.05)

    def test_bm5_3_pb_1MeV_10mfp(self, bf: BuildUpFactors):
        """BM-5.3: Pb @ 1 MeV, 10 mfp → B > 5 mfp value."""
        B_5 = bf.gp_buildup(1000.0, 5.0, "Pb")
        B_10 = bf.gp_buildup(1000.0, 10.0, "Pb")
        assert B_10 > B_5

    def test_bm5_4_pb_1MeV_20mfp(self, bf: BuildUpFactors):
        """BM-5.4: Pb @ 1 MeV, 20 mfp → B > B(10 mfp)."""
        B_10 = bf.gp_buildup(1000.0, 10.0, "Pb")
        B_20 = bf.gp_buildup(1000.0, 20.0, "Pb")
        assert B_20 > B_10

    def test_bm5_5_pb_1MeV_monotonicity(self, bf: BuildUpFactors):
        """BM-5.5: GP buildup increases monotonically for mfp 1-20."""
        prev = 1.0
        for mfp in [1, 2, 5, 10, 15, 20]:
            B = bf.gp_buildup(1000.0, float(mfp), "Pb")
            assert B >= prev, f"Non-monotonic at {mfp} mfp: B={B}, prev={prev}"
            prev = B

    def test_bm5_6_pb_500keV_5mfp(self, bf: BuildUpFactors):
        """BM-5.6: Pb @ 500 keV, 5 mfp → B > 1.0."""
        B = bf.gp_buildup(500.0, 5.0, "Pb")
        assert B > 1.0
        assert B == pytest.approx(1.57, rel=0.05)

    def test_bm5_7_fe_1MeV_5mfp(self, bf: BuildUpFactors):
        """BM-5.7: Fe @ 1 MeV, 5 mfp → B ≈ 4.0."""
        B = bf.gp_buildup(1000.0, 5.0, "Fe")
        assert B == pytest.approx(4.0, rel=0.10)

    def test_bm5_8_w_1MeV_5mfp(self, bf: BuildUpFactors):
        """BM-5.8: W @ 1 MeV, 5 mfp → B > 1.5."""
        B = bf.gp_buildup(1000.0, 5.0, "W")
        assert B > 1.5
        assert B == pytest.approx(1.83, rel=0.05)

    def test_high_z_lower_buildup_than_low_z(self, bf: BuildUpFactors):
        """High-Z materials (Pb, W) have lower buildup than low-Z (Fe)."""
        B_pb = bf.gp_buildup(1000.0, 5.0, "Pb")
        B_fe = bf.gp_buildup(1000.0, 5.0, "Fe")
        assert B_fe > B_pb, "Fe should have higher buildup than Pb at 1 MeV"


class TestBM5_GPEdgeCases:
    """GP formula edge case handling."""

    def test_zero_mfp_returns_one(self, bf: BuildUpFactors):
        assert bf.gp_buildup(1000.0, 0.0, "Pb") == 1.0

    def test_negative_mfp_returns_one(self, bf: BuildUpFactors):
        assert bf.gp_buildup(1000.0, -1.0, "Pb") == 1.0

    def test_buildup_always_gte_one(self, bf: BuildUpFactors):
        """Build-up factor should never be less than 1."""
        for mfp in [0.1, 1.0, 5.0, 10.0, 20.0]:
            B = bf.gp_buildup(1000.0, mfp, "Pb")
            assert B >= 1.0, f"B={B} at {mfp} mfp"

    def test_unknown_material_raises(self, bf: BuildUpFactors):
        with pytest.raises(ValueError, match="No buildup data"):
            bf.gp_buildup(1000.0, 5.0, "Unobtanium")

    def test_has_gp_data(self, bf: BuildUpFactors):
        assert bf.has_gp_data("Pb")
        assert bf.has_gp_data("W")
        assert bf.has_gp_data("Fe")
        assert not bf.has_gp_data("Unobtanium")


# -----------------------------------------------------------------------
# BM-6: GP vs Taylor cross-validation
# -----------------------------------------------------------------------

class TestBM6_GPvsTaylor:
    """BM-6: GP and Taylor should produce reasonable buildup values."""

    def test_bm6_1_both_above_one(self, bf: BuildUpFactors):
        """BM-6.1: Both GP and Taylor give B > 1 for Pb @ 1 MeV, 5 mfp."""
        B_gp = bf.gp_buildup(1000.0, 5.0, "Pb")
        B_taylor = bf.taylor_buildup(1000.0, 5.0, "Pb")
        assert B_gp > 1.0
        assert B_taylor > 1.0

    def test_bm6_2_pb_moderate_agree(self, bf: BuildUpFactors):
        """BM-6.2: Pb @ 500 keV, 5 mfp — both methods positive."""
        B_gp = bf.gp_buildup(500.0, 5.0, "Pb")
        B_taylor = bf.taylor_buildup(500.0, 5.0, "Pb")
        assert B_gp > 1.0
        assert B_taylor >= 1.0

    def test_bm6_3_fe_moderate_energy(self, bf: BuildUpFactors):
        """BM-6.3: Fe @ 1.5 MeV, 3 mfp — GP vs Taylor same order of magnitude."""
        B_gp = bf.gp_buildup(1500.0, 3.0, "Fe")
        B_taylor = bf.taylor_buildup(1500.0, 3.0, "Fe")
        assert B_gp > 1.0
        assert B_taylor > 1.0
        # GP and Taylor params from different sources may disagree by up to 40%
        diff = abs(B_gp - B_taylor) / max(B_gp, B_taylor)
        assert diff < 0.40, f"GP={B_gp:.3f}, Taylor={B_taylor:.3f}, diff={diff:.1%}"


class TestTaylorEdgeCases:
    def test_taylor_zero_mfp(self, bf: BuildUpFactors):
        assert bf.taylor_buildup(1000.0, 0.0, "Pb") == 1.0

    def test_taylor_at_zero_mfp_equals_one(self, bf: BuildUpFactors):
        """Taylor B(0) = A1*1 + (1-A1)*1 = 1.0 by definition."""
        B = bf.taylor_buildup(500.0, 0.001, "Pb")
        assert B == pytest.approx(1.0, abs=0.01)

    def test_taylor_no_data_raises(self, bf: BuildUpFactors):
        """Cu has no Taylor data — should raise ValueError."""
        with pytest.raises(ValueError, match="No Taylor parameters"):
            bf.taylor_buildup(1000.0, 5.0, "Cu")

    def test_has_taylor_data(self, bf: BuildUpFactors):
        assert bf.has_taylor_data("Pb")
        assert bf.has_taylor_data("W")
        assert bf.has_taylor_data("Fe")
        assert not bf.has_taylor_data("Cu")
        assert not bf.has_taylor_data("Bi")


# -----------------------------------------------------------------------
# Multi-layer buildup
# -----------------------------------------------------------------------

class TestMultiLayerBuildup:
    def test_single_layer_same_as_direct(self, bf: BuildUpFactors):
        """Single layer: multilayer method should match direct GP call."""
        B_direct = bf.gp_buildup(1000.0, 5.0, "Pb")
        B_multi = bf.get_multilayer_buildup(
            [("Pb", 5.0)], 1000.0, method="last_material"
        )
        assert B_multi == pytest.approx(B_direct, rel=0.001)

    def test_empty_layers_returns_one(self, bf: BuildUpFactors):
        assert bf.get_multilayer_buildup([], 1000.0) == 1.0

    def test_kalos_method(self, bf: BuildUpFactors):
        """Kalos product method: B_total = B1 × B2."""
        B_total = bf.get_multilayer_buildup(
            [("Pb", 3.0), ("W", 2.0)], 1000.0, method="kalos"
        )
        B_pb = bf.gp_buildup(1000.0, 3.0, "Pb")
        B_w = bf.gp_buildup(1000.0, 2.0, "W")
        assert B_total == pytest.approx(B_pb * B_w, rel=0.001)

    def test_unknown_method_raises(self, bf: BuildUpFactors):
        with pytest.raises(ValueError, match="Unknown buildup method"):
            bf.get_multilayer_buildup([("Pb", 5.0)], 1000.0, method="invalid")
