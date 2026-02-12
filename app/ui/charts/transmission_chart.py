"""Transmission chart — transmission ratio vs material thickness.

Plots Beer-Lambert transmission for selected materials at a given energy.

Reference: Phase-05 spec — FR-3.3.4.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.units import cm_to_mm
from app.ui.charts.base_chart import BaseChart
from app.ui.widgets.material_selector import MaterialSelector
from app.ui.styles.colors import MATERIAL_COLORS


class TransmissionChartWidget(QWidget):
    """Transmission vs thickness chart with material comparison."""

    def __init__(
        self,
        material_service: MaterialService,
        physics_engine: PhysicsEngine,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._material_service = material_service
        self._physics_engine = physics_engine
        self._energy: float = 1000.0  # keV default

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._selector = MaterialSelector(material_service)
        self._selector.selection_changed.connect(lambda _: self._update_chart())
        layout.addWidget(self._selector)

        self._energy_label = QLabel(f"Enerji: {self._energy:.0f} keV")
        self._energy_label.setStyleSheet("color: #B0BEC5; font-size: 9pt;")
        layout.addWidget(self._energy_label)

        self._chart = BaseChart(
            title="Iletim Orani vs Kalinlik",
            x_label="Kalinlik [mm]",
            y_label="Iletim (T)",
        )
        self._chart.enable_crosshair()
        layout.addWidget(self._chart, stretch=1)

        self._update_chart()

    def set_energy(self, energy_keV: float) -> None:
        """Update energy and redraw chart."""
        self._energy = energy_keV
        self._energy_label.setText(f"Enerji: {energy_keV:.0f} keV")
        self._update_chart()

    def _update_chart(self) -> None:
        """Compute and plot transmission vs thickness for selected materials."""
        self._chart.clear_curves()

        for mat_id in self._selector.selected_materials():
            try:
                points = self._physics_engine.thickness_sweep(
                    mat_id, self._energy,
                    max_thickness_mm=100.0,
                    steps=200,
                )
                if not points:
                    continue
                thickness_mm = np.array([float(cm_to_mm(p.thickness_cm)) for p in points])
                transmission = np.array([p.transmission for p in points])
                color = MATERIAL_COLORS.get(mat_id, "#B0BEC5")
                self._chart.add_curve(
                    thickness_mm, transmission,
                    name=mat_id, color=color,
                )
            except (KeyError, ValueError):
                continue
