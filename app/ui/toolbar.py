"""Main toolbar — collimator type selection, energy slider, simulation.

Reference: FRD §6 — UI/UX Design, §4.2 FR-2.2.
"""

from PyQt6.QtWidgets import (
    QToolBar, QToolButton, QLabel, QSlider, QWidget, QHBoxLayout, QMenu,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSignalBlocker

from app.core.i18n import t, TranslationManager
from app.core.spectrum_models import effective_energy_kVp
from app.models.geometry import CollimatorType


def _get_type_name(ctype: CollimatorType) -> str:
    """Get translated display name for a collimator type."""
    return t(f"collimator_type.{ctype.name}", ctype.value)


# FRD §4.2 FR-2.2 — Energy presets (technical names, keep as-is)
_ENERGY_PRESETS: list[tuple[str, str, float]] = [
    ("Luggage Scan (80 kVp)", "kVp", 80),
    ("Cargo Low (160 kVp)", "kVp", 160),
    ("Cargo Standard (225 kVp)", "kVp", 225),
    ("Cargo Medium (320 kVp)", "kVp", 320),
    ("LINAC Low (1 MeV)", "MeV", 1.0),
    ("LINAC Medium (3.5 MeV)", "MeV", 3.5),
    ("LINAC High (6 MeV)", "MeV", 6.0),
]

# Added filtration presets: (key, material_id, thickness_mm)
# "Yok"/"None" is translatable; technical filter specs stay as-is
_FILTER_PRESETS: list[tuple[str, str | None, float]] = [
    ("none", None, 0.0),
    ("1 mm Cu", "Cu", 1.0),
    ("2 mm Al", "Al", 2.0),
    ("0.5 mm Cu", "Cu", 0.5),
]


class MainToolBar(QToolBar):
    """Application toolbar with collimator type menu and energy slider."""

    collimator_type_changed = pyqtSignal(object)  # CollimatorType
    custom_template_requested = pyqtSignal()  # blank geometry
    energy_changed = pyqtSignal(float)  # keV
    energy_mode_changed = pyqtSignal(str)  # "kVp" or "MeV"
    tube_config_changed = pyqtSignal()  # target, window, or energy changed
    compare_requested = pyqtSignal()  # multi-energy compare
    threshold_edit_requested = pyqtSignal()  # G-10: edit quality thresholds
    validation_requested = pyqtSignal()  # run physics validation tests
    about_requested = pyqtSignal()  # show about dialog

    # Phase 6: File menu signals
    new_requested = pyqtSignal()
    open_requested = pyqtSignal()
    import_external_requested = pyqtSignal()  # external format import
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
        self._file_menu = QMenu(self)

        self._action_new = self._file_menu.addAction("", self.new_requested.emit)
        self._action_open = self._file_menu.addAction("", self.open_requested.emit)
        self._action_import_ext = self._file_menu.addAction("", self.import_external_requested.emit)
        self._file_menu.addSeparator()
        self._action_save = self._file_menu.addAction("", self.save_requested.emit)
        self._action_save_as = self._file_menu.addAction("", self.save_as_requested.emit)
        self._file_menu.addSeparator()
        self._recent_menu = self._file_menu.addMenu("")
        self._file_menu.addSeparator()
        self._action_version_history = self._file_menu.addAction("", self.version_history_requested.emit)
        self._file_menu.addSeparator()
        self._action_export = self._file_menu.addAction("", self.export_requested.emit)

        self._btn_file.setMenu(self._file_menu)
        self._btn_file.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.addWidget(self._btn_file)

        self.addSeparator()

        # Collimator type button with menu
        self._btn_type = QToolButton()

        self._type_menu = QMenu(self)
        self._type_actions: list[tuple[CollimatorType, object]] = []
        for ctype in CollimatorType:
            action = self._type_menu.addAction("")
            action.triggered.connect(
                lambda checked, ct=ctype: self._on_type_selected(ct)
            )
            self._type_actions.append((ctype, action))
        self._type_menu.addSeparator()
        self._action_custom = self._type_menu.addAction("")
        self._action_custom.triggered.connect(self._on_custom_selected)

        self._btn_type.setMenu(self._type_menu)
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
        self._btn_mode.setCheckable(True)
        self._btn_mode.setChecked(False)  # unchecked = kVp
        self._btn_mode.toggled.connect(self._on_mode_toggled)
        energy_layout.addWidget(self._btn_mode)

        self._lbl_energy = QLabel()
        energy_layout.addWidget(self._lbl_energy)

        self._slider_energy = QSlider(Qt.Orientation.Horizontal)
        self._slider_energy.setFixedWidth(180)
        energy_layout.addWidget(self._slider_energy)

        self._lbl_energy_value = QLabel()
        self._lbl_energy_value.setFixedWidth(140)
        self._slider_energy.valueChanged.connect(self._on_energy_changed)
        energy_layout.addWidget(self._lbl_energy_value)

        # Presets dropdown
        self._btn_presets = QToolButton()
        preset_menu = QMenu(self)
        for name, mode, val in _ENERGY_PRESETS:
            action = preset_menu.addAction(name)
            action.triggered.connect(
                lambda checked, m=mode, v=val: self._apply_preset(m, v)
            )
        self._btn_presets.setMenu(preset_menu)
        self._btn_presets.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        energy_layout.addWidget(self._btn_presets)

        # Target material selector (kVp mode only)
        self._combo_target = QComboBox()
        self._combo_target.addItem("", "W")
        self._combo_target.addItem("", "Mo")
        self._combo_target.addItem("", "Rh")
        self._combo_target.addItem("", "Cu")
        self._combo_target.addItem("", "Ag")
        self._combo_target.setCurrentIndex(0)
        self._combo_target.currentIndexChanged.connect(self._on_tube_param_changed)
        energy_layout.addWidget(self._combo_target)

        # Window type selector (kVp mode only)
        self._combo_window = QComboBox()
        self._combo_window.addItem("", "glass")
        self._combo_window.addItem("", "Be")
        self._combo_window.setCurrentIndex(0)
        self._combo_window.currentIndexChanged.connect(self._on_tube_param_changed)
        energy_layout.addWidget(self._combo_window)

        # Added filtration selector (kVp mode only)
        self._combo_filter = QComboBox()
        for key, mat_id, thickness in _FILTER_PRESETS:
            self._combo_filter.addItem(key, (mat_id, thickness))
        self._combo_filter.setCurrentIndex(1)  # default: 1mm Cu
        self._combo_filter.currentIndexChanged.connect(self._on_tube_param_changed)
        energy_layout.addWidget(self._combo_filter)

        self.addWidget(energy_widget)

        # Initialize slider for kVp mode
        self._apply_mode_settings()

        self.addSeparator()

        # Grid spacing selector
        self._btn_grid = QToolButton()
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
        self._btn_simulate.setProperty("cssClass", "primary")
        self.addWidget(self._btn_simulate)

        # Compare button (G-3: multi-energy overlay)
        self._btn_compare = QToolButton()
        self._btn_compare.clicked.connect(self.compare_requested.emit)
        self.addWidget(self._btn_compare)

        # Scatter toggle button
        self._btn_scatter = QToolButton()
        self._btn_scatter.setCheckable(True)
        self._btn_scatter.setChecked(False)
        self._btn_scatter.toggled.connect(self._on_scatter_toggled)
        self.addWidget(self._btn_scatter)

        # Threshold settings button (G-10)
        self._btn_thresholds = QToolButton()
        self._btn_thresholds.clicked.connect(self.threshold_edit_requested.emit)
        self.addWidget(self._btn_thresholds)

        # Validation button
        self._btn_validation = QToolButton()
        self._btn_validation.clicked.connect(self.validation_requested.emit)
        self.addWidget(self._btn_validation)

        self.addSeparator()

        # Dimensions toggle button
        self._btn_dimensions = QToolButton()
        self._btn_dimensions.setCheckable(True)
        self._btn_dimensions.setChecked(True)
        self.addWidget(self._btn_dimensions)

        # Fit to content button
        self._btn_fit = QToolButton()
        self.addWidget(self._btn_fit)

        self.addSeparator()

        # About button
        self._btn_about = QToolButton()
        self._btn_about.clicked.connect(self.about_requested.emit)
        self.addWidget(self._btn_about)

        self.addSeparator()

        # Language selector
        self._combo_lang = QComboBox()
        from app.constants import SUPPORTED_LANGUAGES
        for code, display in SUPPORTED_LANGUAGES:
            self._combo_lang.addItem(display, code)
        # Set current from TranslationManager
        mgr = TranslationManager.instance()
        for i in range(self._combo_lang.count()):
            if self._combo_lang.itemData(i) == mgr.lang:
                self._combo_lang.setCurrentIndex(i)
                break
        self._combo_lang.currentIndexChanged.connect(self._on_language_changed)
        self.addWidget(self._combo_lang)

        # Apply translations and register for language changes
        self.retranslate_ui()
        TranslationManager.on_language_changed(self.retranslate_ui)

    # ── i18n ─────────────────────────────────────────────────────────

    def retranslate_ui(self) -> None:
        """Update all translatable text from the current language."""
        # File button + menu
        self._btn_file.setText(t("toolbar.file", "File"))
        self._btn_file.setToolTip(t("toolbar.file_tooltip", "File operations"))

        self._action_new.setText(t("toolbar.new", "New"))
        self._action_open.setText(t("toolbar.open", "Open..."))
        self._action_import_ext.setText(t("toolbar.import_external", "Import External Format..."))
        self._action_save.setText(t("toolbar.save", "Save"))
        self._action_save_as.setText(t("toolbar.save_as", "Save As..."))
        self._recent_menu.setTitle(t("toolbar.recent", "Recent"))
        self._action_version_history.setText(t("toolbar.version_history", "Version History..."))
        self._action_export.setText(t("toolbar.export", "Export..."))

        # Collimator type button + menu
        self._btn_type.setText(t("toolbar.collimator_type", "Collimator Type"))
        self._btn_type.setToolTip(t("toolbar.collimator_type_tooltip", "Select collimator type"))
        for ctype, action in self._type_actions:
            action.setText(_get_type_name(ctype))
        self._action_custom.setText(t("toolbar.custom_blank", "Custom (Blank)"))

        # Energy mode
        self._btn_mode.setToolTip(t("toolbar.energy_mode_tooltip", "Energy mode: kVp (X-ray tube) / MeV (LINAC)"))
        self._lbl_energy.setText(t("toolbar.energy", "Energy:"))
        self._slider_energy.setToolTip(t("toolbar.photon_energy", "Photon energy"))

        # Presets
        self._btn_presets.setText(t("toolbar.preset", "Preset"))
        self._btn_presets.setToolTip(t("toolbar.preset_tooltip", "Energy presets"))

        # Target combo
        self._combo_target.setToolTip(t("toolbar.target_tooltip", "X-ray tube target material"))
        with QSignalBlocker(self._combo_target):
            self._combo_target.setItemText(0, t("target.W", "W (Tungsten)"))
            self._combo_target.setItemText(1, t("target.Mo", "Mo (Molybdenum)"))
            self._combo_target.setItemText(2, t("target.Rh", "Rh (Rhodium)"))
            self._combo_target.setItemText(3, t("target.Cu", "Cu (Copper)"))
            self._combo_target.setItemText(4, t("target.Ag", "Ag (Silver)"))

        # Window combo
        self._combo_window.setToolTip(t("toolbar.window_tooltip", "Tube window type"))
        with QSignalBlocker(self._combo_window):
            self._combo_window.setItemText(0, t("toolbar.window_glass", "Glass (1mm Al-eq)"))
            self._combo_window.setItemText(1, t("toolbar.window_be", "Be (0.5mm)"))

        # Filter combo
        self._combo_filter.setToolTip(t("toolbar.filter_tooltip", "Added filtration (external filter)"))
        with QSignalBlocker(self._combo_filter):
            self._combo_filter.setItemText(0, t("toolbar.filter_none", "None"))
            for i, (key, _mat, _th) in enumerate(_FILTER_PRESETS):
                if i > 0:  # index 0 already set above
                    self._combo_filter.setItemText(i, key)

        # Grid
        self._btn_grid.setText("Grid: 10mm")
        self._btn_grid.setToolTip(t("toolbar.grid_tooltip", "Grid spacing"))

        # Simulate
        self._btn_simulate.setText(t("toolbar.simulate", "Simulate"))
        self._btn_simulate.setToolTip(t("toolbar.simulate_tooltip", "Start ray-tracing simulation"))

        # Compare
        self._btn_compare.setText(t("toolbar.compare", "Compare"))
        self._btn_compare.setToolTip(t("toolbar.compare_tooltip", "Multi-energy simulation comparison"))

        # Scatter
        self._btn_scatter.setText(f"Scatter: {'ON' if self._btn_scatter.isChecked() else 'OFF'}")
        self._btn_scatter.setToolTip(t("toolbar.scatter_tooltip", "Include Compton scatter simulation"))

        # Thresholds
        self._btn_thresholds.setText(t("toolbar.thresholds", "Thresholds"))
        self._btn_thresholds.setToolTip(t("toolbar.thresholds_tooltip", "Edit quality metric thresholds"))

        # Validation
        self._btn_validation.setText(t("toolbar.validation", "Validation"))
        self._btn_validation.setToolTip(t("toolbar.validation_tooltip", "Run physics engine validation tests"))

        # Dimensions
        self._btn_dimensions.setText(t("toolbar.dimensions", "Dimensions"))
        self._btn_dimensions.setToolTip(t("toolbar.dimensions_tooltip", "Show/hide dimension lines"))

        # Fit
        self._btn_fit.setText(t("toolbar.fit", "Fit"))
        self._btn_fit.setToolTip(t("toolbar.fit_tooltip", "Zoom to fit all content (F)"))

        # About
        self._btn_about.setText(t("toolbar.about", "About"))
        self._btn_about.setToolTip(t("toolbar.about_tooltip", "About the application"))

        # Language selector
        self._combo_lang.setToolTip(t("toolbar.language_tooltip", "Interface language"))

    # ── Language selector ────────────────────────────────────────────

    def _on_language_changed(self, idx: int) -> None:
        lang = self._combo_lang.itemData(idx)
        if lang:
            from PyQt6.QtCore import QSettings
            QSettings().setValue("language", lang)
            TranslationManager.instance().set_language(lang)

    # ── Energy mode & presets ────────────────────────────────────────

    def _on_mode_toggled(self, checked: bool) -> None:
        """Toggle between kVp and MeV mode."""
        self._energy_mode = "MeV" if checked else "kVp"
        self._btn_mode.setText(self._energy_mode)
        self._apply_mode_settings()
        # Target/window/filter selectors only relevant in kVp mode
        is_kvp = self._energy_mode == "kVp"
        self._combo_target.setVisible(is_kvp)
        self._combo_window.setVisible(is_kvp)
        self._combo_filter.setVisible(is_kvp)
        self.energy_mode_changed.emit(self._energy_mode)
        # Re-emit energy with new conversion
        self._on_energy_changed(self._slider_energy.value())

    def _apply_mode_settings(self) -> None:
        """Configure slider range based on current energy mode."""
        self._slider_energy.blockSignals(True)
        if self._energy_mode == "kVp":
            self._slider_energy.setMinimum(80)
            self._slider_energy.setMaximum(450)
            self._slider_energy.setSingleStep(5)
            self._slider_energy.setValue(225)
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
        if self._energy_mode == "kVp":
            self.tube_config_changed.emit()

    def _on_tube_param_changed(self) -> None:
        """Target or window type changed — update label and emit signal."""
        self._update_energy_label(self._slider_energy.value())
        self.tube_config_changed.emit()

    def _update_energy_label(self, slider_value: int) -> None:
        """Update the energy label based on mode and slider value."""
        if self._energy_mode == "kVp":
            eff = effective_energy_kVp(slider_value)
            target = self._combo_target.currentData()
            self._lbl_energy_value.setText(
                f"{slider_value} kVp (eff. {eff:.0f} keV, {target})"
            )
        else:
            mev = slider_value / 1000.0
            self._lbl_energy_value.setText(
                f"{mev:.1f} MeV ({slider_value} keV)"
            )

    # ── Type / grid ──────────────────────────────────────────────────

    def _on_type_selected(self, ctype: CollimatorType) -> None:
        self._btn_type.setText(_get_type_name(ctype))
        self.collimator_type_changed.emit(ctype)

    def _on_custom_selected(self) -> None:
        self._btn_type.setText(t("toolbar.custom", "Custom"))
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

    def get_target_id(self) -> str:
        """Current X-ray tube target material ID (e.g. 'W', 'Mo')."""
        return self._combo_target.currentData() or "W"

    def get_window_type(self) -> str:
        """Current tube window type: 'glass' or 'Be'."""
        return self._combo_window.currentData() or "glass"

    def get_window_thickness_mm(self) -> float:
        """Window thickness [mm] based on current selection."""
        wt = self.get_window_type()
        if wt == "Be":
            return 0.5
        return 1.0  # glass (Al-equivalent)

    def get_added_filtration(self) -> list[tuple[str, float]]:
        """Current added filtration list: [(material_id, thickness_mm), ...]."""
        data = self._combo_filter.currentData()
        if data is None:
            return []
        mat_id, thickness = data
        if mat_id is None or thickness <= 0:
            return []
        return [(mat_id, thickness)]
