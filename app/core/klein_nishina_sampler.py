"""Klein-Nishina angular sampling via Kahn rejection algorithm.

Samples Compton scattering angles weighted by the Klein-Nishina
differential cross-section. Uses numpy.random for reproducible RNG.

All energies in keV, angles in radian (core units).

Reference: Phase-07 spec — Kahn Algorithm.
"""

from __future__ import annotations

import math

import numpy as np

from app.core.compton_engine import ComptonEngine

# Rest mass of electron [keV]
_ELECTRON_MASS_KEV = 511.0


class KleinNishinaSampler:
    """Samples Compton scattering angles using the Kahn rejection algorithm.

    The Kahn algorithm is an efficient rejection sampling method that
    generates angles from the Klein-Nishina distribution without
    requiring numerical inversion of the CDF.

    Args:
        rng: numpy random Generator instance (for reproducibility in tests).
             If None, creates a default unseeded generator.
    """

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self._rng = rng or np.random.default_rng()
        self._compton = ComptonEngine()

    @property
    def rng(self) -> np.random.Generator:
        """Access the random number generator."""
        return self._rng

    def sample_compton_angle(
        self, energy_keV: float,
    ) -> tuple[float, float, float]:
        """Sample a single Compton scattering event using Kahn algorithm.

        Args:
            energy_keV: Incident photon energy [keV].

        Returns:
            (theta_rad, phi_rad, E_scattered_keV):
            - theta_rad: Polar scattering angle [radian, 0..π].
            - phi_rad: Azimuthal angle [radian, 0..2π] (isotropic).
            - E_scattered_keV: Scattered photon energy [keV].
        """
        alpha = energy_keV / _ELECTRON_MASS_KEV
        rng = self._rng

        while True:
            r1 = rng.random()
            r2 = rng.random()
            r3 = rng.random()

            if r1 <= (1.0 + 2.0 * alpha) / (9.0 + 2.0 * alpha):
                # Low-energy branch
                xi = 1.0 + 2.0 * alpha * r2
                if r3 <= 4.0 * (1.0 / xi - 1.0 / (xi * xi)):
                    break
            else:
                # High-energy branch
                xi = (1.0 + 2.0 * alpha) / (1.0 + 2.0 * alpha * r2)
                cos_theta = 1.0 - (xi - 1.0) / alpha
                if r3 <= 0.5 * (cos_theta * cos_theta + 1.0 / xi):
                    break

        cos_theta = 1.0 - (xi - 1.0) / alpha
        # Numerical guard: clamp to [-1, 1]
        cos_theta = max(-1.0, min(1.0, cos_theta))
        theta = math.acos(cos_theta)
        E_scattered = energy_keV / xi
        phi = 2.0 * math.pi * rng.random()

        return theta, phi, E_scattered

    def sample_batch(
        self, energy_keV: float, n: int,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Sample N Compton scattering events.

        Useful for benchmarking and statistical validation.

        Args:
            energy_keV: Incident photon energy [keV].
            n: Number of samples.

        Returns:
            (thetas, phis, energies) — numpy arrays of length n.
            thetas [radian], phis [radian], energies [keV].
        """
        thetas = np.empty(n)
        phis = np.empty(n)
        energies = np.empty(n)

        for i in range(n):
            thetas[i], phis[i], energies[i] = self.sample_compton_angle(energy_keV)

        return thetas, phis, energies

    def mean_angle_analytic(self, energy_keV: float, n_bins: int = 1000) -> float:
        """Compute the analytic mean scattering angle via numerical integration.

        <θ> = ∫ θ × (dσ/dΩ) × sin(θ) dθ  /  ∫ (dσ/dΩ) × sin(θ) dθ

        Used for BM-8.1 validation: compare sampled mean to this value.

        Args:
            energy_keV: Incident photon energy [keV].
            n_bins: Numerical integration resolution.

        Returns:
            Mean scattering angle [radian].
        """
        thetas = np.linspace(0, math.pi, n_bins)
        dsigma = np.array([
            self._compton.klein_nishina_differential(energy_keV, float(t))
            for t in thetas
        ])
        sin_theta = np.sin(thetas)
        weights = dsigma * sin_theta
        d_theta = thetas[1] - thetas[0]

        numerator = np.sum(thetas * weights) * d_theta
        denominator = np.sum(weights) * d_theta

        return float(numerator / denominator) if denominator > 0 else 0.0
