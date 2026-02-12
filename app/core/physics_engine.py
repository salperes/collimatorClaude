"""Physics engine — Beer-Lambert attenuation, HVL/TVL, sweep functions.

All internal calculations in core units (cm, keV).
Layer thickness inputs are in mm (UI units) and converted via units.py.

Reference: FRD §4.2, §7.1–7.4, docs/phase-02-physics-engine.md.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from app.core.units import mm_to_cm, thickness_to_mfp, transmission_to_dB
from app.models.geometry import CollimatorLayer
from app.models.results import (
    AttenuationResult,
    HvlTvlResult,
    LayerAttenuation,
    ThicknessSweepPoint,
)

if TYPE_CHECKING:
    from app.core.build_up_factors import BuildUpFactors
    from app.core.material_database import MaterialService


class PhysicsEngine:
    """Analytical photon attenuation engine.

    Provides Beer-Lambert multi-layer attenuation, HVL/TVL calculation,
    and energy/thickness sweep functions.

    Args:
        material_service: Material database for μ/ρ lookups.
        buildup_service: Optional build-up factor calculator.
    """

    def __init__(
        self,
        material_service: MaterialService,
        buildup_service: BuildUpFactors | None = None,
    ) -> None:
        self._materials = material_service
        self._buildup = buildup_service

    def linear_attenuation(
        self,
        material_id: str,
        energy_keV: float,
    ) -> float:
        """Linear attenuation coefficient.

        μ [cm⁻¹] = (μ/ρ) [cm²/g] × ρ [g/cm³]

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            μ [cm⁻¹].
        """
        mu_rho = self._materials.get_mu_rho(material_id, energy_keV)
        density = self._materials.get_material(material_id).density
        return mu_rho * density

    def compton_linear_attenuation(
        self,
        material_id: str,
        energy_keV: float,
    ) -> float:
        """Compton scattering linear attenuation coefficient.

        μ_compton [cm⁻¹] = (μ/ρ)_compton [cm²/g] × ρ [g/cm³]

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            μ_compton [cm⁻¹].
        """
        mu_rho_c = self._materials.get_compton_mu_rho(material_id, energy_keV)
        density = self._materials.get_material(material_id).density
        return mu_rho_c * density

    def calculate_attenuation(
        self,
        layers: list[CollimatorLayer],
        energy_keV: float,
        include_buildup: bool = False,
    ) -> AttenuationResult:
        """Multi-layer Beer-Lambert attenuation.

        I/I₀ = B(E, μx) × exp(-Σ μᵢxᵢ)

        Layer thicknesses are in mm (UI units) and converted internally.

        Args:
            layers: Collimator layers with thickness in mm.
            energy_keV: Photon energy [keV].
            include_buildup: Apply build-up factor correction.

        Returns:
            AttenuationResult with transmission, dB, per-layer breakdown.
        """
        if not layers:
            return AttenuationResult(
                transmission=1.0,
                attenuation_dB=0.0,
                total_mfp=0.0,
            )

        layer_results: list[LayerAttenuation] = []
        total_mfp = 0.0
        layers_mfp_pairs: list[tuple[str, float]] = []

        for layer in layers:
            if not layer.material_id or layer.thickness <= 0:
                continue
            thickness_cm = float(mm_to_cm(layer.thickness))
            mu = self.linear_attenuation(layer.material_id, energy_keV)
            mfp = float(thickness_to_mfp(thickness_cm, mu))
            total_mfp += mfp

            layer_results.append(LayerAttenuation(
                material_id=layer.material_id,
                thickness_cm=thickness_cm,
                mu_per_cm=mu,
                mfp=mfp,
            ))
            layers_mfp_pairs.append((layer.material_id, mfp))

        transmission = math.exp(-total_mfp)

        buildup_factor = 1.0
        if include_buildup and self._buildup and layers_mfp_pairs:
            buildup_factor = self._buildup.get_multilayer_buildup(
                layers_mfp_pairs, energy_keV,
            )
            transmission *= buildup_factor

        # Clamp transmission to [0, 1]
        transmission = min(max(transmission, 0.0), 1.0)

        return AttenuationResult(
            transmission=transmission,
            attenuation_dB=float(transmission_to_dB(transmission)),
            total_mfp=total_mfp,
            layers=layer_results,
            buildup_factor=buildup_factor,
        )

    def energy_sweep(
        self,
        layers: list[CollimatorLayer],
        min_keV: float,
        max_keV: float,
        steps: int,
        include_buildup: bool = False,
    ) -> list[AttenuationResult]:
        """Attenuation over a range of energies (log-spaced).

        Args:
            layers: Collimator layers.
            min_keV: Lower energy bound [keV].
            max_keV: Upper energy bound [keV].
            steps: Number of energy points.
            include_buildup: Apply build-up factor correction.

        Returns:
            List of AttenuationResult, one per energy step.
        """
        energies = np.geomspace(min_keV, max_keV, steps)
        return [
            self.calculate_attenuation(layers, float(E), include_buildup)
            for E in energies
        ]

    def calculate_hvl_tvl(
        self,
        material_id: str,
        energy_keV: float,
    ) -> HvlTvlResult:
        """Half-value layer, tenth-value layer, and mean free path.

        HVL = ln(2) / μ [cm]
        TVL = ln(10) / μ [cm]
        MFP = 1 / μ [cm]

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].

        Returns:
            HvlTvlResult with all values in cm.
        """
        mu = self.linear_attenuation(material_id, energy_keV)
        if mu <= 0:
            return HvlTvlResult()

        return HvlTvlResult(
            hvl_cm=math.log(2) / mu,
            tvl_cm=math.log(10) / mu,
            mfp_cm=1.0 / mu,
            mu_per_cm=mu,
        )

    def thickness_sweep(
        self,
        material_id: str,
        energy_keV: float,
        max_thickness_mm: float,
        steps: int,
    ) -> list[ThicknessSweepPoint]:
        """Transmission vs thickness for a single material.

        Args:
            material_id: Material identifier.
            energy_keV: Photon energy [keV].
            max_thickness_mm: Maximum thickness [mm].
            steps: Number of thickness points.

        Returns:
            List of ThicknessSweepPoint.
        """
        mu = self.linear_attenuation(material_id, energy_keV)
        max_cm = float(mm_to_cm(max_thickness_mm))
        thicknesses = np.linspace(0, max_cm, steps)

        results: list[ThicknessSweepPoint] = []
        for t_cm in thicknesses:
            T = math.exp(-mu * t_cm)
            results.append(ThicknessSweepPoint(
                thickness_cm=float(t_cm),
                transmission=T,
                attenuation_dB=float(transmission_to_dB(T)),
            ))
        return results
