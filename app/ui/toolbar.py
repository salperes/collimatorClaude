"""Main toolbar — collimator type selection, energy slider, simulation.

Reference: FRD §6 — UI/UX Design, §4.2 FR-2.2.
"""

from PyQt6.QtWidgets import (
    QToolBar, QToolButton, QLabel, QSlider, QWidget, QHBoxLayout, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.core.spectrum_models import effective_energy_kVp
from app.models.geometry import CollimatorType


_TYPE_NAMES = {
    CollimatorType.FAN_BEAM: "Yelpaze (Fan Beam)",
    CollimatorType.PENCIL_BEAM: "Kalem (Pencil Beam)",
    CollimatorType.SLIT: "Yarık (Slit)",
}

# FRD §4.2 FR-2.2 — Energy presets
_ENERGY_PRESETS: list[tuple[str, str, float]] = [
    ("Luggage Scan (80 kVp)", "kVp", 80),
    ("Cargo Low (160 kVp)", "kVp", 160),
    ("Cargo Medium (320 kVp)", "kVp", 320),
    ("LINAC Low (1 MeV)", "MeV", 1.0),
    ("LINAC Medium (3.5 MeV)", "MeV", 3.5),
    ("LINAC High (6 MeV)", "MeV", 6.0),
]


class MainToolBar(QToolBar):
    """Application toolbar with collimator type menu and energy slider."""

    collimator_type_changed = pyqtSignal(object)  # CollimatorType
    custom_template_requested = pyqtSignal()  # blank geometry
    energy_changed = pyqtSignal(float)  # keV
    energy_mode_changed = pyqtSignal(str)  # "kVp" or "MeV"
    compare_requested = pyqtSignal()  # multi-energy compare
    threshold_edit_requested = pyqtSignal()  # G-10: edit quality thresholds
    validation_requested = pyqtSignal()  # run physics validation tests

    # Phase 6: File menu signals
    new_requested = pyqtSignal()
    open_requested = pyqtSignal()
    save_requested = pyqtSignal()
    save_as_requested = pyqtSignal()
    export_requested = pyqtSignal()
    version_history_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self._energy_mode: str = "kVp"  # "kVp" or "MeV"
        self._build_ui()

    def _build_ui(self):
        # File button with menu
        self._btn_file = QToolButton()
        self._btn_file.setText("Dosya")
        self._btn_file.setToolTip("Dosya islemleri")

        file_menu = QMenu(self)
        file_menu.addAction("Yeni", self.new_requested.emit)
        file_menu.addAction("Ac...", self.open_requested.emit)
        file_menu.addSeparator()
        file_menu.addAction("Kaydet", self.save_requested.emit)
        file_menu.addAction("Farkli Kaydet...", self.save_as_requested.emit)
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Son Kullanilanlar")
        file_menu.addSeparator()
        file_menu.addAction("Versiyon Gecmisi...", self.version_history_requested.emit)
        file_menu.addSeparator()
        file_menu.addAction("Disa Aktar...", self.export_requested.emit)

        self._btn_file.setMenu(file_menu)
        self._btn_file.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.addWidget(self._btn_file)

        self.addSeparator()

        # Collimator type button with menu
        self._btn_type = QToolButton()
        self._btn_type.setText("Kolimatör Tipi")
        self._btn_type.setToolTip("Kolimatör tipini seçin")

        type_menu = QMenu(self)
        for ctype, display_name in _TYPE_NAMES.items():
            action = type_menu.addAction(display_name)
            action.triggered.connect(
                lambda checked, t=ctype: self._on_type_selected(t)
            )
        type_menu.addSeparator()
        action_custom = type_menu.addAction("Özel (Boş)")
        action_custom.triggered.connect(self._on_custom_selected)

        self._btn_type.setMenu(type_menu)
        self._btn_type.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.addWidget(self._btn_type)

        self.addSeparator()

        # Energy group: mode toggle + slider + presets
        energy_widget = QWidget()
        energy_layout = QHBoxLayout(energy_widget)
        energy_layout.setContentsMargins(4, 0, 4, 0)
        energy_layout.setSpacing(6)

        # Mode toggle (kVp / MeV)
        self._btn_mode = QToolButton()
        self._btn_mode.setText("kVp")
        self._btn_mode.setToolTip("Enerji modu: kVp (X-ray tup) / MeV (LINAC)")
        self._btn_mode.setCheckable(True)
        self._btn_mode.setChecked(False)  # unchecked = kVp
        self._btn_mode.toggled.connect(self._on_mode_toggled)
        energy_layout.addWidget(self._btn_mode)

        energy_label = QLabel("Enerji:")
        energy_layout.addWidget(energy_label)

        self._slider_energy = QSlider(Qt.Orientation.Horizontal)
        self._slider_energy.setFixedWidth(180)
        self._slider_energy.setToolTip("Foton enerjisi")
        energy_layout.addWidget(self._slider_energy)

        self._lbl_energy_value = QLabel()
        self._lbl_energy_value.setFixedWidth(140)
        self._slider_energy.valueChanged.connect(self._on_energy_changed)
        energy_layout.addWidget(self._lbl_energy_value)

        # Presets dropdown
        self._btn_presets = QToolButton()
        self._btn_presets.setText("Preset")
        self._btn_presets.setToolTip("Enerji preset'leri (FRD §4.2)")
        preset_menu = QMenu(self)
        for name, mode, val in _ENERGY_PRESETS:
            action = preset_menu.addAction(name)
            action.triggered.connect(
                lambda checked, m=mode, v=val: self._apply_preset(m, v)
            )
        self._btn_presets.setMenu(preset_menu)
        self._btn_presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        energy_layout.addWidget(self._btn_presets)

        self.addWidget(energy_widget)

        # Initialize slider for kVp mode
        self._apply_mode_settings()

        self.addSeparator()

        # Grid spacing selector
        self._btn_grid = QToolButton()
        self._btn_grid.setText("Grid: 10mm")
        self._btn_grid.setToolTip("Izgara aralığı")
        grid_menu = QMenu(self)
        for spacing in [1, 5, 10, 50]:
            action = grid_menu.addAction(f"{spacing} mm")
            action.triggered.connect(
                lambda checked, s=spacing: self._on_grid_selected(s)
            )
        self._btn_grid.setMenu(grid_menu)
        self._btn_grid.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.addWidget(self._btn_grid)

        self.addSeparator()

        # Simulate button
        self._btn_simulate = QToolButton()
        self._btn_simulate.setText("Simüle Et")
        self._btn_simulate.setToolTip("Işın izleme simülasyonunu başlat")
        self._btn_simulate.setProperty("cssClass", "primary")
        self.addWidget(self._btn_simulate)

        # Compare button (G-3: multi-energy overlay)
        self._btn_compare = QToolButton()
        self._btn_compare.setText("Karsilastir")
        self._btn_compare.setToolTip("Birden fazla enerjide simülasyon karsilastirmasi")
        self._btn_compare.clicked.connect(self.compare_requested.emit)
        self.addWidget(self._btn_compare)

        # Scatter toggle button
        self._btn_scatter = QToolButton()
        self._btn_scatter.setText("Scatter: OFF")
        self._btn_scatter.setToolTip("Compton scatter simulasyonunu dahil et")
        self._btn_scatter.setCheckable(True)
        self._btn_scatter.setChecked(False)
        self._btn_scatter.toggled.connect(self._on_scatter_toggled)
        self.addWidget(self._btn_scatter)

        # Threshold settings button (G-10)
        self._btn_thresholds = QToolButton()
        self._btn_thresholds.setText("Esikler")
        self._btn_thresholds.setToolTip("Kalite metrik esik degerlerini duzenle")
        self._btn_thresholds.clicked.connect(self.threshold_edit_requested.emit)
        self.addWidget(self._btn_thresholds)

        # Validation button
        self._btn_validation = QToolButton()
        self._btn_validation.setText("Dogrulama")
        self._btn_validation.setToolTip("Fizik motoru dogrulama testlerini calistir")
        self._btn_validation.clicked.connect(self.validation_requested.emit)
        self.addWidget(self._btn_validation)

        self.addSeparator()

        # Dimensions toggle button
        self._btn_dimensions = QToolButton()
        self._btn_dimensions.setText("Boyutlar")
        self._btn_dimensions.setToolTip("Ölçü çizgilerini göster/gizle")
        self._btn_dimensions.setCheckable(True)
        self._btn_dimensions.setChecked(True)
        self.addWidget(self._btn_dimensions)

        # Fit to content button
        self._btn_fit = QToolButton()
        self._btn_fit.setText("Sığdır")
        self._btn_fit.setToolTip("Tüm içeriğe zoom yap (F)")
        self.addWidget(self._btn_fit)

    # ── Energy mode & presets ────────────────────────────────────────

    def _on_mode_toggled(self, checked: bool) -> None:
        """Toggle between kVp and MeV mode."""
        self._energy_mode = "MeV" if checked else "kVp"
        self._btn_mode.setText(self._energy_mode)
        self._apply_mode_settings()
        self.energy_mode_changed.emit(self._energy_mode)
        # Re-emit energy with new conversion
        self._on_energy_changed(self._slider_energy.value())

    def _apply_mode_settings(self) -> None:
        """Configure slider range based on current energy mode."""
        self._slider_energy.blockSignals(True)
        if self._energy_mode == "kVp":
            self._slider_energy.setMinimum(80)
            self._slider_energy.setMaximum(300)
            self._slider_energy.setSingleStep(10)
            self._slider_energy.setValue(160)
        else:  # MeV
            # Slider in keV: 500–6000
            self._slider_energy.setMinimum(500)
            self._slider_energy.setMaximum(6000)
            self._slider_energy.setSingleStep(100)
            self._slider_energy.setValue(1000)
        self._slider_energy.blockSignals(False)
        self._update_energy_label(self._slider_energy.value())

    def _apply_preset(self, mode: str, value: float) -> None:
        """Apply an energy preset."""
        # Switch mode if needed
        if mode == "MeV" and self._energy_mode != "MeV":
            self._btn_mode.setChecked(True)  # triggers _on_mode_toggled
        elif mode == "kVp" and self._energy_mode != "kVp":
            self._btn_mode.setChecked(False)

        if mode == "kVp":
            self._slider_energy.setValue(int(value))
        else:
            # MeV → keV for slider
            self._slider_energy.setValue(int(value * 1000))

    def _on_energy_changed(self, value: int) -> None:
        self._update_energy_label(value)
        keV = self.get_energy_keV()
        self.energy_changed.emit(keV)

    def _update_energy_label(self, slider_value: int) -> None:
        """Update the energy label based on mode and slider value."""
        if self._energy_mode == "kVp":
            eff = effective_energy_kVp(slider_value)
            self._lbl_energy_value.setText(
                f"{slider_value} kVp (eff. {eff:.0f} keV)"
            )
        else:
            mev = slider_value / 1000.0
            self._lbl_energy_value.setText(
                f"{mev:.1f} MeV ({slider_value} keV)"
            )

    # ── Type / grid ──────────────────────────────────────────────────

    def _on_type_selected(self, ctype: CollimatorType) -> None:
        self._btn_type.setText(_TYPE_NAMES.get(ctype, "Kolimatör Tipi"))
        self.collimator_type_changed.emit(ctype)

    def _on_custom_selected(self) -> None:
        self._btn_type.setText("Özel")
        self.custom_template_requested.emit()

    def _on_grid_selected(self, spacing: int) -> None:
        self._btn_grid.setText(f"Grid: {spacing}mm")

    def _on_scatter_toggled(self, checked: bool) -> None:
        self._btn_scatter.setText(f"Scatter: {'ON' if checked else 'OFF'}")

    # ── Properties ───────────────────────────────────────────────────

    @property
    def energy_mode(self) -> str:
        """Current energy mode: 'kVp' or 'MeV'."""
        return self._energy_mode

    @property
    def fit_button(self) -> QToolButton:
        """Access the fit-to-content button for signal connection."""
        return self._btn_fit

    @property
    def grid_button(self) -> QToolButton:
        return self._btn_grid

    @property
    def dimensions_button(self) -> QToolButton:
        return self._btn_dimensions

    @property
    def scatter_button(self) -> QToolButton:
        """Access the scatter toggle button."""
        return self._btn_scatter

    @property
    def recent_menu(self) -> QMenu:
        """Access the recent designs submenu."""
        return self._recent_menu

    def get_energy_keV(self) -> float:
        """Current effective energy [keV].

        In kVp mode: returns effective energy (kVp/3).
        In MeV mode: returns slider value directly in keV.
        """
        val = self._slider_energy.value()
        if self._energy_mode == "kVp":
            return effective_energy_kVp(val)
        return float(val)

    def get_slider_raw(self) -> int:
        """Raw slider value (kVp or keV depending on mode)."""
        return self._slider_energy.value()
