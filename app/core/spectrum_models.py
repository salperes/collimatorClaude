"""Spectrum models — kVp bremsstrahlung and MeV approximations.

Simple analytical models for initial design calculations.
Full spectrum modelling (beam hardening, flattening filter) is out of scope.

Reference: FRD §7.3, docs/phase-02-physics-engine.md §kVp Spektrum Modeli.
"""

import numpy as np


def kramers_spectrum(
    kVp: float,
    num_bins: int = 100,
    Z: float = 74.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Kramers (unfiltered) bremsstrahlung spectrum approximation.

    Φ(E) ∝ Z × (E_max - E) / E

    Args:
        kVp: Tube voltage [kVp], used as E_max in keV.
        num_bins: Number of energy bins.
        Z: Target atomic number (default: W = 74).

    Returns:
        (energies_keV, phi) — energy bin centers [keV] and relative intensity.
        Normalized so that sum(phi) = 1.
    """
    E_min = max(1.0, kVp * 0.01)  # Avoid zero; start at 1% of kVp
    energies = np.linspace(E_min, kVp * 0.99, num_bins)
    phi = Z * (kVp - energies) / energies
    phi = np.maximum(phi, 0.0)

    total = phi.sum()
    if total > 0:
        phi /= total

    return energies, phi


def effective_energy_kVp(kVp: float, filtered: bool = False) -> float:
    """Effective (average) energy for a kVp bremsstrahlung source.

    Args:
        kVp: Tube voltage [kVp].
        filtered: If *True*, assumes Al filtration (E_avg ≈ kVp/2.5).

    Returns:
        Effective energy [keV].
    """
    if filtered:
        return kVp / 2.5
    return kVp / 3.0


def monoenergetic_energy_MeV(endpoint_MeV: float) -> float:
    """Approximate effective energy for a MeV linac source.

    For bremsstrahlung endpoint, E_avg ≈ endpoint/3.
    First approximation; real spectrum depends on target and filters.

    Args:
        endpoint_MeV: Bremsstrahlung endpoint energy [MeV].

    Returns:
        Approximate effective energy [MeV].
    """
    return endpoint_MeV / 3.0
