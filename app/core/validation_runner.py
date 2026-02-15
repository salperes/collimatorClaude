"""Standalone physics validation runner — V1-V6 checks.

Runs the same cross-validation checks as ``tests/test_validation.py`` but
without pytest dependency.  Returns structured results suitable for UI
display and PDF report generation.

If xraylib is not installed, xraylib-dependent checks are skipped (not failed).
Analytical checks (V2, V3, V5, V6) always run.

All energies in keV, angles in radians (core units).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.core.build_up_factors import BuildUpFactors
from app.core.compton_engine import ComptonEngine
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine

# Try importing xraylib — graceful degradation if unavailable
try:
    import xraylib as _xrl
    _XRAYLIB_AVAILABLE = True
    _XRAYLIB_VERSION = getattr(_xrl, "__version__", "unknown")
except ImportError:
    _xrl = None  # type: ignore[assignment]
    _XRAYLIB_AVAILABLE = False
    _XRAYLIB_VERSION = "N/A"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Single validation check result."""
    test_id: str
    group: str          # "V1", "V2", "V3", "V4", "V5", "V6"
    description: str
    our_value: float
    ref_value: float
    tolerance_pct: float
    passed: bool
    skipped: bool = False
    note: str = ""

    @property
    def diff_pct(self) -> float:
        if self.ref_value != 0:
            return abs(self.our_value - self.ref_value) / abs(self.ref_value) * 100
        return abs(self.our_value - self.ref_value) * 100


