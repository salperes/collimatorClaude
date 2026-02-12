"""Compton scattering analysis data models.

Reference: FRD §3 — Data Models, §5.4 Klein-Nishina.
"""

from dataclasses import dataclass, field


@dataclass
class ComptonAnalysis:
    """Results from Compton scatter analysis.

    Attributes:
        incident_energy_keV: Incident photon energy [keV].
        scatter_angles_deg: Scatter angle bins [degree].
        scattered_energies_keV: Scattered photon energy per angle [keV].
        differential_cross_sections: dσ/dΩ per angle [cm²/sr].
        total_cross_section: Integrated Klein-Nishina σ [cm²].
        scatter_to_primary_ratio: SPR (scatter / primary intensity).
    """
    incident_energy_keV: float = 0.0
    scatter_angles_deg: list[float] = field(default_factory=list)
    scattered_energies_keV: list[float] = field(default_factory=list)
    differential_cross_sections: list[float] = field(default_factory=list)
    total_cross_section: float = 0.0
    scatter_to_primary_ratio: float = 0.0
