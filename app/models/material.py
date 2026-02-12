"""Material data models.

Defines material properties, composition, and attenuation data structures.
Reference: FRD §3 — Data Models.
"""

from dataclasses import dataclass, field
from enum import Enum


class MaterialCategory(Enum):
    PURE_ELEMENT = "pure_element"
    ALLOY = "alloy"


@dataclass
class Composition:
    """Single element in an alloy composition.

    Attributes:
        element: Element symbol (e.g. "Fe", "Cr", "Ni").
        weight_fraction: Weight fraction [0.0–1.0].
    """
    element: str
    weight_fraction: float


@dataclass
class AttenuationDataPoint:
    """Single energy point in attenuation data.

    All cross-section values in cm²/g.

    Attributes:
        energy_keV: Photon energy [keV].
        mass_attenuation: Total μ/ρ (coherent included) [cm²/g].
        mass_energy_absorption: μ_en/ρ [cm²/g].
        photoelectric: Photoelectric component [cm²/g].
        compton: Compton scattering component [cm²/g].
        pair_production: Pair production component (>1.022 MeV) [cm²/g].
    """
    energy_keV: float
    mass_attenuation: float
    mass_energy_absorption: float
    photoelectric: float
    compton: float
    pair_production: float


@dataclass
class Material:
    """Material definition with physical properties.

    Attributes:
        id: Unique identifier ("Pb", "W", "SS304", etc.).
        name: Display name.
        symbol: Chemical symbol.
        atomic_number: Atomic number (effective Z for alloys).
        density: Density [g/cm³].
        color: Hex color code for UI display.
        category: Pure element or alloy.
        composition: Element list for alloys.
        attenuation_data: Energy-dependent attenuation data.
    """
    id: str
    name: str
    symbol: str
    atomic_number: float
    density: float
    color: str
    category: MaterialCategory
    composition: list[Composition] = field(default_factory=list)
    attenuation_data: list[AttenuationDataPoint] = field(default_factory=list)
