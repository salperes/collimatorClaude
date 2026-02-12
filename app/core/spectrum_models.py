"""Spectrum models — realistic X-ray tube spectrum with filtration.

Generates bremsstrahlung continuum (Kramers), adds characteristic X-ray
peaks (Ka, Kb), and applies Beer-Lambert filtration through tube window
(glass or beryllium) and optional added filters (Al, Cu, etc.).

Supports multiple target materials: W, Mo, Rh, Cu, Ag.

All internal computations in core units: cm, keV.

Reference: FRD §7.3, docs/phase-02-physics-engine.md §kVp Spektrum Modeli.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from app.core.units import mm_to_cm

if TYPE_CHECKING:
    from app.core.material_database import MaterialService


# ── Target Data ─────────────────────────────────────────────────────

@dataclass
class CharLine:
    """A single characteristic X-ray emission line."""
    name: str
    energy_keV: float
    relative_intensity: float


@dataclass
class XRayTarget:
    """X-ray tube target material properties."""
    symbol: str
    Z: int
    name: str
    k_edge_keV: float
    density_gcm3: float
    char_lines: list[CharLine] = field(default_factory=list)


def _load_targets(
    data_path: str | pathlib.Path | None = None,
) -> dict[str, XRayTarget]:
    """Load target database from xray_targets.json.

    Args:
        data_path: Path to xray_targets.json.  Auto-detected if None.

    Returns:
        Dict mapping target symbol to XRayTarget.
    """
    if data_path is None:
        data_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "data"
            / "xray_targets.json"
        )
    data_path = pathlib.Path(data_path)

    with open(data_path, encoding="utf-8") as f:
        raw = json.load(f)

    targets: dict[str, XRayTarget] = {}
    for symbol, info in raw["targets"].items():
        lines = [
            CharLine(
                name=cl["name"],
                energy_keV=cl["energy_keV"],
                relative_intensity=cl["relative_intensity"],
            )
            for cl in info["char_lines"]
        ]
        targets[symbol] = XRayTarget(
            symbol=symbol,
            Z=info["Z"],
            name=info["name"],
            k_edge_keV=info["k_edge_keV"],
            density_gcm3=info["density_gcm3"],
            char_lines=lines,
        )
    return targets


# Module-level cache (loaded once)
_TARGETS: dict[str, XRayTarget] | None = None


def _get_targets() -> dict[str, XRayTarget]:
    global _TARGETS
    if _TARGETS is None:
        _TARGETS = _load_targets()
    return _TARGETS


# ── Tube Configuration ──────────────────────────────────────────────

@dataclass
class TubeConfig:
    """X-ray tube configuration for spectrum generation.

    Attributes:
        target_id: Target material symbol ("W", "Mo", "Rh", "Cu", "Ag").
        kVp: Tube voltage [kVp], used as E_max.
        window_type: Tube window type — "glass", "Be", or "none".
        window_thickness_mm: Window thickness [mm].
            Glass: Al-equivalent thickness (default 1.0 mm).
            Be: actual beryllium thickness (default 0.5 mm).
        added_filtration: List of (material_id, thickness_mm) tuples
            for added external filters.  Example: [("Al", 2.5)].
    """
    target_id: str = "W"
    kVp: float = 120.0
    window_type: str = "glass"
    window_thickness_mm: float = 1.0
    added_filtration: list[tuple[str, float]] = field(default_factory=list)


# ── Spectrum Generator ──────────────────────────────────────────────

class XRaySpectrum:
    """Realistic X-ray tube spectrum generator.

    Combines Kramers bremsstrahlung with characteristic X-ray peaks,
    then applies Beer-Lambert filtration through the tube window and
    any added filters using MaterialService for mu/rho lookups.

    Args:
        material_service: Material database for mu/rho lookups.
    """

    def __init__(self, material_service: MaterialService) -> None:
        self._materials = material_service
        self._targets = _get_targets()

    def available_targets(self) -> list[str]:
        """Return available target material symbols."""
        return list(self._targets.keys())

    def get_target(self, target_id: str) -> XRayTarget:
        """Return target info by symbol.

        Raises:
            KeyError: If target_id not found.
        """
        return self._targets[target_id]

    def generate(
        self,
        config: TubeConfig,
        num_bins: int = 200,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Generate a filtered X-ray tube spectrum.

        Pipeline:
          1. Kramers bremsstrahlung continuum
          2. + Characteristic lines (Gaussian peaks, if kVp > K-edge)
          3. x Window filtration (Beer-Lambert)
          4. x Added filtration (Beer-Lambert)
          5. Normalize so sum(phi) = 1

        Args:
            config: Tube configuration.
            num_bins: Number of energy bins.

        Returns:
            (energies_keV, phi) — bin centers [keV] and normalized intensities.
        """
        target = self._targets[config.target_id]
        kVp = config.kVp

        # Energy grid: start slightly above 0, end just below kVp
        E_min = max(1.0, kVp * 0.01)
        E_max = kVp * 0.999
        if E_max <= E_min:
            return (
                np.array([E_min], dtype=np.float64),
                np.array([1.0], dtype=np.float64),
            )
        energies = np.linspace(E_min, E_max, num_bins)

        # Step 1: Kramers bremsstrahlung continuum
        phi = float(target.Z) * (kVp - energies) / energies
        phi = np.maximum(phi, 0.0)

        # Step 2: Add characteristic lines (if kVp exceeds K-edge)
        if kVp > target.k_edge_keV and target.char_lines:
            phi = self._add_characteristic_peaks(phi, energies, target, kVp)

        # Step 3: Window filtration
        phi = self._apply_filtration(
            phi, energies, config.window_type, config.window_thickness_mm,
        )

        # Step 4: Added filtration
        for mat_id, thickness_mm in config.added_filtration:
            phi = self._apply_material_filter(
                phi, energies, mat_id, thickness_mm,
            )

        # Step 5: Normalize
        phi = np.maximum(phi, 0.0)
        total = phi.sum()
        if total > 0:
            phi /= total

        return energies, phi

    def generate_unfiltered(
        self,
        config: TubeConfig,
        num_bins: int = 200,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        """Generate raw (unfiltered) spectrum for comparison.

        Only Kramers + characteristic lines, no filtration applied.

        Args:
            config: Tube configuration (only target_id and kVp used).
            num_bins: Number of energy bins.

        Returns:
            (energies_keV, phi) — normalized.
        """
        target = self._targets[config.target_id]
        kVp = config.kVp

        E_min = max(1.0, kVp * 0.01)
        E_max = kVp * 0.999
        if E_max <= E_min:
            return (
                np.array([E_min], dtype=np.float64),
                np.array([1.0], dtype=np.float64),
            )
        energies = np.linspace(E_min, E_max, num_bins)

        phi = float(target.Z) * (kVp - energies) / energies
        phi = np.maximum(phi, 0.0)

        if kVp > target.k_edge_keV and target.char_lines:
            phi = self._add_characteristic_peaks(phi, energies, target, kVp)

        total = phi.sum()
        if total > 0:
            phi /= total
        return energies, phi

    def effective_energy(
        self, config: TubeConfig, num_bins: int = 200,
    ) -> float:
        """Weighted mean energy of the filtered spectrum [keV].

        E_eff = sum(E_i * phi_i) / sum(phi_i)

        Args:
            config: Tube configuration.
            num_bins: Number of energy bins for spectrum generation.

        Returns:
            Effective energy [keV].
        """
        energies, phi = self.generate(config, num_bins=num_bins)
        total = phi.sum()
        if total <= 0:
            return config.kVp / 3.0
        return float(np.sum(energies * phi) / total)

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _add_characteristic_peaks(
        phi: NDArray[np.float64],
        energies: NDArray[np.float64],
        target: XRayTarget,
        kVp: float,
    ) -> NDArray[np.float64]:
        """Add characteristic X-ray peaks as Gaussians.

        Characteristic radiation fraction increases with overvoltage
        (kVp relative to K-edge).

        Args:
            phi: Current spectrum array (copied, not modified in-place).
            energies: Energy bin centers [keV].
            target: Target material info.
            kVp: Tube voltage [kVp].

        Returns:
            New phi with characteristic peaks added.
        """
        # Overvoltage ratio determines characteristic yield
        overvoltage = kVp / target.k_edge_keV
        # Empirical: char_fraction ~ 0.5 * (1 - 1/overvoltage), capped
        char_fraction = min(0.5, 0.5 * (1.0 - 1.0 / overvoltage))

        if char_fraction <= 0:
            return phi

        brem_max = float(np.max(phi)) if np.max(phi) > 0 else 1.0
        char_scale = char_fraction * brem_max

        # Gaussian sigma: ~0.15 keV (broader than natural line width)
        bin_width = (energies[-1] - energies[0]) / max(1, len(energies) - 1)
        sigma = max(0.15, bin_width * 0.5)

        result = phi.copy()
        for line in target.char_lines:
            if line.energy_keV >= kVp:
                continue
            gaussian = (
                char_scale
                * line.relative_intensity
                * np.exp(-0.5 * ((energies - line.energy_keV) / sigma) ** 2)
            )
            result = result + gaussian

        return result

    def _apply_filtration(
        self,
        phi: NDArray[np.float64],
        energies: NDArray[np.float64],
        window_type: str,
        thickness_mm: float,
    ) -> NDArray[np.float64]:
        """Apply tube window filtration.

        Glass window is modeled as aluminum-equivalent.
        Be window uses actual beryllium attenuation.

        Args:
            phi: Spectrum intensities.
            energies: Energy bin centers [keV].
            window_type: "glass", "Be", or "none".
            thickness_mm: Window thickness [mm].

        Returns:
            Filtered spectrum.
        """
        if window_type == "none" or thickness_mm <= 0:
            return phi

        if window_type == "glass":
            mat_id = "Al"
        elif window_type == "Be":
            mat_id = "Be"
        else:
            return phi

        return self._apply_material_filter(phi, energies, mat_id, thickness_mm)

    def _apply_material_filter(
        self,
        phi: NDArray[np.float64],
        energies: NDArray[np.float64],
        material_id: str,
        thickness_mm: float,
    ) -> NDArray[np.float64]:
        """Apply Beer-Lambert filtration for a single material layer.

        I(E) = I_0(E) * exp(-mu(E) * thickness)
        where mu(E) = (mu/rho)(E) * rho  [cm^-1]

        Args:
            phi: Spectrum intensities.
            energies: Energy bin centers [keV].
            material_id: Filter material (must exist in MaterialService).
            thickness_mm: Filter thickness [mm].

        Returns:
            Filtered spectrum.
        """
        if thickness_mm <= 0:
            return phi

        thickness_cm = mm_to_cm(thickness_mm)
        density = self._materials.get_material(material_id).density

        mu_rho = np.array([
            self._materials.get_mu_rho(material_id, float(E))
            for E in energies
        ])
        mu_linear = mu_rho * density
        transmission = np.exp(-mu_linear * thickness_cm)

        return phi * transmission


# ── Legacy API (backward-compatible, no MaterialService needed) ─────


def kramers_spectrum(
    kVp: float,
    num_bins: int = 100,
    Z: float = 74.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Kramers (unfiltered) bremsstrahlung spectrum approximation.

    Phi(E) proportional to Z * (E_max - E) / E

    Args:
        kVp: Tube voltage [kVp], used as E_max in keV.
        num_bins: Number of energy bins.
        Z: Target atomic number (default: W = 74).

    Returns:
        (energies_keV, phi) — energy bin centers [keV] and relative intensity.
        Normalized so that sum(phi) = 1.
    """
    E_min = max(1.0, kVp * 0.01)
    energies = np.linspace(E_min, kVp * 0.99, num_bins)
    phi = Z * (kVp - energies) / energies
    phi = np.maximum(phi, 0.0)

    total = phi.sum()
    if total > 0:
        phi /= total

    return energies, phi


def effective_energy_kVp(kVp: float, filtered: bool = False) -> float:
    """Effective (average) energy for a kVp bremsstrahlung source.

    Quick approximation — does not use full spectrum model.

    Args:
        kVp: Tube voltage [kVp].
        filtered: If *True*, assumes Al filtration (E_avg ~ kVp/2.5).

    Returns:
        Effective energy [keV].
    """
    if filtered:
        return kVp / 2.5
    return kVp / 3.0


def monoenergetic_energy_MeV(endpoint_MeV: float) -> float:
    """Approximate effective energy for a MeV linac source.

    For bremsstrahlung endpoint, E_avg ~ endpoint/3.

    Args:
        endpoint_MeV: Bremsstrahlung endpoint energy [MeV].

    Returns:
        Approximate effective energy [MeV].
    """
    return endpoint_MeV / 3.0
