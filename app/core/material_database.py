"""Material database service — loads NIST XCOM data and provides μ/ρ lookup.

Loads all material JSON files from ``data/nist_xcom/``, provides log-log
interpolation for arbitrary energies, and alloy mixture rule.

All returned μ/ρ values are in cm²/g (core units).
Energy inputs are in keV (core units).
"""

import json
import logging
import pathlib

import numpy as np

from app.models.material import (
    AttenuationDataPoint,
    Composition,
    Material,
    MaterialCategory,
)

logger = logging.getLogger(__name__)

# Material ID → JSON filename mapping
_MATERIAL_FILES: dict[str, str] = {
    "Pb": "lead.json",
    "W": "tungsten.json",
    "Bi": "bismuth.json",
    "Al": "aluminum.json",
    "Cu": "copper.json",
    "Be": "beryllium.json",
    "SS304": "steel_304.json",
    "SS316": "steel_316.json",
    "Bronze": "bronze.json",
}


class MaterialService:
    """Service for material property lookup and attenuation coefficient queries.

    Loads NIST XCOM data from JSON files and provides:
    - Material metadata (name, density, composition)
    - Mass attenuation coefficient (μ/ρ) via log-log interpolation
    - Alloy mixture rule for custom compositions

    Args:
        data_dir: Path to ``data/nist_xcom/`` directory.  If *None*, auto-
                  detected relative to the project root.
    """

    def __init__(self, data_dir: str | pathlib.Path | None = None) -> None:
        if data_dir is None:
            data_dir = pathlib.Path(__file__).resolve().parents[2] / "data" / "nist_xcom"
        self._data_dir = pathlib.Path(data_dir)
        self._materials: dict[str, Material] = {}
        self._load_materials()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_materials(self) -> list[Material]:
        """Return all loaded materials."""
        return list(self._materials.values())

    def get_material(self, material_id: str) -> Material:
        """Return a single material by ID.

        Raises:
            KeyError: If *material_id* is not found.
        """
        try:
            return self._materials[material_id]
        except KeyError:
            raise KeyError(f"Unknown material: {material_id!r}")

    def get_attenuation_data(
        self,
        material_id: str,
        min_energy_keV: float = 1.0,
        max_energy_keV: float = 20_000.0,
    ) -> list[AttenuationDataPoint]:
        """Return attenuation data points within the energy range.

        Args:
            material_id: Material identifier.
            min_energy_keV: Lower energy bound [keV].
            max_energy_keV: Upper energy bound [keV].
        """
        mat = self.get_material(material_id)
        return [
            dp for dp in mat.attenuation_data
            if min_energy_keV <= dp.energy_keV <= max_energy_keV
        ]

    def get_mu_rho(self, material_id: str, energy_keV: float) -> float:
        """Mass attenuation coefficient via log-log interpolation.

        Uses ``numpy.interp`` on log(E) vs log(μ/ρ) for smooth interpolation
        between NIST data points.  Extrapolates as constant outside the
        tabulated range.

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            μ/ρ [cm²/g].
        """
        mat = self.get_material(material_id)
        data = mat.attenuation_data
        if not data:
            raise ValueError(f"No attenuation data for material {material_id!r}")

        energies = np.array([dp.energy_keV for dp in data])
        mu_rho = np.array([dp.mass_attenuation for dp in data])

        log_E = np.log(energies)
        log_mu = np.log(mu_rho)
        log_query = np.log(energy_keV)

        return float(np.exp(np.interp(log_query, log_E, log_mu)))

    def get_compton_mu_rho(self, material_id: str, energy_keV: float) -> float:
        """Compton scattering mass attenuation coefficient via log-log interpolation.

        Uses the ``compton`` field from NIST XCOM data (incoherent scattering).

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            (μ/ρ)_compton [cm²/g].
        """
        mat = self.get_material(material_id)
        data = mat.attenuation_data
        if not data:
            raise ValueError(f"No attenuation data for material {material_id!r}")

        energies = np.array([dp.energy_keV for dp in data])
        mu_compton = np.array([dp.compton for dp in data])

        # Guard against zero Compton values at very low energies
        mu_compton = np.maximum(mu_compton, 1e-30)

        log_E = np.log(energies)
        log_mu = np.log(mu_compton)
        log_query = np.log(energy_keV)

        return float(np.exp(np.interp(log_query, log_E, log_mu)))

    def get_photoelectric_mu_rho(self, material_id: str, energy_keV: float) -> float:
        """Photoelectric mass attenuation coefficient via log-log interpolation.

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            (μ/ρ)_pe [cm²/g].
        """
        mat = self.get_material(material_id)
        data = mat.attenuation_data
        if not data:
            raise ValueError(f"No attenuation data for material {material_id!r}")

        energies = np.array([dp.energy_keV for dp in data])
        mu_pe = np.array([dp.photoelectric for dp in data])
        mu_pe = np.maximum(mu_pe, 1e-30)

        log_E = np.log(energies)
        log_mu = np.log(mu_pe)
        log_query = np.log(energy_keV)
        return float(np.exp(np.interp(log_query, log_E, log_mu)))

    def get_pair_production_mu_rho(self, material_id: str, energy_keV: float) -> float:
        """Pair production mass attenuation coefficient via log-log interpolation.

        Returns 0.0 for energies below threshold (~1022 keV).

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            (μ/ρ)_pp [cm²/g].
        """
        mat = self.get_material(material_id)
        data = mat.attenuation_data
        if not data:
            raise ValueError(f"No attenuation data for material {material_id!r}")

        energies = np.array([dp.energy_keV for dp in data])
        mu_pp = np.array([dp.pair_production for dp in data])

        # If all values are zero (below threshold), return 0
        if np.max(mu_pp) < 1e-30:
            return 0.0

        # For entries with zero pair production, use floor for log safety
        mu_pp = np.maximum(mu_pp, 1e-30)

        log_E = np.log(energies)
        log_mu = np.log(mu_pp)
        log_query = np.log(energy_keV)
        result = float(np.exp(np.interp(log_query, log_E, log_mu)))
        return result if result > 1e-20 else 0.0

    def get_mu_rho_alloy(
        self,
        composition: list[Composition],
        energy_keV: float,
    ) -> float:
        """Mass attenuation coefficient for an alloy via mixture rule.

        (μ/ρ)_alloy = Σ(wᵢ × (μ/ρ)ᵢ)

        Each element in *composition* must be a material ID present in the
        database (e.g. ``"Cu"``, ``"Al"``).

        Args:
            composition: List of ``Composition(element, weight_fraction)``.
            energy_keV: Photon energy [keV].

        Returns:
            (μ/ρ)_alloy [cm²/g].
        """
        total = 0.0
        for comp in composition:
            mu_rho_i = self.get_mu_rho(comp.element, energy_keV)
            total += comp.weight_fraction * mu_rho_i
        return total

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_materials(self) -> None:
        """Load all material JSON files into the cache."""
        for mat_id, filename in _MATERIAL_FILES.items():
            filepath = self._data_dir / filename
            if not filepath.exists():
                logger.warning("Material file not found: %s", filepath)
                continue
            try:
                self._load_single(mat_id, filepath)
            except Exception:
                logger.exception("Failed to load material %s from %s", mat_id, filepath)

    def _load_single(self, mat_id: str, filepath: pathlib.Path) -> None:
        """Parse a single material JSON file."""
        with open(filepath, encoding="utf-8") as f:
            raw = json.load(f)

        # Parse composition (alloys only)
        composition: list[Composition] = []
        for entry in raw.get("composition", []):
            composition.append(
                Composition(
                    element=entry["element"],
                    weight_fraction=entry["weight_fraction"],
                )
            )

        # Parse attenuation data
        attenuation: list[AttenuationDataPoint] = []
        for dp in raw.get("data_points", []):
            attenuation.append(
                AttenuationDataPoint(
                    energy_keV=dp["energy_keV"],
                    mass_attenuation=dp["mass_attenuation"],
                    mass_energy_absorption=dp.get("mass_energy_absorption", 0.0),
                    photoelectric=dp.get("photoelectric", 0.0),
                    compton=dp.get("compton", 0.0),
                    pair_production=dp.get("pair_production", 0.0),
                )
            )

        category_str = raw.get("category", "pure_element")
        category = (
            MaterialCategory.ALLOY
            if category_str == "alloy"
            else MaterialCategory.PURE_ELEMENT
        )

        material = Material(
            id=raw.get("material_id", mat_id),
            name=raw.get("name", mat_id),
            symbol=raw.get("symbol", mat_id),
            atomic_number=raw.get("atomic_number", 0),
            density=raw.get("density_g_cm3", 0.0),
            color="",
            category=category,
            composition=composition,
            attenuation_data=attenuation,
        )
        self._materials[mat_id] = material
