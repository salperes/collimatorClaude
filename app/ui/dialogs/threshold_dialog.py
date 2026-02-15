"""Quality metric threshold configuration dialog.

Allows user to customize penumbra, flatness, leakage, and
collimation ratio thresholds for quality classification.

Reference: FRD §4.3 FR-3.4.6.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QDoubleSpinBox, QGroupBox, QFormLayout,
)

from app.core.i18n import t


# Default thresholds (matching beam_simulation.py defaults)
DEFAULT_THRESHOLDS = {
    "penumbra_excellent": 5.0,
    "penumbra_acceptable": 10.0,
    "flatness_excellent": 3.0,
    "flatness_acceptable": 10.0,
    "leakage_excellent": 0.1,
    "leakage_acceptable": 5.0,
    "cr_excellent": 30.0,
    "cr_acceptable": 10.0,
}


class ThresholdDialog(QDialog):
    """Dialog for editing quality metric thresholds."""

    def __init__(self, current: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dialogs.threshold_title", "Quality Threshold Values"))
        self.setMinimumWidth(380)
        self._spins: dict[str, QDoubleSpinBox] = {}
        self._current = current or dict(DEFAULT_THRESHOLDS)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Penumbra group
        pen_group = QGroupBox(t("dialogs.threshold_penumbra", "Penumbra [mm] (lower = better)"))
        pen_form = QFormLayout(pen_group)
        pen_form.addRow(t("dialogs.threshold_excellent_le", "Excellent <="), self._spin("penumbra_excellent", 0.1, 50.0))
        pen_form.addRow(t("dialogs.threshold_acceptable_le", "Acceptable <="), self._spin("penumbra_acceptable", 0.1, 100.0))
        layout.addWidget(pen_group)

        # Flatness group
        flat_group = QGroupBox(t("dialogs.threshold_flatness", "Flatness [%] (lower = better)"))
        flat_form = QFormLayout(flat_group)
        flat_form.addRow(t("dialogs.threshold_excellent_le", "Excellent <="), self._spin("flatness_excellent", 0.1, 50.0))
        flat_form.addRow(t("dialogs.threshold_acceptable_le", "Acceptable <="), self._spin("flatness_acceptable", 0.1, 100.0))
        layout.addWidget(flat_group)

        # Leakage group
        leak_group = QGroupBox(t("dialogs.threshold_leakage", "Leakage [%] (lower = better)"))
        leak_form = QFormLayout(leak_group)
        leak_form.addRow(t("dialogs.threshold_excellent_le", "Excellent <="), self._spin("leakage_excellent", 0.001, 50.0))
        leak_form.addRow(t("dialogs.threshold_acceptable_le", "Acceptable <="), self._spin("leakage_acceptable", 0.01, 100.0))
        layout.addWidget(leak_group)

        # CR group
        cr_group = QGroupBox(t("dialogs.threshold_cr", "Collim. Ratio [dB] (higher = better)"))
        cr_form = QFormLayout(cr_group)
        cr_form.addRow(t("dialogs.threshold_excellent_ge", "Excellent >="), self._spin("cr_excellent", 1.0, 100.0))
        cr_form.addRow(t("dialogs.threshold_acceptable_ge", "Acceptable >="), self._spin("cr_acceptable", 1.0, 100.0))
        layout.addWidget(cr_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_reset = QPushButton(t("dialogs.threshold_default", "Default"))
        btn_reset.clicked.connect(self._reset_defaults)
        btn_ok = QPushButton(t("common.apply", "Apply"))
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(t("common.cancel", "Cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _spin(self, key: str, min_val: float, max_val: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setDecimals(2)
        spin.setSingleStep(0.5)
        spin.setValue(self._current.get(key, DEFAULT_THRESHOLDS[key]))
        self._spins[key] = spin
        return spin

    def _reset_defaults(self) -> None:
        for key, val in DEFAULT_THRESHOLDS.items():
            if key in self._spins:
                self._spins[key].setValue(val)

    def get_thresholds(self) -> dict[str, float]:
        """Return current threshold values."""
        return {key: spin.value() for key, spin in self._spins.items()}
