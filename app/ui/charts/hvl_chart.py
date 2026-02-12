"""HVL chart — Half-Value Layer vs energy.

Plots HVL [mm] for selected materials across an energy range.

Reference: Phase-05 spec — FR-3.3.3.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.units import cm_to_mm
from app.ui.charts.base_chart import BaseChart
from app.ui.widgets.material_selector import MaterialSelector
from app.ui.styles.colors import MATERIAL_COLORS


class HvlChartWidget(QWidget):
    """HVL vs energy chart with material comparison."""

    def __init__(
        self,
        material_service: MaterialService,
        physics_engine: PhysicsEngine,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._material_service = material_service
        self._physics_engine = physics_engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._selector = MaterialSelector(material_service)
        self._selector.selection_changed.connect(lambda _: self._update_chart())
        layout.addWidget(self._selector)

        self._chart = BaseChart(
            title="Yari Deger Kalinligi (HVL)",
            x_label="Enerji [keV]",
            y_label="HVL [mm]",
            log_x=True,
        )
        self._chart.enable_crosshair()
        layout.addWidget(self._chart, stretch=1)

        self._update_chart()

    def _update_chart(self) -> None:
        """Compute and plot HVL vs energy for selected materials."""
        self._chart.clear_curves()

        energies = np.logspace(np.log10(30), np.log10(6000), 60)

        for mat_id in self._selector.selected_materials():
            hvl_mm = []
            valid_energies = []
            for e in energies:
                try:
                    result = self._physics_engine.calculate_hvl_tvl(mat_id, float(e))
                    hvl_val = float(cm_to_mm(result.hvl_cm))
                    if hvl_val > 0:
                        hvl_mm.append(hvl_val)
                        valid_energies.append(e)
                except (KeyError, ValueError, ZeroDivisionError):
                    continue

            if valid_energies:
                color = MATERIAL_COLORS.get(mat_id, "#B0BEC5")
                self._chart.add_curve(
                    np.array(valid_energies),
                    np.array(hvl_mm),
                    name=mat_id,
                    color=color,
                )
