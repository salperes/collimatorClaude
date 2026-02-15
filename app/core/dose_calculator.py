"""Absolute dose rate calculator.

Converts source parameters (tube current, LINAC PPS/dose) into
absolute dose rate at the detector plane using inverse-square law.

All internal calculations use core units:
    - Distance: cm (converted from mm inputs)
    - Energy: keV
    - Dose rate output: Gy/h

Reference: IAEA TRS-457, IEC 60601-1-3 tube output standards.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.models.geometry import SourceConfig


@dataclass
class TubeOutputCoefficients:
    """Empirical tube output Y = C * kVp^n [mGy/mAs @1m].

    Attributes:
        C: Proportionality constant.
        n: Power exponent (typically 2.0-2.5).
        target_id: Target material this applies to.
    """
    C: float
    n: float
    target_id: str


# Empirical coefficients per anode target material.
# Sources: IEC 60601-1-3 typical values, BJR Supplement 17.
# Y(kVp) = C * kVp^n  [mGy/mAs @1m]
_DEFAULT_TUBE_COEFFICIENTS: dict[str, TubeOutputCoefficients] = {
    "W":  TubeOutputCoefficients(C=3.00e-6, n=2.30, target_id="W"),
    "Mo": TubeOutputCoefficients(C=2.50e-6, n=2.20, target_id="Mo"),
    "Rh": TubeOutputCoefficients(C=2.70e-6, n=2.20, target_id="Rh"),
    "Cu": TubeOutputCoefficients(C=2.80e-6, n=2.25, target_id="Cu"),
    "Ag": TubeOutputCoefficients(C=2.60e-6, n=2.20, target_id="Ag"),
}


class DoseCalculator:
    """Calculates absolute dose rate at the detector plane.

    Supports two source modes:
    - **Tube (kVp)**: Empirical power-law or lookup-table tube output,
      scaled by tube current and inverse-square to detector distance.
    - **LINAC (MeV)**: Linear PPS-dose model with inverse-square from
      isocentric reference distance (1 m) to detector.

    Output unit: Gy/h.
    """

    def __init__(self, lookup_table_path: str | Path | None = None) -> None:
        self._lookup_table: list[dict] | None = None
        if lookup_table_path:
            self._load_lookup_table(Path(lookup_table_path))

    # ------------------------------------------------------------------
    # Tube mode
    # ------------------------------------------------------------------

    def tube_output_empirical(
        self,
        kVp: float,
        target_id: str = "W",
    ) -> float:
        """Tube output Y(kVp) using empirical power law [mGy/mAs @1m].

        Y = C * kVp^n

        Args:
            kVp: Tube voltage [kVp].
            target_id: Anode target material.

        Returns:
            Tube output [mGy/mAs @1m].
        """
        coeff = _DEFAULT_TUBE_COEFFICIENTS.get(
            target_id, _DEFAULT_TUBE_COEFFICIENTS["W"],
        )
        return coeff.C * (kVp ** coeff.n)

    def tube_output_lookup(
        self,
        kVp: float,
        target_id: str = "W",
        filtration: str = "1mm Al",
    ) -> float:
        """Tube output from lookup table with linear interpolation [mGy/mAs @1m].

        Falls back to empirical if table not loaded or no matching entries.

        Args:
            kVp: Tube voltage [kVp].
            target_id: Anode target material.
            filtration: Filtration description string.

        Returns:
            Tube output [mGy/mAs @1m].
        """
        if not self._lookup_table:
            return self.tube_output_empirical(kVp, target_id)

        entries = [
            e for e in self._lookup_table
            if e.get("target") == target_id
            and e.get("filtration", "") == filtration
        ]
        if not entries:
            return self.tube_output_empirical(kVp, target_id)

        entries.sort(key=lambda e: e["kVp"])
        kvp_vals = [e["kVp"] for e in entries]
        y_vals = [e["Y_mGy_mAs_1m"] for e in entries]

        if kVp <= kvp_vals[0]:
            return y_vals[0]
        if kVp >= kvp_vals[-1]:
            return y_vals[-1]

        for i in range(len(kvp_vals) - 1):
            if kvp_vals[i] <= kVp <= kvp_vals[i + 1]:
                t = (kVp - kvp_vals[i]) / (kvp_vals[i + 1] - kvp_vals[i])
                return y_vals[i] + t * (y_vals[i + 1] - y_vals[i])

        return self.tube_output_empirical(kVp, target_id)

    def tube_dose_rate_Gy_h(
        self,
        kVp: float,
        tube_current_mA: float,
        sdd_mm: float,
        target_id: str = "W",
        method: str = "empirical",
    ) -> float:
        """Absolute dose rate at detector for X-ray tube mode [Gy/h].

        Pipeline:
          1. Y = tube_output(kVp) [mGy/mAs @1m]
          2. dose_rate_1m = Y * I_mA [mGy/s @1m]
          3. dose_rate_det = dose_rate_1m / SDD_m² [mGy/s]
          4. Convert mGy/s → Gy/h (× 3.6)

        Args:
            kVp: Tube voltage [kVp].
            tube_current_mA: Tube current [mA].
            sdd_mm: Source-to-detector distance [mm].
            target_id: Anode target material.
            method: "empirical" or "lookup".

        Returns:
            Unattenuated dose rate at detector [Gy/h].
        """
        if sdd_mm <= 0 or tube_current_mA <= 0 or kVp <= 0:
            return 0.0

        if method == "lookup":
            Y = self.tube_output_lookup(kVp, target_id)
        else:
            Y = self.tube_output_empirical(kVp, target_id)

        sdd_m = sdd_mm / 1000.0

        # Y [mGy/mAs] * I [mA] = mGy/s  (since mA * 1s = mAs)
        dose_rate_1m_mGy_s = Y * tube_current_mA

        # Inverse-square law
        dose_rate_det_mGy_s = dose_rate_1m_mGy_s / (sdd_m ** 2)

        # mGy/s → Gy/h: × 3600 / 1000 = × 3.6
        return dose_rate_det_mGy_s * 3.6

    # ------------------------------------------------------------------
    # LINAC mode
    # ------------------------------------------------------------------

    def linac_dose_rate_Gy_h(
        self,
        pps: int,
        reference_dose_Gy_min: float,
        reference_pps: int,
        sdd_mm: float,
        reference_distance_m: float = 1.0,
    ) -> float:
        """Absolute dose rate at detector for LINAC mode [Gy/h].

        Linear PPS-dose model: dose_rate ∝ PPS (constant dose per pulse).

        Pipeline:
          1. dose_per_pulse = ref_Gy_min / ref_PPS [Gy/min per pulse]
          2. dose_rate_ref = dose_per_pulse * PPS [Gy/min @ ref distance]
          3. dose_rate_det = dose_rate_ref * (ref_dist / SDD)² [Gy/min]
          4. Gy/min → Gy/h (× 60)

        Args:
            pps: Current pulse repetition rate [pulses/s].
            reference_dose_Gy_min: Dose rate at reference PPS [Gy/min].
            reference_pps: Reference pulse rate [pulses/s].
            sdd_mm: Source-to-detector distance [mm].
            reference_distance_m: Isocentric reference distance [m].

        Returns:
            Unattenuated dose rate at detector [Gy/h].
        """
        if reference_pps <= 0 or sdd_mm <= 0 or pps <= 0:
            return 0.0

        dose_per_pulse = reference_dose_Gy_min / reference_pps
        dose_rate_ref_Gy_min = dose_per_pulse * pps

        sdd_m = sdd_mm / 1000.0
        # Inverse-square from reference distance to detector
        dose_rate_det_Gy_min = dose_rate_ref_Gy_min * (
            reference_distance_m / sdd_m
        ) ** 2

        # Gy/min → Gy/h
        return dose_rate_det_Gy_min * 60.0

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def calculate_unattenuated_dose(
        self,
        source: SourceConfig,
        sdd_mm: float,
    ) -> float:
        """Compute unattenuated dose rate at detector plane [Gy/h].

        Dispatches to tube or LINAC calculator based on source config
        (energy_kVp set → tube mode, energy_MeV set → LINAC mode).

        Args:
            source: Source configuration.
            sdd_mm: Source-to-detector distance [mm].

        Returns:
            Unattenuated dose rate at detector [Gy/h].
            Returns 0.0 if source mode is indeterminate.
        """
        if source.energy_kVp is not None:
            return self.tube_dose_rate_Gy_h(
                kVp=source.energy_kVp,
                tube_current_mA=source.tube_current_mA,
                sdd_mm=sdd_mm,
                method=source.tube_output_method,
            )
        elif source.energy_MeV is not None:
            return self.linac_dose_rate_Gy_h(
                pps=source.linac_pps,
                reference_dose_Gy_min=source.linac_dose_rate_Gy_min,
                reference_pps=source.linac_ref_pps,
                sdd_mm=sdd_mm,
            )
        return 0.0

    # ------------------------------------------------------------------
    # Lookup table
    # ------------------------------------------------------------------

    def _load_lookup_table(self, path: Path) -> None:
        """Load tube output lookup table from JSON file."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._lookup_table = data.get("entries", [])
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self._lookup_table = None
