"""Attenuation chart — mu/rho vs energy (log-log) with sub-components.

Plots mass attenuation coefficient for selected materials using NIST XCOM data.
Optionally shows photoelectric, Compton, and pair production sub-components.

Reference: Phase-05 spec — FR-3.3.1, FR-3.3.
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox

from app.core.i18n import t
from app.core.material_database import MaterialService
from app.ui.charts.base_chart import BaseChart
from app.ui.widgets.material_selector import MaterialSelector
from app.ui.styles.colors import MATERIAL_COLORS


class AttenuationChartWidget(QWidget):
    """mu/rho vs energy chart with material comparison and sub-components."""

    def __init__(
        self,
        material_service: MaterialService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._material_service = material_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top row: material selector + component toggle
        top_layout = QHBoxLayout()
        self._selector = MaterialSelector(material_service)
        self._selector.selection_changed.connect(lambda _: self._update_chart())
        top_layout.addWidget(self._selector, stretch=1)

        self._cb_components = QCheckBox(t("charts.show_subcomponents", "Show subcomponents"))
        self._cb_components.setToolTip(
            t("charts.subcomponents_tooltip", "Photoelectric, Compton, pair production components")
        )
        self._cb_components.toggled.connect(lambda _: self._update_chart())
        top_layout.addWidget(self._cb_components)
        layout.addLayout(top_layout)

        self._chart = BaseChart(
            title=t("charts.mass_attenuation_title", "Mass Attenuation Coefficient (μ/ρ)"),
            x_label=t("charts.energy_axis", "Energy [keV]"),
            y_label=t("charts.mu_rho_axis", "μ/ρ [cm²/g]"),
            log_x=True,
            log_y=True,
        )
        self._chart.enable_crosshair()
        layout.addWidget(self._chart, stretch=1)

        self._update_chart()

    def _update_chart(self) -> None:
        """Redraw curves for all selected materials."""
        self._chart.clear_curves()
        show_components = self._cb_components.isChecked()

        for mat_id in self._selector.selected_materials():
            try:
                data = self._material_service.get_attenuation_data(
                    mat_id, min_energy_keV=10, max_energy_keV=6000,
                )
                if not data:
                    continue
                energies = np.array([d.energy_keV for d in data])
                mu_rho = np.array([d.mass_attenuation for d in data])
                color = MATERIAL_COLORS.get(mat_id, "#B0BEC5")
                self._chart.add_curve(
                    energies, mu_rho, name=f"{mat_id} {t('charts.total_suffix', '(total)')}", color=color,
                )

                if show_components:
                    # Photoelectric — dashed, same color darker
                    pe = np.array([d.photoelectric for d in data])
                    if np.max(pe) > 1e-20:
                        self._chart.add_curve(
                            energies, pe,
                            name=f"{mat_id} {t('charts.pe_suffix', 'PE')}", color=color, width=1,
                        )

                    # Compton — dotted
                    comp = np.array([d.compton for d in data])
                    if np.max(comp) > 1e-20:
                        self._chart.add_curve(
                            energies, comp,
                            name=f"{mat_id} {t('charts.compton_suffix', 'Compton')}", color="#10B981", width=1,
                        )

                    # Pair production — dash-dot
                    pp = np.array([d.pair_production for d in data])
                    if np.max(pp) > 1e-20:
                        pp_valid = pp > 1e-20
                        if np.any(pp_valid):
                            self._chart.add_curve(
                                energies[pp_valid], pp[pp_valid],
                                name=f"{mat_id} {t('charts.pp_suffix', 'PP')}", color="#EF4444", width=1,
                            )
            except (KeyError, ValueError):
                continue