@dataclass
class ValidationSummary:
    """Aggregated validation run results."""
    results: list[ValidationResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_s: float = 0.0
    xraylib_available: bool = _XRAYLIB_AVAILABLE
    xraylib_version: str = _XRAYLIB_VERSION


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

_ELEMENT_Z = {"Pb": 82, "Bi": 83}
_SAFE_ENERGIES = [100.0, 200.0, 300.0, 500.0, 800.0]

_ANSI_BUILDUP: dict[tuple[str, float, int], float] = {
    ("Pb", 1.0, 1): 1.24,
    ("Pb", 1.0, 5): 1.88,
    ("Pb", 1.0, 10): 2.82,
    ("Pb", 0.5, 5): 1.56,
    ("Fe", 1.0, 1): 1.98,
    ("Fe", 1.0, 5): 3.71,
    ("Fe", 1.0, 10): 7.60,
    ("W", 1.0, 5): 1.86,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class ValidationRunner:
    """Programmatic validation runner for V1-V6 physics checks.

    Args:
        progress_callback: Optional ``(percent: int, test_id: str) -> None``.
        cancelled_check: Optional ``() -> bool`` returning True to abort.
    """

    def __init__(
        self,
        progress_callback: Callable[[int, str], None] | None = None,
        cancelled_check: Callable[[], bool] | None = None,
    ) -> None:
        self._progress = progress_callback or (lambda p, t: None)
        self._cancelled = cancelled_check or (lambda: False)
        self._results: list[ValidationResult] = []

        # Instantiate services
        self._ms = MaterialService()
        self._bf = BuildUpFactors()
        self._pe = PhysicsEngine(self._ms, self._bf)
        self._ce = ComptonEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_all(self) -> ValidationSummary:
        """Execute all V1-V6 validation checks and return summary."""
        t0 = time.perf_counter()
        self._results.clear()

        groups = [
            self._run_v1_materials,
            self._run_v2_physics,
            self._run_v3_buildup,
            self._run_v4_compton,
            self._run_v5_sampler,
            self._run_v6_beam,
        ]

        total_groups = len(groups)
        for idx, group_fn in enumerate(groups):
            if self._cancelled():
                break
            base_pct = int(idx / total_groups * 100)
            group_fn(base_pct, 100 // total_groups)

        elapsed = time.perf_counter() - t0

        passed = sum(1 for r in self._results if r.passed and not r.skipped)
        failed = sum(1 for r in self._results if not r.passed and not r.skipped)
        skipped = sum(1 for r in self._results if r.skipped)

        return ValidationSummary(
            results=list(self._results),
            total=len(self._results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_s=elapsed,
            xraylib_available=_XRAYLIB_AVAILABLE,
            xraylib_version=_XRAYLIB_VERSION,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add(self, test_id: str, group: str, desc: str,
             ours: float, ref: float, tol_pct: float,
             note: str = "", skipped: bool = False) -> None:
        if skipped:
            self._results.append(ValidationResult(
                test_id=test_id, group=group, description=desc,
                our_value=ours, ref_value=ref, tolerance_pct=tol_pct,
                passed=True, skipped=True, note=note,
            ))
            return

        if ref != 0:
            rel_err = abs(ours - ref) / abs(ref)
        else:
            rel_err = abs(ours - ref)
        passed = rel_err < (tol_pct / 100) if tol_pct > 0 else (ours == ref)

        self._results.append(ValidationResult(
            test_id=test_id, group=group, description=desc,
            our_value=ours, ref_value=ref, tolerance_pct=tol_pct,
            passed=passed, note=note,
        ))

    def _emit(self, base_pct: int, span: int, frac: float, test_id: str) -> None:
        pct = min(base_pct + int(span * frac), 99)
        self._progress(pct, test_id)

    def _xrl_cs_total(self, Z: int, E: float) -> float | None:
        """Safe xraylib CS_Total call — returns None on error."""
        if not _XRAYLIB_AVAILABLE:
            return None
        try:
            return _xrl.CS_Total(Z, E)
        except (ValueError, RuntimeError):
            return None

    # ------------------------------------------------------------------
    # V1: MaterialService — μ/ρ vs xraylib
    # ------------------------------------------------------------------

    def _run_v1_materials(self, base_pct: int, span: int) -> None:
        group = "V1"

        # V1.01 — Total μ/ρ sweep (Pb, Bi × 5 energies)
        checks = [(mat, Z, E) for mat, Z in _ELEMENT_Z.items() for E in _SAFE_ENERGIES]
        for i, (mat_id, Z, E) in enumerate(checks):
            if self._cancelled():
                return
            tid = f"V1-{mat_id}-{int(E)}keV"
            self._emit(base_pct, span, i / max(len(checks), 1), tid)

            ours = self._ms.get_mu_rho(mat_id, E)
            ref = self._xrl_cs_total(Z, E)
            if ref is None:
                self._add(tid, group, f"{mat_id} mu/rho @ {int(E)} keV",
                          ours, 0.0, 3.0, "xraylib unavailable", skipped=True)
            else:
                self._add(tid, group, f"{mat_id} mu/rho @ {int(E)} keV",
                          ours, ref, 3.0)

        # V1.02-05 — Densities
        density_checks = [("Pb", 82), ("W", 74), ("Al", 13), ("Cu", 29)]
        for mat_id, Z in density_checks:
            if self._cancelled():
                return
            tid = f"V1-density-{mat_id}"
            ours = self._ms.get_material(mat_id).density
            if _XRAYLIB_AVAILABLE:
                ref = _xrl.ElementDensity(Z)
                self._add(tid, group, f"{mat_id} density", ours, ref, 2.0)
            else:
                self._add(tid, group, f"{mat_id} density", ours, 0.0, 2.0,
                          "xraylib unavailable", skipped=True)

        # V1.06 — SS304 alloy mixture
        if _XRAYLIB_AVAILABLE:
            tid = "V1-SS304-200keV"
            ours = self._ms.get_mu_rho("SS304", 200.0)
            comp = [(26, 0.68), (24, 0.19), (28, 0.10), (25, 0.02), (14, 0.01)]
            ref = sum(w * _xrl.CS_Total(Z, 200.0) for Z, w in comp)
            self._add(tid, group, "SS304 alloy @ 200 keV (mixture rule)", ours, ref, 5.0)
        else:
            self._add("V1-SS304-200keV", group, "SS304 alloy @ 200 keV",
                      0.0, 0.0, 5.0, "xraylib unavailable", skipped=True)

        # V1.07 — Component sum
        for mat_id in ["Pb", "W", "Al"]:
            for E in [100.0, 300.0, 500.0]:
                if self._cancelled():
                    return
                tid = f"V1-compsum-{mat_id}-{int(E)}keV"
                total = self._ms.get_mu_rho(mat_id, E)
                pe = self._ms.get_photoelectric_mu_rho(mat_id, E)
                compt = self._ms.get_compton_mu_rho(mat_id, E)
                pp = self._ms.get_pair_production_mu_rho(mat_id, E)
                comp_sum = pe + compt + pp
                self._add(tid, group, f"{mat_id} component sum @ {int(E)} keV",
                          comp_sum, total, 5.0)

    # ------------------------------------------------------------------
    # V2: PhysicsEngine — HVL / TVL / attenuation
    # ------------------------------------------------------------------

    def _run_v2_physics(self, base_pct: int, span: int) -> None:
        group = "V2"

        # V2.01-02 — Linear μ = μ/ρ × ρ
        for i, (mat_id, E) in enumerate([("Pb", 200.0), ("W", 300.0)]):
            if self._cancelled():
                return
            tid = f"V2-linear-mu-{mat_id}-{int(E)}"
            self._emit(base_pct, span, i / 11, tid)
            mu_rho = self._ms.get_mu_rho(mat_id, E)
            rho = self._ms.get_material(mat_id).density
            expected = mu_rho * rho
            ours = self._pe.linear_attenuation(mat_id, E)
            self._add(tid, group, f"Linear mu {mat_id} @ {int(E)} keV",
                      ours, expected, 0.1)

        # V2.03-05 — HVL, TVL, MFP formulas
        mu = self._pe.linear_attenuation("Pb", 200.0)
        result = self._pe.calculate_hvl_tvl("Pb", 200.0)

        self._add("V2-HVL-Pb-200", group, "HVL = ln(2)/mu",
                  result.hvl_cm, math.log(2) / mu, 0.1)
        self._add("V2-TVL-Pb-200", group, "TVL = ln(10)/mu",
                  result.tvl_cm, math.log(10) / mu, 0.1)
        self._add("V2-MFP-Pb-200", group, "MFP = 1/mu",
                  result.mfp_cm, 1.0 / mu, 0.1)

        # V2.06 — TVL/HVL ratio = ln(10)/ln(2)
        ratio = result.tvl_cm / result.hvl_cm
        expected_ratio = math.log(10) / math.log(2)
        self._add("V2-TVL/HVL-ratio", group, "TVL/HVL = 3.3219",
                  ratio, expected_ratio, 0.01)

        # V2.07 — Single slab Beer-Lambert
        att = self._pe.calculate_slab_attenuation("Pb", 10.0, 200.0, include_buildup=False)
        expected_T = math.exp(-mu * 1.0)  # 10mm = 1cm
        self._add("V2-BeerLambert-Pb-10mm-200", group,
                  "Beer-Lambert 10mm Pb @ 200 keV",
                  att.transmission, expected_T, 0.1)

        # V2.08 — Multi-slab Beer-Lambert
        att_pb = self._pe.calculate_slab_attenuation("Pb", 5.0, 200.0, include_buildup=False)
        att_w = self._pe.calculate_slab_attenuation("W", 5.0, 200.0, include_buildup=False)
        mu_w = self._pe.linear_attenuation("W", 200.0)
        expected_T2 = math.exp(-mu * 0.5 - mu_w * 0.5)
        combined_T = att_pb.transmission * att_w.transmission
        self._add("V2-multilayer-PbW-200", group,
                  "Multi-slab 5mm Pb + 5mm W @ 200 keV",
                  combined_T, expected_T2, 0.1)

    # ------------------------------------------------------------------
    # V3: BuildUpFactors — ANSI reference values
    # ------------------------------------------------------------------

    def _run_v3_buildup(self, base_pct: int, span: int) -> None:
        group = "V3"

        # V3.01 — B(0 mfp) = 1.0
        for mat_id in ["Pb", "W", "Fe"]:
            B = self._bf.gp_buildup(1000.0, 0.0, mat_id)
            self._add(f"V3-zero-mfp-{mat_id}", group,
                      f"GP B(0) = 1.0 for {mat_id}", B, 1.0, 0.0)

        # V3.02 — GP B at 1 mfp vs ANSI
        B = self._bf.gp_buildup(1000.0, 1.0, "Pb")
        self._add("V3-GP-Pb-1MeV-1mfp", group,
                  "GP Pb 1 MeV 1 mfp vs ANSI", B, 1.24, 5.0)

        # V3.03 — GP vs ANSI table
        for i, ((mat_id, E_MeV, mfp), ref_B) in enumerate(_ANSI_BUILDUP.items()):
            if self._cancelled():
                return
            tid = f"V3-GP-{mat_id}-{E_MeV}MeV-{mfp}mfp"
            self._emit(base_pct, span, i / max(len(_ANSI_BUILDUP), 1), tid)
            B = self._bf.gp_buildup(E_MeV * 1000.0, float(mfp), mat_id)
            self._add(tid, group,
                      f"GP {mat_id} {E_MeV} MeV {mfp} mfp vs ANSI",
                      B, ref_B, 25.0)

        # V3.04 — Monotonic increase
        mfps = [0.1, 0.5, 1, 2, 5, 10, 15, 20]
        values = [self._bf.gp_buildup(1000.0, m, "Pb") for m in mfps]
        is_monotonic = all(values[i] >= values[i - 1] for i in range(1, len(values)))
        self._add("V3-monotonic-Pb", group, "GP B monotonically increases with mfp",
                  1.0 if is_monotonic else 0.0, 1.0, 0.0)

        # V3.05 — Low-Z higher buildup
        B_fe = self._bf.gp_buildup(1000.0, 5.0, "Fe")
        B_pb = self._bf.gp_buildup(1000.0, 5.0, "Pb")
        self._add("V3-lowZ-Fe>Pb", group, "B(Fe) > B(Pb) at same mfp",
                  1.0 if B_fe > B_pb else 0.0, 1.0, 0.0,
                  f"Fe={B_fe:.2f}, Pb={B_pb:.2f}")

        # V3.06 — GP and Taylor both positive
        for mat_id in ["Pb", "Fe"]:
            if not self._bf.has_taylor_data(mat_id):
                continue
            B_gp = self._bf.gp_buildup(1000.0, 5.0, mat_id)
            B_taylor = self._bf.taylor_buildup(1000.0, 5.0, mat_id)
            self._add(f"V3-GPvsTaylor-{mat_id}-5mfp", group,
                      f"GP and Taylor both B > 1 ({mat_id})",
                      1.0 if (B_gp > 1 and B_taylor > 1) else 0.0, 1.0, 0.0,
                      f"GP={B_gp:.2f}, Taylor={B_taylor:.2f}")

        # V3.07 — Taylor B(0) = 1.0
        for mat_id in ["Pb", "Fe"]:
            if not self._bf.has_taylor_data(mat_id):
                continue
            B = self._bf.taylor_buildup(1000.0, 0.0, mat_id)
            self._add(f"V3-Taylor-zero-{mat_id}", group,
                      f"Taylor B(0) = 1.0 ({mat_id})", B, 1.0, 1.0)

    # ------------------------------------------------------------------
    # V4: ComptonEngine — kinematics + KN
    # ------------------------------------------------------------------

    def _run_v4_compton(self, base_pct: int, span: int) -> None:
        group = "V4"
        pi = math.pi

        # V4.01 — Scattered energy vs xraylib.ComptonEnergy
        angle_energy_pairs = [
            (100.0, pi / 4), (100.0, pi / 2), (100.0, pi),
            (500.0, pi / 2), (1000.0, pi / 4), (1000.0, pi / 2),
            (1000.0, pi), (6000.0, pi / 2),
        ]
        for i, (E0, theta) in enumerate(angle_energy_pairs):
            if self._cancelled():
                return
            tid = f"V4-Escatter-{int(E0)}-{theta:.2f}"
            self._emit(base_pct, span, i / 40, tid)
            ours = self._ce.scattered_energy(E0, theta)
            if _XRAYLIB_AVAILABLE:
                ref = _xrl.ComptonEnergy(E0, theta)
                self._add(tid, group,
                          f"E' at E0={int(E0)} keV, theta={math.degrees(theta):.0f} deg",
                          ours, ref, 0.1)
            else:
                # Use analytical formula directly
                alpha = E0 / 511.0
                ref = E0 / (1.0 + alpha * (1.0 - math.cos(theta)))
                self._add(tid, group,
                          f"E' at E0={int(E0)} keV, theta={math.degrees(theta):.0f} deg",
                          ours, ref, 0.01)

        # V4.02 — Energy conservation
        for E0, theta in [(100.0, pi / 2), (1000.0, pi / 2), (6000.0, pi)]:
            E_prime = self._ce.scattered_energy(E0, theta)
            T = self._ce.recoil_electron_energy(E0, theta)
            self._add(f"V4-conservation-{int(E0)}", group,
                      f"E' + T = E0 ({int(E0)} keV)",
                      E_prime + T, E0, 0.0001)

        # V4.03 — Compton edge
        for E0 in [100.0, 511.0, 1000.0, 6000.0]:
            E_min, _ = self._ce.compton_edge(E0)
            alpha = E0 / 511.0
            expected = E0 / (1.0 + 2.0 * alpha)
            self._add(f"V4-edge-{int(E0)}", group,
                      f"Compton edge E'_min ({int(E0)} keV)",
                      E_min, expected, 0.1)

        # V4.04-05 — Wavelength shift
        self._add("V4-wavelength-90", group, "Wavelength shift at 90 deg = lambda_C",
                  self._ce.wavelength_shift(pi / 2),
                  self._ce.COMPTON_WAVELENGTH, 0.1)
        self._add("V4-wavelength-180", group, "Wavelength shift at 180 deg = 2*lambda_C",
                  self._ce.wavelength_shift(pi),
                  2.0 * self._ce.COMPTON_WAVELENGTH, 0.1)

        # V4.06 — KN differential vs xraylib.DCS_KN
        kn_points = [
            (100.0, 0.001), (100.0, pi / 4), (100.0, pi / 2), (100.0, pi),
            (500.0, pi / 2),
            (1000.0, 0.001), (1000.0, pi / 4), (1000.0, pi / 2), (1000.0, pi),
            (6000.0, pi / 4), (6000.0, pi / 2), (6000.0, pi),
        ]
        for E0, theta in kn_points:
            if self._cancelled():
                return
            tid = f"V4-DCS_KN-{int(E0)}-{theta:.2f}"
            ours = self._ce.klein_nishina_differential(E0, theta)
            if _XRAYLIB_AVAILABLE:
                ref = _xrl.DCS_KN(E0, theta) * 1e-24  # barn → cm²
                self._add(tid, group,
                          f"dσ/dΩ at E0={int(E0)}, theta={math.degrees(theta):.0f} deg",
                          ours, ref, 0.5)
            else:
                self._add(tid, group,
                          f"dσ/dΩ at E0={int(E0)}, theta={math.degrees(theta):.0f} deg",
                          ours, 0.0, 0.5, "xraylib unavailable", skipped=True)

        # V4.07 — KN total vs xraylib.CS_KN
        for E0 in [10.0, 100.0, 511.0, 1000.0, 2000.0, 6000.0]:
            if self._cancelled():
                return
            tid = f"V4-CS_KN-{int(E0)}"
            ours = self._ce.total_cross_section(E0)
            if _XRAYLIB_AVAILABLE:
                ref = _xrl.CS_KN(E0) * 1e-24  # barn → cm²
                self._add(tid, group,
                          f"σ_KN total at {int(E0)} keV", ours, ref, 0.5)
            else:
                self._add(tid, group,
                          f"σ_KN total at {int(E0)} keV",
                          ours, 0.0, 0.5, "xraylib unavailable", skipped=True)

        # V4.08 — Thomson limit
        sigma_kn = self._ce.total_cross_section(0.0001)
        sigma_t = self._ce.THOMSON_CROSS_SECTION
        self._add("V4-Thomson-limit", group, "σ_KN(E→0) → σ_Thomson",
                  sigma_kn, sigma_t, 0.1)

    # ------------------------------------------------------------------
    # V5: KleinNishinaSampler — statistical
    # ------------------------------------------------------------------

    def _run_v5_sampler(self, base_pct: int, span: int) -> None:
        from app.core.klein_nishina_sampler import KleinNishinaSampler

        group = "V5"
        rng = np.random.default_rng(42)
        sampler = KleinNishinaSampler(rng=rng)

        # V5.01 — Mean angle at 1 MeV (N=10K for speed)
        N = 10_000
        for E0 in [1000.0, 6000.0]:
            if self._cancelled():
                return
            tid = f"V5-mean-angle-{int(E0)}"
            self._emit(base_pct, span, 0.3 if E0 == 1000 else 0.6, tid)

            thetas = np.array([sampler.sample_compton_angle(E0)[0] for _ in range(N)])
            sample_mean = float(np.mean(thetas))
            analytical_mean = self._analytical_mean_angle(E0)
            self._add(tid, group,
                      f"Mean angle at {int(E0)} keV (N={N})",
                      sample_mean, analytical_mean, 3.0)

        # V5.02 — Energy bounds
        E0 = 1000.0
        E_min, _ = self._ce.compton_edge(E0)
        all_ok = True
        for _ in range(5000):
            _, _, E_sc = sampler.sample_compton_angle(E0)
            if E_sc > E0 + 1e-6 or E_sc < E_min - 1e-6:
                all_ok = False
                break
        self._add("V5-energy-bounds", group, "All E' within [E'_min, E0]",
                  1.0 if all_ok else 0.0, 1.0, 0.0)

        # V5.03 — Angle bounds
        all_ok = True
        for _ in range(5000):
            theta, phi, _ = sampler.sample_compton_angle(E0)
            if theta < -1e-10 or theta > math.pi + 1e-10:
                all_ok = False
                break
            if phi < -1e-10 or phi > 2 * math.pi + 1e-10:
                all_ok = False
                break
        self._add("V5-angle-bounds", group, "All theta in [0,pi], phi in [0,2pi]",
                  1.0 if all_ok else 0.0, 1.0, 0.0)

    def _analytical_mean_angle(self, E0_keV: float, n_bins: int = 1000) -> float:
        thetas = np.linspace(0, math.pi, n_bins)
        dtheta = thetas[1] - thetas[0]
        weights = np.array([
            self._ce.klein_nishina_differential(E0_keV, float(th)) * math.sin(float(th))
            for th in thetas
        ])
        normalizer = np.sum(weights) * dtheta
        return float(np.sum(weights * thetas) * dtheta / normalizer)

    # ------------------------------------------------------------------
    # V6: Beam Simulation — analytical slab
    # ------------------------------------------------------------------

    def _run_v6_beam(self, base_pct: int, span: int) -> None:
        group = "V6"

        # V6.01 — Single slab
        tid = "V6-slab-Pb-10mm-200"
        self._emit(base_pct, span, 0.0, tid)
        result = self._pe.calculate_slab_attenuation("Pb", 10.0, 200.0, include_buildup=False)
        mu = self._pe.linear_attenuation("Pb", 200.0)
        expected = math.exp(-mu * 1.0)
        self._add(tid, group, "10mm Pb @ 200 keV", result.transmission, expected, 0.1)

        # V6.02 — Multi-slab
        att_pb = self._pe.calculate_slab_attenuation("Pb", 5.0, 200.0, include_buildup=False)
        att_w = self._pe.calculate_slab_attenuation("W", 5.0, 200.0, include_buildup=False)
        mu_w = self._pe.linear_attenuation("W", 200.0)
        expected2 = math.exp(-mu * 0.5 - mu_w * 0.5)
        combined_T = att_pb.transmission * att_w.transmission
        self._add("V6-multi-PbW-200", group, "5mm Pb + 5mm W @ 200 keV",
                  combined_T, expected2, 0.1)

        # V6.03 — Thick slab near zero
        result3 = self._pe.calculate_slab_attenuation("Pb", 100.0, 100.0, include_buildup=False)
        self._add("V6-thick-Pb-100mm", group, "100mm Pb @ 100 keV -> T ~ 0",
                  1.0 if result3.transmission < 1e-30 else 0.0, 1.0, 0.0)

        # V6.04 — At HVL -> T = 0.5
        hvl_result = self._pe.calculate_hvl_tvl("Pb", 200.0)
        hvl_mm = hvl_result.hvl_cm * 10.0
        att_hvl = self._pe.calculate_slab_attenuation("Pb", hvl_mm, 200.0, include_buildup=False)
        self._add("V6-at-HVL", group, "T at HVL = 0.5",
                  att_hvl.transmission, 0.5, 0.1)

        # V6.05 — At TVL -> T = 0.1
        tvl_mm = hvl_result.tvl_cm * 10.0
        att_tvl = self._pe.calculate_slab_attenuation("Pb", tvl_mm, 200.0, include_buildup=False)
        self._add("V6-at-TVL", group, "T at TVL = 0.1",
                  att_tvl.transmission, 0.1, 0.1)

        self._progress(99, "V6 complete")
