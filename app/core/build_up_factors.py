"""Build-up factor calculations — GP and Taylor formulas.

Loads fitting parameters from ``buildup_coefficients.json`` and evaluates
Geometric Progression (GP) and Taylor two-term exponential build-up
factors for gamma-ray shielding calculations.

All energies in keV (core units).  Penetration depth in mfp (dimensionless).

Reference:
    ANSI/ANS-6.4.3-1991, Harima (1983), Taylor (1954).
"""

import json
import logging
import math
import pathlib

import numpy as np

logger = logging.getLogger(__name__)

# Alloys/compounds without dedicated buildup data → nearest parent element.
# SS304/SS316 are iron-based stainless steels; Bronze is copper-based;
# Beryllium (Z=4) has no published GP/Taylor data — use Al (Z=13) as
# closest available low-Z surrogate.
_BUILDUP_FALLBACK: dict[str, str] = {
    "SS304": "Fe",
    "SS316": "Fe",
    "Bronze": "Cu",
    "Be": "Al",
}


class BuildUpFactors:
    """Build-up factor service using GP and Taylor fitting formulas.

    Args:
        coefficients_path: Path to ``buildup_coefficients.json``.  If *None*,
            auto-detected relative to the project root.
    """

    def __init__(
        self,
        coefficients_path: str | pathlib.Path | None = None,
    ) -> None:
        if coefficients_path is None:
            coefficients_path = (
                pathlib.Path(__file__).resolve().parents[2]
                / "buildup_coefficients.json"
            )
        self._path = pathlib.Path(coefficients_path)
        self._data: dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def gp_buildup(
        self,
        energy_keV: float,
        mfp: float,
        material_id: str,
    ) -> float:
        """Geometric Progression build-up factor.

        B(E, x) = 1 + (b-1)(K^x - 1)/(K - 1)  for K ≠ 1
        B(E, x) = 1 + (b-1)x                     for K ≈ 1

        K(x) = c·x^a + d·[tanh(x/Xk - 2) - tanh(-2)] / [1 - tanh(-2)]

        Args:
            energy_keV: Photon energy [keV].
            mfp: Penetration depth [mean free paths, dimensionless].
            material_id: Material identifier (e.g. "Pb", "W", "Fe").

        Returns:
            Build-up factor B [dimensionless, ≥ 1].
        """
        if mfp <= 0:
            return 1.0

        params = self._interpolate_gp_params(material_id, energy_keV)
        b = params["b"]
        c = params["c"]
        a = params["a"]
        Xk = params["Xk"]
        d = params["d"]

        # K(x) calculation
        tanh_neg2 = math.tanh(-2.0)
        denom_tanh = 1.0 - tanh_neg2
        if denom_tanh == 0:
            denom_tanh = 1e-30

        # Guard against x^a when x is very small and a is negative
        if mfp > 0 and a != 0:
            x_pow_a = mfp ** a
        else:
            x_pow_a = 1.0

        K = c * x_pow_a + d * (math.tanh(mfp / max(Xk, 1e-10) - 2.0) - tanh_neg2) / denom_tanh

        # B(E, x) calculation
        if abs(K - 1.0) < 1e-6:
            B = 1.0 + (b - 1.0) * mfp
        else:
            K_pow_x = K ** mfp
            B = 1.0 + (b - 1.0) * (K_pow_x - 1.0) / (K - 1.0)

        return max(B, 1.0)

    def taylor_buildup(
        self,
        energy_keV: float,
        mfp: float,
        material_id: str,
    ) -> float:
        """Taylor two-term exponential build-up factor.

        B(E, x) = A1·exp(-α₁·x) + (1 - A1)·exp(-α₂·x)

        Args:
            energy_keV: Photon energy [keV].
            mfp: Penetration depth [mean free paths, dimensionless].
            material_id: Material identifier.

        Returns:
            Build-up factor B [dimensionless, ≥ 1].

        Raises:
            ValueError: If Taylor parameters are not available for *material_id*.
        """
        if mfp <= 0:
            return 1.0

        params = self._interpolate_taylor_params(material_id, energy_keV)
        A1 = params["A1"]
        alpha1 = params["alpha1"]
        alpha2 = params["alpha2"]

        B = A1 * math.exp(-alpha1 * mfp) + (1.0 - A1) * math.exp(-alpha2 * mfp)
        return max(B, 1.0)

    def get_multilayer_buildup(
        self,
        layers_mfp: list[tuple[str, float]],
        energy_keV: float,
        method: str = "last_material",
    ) -> float:
        """Multi-layer composite build-up factor.

        Args:
            layers_mfp: List of (material_id, mfp) pairs for each layer.
            energy_keV: Photon energy [keV].
            method: Calculation method:
                - ``"last_material"``: Last material's B at total mfp (conservative).
                - ``"kalos"``: B_total = ∏ Bᵢ(mfpᵢ).

        Returns:
            Composite build-up factor [dimensionless, ≥ 1].
        """
        if not layers_mfp:
            return 1.0

        total_mfp = sum(m for _, m in layers_mfp)
        if total_mfp <= 0:
            return 1.0

        if method == "last_material":
            last_mat = layers_mfp[-1][0]
            return self.gp_buildup(energy_keV, total_mfp, last_mat)

        elif method == "kalos":
            B_total = 1.0
            for mat_id, layer_mfp in layers_mfp:
                if layer_mfp > 0:
                    B_total *= self.gp_buildup(energy_keV, layer_mfp, mat_id)
            return max(B_total, 1.0)

        else:
            raise ValueError(f"Unknown buildup method: {method!r}")

    def has_gp_data(self, material_id: str) -> bool:
        """Check if GP parameters are available for a material (incl. fallback)."""
        try:
            resolved = self._resolve_material(material_id)
        except ValueError:
            return False
        mat = self._data.get("materials", {}).get(resolved, {})
        return len(mat.get("gp_parameters", {}).get("data", [])) > 0

    def has_taylor_data(self, material_id: str) -> bool:
        """Check if Taylor parameters are available for a material (incl. fallback)."""
        try:
            resolved = self._resolve_material(material_id)
        except ValueError:
            return False
        mat = self._data.get("materials", {}).get(resolved, {})
        return len(mat.get("taylor_parameters", {}).get("data", [])) > 0

    # ------------------------------------------------------------------
    # Internal — parameter interpolation
    # ------------------------------------------------------------------

    def _resolve_material(self, material_id: str) -> str:
        """Resolve alloy material_id to parent element via fallback map."""
        if material_id in self._data.get("materials", {}):
            return material_id
        resolved = _BUILDUP_FALLBACK.get(material_id)
        if resolved and resolved in self._data.get("materials", {}):
            logger.debug(
                "Buildup fallback: %s → %s", material_id, resolved,
            )
            return resolved
        raise ValueError(f"No buildup data for material: {material_id!r}")

    def _interpolate_gp_params(
        self,
        material_id: str,
        energy_keV: float,
    ) -> dict[str, float]:
        """Interpolate GP parameters at arbitrary energy via log interpolation."""
        resolved_id = self._resolve_material(material_id)
        mat = self._data["materials"][resolved_id]

        gp_data = mat.get("gp_parameters", {}).get("data", [])
        if not gp_data:
            raise ValueError(f"No GP parameters for material: {material_id!r}")

        energy_MeV = energy_keV / 1000.0
        energies = np.array([p["energy_MeV"] for p in gp_data])

        # Clamp to data range
        energy_MeV = np.clip(energy_MeV, energies[0], energies[-1])
        log_E = np.log(energies)
        log_q = np.log(energy_MeV)

        result = {}
        for param_name in ("b", "c", "a", "Xk", "d"):
            values = np.array([p[param_name] for p in gp_data])
            result[param_name] = float(np.interp(log_q, log_E, values))

        return result

    def _interpolate_taylor_params(
        self,
        material_id: str,
        energy_keV: float,
    ) -> dict[str, float]:
        """Interpolate Taylor parameters at arbitrary energy."""
        resolved_id = self._resolve_material(material_id)
        mat = self._data["materials"][resolved_id]

        taylor_data = mat.get("taylor_parameters", {}).get("data", [])
        if not taylor_data:
            raise ValueError(
                f"No Taylor parameters for material: {material_id!r}"
            )

        energy_MeV = energy_keV / 1000.0
        energies = np.array([p["energy_MeV"] for p in taylor_data])

        energy_MeV = np.clip(energy_MeV, energies[0], energies[-1])
        log_E = np.log(energies)
        log_q = np.log(energy_MeV)

        result = {}
        for param_name in ("A1", "alpha1", "alpha2"):
            values = np.array([p[param_name] for p in taylor_data])
            result[param_name] = float(np.interp(log_q, log_E, values))

        return result

    # ------------------------------------------------------------------
    # Internal — data loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load buildup coefficients JSON."""
        with open(self._path, encoding="utf-8") as f:
            self._data = json.load(f)
