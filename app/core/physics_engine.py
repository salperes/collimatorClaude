"""Physics engine — Beer-Lambert attenuation, HVL/TVL, sweep functions.

All internal calculations in core units (cm, keV).
Wall thickness inputs are in mm (UI units) and converted via units.py.

Reference: FRD §4.2, §7.1–7.4, docs/phase-02-physics-engine.md.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from app.core.units import mm_to_cm, cm_to_mm, thickness_to_mfp, transmission_to_dB
from app.models.geometry import CollimatorStage, CollimatorType
from app.models.results import (
    AttenuationResult,
    HvlTvlResult,
    LayerAttenuation,
    ThicknessSweepPoint,
)

if TYPE_CHECKING:
    from app.core.build_up_factors import BuildUpFactors
    from app.core.material_database import MaterialService


def effective_wall_thickness_mm(
    stage: CollimatorStage,
    ctype: CollimatorType,
) -> float:
    """Compute effective shielding wall thickness from solid stage geometry.

    For a solid stage, effective wall = (outer_width/2) - aperture_half_width
    at the midpoint of the stage height.

    Args:
        stage: CollimatorStage [mm, degree].
        ctype: Collimator type.
    Returns:
        Effective wall thickness per side [mm].
    """
    from app.core.ray_tracer import aperture_half_width_at_y
    stage_h_cm = mm_to_cm(stage.outer_height)
    mid_y_cm = stage_h_cm / 2.0
    ap_half_cm = aperture_half_width_at_y(
        stage.aperture, ctype, mid_y_cm, stage_h_cm,
    )
    ap_half_mm = cm_to_mm(ap_half_cm)
    return max(0.0, (stage.outer_width / 2.0) - ap_half_mm)


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

    def calculate_slab_attenuation(
        self,
        material_id: str,
        thickness_mm: float,
        energy_keV: float,
        include_buildup: bool = False,
    ) -> AttenuationResult:
        """Single-slab Beer-Lambert attenuation.

        Pure material + thickness calculation. Does not depend on
        stage geometry — for analytical / validation use.

        Args:
            material_id: Material identifier (e.g. "Pb").
            thickness_mm: Slab thickness [mm].
            energy_keV: Photon energy [keV].
            include_buildup: Apply build-up factor correction.

        Returns:
            AttenuationResult with transmission, dB, per-layer breakdown.
        """
        if not material_id or thickness_mm <= 0:
            return AttenuationResult(
                transmission=1.0, attenuation_dB=0.0, total_mfp=0.0,
            )
        thickness_cm = float(mm_to_cm(thickness_mm))
        mu = self.linear_attenuation(material_id, energy_keV)
        mfp = float(thickness_to_mfp(thickness_cm, mu))

        transmission = math.exp(-mfp)
        buildup_factor = 1.0
        if include_buildup and self._buildup:
            buildup_factor = self._buildup.get_multilayer_buildup(
                [(material_id, mfp)], energy_keV,
            )
            transmission *= buildup_factor

        transmission = min(max(transmission, 0.0), 1.0)
        return AttenuationResult(
            transmission=transmission,
            attenuation_dB=float(transmission_to_dB(transmission)),
            total_mfp=mfp,
            layers=[LayerAttenuation(
                material_id=material_id,
                thickness_cm=thickness_cm,
                mu_per_cm=mu,
                mfp=mfp,
            )],
            buildup_factor=buildup_factor,
        )

    def calculate_attenuation(
        self,
        stages: list[CollimatorStage],
        energy_keV: float,
        include_buildup: bool = False,
        ctype: CollimatorType = CollimatorType.SLIT,
    ) -> AttenuationResult:
        """Multi-stage Beer-Lambert attenuation.

        I/I₀ = B(E, μx) × exp(-Σ μᵢxᵢ)

        Effective wall thickness is computed from stage geometry:
        wall = (outer_width/2) - aperture_half_width_at_midpoint.

        Args:
            stages: Collimator stages [mm, degree].
            energy_keV: Photon energy [keV].
            include_buildup: Apply build-up factor correction.
            ctype: Collimator type (for aperture shape computation).

        Returns:
            AttenuationResult with transmission, dB, per-stage breakdown.
        """
        if not stages:
            return AttenuationResult(
                transmission=1.0,
                attenuation_dB=0.0,
                total_mfp=0.0,
            )

        layer_results: list[LayerAttenuation] = []
        total_mfp = 0.0
        layers_mfp_pairs: list[tuple[str, float]] = []

        for stage in stages:
            if not stage.material_id:
                continue
            wall_mm = effective_wall_thickness_mm(stage, ctype)
            if wall_mm <= 0:
                continue
            thickness_cm = float(mm_to_cm(wall_mm))
            mu = self.linear_attenuation(stage.material_id, energy_keV)
            mfp = float(thickness_to_mfp(thickness_cm, mu))
            total_mfp += mfp

            layer_results.append(LayerAttenuation(
                material_id=stage.material_id,
                thickness_cm=thickness_cm,
                mu_per_cm=mu,
                mfp=mfp,
            ))
            layers_mfp_pairs.append((stage.material_id, mfp))

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
        stages: list[CollimatorStage],
        min_keV: float,
        max_keV: float,
        steps: int,
        include_buildup: bool = False,
        ctype: CollimatorType = CollimatorType.SLIT,
    ) -> list[AttenuationResult]:
        """Attenuation over a range of energies (log-spaced).

        Args:
            stages: Collimator stages.
            min_keV: Lower energy bound [keV].
            max_keV: Upper energy bound [keV].
            steps: Number of energy points.
            include_buildup: Apply build-up factor correction.
            ctype: Collimator type (for aperture shape computation).

        Returns:
            List of AttenuationResult, one per energy step.
        """
        energies = np.geomspace(min_keV, max_keV, steps)
        return [
            self.calculate_attenuation(stages, float(E), include_buildup, ctype)
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
