"""CSV export — beam profile and attenuation data.

BOM UTF-8 encoding for Excel compatibility.

Reference: Phase-06 spec — FR-4.2.
"""

from __future__ import annotations

import csv

from app.core.units import rad_to_deg, Gy_h_to_µSv_h
from app.models.simulation import SimulationResult


class CsvExporter:
    """CSV file export operations."""

    def export_beam_profile(
        self, result: SimulationResult, output_path: str,
    ) -> None:
        """Export beam profile as CSV.

        Columns: Position (mm), Intensity, Angle (degree).

        Args:
            result: Simulation result with beam profile.
            output_path: Destination file path (.csv).
        """
        profile = result.beam_profile
        has_dose = result.unattenuated_dose_rate_Gy_h > 0
        unatt = result.unattenuated_dose_rate_Gy_h

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            headers = ["Position (mm)", "Intensity", "Angle (degree)"]
            if has_dose:
                headers.extend(["Dose Rate (Gy/h)", "Dose Rate (\u00b5Sv/h)"])
            writer.writerow(headers)
            for i in range(len(profile.positions_mm)):
                pos = float(profile.positions_mm[i])
                intensity = float(profile.intensities[i])
                angle_deg = float(rad_to_deg(profile.angles_rad[i])) if i < len(profile.angles_rad) else 0.0
                row = [f"{pos:.4f}", f"{intensity:.6f}", f"{angle_deg:.4f}"]
                if has_dose:
                    dose_gy_h = intensity * unatt
                    row.extend([f"{dose_gy_h:.6g}", f"{Gy_h_to_µSv_h(dose_gy_h):.2f}"])
                writer.writerow(row)

    def export_attenuation_summary(
        self,
        rows: list[dict],
        output_path: str,
    ) -> None:
        """Export attenuation summary as CSV.

        Each row dict should contain: energy_keV, material, thickness_mm,
        mu_rho, mu, hvl_mm, tvl_mm, transmission_pct, attenuation_dB.

        Args:
            rows: List of row dicts.
            output_path: Destination file path (.csv).
        """
        headers = [
            "Energy (keV)", "Material", "Thickness (mm)",
            "mu/rho (cm2/g)", "mu (cm-1)",
            "HVL (mm)", "TVL (mm)",
            "Transmission (%)", "Attenuation (dB)",
        ]
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for r in rows:
                writer.writerow([
                    r.get("energy_keV", ""),
                    r.get("material", ""),
                    r.get("thickness_mm", ""),
                    r.get("mu_rho", ""),
                    r.get("mu", ""),
                    r.get("hvl_mm", ""),
                    r.get("tvl_mm", ""),
                    r.get("transmission_pct", ""),
                    r.get("attenuation_dB", ""),
                ])
