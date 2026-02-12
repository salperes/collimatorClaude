"""Multi-energy comparison dialog — select energies for overlay.

FRD §4.2 FR-2.2 — Energy comparison feature.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QPushButton, QSpinBox, QGroupBox,
)
from PyQt6.QtCore import Qt

from app.core.spectrum_models import effective_energy_kVp


# Default energy presets for comparison
_COMPARE_PRESETS: list[tuple[str, float]] = [
    ("80 kVp (27 keV)", effective_energy_kVp(80)),
    ("160 kVp (53 keV)", effective_energy_kVp(160)),
    ("320 kVp (107 keV)", effective_energy_kVp(320)),
    ("1 MeV (1000 keV)", 1000.0),
    ("3.5 MeV (3500 keV)", 3500.0),
    ("6 MeV (6000 keV)", 6000.0),
]


class CompareDialog(QDialog):
    """Dialog for selecting multiple energies to compare beam profiles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enerji Karsilastirmasi")
        self.setMinimumWidth(350)
        self._checkboxes: list[tuple[QCheckBox, float]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Presets group
        group = QGroupBox("Enerji Preset'leri")
        group_layout = QVBoxLayout(group)

        for label, keV in _COMPARE_PRESETS:
            cb = QCheckBox(label)
            group_layout.addWidget(cb)
            self._checkboxes.append((cb, keV))

        # Pre-select first 3 (kVp range)
        for cb, _ in self._checkboxes[:3]:
            cb.setChecked(True)

        layout.addWidget(group)

        # Custom energy input
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("Ozel enerji [keV]:"))
        self._custom_spin = QSpinBox()
        self._custom_spin.setRange(10, 10000)
        self._custom_spin.setValue(500)
        self._custom_spin.setSingleStep(50)
        custom_layout.addWidget(self._custom_spin)
        self._cb_custom = QCheckBox("Ekle")
        custom_layout.addWidget(self._cb_custom)
        layout.addLayout(custom_layout)

        # Ray count
        ray_layout = QHBoxLayout()
        ray_layout.addWidget(QLabel("Isin sayisi:"))
        self._spin_rays = QSpinBox()
        self._spin_rays.setRange(36, 3600)
        self._spin_rays.setValue(360)
        self._spin_rays.setSingleStep(36)
        ray_layout.addWidget(self._spin_rays)
        layout.addLayout(ray_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Karsilastir")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Iptal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_energies_keV(self) -> list[float]:
        """Return list of selected energies [keV]."""
        energies = []
        for cb, keV in self._checkboxes:
            if cb.isChecked():
                energies.append(keV)
        if self._cb_custom.isChecked():
            energies.append(float(self._custom_spin.value()))
        return sorted(set(energies))

    def get_num_rays(self) -> int:
        """Return selected ray count."""
        return self._spin_rays.value()
