"""SPR profile chart — Scatter-to-Primary Ratio visualization.

Displays SPR per spatial bin from scatter simulation results.
Uses pyqtgraph BaseChart with crosshair.

Reference: FRD §4.2 FR-2.7, Phase-07 spec.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.core.i18n import t
from app.ui.charts.base_chart import BaseChart
from app.ui.styles.colors import WARNING, ERROR, ACCENT, TEXT_SECONDARY


class SprChartWidget(QWidget):
    """SPR profile visualization widget.

    Shows SPR (Scatter-to-Primary Ratio) as a function of detector
    position, with threshold lines for typical acceptable levels.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._info_label = QLabel(t("charts.spr_waiting", "Waiting for scatter simulation..."))
        self._info_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9pt; padding: 4px;"
        )
        layout.addWidget(self._info_label)

        self._chart = BaseChart(
            title=t("charts.spr_title", "SPR Profile (Scatter-to-Primary Ratio)"),
            x_label=t("charts.detector_position", "Detector Position (mm)"),
            y_label=t("charts.spr_axis", "SPR"),
        )
        self._chart.enable_crosshair()
        layout.addWidget(self._chart)

        self._threshold_lines: list = []

    def update_scatter_result(self, scatter_result) -> None:
        """Update SPR chart with scatter simulation data.

        Args:
            scatter_result: ScatterResult from scatter_tracer.
        """
        self._chart.clear_curves()
        for line in self._threshold_lines:
            self._chart.plot_widget.removeItem(line)
        self._threshold_lines.clear()

        positions = scatter_result.spr_positions_mm
        spr = scatter_result.spr_profile

        if len(positions) == 0 or len(spr) == 0:
            self._info_label.setText(
                t("charts.spr_no_data", "No SPR data — scatter did not reach detector.")
            )
            return

        # SPR curve
        self._chart.add_curve(
            positions, spr,
            name="SPR", color=WARNING, width=2,
        )

        # Threshold lines
        from PyQt6.QtCore import Qt
        line_5 = self._chart.add_infinite_line(
            pos=0.05, angle=0, color=ACCENT,
            style=Qt.PenStyle.DashLine,
            label="SPR=5%",
        )
        self._threshold_lines.append(line_5)

        line_10 = self._chart.add_infinite_line(
            pos=0.10, angle=0, color=ERROR,
            style=Qt.PenStyle.DashLine,
            label="SPR=10%",
        )
        self._threshold_lines.append(line_10)

        # Info text
        mean_spr = float(np.mean(spr))
        max_spr = float(np.max(spr))
        frac_pct = scatter_result.total_scatter_fraction * 100.0
        self._info_label.setText(
            t("charts.spr_info", "Mean SPR: {mean} | Max SPR: {max} | Scatter Fraction: {frac}% | Mean E': {energy} keV").format(
                mean=f"{mean_spr:.4f}",
                max=f"{max_spr:.4f}",
                frac=f"{frac_pct:.2f}",
                energy=f"{scatter_result.mean_scattered_energy_keV:.1f}",
            )
        )

    def clear(self) -> None:
        """Reset the chart."""
        self._chart.clear_curves()
        for line in self._threshold_lines:
            self._chart.plot_widget.removeItem(line)
        self._threshold_lines.clear()
        self._info_label.setText(t("charts.spr_waiting", "Waiting for scatter simulation..."))
