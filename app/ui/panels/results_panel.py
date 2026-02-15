"""Results panel — simulation quality score card.

Displays quality metrics from beam simulation:
  - Status dot (green/yellow/red) + name + value + unit
  - Summary line: energy, ray count, elapsed time
  - Overall pass/fail indicator

Reference: Phase 4 spec — ResultsPanel.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
)
from PyQt6.QtCore import Qt

import numpy as np

from app.core.i18n import t, TranslationManager
from app.core.units import Gy_h_to_µSv_h
from app.models.simulation import MetricStatus, QualityMetrics, SimulationResult


# Status dot colors
_STATUS_COLORS: dict[MetricStatus, str] = {
    MetricStatus.EXCELLENT: "#22C55E",    # green
    MetricStatus.ACCEPTABLE: "#F59E0B",   # yellow/amber
    MetricStatus.POOR: "#EF4444",         # red
}


class ResultsPanel(QWidget):
    """Score card showing beam simulation quality metrics.

    Each metric row: [status dot] [name]: [value] [unit]
    Summary line: energy | rays | time
    Overall: pass/fail indicator
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._metric_rows: list[tuple[QLabel, QLabel]] = []
        self._build_ui()
        TranslationManager.on_language_changed(self.retranslate_ui)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Overall status
        self._overall_label = QLabel(t("results.waiting", "Waiting for simulation..."))
        self._overall_label.setProperty("cssClass", "prop-label")
        self._overall_label.setFixedWidth(300)
        layout.addWidget(self._overall_label)

        # Metric rows container
        self._metrics_frame = QFrame()
        self._metrics_frame.setProperty("cssClass", "prop-frame")
        self._metrics_layout = QVBoxLayout(self._metrics_frame)
        self._metrics_layout.setContentsMargins(6, 4, 6, 4)
        self._metrics_layout.setSpacing(2)
        layout.addWidget(self._metrics_frame)

        # Summary line
        self._summary_label = QLabel("")
        self._summary_label.setProperty("cssClass", "prop-label")
        layout.addWidget(self._summary_label)

    def retranslate_ui(self) -> None:
        """Update translatable strings after language change.

        Note: dynamic content (metric rows, scatter rows) is rebuilt
        on next update_result() call — only the static waiting text
        and summary need refreshing here if no result is displayed.
        """
        # If still in waiting state, update the waiting text
        if not self._metric_rows:
            self._overall_label.setText(t("results.waiting", "Waiting for simulation..."))

    def update_result(self, result: SimulationResult) -> None:
        """Update the score card with simulation results."""
        # Clear old metric rows
        while self._metrics_layout.count():
            item = self._metrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._metric_rows.clear()

        qm = result.quality_metrics

        # Add metric rows
        for metric in qm.metrics:
            row = QHBoxLayout()
            row.setSpacing(6)

            # Status dot
            dot = QLabel("\u2B24")  # filled circle
            color = _STATUS_COLORS.get(metric.status, "#64748B")
            dot.setStyleSheet(f"color: {color}; font-size: 8pt;")
            dot.setFixedWidth(14)
            row.addWidget(dot)

            # Name + value
            text = f"{metric.name}: {metric.value:.2f} {metric.unit}"
            value_label = QLabel(text)
            value_label.setStyleSheet("color: #F8FAFC; font-size: 9pt;")
            row.addWidget(value_label)
            row.addStretch()

            container = QWidget()
            container.setLayout(row)
            self._metrics_layout.addWidget(container)
            self._metric_rows.append((dot, value_label))

        # FWHM row (info only, no status)
        if qm.fwhm_mm > 0:
            fwhm_row = QHBoxLayout()
            fwhm_row.setSpacing(6)
            fwhm_dot = QLabel("\u2022")
            fwhm_dot.setStyleSheet("color: #64748B; font-size: 8pt;")
            fwhm_dot.setFixedWidth(14)
            fwhm_row.addWidget(fwhm_dot)
            fwhm_label = QLabel(f"FWHM: {qm.fwhm_mm:.1f} mm")
            fwhm_label.setStyleSheet("color: #94A3B8; font-size: 9pt;")
            fwhm_row.addWidget(fwhm_label)
            fwhm_row.addStretch()
            fwhm_container = QWidget()
            fwhm_container.setLayout(fwhm_row)
            self._metrics_layout.addWidget(fwhm_container)

        # Overall status
        if qm.all_pass:
            self._overall_label.setText(t("results.all_pass", "ALL PASS"))
            self._overall_label.setStyleSheet(
                "color: #22C55E; font-weight: bold; font-size: 10pt;"
            )
        else:
            self._overall_label.setText(t("results.some_fail", "SOME METRICS FAILED"))
            self._overall_label.setStyleSheet(
                "color: #EF4444; font-weight: bold; font-size: 10pt;"
            )

        # Summary
        bu_text = (
            t("results.buildup_on", "build-up ON")
            if result.include_buildup
            else t("results.buildup_off", "build-up OFF")
        )
        summary = t(
            "results.summary_format",
            "E={energy:.0f} keV | N={rays} rays | t={time:.2f} s | {buildup}",
        ).format(
            energy=result.energy_keV,
            rays=result.num_rays,
            time=result.elapsed_seconds,
            buildup=bu_text,
        )
        self._summary_label.setText(summary)

        # Dose info rows (only if dose is computed)
        self._update_dose_info(result)

    def _update_dose_info(self, result: SimulationResult) -> None:
        """Add dose rate summary rows below quality metrics."""
        # Remove old dose rows
        for w in getattr(self, "_dose_widgets", []):
            w.deleteLater()
        self._dose_widgets: list[QWidget] = []

        unatt = result.unattenuated_dose_rate_Gy_h
        if unatt <= 0:
            return

        max_intensity = float(np.max(result.beam_profile.intensities)) if len(result.beam_profile.intensities) > 0 else 0.0
        max_dose = max_intensity * unatt

        dose_lines = [
            (t("results.open_beam", "Open Beam"),
             f"{unatt:.4g} Gy/h ({Gy_h_to_µSv_h(unatt):.1f} \u00b5Sv/h)"),
            (t("results.max_beam", "Max Beam"),
             f"{max_dose:.4g} Gy/h ({Gy_h_to_µSv_h(max_dose):.1f} \u00b5Sv/h)"),
        ]

        for name, value in dose_lines:
            row = QHBoxLayout()
            row.setSpacing(6)
            dot = QLabel("\u2022")
            dot.setStyleSheet("color: #3B82F6; font-size: 8pt;")
            dot.setFixedWidth(14)
            row.addWidget(dot)
            lbl = QLabel(f"{name}: {value}")
            lbl.setStyleSheet("color: #94A3B8; font-size: 9pt;")
            row.addWidget(lbl)
            row.addStretch()
            container = QWidget()
            container.setLayout(row)
            self._metrics_layout.addWidget(container)
            self._dose_widgets.append(container)

    def update_layer_breakdown(self, attn_with: object, attn_without: object) -> None:
        """Show per-layer attenuation table with build-up comparison (G-7, G-8).

        Args:
            attn_with: AttenuationResult with build-up.
            attn_without: AttenuationResult without build-up.
        """
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #475569;")
        self._metrics_layout.addWidget(sep)

        header = QLabel(t("results.stage_breakdown", "Stage Attenuation Breakdown"))
        header.setStyleSheet("color: #60A5FA; font-size: 9pt; font-weight: bold;")
        self._metrics_layout.addWidget(header)

        # Column header
        col_hdr = QLabel(
            "  Malzeme    | kalınlık  |   mu     |   mfp"
        )
        col_hdr.setStyleSheet("color: #64748B; font-size: 8pt; font-family: monospace;")
        self._metrics_layout.addWidget(col_hdr)

        for la in attn_without.layers:
            t_mm = la.thickness_cm * 10.0
            text = (
                f"  {la.material_id:<10s} | "
                f"{t_mm:6.1f} mm | "
                f"{la.mu_per_cm:7.3f}/cm | "
                f"{la.mfp:5.2f} mfp"
            )
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #CBD5E1; font-size: 8pt; font-family: monospace;")
            self._metrics_layout.addWidget(lbl)

        # Build-up comparison row
        t_no = attn_without.transmission
        t_bu = attn_with.transmission
        bu_factor = attn_with.buildup_factor

        bu_row = QHBoxLayout()
        bu_row.setSpacing(4)
        bu_lbl = QLabel(
            f"Build-up OFF: T={t_no:.4e}  |  "
            f"Build-up ON: T={t_bu:.4e} (B={bu_factor:.3f})"
        )
        bu_lbl.setStyleSheet("color: #94A3B8; font-size: 8pt;")
        bu_lbl.setWordWrap(True)
        bu_row.addWidget(bu_lbl)
        bu_container = QWidget()
        bu_container.setLayout(bu_row)
        self._metrics_layout.addWidget(bu_container)

    def update_scatter_result(self, scatter_result) -> None:
        """Add scatter metrics below the primary metrics.

        Args:
            scatter_result: ScatterResult from scatter simulation.
        """
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #475569;")
        self._metrics_layout.addWidget(sep)

        # Scatter header
        header = QLabel(t("results.scatter_header", "Scatter (single scatter)"))
        header.setStyleSheet("color: #FFA726; font-size: 9pt; font-weight: bold;")
        self._metrics_layout.addWidget(header)

        # Scatter fraction
        frac_pct = scatter_result.total_scatter_fraction * 100.0
        self._add_info_row(f"Scatter Ratio: {frac_pct:.2f} %")

        # Mean scattered energy
        if scatter_result.mean_scattered_energy_keV > 0:
            self._add_info_row(
                f"Mean Scatter E: {scatter_result.mean_scattered_energy_keV:.1f} keV"
            )

        # Interaction count
        self._add_info_row(
            f"Interactions: {scatter_result.num_interactions} "
            f"({scatter_result.num_reaching_detector} to detector)"
        )

        # Disclaimer
        disclaimer = QLabel(
            t(
                "results.scatter_disclaimer",
                "Simplified single-scatter model \u2014 "
                "MC validation recommended for precise analysis.",
            )
        )
        disclaimer.setStyleSheet("color: #64748B; font-size: 7pt;")
        disclaimer.setWordWrap(True)
        self._metrics_layout.addWidget(disclaimer)

    def _add_info_row(self, text: str) -> None:
        """Add a simple info row to metrics layout."""
        row = QHBoxLayout()
        row.setSpacing(6)
        dot = QLabel("\u2022")
        dot.setStyleSheet("color: #FFA726; font-size: 8pt;")
        dot.setFixedWidth(14)
        row.addWidget(dot)
        label = QLabel(text)
        label.setStyleSheet("color: #CBD5E1; font-size: 9pt;")
        row.addWidget(label)
        row.addStretch()
        container = QWidget()
        container.setLayout(row)
        self._metrics_layout.addWidget(container)

    def clear(self) -> None:
        """Reset the panel to waiting state."""
        while self._metrics_layout.count():
            item = self._metrics_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._metric_rows.clear()
        self._overall_label.setText(t("results.waiting", "Waiting for simulation..."))
        self._overall_label.setStyleSheet(
            "color: #94A3B8; font-size: 8pt;"
        )
        self._summary_label.setText("")
