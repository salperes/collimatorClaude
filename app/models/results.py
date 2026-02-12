"""Physics engine result data models.

Dataclasses returned by PhysicsEngine, BuildUpFactors, and ComptonEngine.
Reference: FRD §5 — Computation Engine, docs/phase-02-physics-engine.md.
"""

from dataclasses import dataclass, field


@dataclass
class LayerAttenuation:
    """Per-layer attenuation breakdown.

    Attributes:
        material_id: Material identifier.
        thickness_cm: Layer thickness [cm].
        mu_per_cm: Linear attenuation coefficient [cm⁻¹].
        mfp: Optical thickness μ×x [dimensionless].
    """
    material_id: str = ""
    thickness_cm: float = 0.0
    mu_per_cm: float = 0.0
    mfp: float = 0.0


@dataclass
class AttenuationResult:
    """Multi-layer Beer-Lambert attenuation result.

    Attributes:
        transmission: I/I₀ ratio [0–1].
        attenuation_dB: Attenuation in dB (positive).
        total_mfp: Total optical thickness [mfp].
        layers: Per-layer breakdown.
        buildup_factor: Applied build-up factor (1.0 if not used).
    """
    transmission: float = 1.0
    attenuation_dB: float = 0.0
    total_mfp: float = 0.0
    layers: list[LayerAttenuation] = field(default_factory=list)
    buildup_factor: float = 1.0


@dataclass
class HvlTvlResult:
    """Half-value / tenth-value layer result.

    All lengths in cm (core units).

    Attributes:
        hvl_cm: Half-value layer [cm].
        tvl_cm: Tenth-value layer [cm].
        mfp_cm: Mean free path [cm].
        mu_per_cm: Linear attenuation coefficient [cm⁻¹].
    """
    hvl_cm: float = 0.0
    tvl_cm: float = 0.0
    mfp_cm: float = 0.0
    mu_per_cm: float = 0.0


@dataclass
class ThicknessSweepPoint:
    """Single point in a thickness sweep.

    Attributes:
        thickness_cm: Material thickness [cm].
        transmission: I/I₀ ratio [0–1].
        attenuation_dB: Attenuation in dB.
    """
    thickness_cm: float = 0.0
    transmission: float = 1.0
    attenuation_dB: float = 0.0


@dataclass
class KleinNishinaResult:
    """Klein-Nishina angular distribution.

    Attributes:
        angles_rad: Scattering angles [radian].
        dsigma_domega: Differential cross-section per angle [cm²/sr/electron].
        scattered_energies_keV: Scattered photon energy per angle [keV].
    """
    angles_rad: list[float] = field(default_factory=list)
    dsigma_domega: list[float] = field(default_factory=list)
    scattered_energies_keV: list[float] = field(default_factory=list)


@dataclass
class ComptonSpectrumResult:
    """Compton scattered photon energy spectrum.

    Attributes:
        energy_bins_keV: Energy bin centers [keV].
        weights: Relative probability per bin.
    """
    energy_bins_keV: list[float] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)


@dataclass
class AngleEnergyMapResult:
    """Angle vs energy map for Compton scattering.

    Attributes:
        angles_rad: Scattering angles [radian].
        scattered_energies_keV: Scattered photon energy per angle [keV].
        recoil_energies_keV: Recoil electron energy per angle [keV].
        wavelength_shifts_angstrom: Wavelength shift per angle [Å].
    """
    angles_rad: list[float] = field(default_factory=list)
    scattered_energies_keV: list[float] = field(default_factory=list)
    recoil_energies_keV: list[float] = field(default_factory=list)
    wavelength_shifts_angstrom: list[float] = field(default_factory=list)


@dataclass
class CrossSectionResult:
    """Klein-Nishina total cross-section vs energy.

    Attributes:
        energies_keV: Photon energies [keV].
        sigma_kn: Total KN cross-section per energy [cm²/electron].
    """
    energies_keV: list[float] = field(default_factory=list)
    sigma_kn: list[float] = field(default_factory=list)
