"""Simulation configuration dialog — ray count, build-up, scatter options.

Allows user to configure simulation parameters before running.

Reference: Phase-06 spec.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QSpinBox, QVBoxLayout,
)

from app.constants import DEFAULT_NUM_RAYS, MAX_NUM_RAYS, MIN_NUM_RAYS
from app.core.i18n import t
from app.models.simulation import ComptonConfig, SimulationConfig


class SimulationConfigDialog(QDialog):
    """Dialog for configuring simulation parameters."""

    def __init__(
        self,
        current: SimulationConfig | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(t("dialogs.sim_config_title", "Simulation Settings"))
        self.setMinimumWidth(380)
        self._current = current
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        cur = self._current

        # General group
        gen_group = QGroupBox(t("dialogs.sim_config_general", "General"))
        gen_form = QFormLayout(gen_group)

        self._spin_rays = QSpinBox()
        self._spin_rays.setRange(MIN_NUM_RAYS, MAX_NUM_RAYS)
        self._spin_rays.setSingleStep(1000)
        self._spin_rays.setValue(cur.num_rays if cur else DEFAULT_NUM_RAYS)
        gen_form.addRow(t("dialogs.sim_config_rays", "Ray Count:"), self._spin_rays)

        self._cb_buildup = QCheckBox(t("dialogs.sim_config_include", "Include"))
        self._cb_buildup.setChecked(cur.include_buildup if cur else True)
        gen_form.addRow(t("dialogs.sim_config_buildup", "Build-up:"), self._cb_buildup)

        self._cb_air = QCheckBox(t("isodose.include_air", "Air Attenuation"))
        self._cb_air.setChecked(cur.include_air if cur else False)
        gen_form.addRow(t("dialogs.sim_config_air", "Air:"), self._cb_air)

        self._cb_inverse_sq = QCheckBox(t("isodose.include_inverse_sq", "1/r² Inverse Square"))
        self._cb_inverse_sq.setChecked(cur.include_inverse_sq if cur else False)
        gen_form.addRow(t("dialogs.sim_config_inverse_sq", "1/r²:"), self._cb_inverse_sq)

        layout.addWidget(gen_group)

        # Scatter group
        scatter_group = QGroupBox(t("dialogs.sim_config_compton", "Compton Scatter"))
        scatter_form = QFormLayout(scatter_group)

        cc = cur.compton_config if cur else ComptonConfig()

        self._cb_scatter = QCheckBox(t("dialogs.sim_config_scatter_include", "Include Scatter"))
        self._cb_scatter.setChecked(cur.include_scatter if cur else False)
        self._cb_scatter.toggled.connect(self._on_scatter_toggled)
        scatter_form.addRow(self._cb_scatter)

        self._spin_scatter_order = QSpinBox()
        self._spin_scatter_order.setRange(1, 5)
        self._spin_scatter_order.setValue(cc.max_scatter_order)
        scatter_form.addRow(t("dialogs.sim_config_max_scatter", "Max Scatter Order:"), self._spin_scatter_order)

        self._spin_scatter_rays = QSpinBox()
        self._spin_scatter_rays.setRange(1, 100)
        self._spin_scatter_rays.setValue(cc.scatter_rays_per_interaction)
        scatter_form.addRow(t("dialogs.sim_config_rays_per_interaction", "Rays/Interaction:"), self._spin_scatter_rays)

        self._spin_min_energy = QDoubleSpinBox()
        self._spin_min_energy.setRange(1.0, 1000.0)
        self._spin_min_energy.setSingleStep(5.0)
        self._spin_min_energy.setDecimals(1)
        self._spin_min_energy.setSuffix(" keV")
        self._spin_min_energy.setValue(cc.min_energy_cutoff_keV)
        scatter_form.addRow(t("dialogs.sim_config_min_energy", "Min Energy Cutoff:"), self._spin_min_energy)

        layout.addWidget(scatter_group)

        self._on_scatter_toggled(self._cb_scatter.isChecked())

        # Isodose group
        isodose_group = QGroupBox(t("dialogs.sim_config_isodose", "Isodose Map"))
        isodose_form = QFormLayout(isodose_group)

        self._cb_isodose = QCheckBox(t("dialogs.sim_config_isodose_include", "Compute Isodose Map"))
        self._cb_isodose.setChecked(cur.compute_isodose if cur else False)
        self._cb_isodose.toggled.connect(self._on_isodose_toggled)
        isodose_form.addRow(self._cb_isodose)

        self._spin_isodose_nx = QSpinBox()
        self._spin_isodose_nx.setRange(20, 300)
        self._spin_isodose_nx.setSingleStep(10)
        self._spin_isodose_nx.setValue(cur.isodose_nx if cur else 120)
        isodose_form.addRow(
            t("dialogs.sim_config_isodose_nx", "X Resolution:"),
            self._spin_isodose_nx,
        )

        self._spin_isodose_ny = QSpinBox()
        self._spin_isodose_ny.setRange(20, 200)
        self._spin_isodose_ny.setSingleStep(10)
        self._spin_isodose_ny.setValue(cur.isodose_ny if cur else 80)
        isodose_form.addRow(
            t("dialogs.sim_config_isodose_ny", "Y Resolution:"),
            self._spin_isodose_ny,
        )

        layout.addWidget(isodose_group)

        self._on_isodose_toggled(self._cb_isodose.isChecked())

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_scatter_toggled(self, enabled: bool) -> None:
        """Enable/disable scatter sub-settings."""
        self._spin_scatter_order.setEnabled(enabled)
        self._spin_scatter_rays.setEnabled(enabled)
        self._spin_min_energy.setEnabled(enabled)

    def _on_isodose_toggled(self, enabled: bool) -> None:
        """Enable/disable isodose resolution settings."""
        self._spin_isodose_nx.setEnabled(enabled)
        self._spin_isodose_ny.setEnabled(enabled)

    def get_config(self) -> SimulationConfig:
        """Return SimulationConfig from current dialog values."""
        compton_cfg = ComptonConfig(
            enabled=self._cb_scatter.isChecked(),
            max_scatter_order=self._spin_scatter_order.value(),
            scatter_rays_per_interaction=self._spin_scatter_rays.value(),
            min_energy_cutoff_keV=self._spin_min_energy.value(),
        )
        return SimulationConfig(
            num_rays=self._spin_rays.value(),
            include_buildup=self._cb_buildup.isChecked(),
            include_air=self._cb_air.isChecked(),
            include_inverse_sq=self._cb_inverse_sq.isChecked(),
            include_scatter=self._cb_scatter.isChecked(),
            compton_config=compton_cfg,
            compute_isodose=self._cb_isodose.isChecked(),
            isodose_nx=self._spin_isodose_nx.value(),
            isodose_ny=self._spin_isodose_ny.value(),
        )
