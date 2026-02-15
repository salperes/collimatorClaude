"""Spectrum chart widget — X-ray tube spectrum visualization.

Shows bremsstrahlung continuum with characteristic peaks, filtered and
unfiltered spectra for comparison, and effective energy marker.

Reference: Phase-05 spec — custom chart for tube spectrum display.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox

from app.core.i18n import t
from app.core.material_database import MaterialService
from app.core.spectrum_models import TubeConfig, XRaySpectrum
from app.ui.charts.base_chart import BaseChart


class SpectrumChartWidget(QWidget):
    """X-ray tube spectrum chart with filtered/unfiltered overlay.

    Displays:
    - Filtered spectrum (blue, primary)
    - Unfiltered spectrum (gray, comparison, optional)
    - Effective energy vertical marker line
    - Characteristic peak annotations
    """

    def __init__(
        self,
        material_service: MaterialService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._spectrum = XRaySpectrum(material_service)
        self._config: TubeConfig | None = None
        self._eff_line = None  # InfiniteLine for effective energy

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top row: options
        top_layout = QHBoxLayout()
        self._cb_unfiltered = QCheckBox(t("charts.show_unfiltered", "Show unfiltered spectrum"))
        self._cb_unfiltered.setChecked(True)
        self._cb_unfiltered.toggled.connect(lambda _: self._redraw())
        top_layout.addWidget(self._cb_unfiltered)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Chart
        self._chart = BaseChart(
            title=t("charts.spectrum_title", "X-ray Tube Spectrum"),
            x_label=t("charts.energy_axis", "Energy [keV]"),
            y_label=t("charts.relative_intensity", "Relative Intensity"),
        )
        self._chart.enable_crosshair()
        layout.addWidget(self._chart, stretch=1)

    def update_spectrum(self, config: TubeConfig) -> None:
        """Regenerate and plot the spectrum for the given tube configuration.

        Args:
            config: X-ray tube configuration.
        """
        self._config = config
        self._redraw()

    def _redraw(self) -> None:
        """Redraw spectrum curves."""
        config = self._config
        if config is None:
            return

        self._chart.clear_curves()
        if self._eff_line is not None:
            self._chart.plot_widget.removeItem(self._eff_line)
            self._eff_line = None

        # Filtered spectrum
        energies, phi = self._spectrum.generate(config)
        self._chart.add_curve(
            energies, phi, name=t("charts.filtered", "Filtered"), color="#60A5FA", width=2,
        )

        # Unfiltered comparison (optional)
        if self._cb_unfiltered.isChecked():
            e_unfilt, phi_unfilt = self._spectrum.generate_unfiltered(config)
            self._chart.add_curve(
                e_unfilt, phi_unfilt,
                name=t("charts.unfiltered", "Unfiltered"), color="#64748B", width=1,
            )

        # Effective energy vertical marker
        e_eff = self._spectrum.effective_energy(config)
        self._eff_line = self._chart.add_infinite_line(
            pos=e_eff, angle=90, color="#F59E0B",
            label=t("charts.eff_energy", "E_eff = {energy} keV").format(energy=f"{e_eff:.1f}"),
        )
