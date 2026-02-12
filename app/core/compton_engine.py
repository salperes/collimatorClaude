"""Compton scattering engine — Klein-Nishina, kinematics, cross-sections.

All energies in keV, angles in radians (core units).

Reference: FRD §5.4, §7.6.1–7.6.3, docs/phase-02-physics-engine.md.
"""

import math

import numpy as np

from app.models.results import (
    AngleEnergyMapResult,
    ComptonSpectrumResult,
    CrossSectionResult,
    KleinNishinaResult,
)


class ComptonEngine:
    """Analytical Compton scattering calculations.

    Provides Compton kinematics, Klein-Nishina differential and total
    cross-sections, and angular/energy distributions.
    """

    # Physical constants
    ELECTRON_MASS_KEV: float = 511.0
    CLASSICAL_ELECTRON_RADIUS: float = 2.818e-13  # r₀ [cm]
    COMPTON_WAVELENGTH: float = 0.02426  # λ_C [Angstrom]
    THOMSON_CROSS_SECTION: float = 6.6524e-25  # σ_T [cm²]

    def scattered_energy(self, E0_keV: float, theta_rad: float) -> float:
        """Scattered photon energy after Compton scattering.

        E' = E₀ / [1 + (E₀/511)(1 - cos θ)]

        Args:
            E0_keV: Incident photon energy [keV].
            theta_rad: Scattering angle [radian].

        Returns:
            E' scattered photon energy [keV].
        """
        alpha = E0_keV / self.ELECTRON_MASS_KEV
        return E0_keV / (1.0 + alpha * (1.0 - math.cos(theta_rad)))

    def recoil_electron_energy(self, E0_keV: float, theta_rad: float) -> float:
        """Recoil electron kinetic energy.

        T = E₀ - E'

        Args:
            E0_keV: Incident photon energy [keV].
            theta_rad: Scattering angle [radian].

        Returns:
            T recoil electron energy [keV].
        """
        return E0_keV - self.scattered_energy(E0_keV, theta_rad)

    def compton_edge(self, E0_keV: float) -> tuple[float, float]:
        """Compton edge — maximum energy transfer (θ = 180°).

        Returns:
            (E'_min, T_max) — minimum scattered energy and maximum recoil energy [keV].
        """
        alpha = E0_keV / self.ELECTRON_MASS_KEV
        E_prime_min = E0_keV / (1.0 + 2.0 * alpha)
        T_max = E0_keV * 2.0 * alpha / (1.0 + 2.0 * alpha)
        return E_prime_min, T_max

    def wavelength_shift(self, theta_rad: float) -> float:
        """Compton wavelength shift.

        Δλ = λ_C × (1 - cos θ) [Angstrom]

        Args:
            theta_rad: Scattering angle [radian].

        Returns:
            Δλ wavelength shift [Angstrom].
        """
        return self.COMPTON_WAVELENGTH * (1.0 - math.cos(theta_rad))

    def klein_nishina_differential(
        self,
        E0_keV: float,
        theta_rad: float,
    ) -> float:
        """Klein-Nishina differential cross-section.

        dσ/dΩ = (r₀²/2) × (E'/E₀)² × [E'/E₀ + E₀/E' - sin²θ]

        Args:
            E0_keV: Incident photon energy [keV].
            theta_rad: Scattering angle [radian].

        Returns:
            dσ/dΩ [cm²/sr/electron].
        """
        r0 = self.CLASSICAL_ELECTRON_RADIUS
        E_prime = self.scattered_energy(E0_keV, theta_rad)
        ratio = E_prime / E0_keV
        sin2_theta = math.sin(theta_rad) ** 2

        return (r0 ** 2 / 2.0) * ratio ** 2 * (ratio + 1.0 / ratio - sin2_theta)

    def total_cross_section(self, E0_keV: float) -> float:
        """Total Klein-Nishina cross-section (analytical).

        σ_KN = 2πr₀² { [(1+a)/a²][2(1+a)/(1+2a) - ln(1+2a)/a]
                        + ln(1+2a)/(2a) - (1+3a)/(1+2a)² }

        where a = E₀/m_e c²

        Args:
            E0_keV: Incident photon energy [keV].

        Returns:
            σ_KN [cm²/electron].
        """
        r0 = self.CLASSICAL_ELECTRON_RADIUS
        a = E0_keV / self.ELECTRON_MASS_KEV

        if a < 1e-6:
            # Thomson limit: σ → σ_T as E → 0
            return self.THOMSON_CROSS_SECTION

        term1 = ((1 + a) / a ** 2) * (
            2 * (1 + a) / (1 + 2 * a) - math.log(1 + 2 * a) / a
        )
        term2 = math.log(1 + 2 * a) / (2 * a)
        term3 = (1 + 3 * a) / (1 + 2 * a) ** 2

        return 2 * math.pi * r0 ** 2 * (term1 + term2 - term3)

    def klein_nishina_distribution(
        self,
        energy_keV: float,
        angular_bins: int = 180,
    ) -> KleinNishinaResult:
        """Klein-Nishina angular distribution from 0° to 180°.

        Args:
            energy_keV: Incident photon energy [keV].
            angular_bins: Number of angular bins.

        Returns:
            KleinNishinaResult with angles, dσ/dΩ, and scattered energies.
        """
        angles = np.linspace(0, math.pi, angular_bins + 1)
        dsigma = []
        energies = []
        for theta in angles:
            dsigma.append(self.klein_nishina_differential(energy_keV, float(theta)))
            energies.append(self.scattered_energy(energy_keV, float(theta)))

        return KleinNishinaResult(
            angles_rad=angles.tolist(),
            dsigma_domega=dsigma,
            scattered_energies_keV=energies,
        )

    def scattered_energy_spectrum(
        self,
        energy_keV: float,
        num_bins: int = 100,
    ) -> ComptonSpectrumResult:
        """Scattered photon energy spectrum weighted by KN cross-section.

        Args:
            energy_keV: Incident photon energy [keV].
            num_bins: Number of energy bins.

        Returns:
            ComptonSpectrumResult with energy bins and probability weights.
        """
        E_prime_min, _ = self.compton_edge(energy_keV)
        bins = np.linspace(E_prime_min, energy_keV, num_bins)
        weights = []

        for E_bin in bins:
            # Inverse: θ from E'
            alpha = energy_keV / self.ELECTRON_MASS_KEV
            cos_theta = 1.0 - (1.0 / (E_bin / energy_keV) - 1.0) / alpha
            cos_theta = max(-1.0, min(1.0, cos_theta))
            theta = math.acos(cos_theta)
            dsigma = self.klein_nishina_differential(energy_keV, theta)
            weights.append(dsigma)

        # Normalize
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        return ComptonSpectrumResult(
            energy_bins_keV=bins.tolist(),
            weights=weights,
        )

    def angle_energy_map(
        self,
        energy_keV: float,
        angular_steps: int = 361,
    ) -> AngleEnergyMapResult:
        """Angle vs energy map: E', T, Δλ for each scattering angle.

        Args:
            energy_keV: Incident photon energy [keV].
            angular_steps: Number of angular steps (0° to 180°).

        Returns:
            AngleEnergyMapResult with arrays for each quantity.
        """
        angles = np.linspace(0, math.pi, angular_steps)
        scattered = []
        recoil = []
        wavelength = []

        for theta in angles:
            theta_f = float(theta)
            scattered.append(self.scattered_energy(energy_keV, theta_f))
            recoil.append(self.recoil_electron_energy(energy_keV, theta_f))
            wavelength.append(self.wavelength_shift(theta_f))

        return AngleEnergyMapResult(
            angles_rad=angles.tolist(),
            scattered_energies_keV=scattered,
            recoil_energies_keV=recoil,
            wavelength_shifts_angstrom=wavelength,
        )

    def cross_section_vs_energy(
        self,
        min_keV: float,
        max_keV: float,
        steps: int,
    ) -> CrossSectionResult:
        """Total KN cross-section over an energy range.

        Args:
            min_keV: Lower energy bound [keV].
            max_keV: Upper energy bound [keV].
            steps: Number of energy points (log-spaced).

        Returns:
            CrossSectionResult with energies and σ_KN values.
        """
        energies = np.geomspace(min_keV, max_keV, steps)
        sigmas = [self.total_cross_section(float(E)) for E in energies]

        return CrossSectionResult(
            energies_keV=energies.tolist(),
            sigma_kn=sigmas,
        )
