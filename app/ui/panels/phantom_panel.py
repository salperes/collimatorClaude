"""Phantom panel — test object configuration UI.

Add/remove/edit phantoms (wire, line-pair, grid).
Syncs bidirectionally with GeometryController.

Reference: Phase-03.5 spec — Phantom Panel.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QComboBox, QCheckBox, QFrame, QListWidget,
    QListWidgetItem, QPushButton,
)

from app.ui.widgets.smart_spinbox import SmartDoubleSpinBox
from PyQt6.QtCore import QSignalBlocker, Qt

from app.constants import MATERIAL_IDS
from app.core.i18n import t, TranslationManager
from app.models.phantom import (
    GridPhantom,
    LinePairPhantom,
    PhantomType,
    WirePhantom,
)
from app.ui.canvas.geometry_controller import GeometryController


class PhantomPanel(QWidget):
    """Panel for managing test objects (phantoms).

    Sections: phantom list, common properties, type-specific properties.
    """

    def __init__(
        self,
        controller: GeometryController,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._build_ui()
        self._connect_signals()
        self._refresh_all()
        TranslationManager.on_language_changed(self.retranslate_ui)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # --- Add/Remove buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(3)

        self._btn_add_wire = QPushButton(t("phantom.add_wire", "+ Wire"))
        self._btn_add_wire.setProperty("cssClass", "small")
        btn_row.addWidget(self._btn_add_wire)

        self._btn_add_lp = QPushButton(t("phantom.add_lp", "+ Line"))
        self._btn_add_lp.setProperty("cssClass", "small")
        btn_row.addWidget(self._btn_add_lp)

        self._btn_add_grid = QPushButton(t("phantom.add_grid", "+ Grid"))
        self._btn_add_grid.setProperty("cssClass", "small")
        btn_row.addWidget(self._btn_add_grid)

        self._btn_remove = QPushButton(t("phantom.remove", "- Remove"))
        self._btn_remove.setProperty("cssClass", "small-danger")
        btn_row.addWidget(self._btn_remove)

        layout.addLayout(btn_row)

        # --- Phantom list ---
        self._list = QListWidget()
        self._list.setMaximumHeight(100)
        self._list.setProperty("cssClass", "small-list")
        layout.addWidget(self._list)

        # --- Common properties ---
        common_frame = self._make_frame()
        common_layout = QVBoxLayout(common_frame)
        common_layout.setContentsMargins(6, 4, 6, 4)
        common_layout.setSpacing(3)

        # Y Position
        row_y = QHBoxLayout()
        self._lbl_y_position = self._prop_label(t("phantom.y_position_mm", "Y Pos (mm):"))
        row_y.addWidget(self._lbl_y_position)
        self._spin_y = SmartDoubleSpinBox()
        self._spin_y.setRange(0, 5000)
        self._spin_y.setDecimals(2)
        self._spin_y.setSingleStep(1.0)
        row_y.addWidget(self._spin_y)
        common_layout.addLayout(row_y)

        # Material
        row_mat = QHBoxLayout()
        self._lbl_material = self._prop_label(t("phantom.material", "Material:"))
        row_mat.addWidget(self._lbl_material)
        self._combo_material = QComboBox()
        self._combo_material.setProperty("cssClass", "small-combo")
        for mid in MATERIAL_IDS:
            self._combo_material.addItem(mid, mid)
        row_mat.addWidget(self._combo_material)
        common_layout.addLayout(row_mat)

        # Enabled
        row_en = QHBoxLayout()
        self._lbl_enabled = self._prop_label(t("phantom.enabled", "Enabled:"))
        row_en.addWidget(self._lbl_enabled)
        self._chk_enabled = QCheckBox()
        self._chk_enabled.setChecked(True)
        row_en.addWidget(self._chk_enabled)
        row_en.addStretch()
        common_layout.addLayout(row_en)

        layout.addWidget(common_frame)

        # --- Wire properties ---
        self._wire_frame = self._make_frame()
        wire_layout = QVBoxLayout(self._wire_frame)
        wire_layout.setContentsMargins(6, 4, 6, 4)
        wire_layout.setSpacing(3)

        row_wd = QHBoxLayout()
        self._lbl_wire_diameter = self._prop_label(t("phantom.diameter_mm", "Dia (mm):"))
        row_wd.addWidget(self._lbl_wire_diameter)
        self._spin_wire_d = SmartDoubleSpinBox()
        self._spin_wire_d.setRange(0.01, 10.0)
        self._spin_wire_d.setDecimals(2)
        self._spin_wire_d.setSingleStep(0.1)
        row_wd.addWidget(self._spin_wire_d)
        wire_layout.addLayout(row_wd)

        layout.addWidget(self._wire_frame)

        # --- Line-pair properties ---
        self._lp_frame = self._make_frame()
        lp_layout = QVBoxLayout(self._lp_frame)
        lp_layout.setContentsMargins(6, 4, 6, 4)
        lp_layout.setSpacing(3)

        row_freq = QHBoxLayout()
        self._lbl_frequency = self._prop_label(t("phantom.frequency", "Frequency:"))
        row_freq.addWidget(self._lbl_frequency)
        self._spin_lp_freq = SmartDoubleSpinBox()
        self._spin_lp_freq.setRange(0.1, 20.0)
        self._spin_lp_freq.setSuffix(" lp/mm")
        self._spin_lp_freq.setDecimals(2)
        self._spin_lp_freq.setSingleStep(0.1)
        row_freq.addWidget(self._spin_lp_freq)
        lp_layout.addLayout(row_freq)

        row_bt = QHBoxLayout()
        self._lbl_thickness = self._prop_label(t("phantom.thickness_mm", "Thick (mm):"))
        row_bt.addWidget(self._lbl_thickness)
        self._spin_lp_thick = SmartDoubleSpinBox()
        self._spin_lp_thick.setRange(0.1, 10.0)
        self._spin_lp_thick.setDecimals(2)
        self._spin_lp_thick.setSingleStep(0.1)
        row_bt.addWidget(self._spin_lp_thick)
        lp_layout.addLayout(row_bt)

        row_nc = QHBoxLayout()
        self._lbl_cycles = self._prop_label(t("phantom.cycles", "Cycles:"))
        row_nc.addWidget(self._lbl_cycles)
        self._spin_lp_cycles = QSpinBox()
        self._spin_lp_cycles.setRange(1, 50)
        row_nc.addWidget(self._spin_lp_cycles)
        lp_layout.addLayout(row_nc)

        layout.addWidget(self._lp_frame)

        # --- Grid properties ---
        self._grid_frame = self._make_frame()
        grid_layout = QVBoxLayout(self._grid_frame)
        grid_layout.setContentsMargins(6, 4, 6, 4)
        grid_layout.setSpacing(3)

        row_pitch = QHBoxLayout()
        self._lbl_pitch = self._prop_label(t("phantom.pitch_mm", "Pitch (mm):"))
        row_pitch.addWidget(self._lbl_pitch)
        self._spin_grid_pitch = SmartDoubleSpinBox()
        self._spin_grid_pitch.setRange(0.1, 50.0)
        self._spin_grid_pitch.setDecimals(2)
        self._spin_grid_pitch.setSingleStep(0.5)
        row_pitch.addWidget(self._spin_grid_pitch)
        grid_layout.addLayout(row_pitch)

        row_gw = QHBoxLayout()
        self._lbl_grid_wire_d = self._prop_label(t("phantom.wire_dia_mm", "Wire (mm):"))
        row_gw.addWidget(self._lbl_grid_wire_d)
        self._spin_grid_wd = SmartDoubleSpinBox()
        self._spin_grid_wd.setRange(0.01, 5.0)
        self._spin_grid_wd.setDecimals(2)
        self._spin_grid_wd.setSingleStep(0.1)
        row_gw.addWidget(self._spin_grid_wd)
        grid_layout.addLayout(row_gw)

        layout.addWidget(self._grid_frame)

        layout.addStretch()

    def _prop_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("cssClass", "prop-label")
        lbl.setFixedWidth(65)
        return lbl

    def _make_frame(self) -> QFrame:
        frame = QFrame()
        frame.setProperty("cssClass", "prop-frame")
        return frame

    def _connect_signals(self) -> None:
        ctrl = self._controller

        # Controller -> panel
        ctrl.phantom_added.connect(self._refresh_all)
        ctrl.phantom_removed.connect(self._refresh_all)
        ctrl.phantom_changed.connect(self._on_phantom_changed)
        ctrl.phantom_selected.connect(self._on_phantom_selected)
        ctrl.geometry_changed.connect(self._refresh_all)

        # Button clicks
        self._btn_add_wire.clicked.connect(
            lambda: ctrl.add_phantom(PhantomType.WIRE))
        self._btn_add_lp.clicked.connect(
            lambda: ctrl.add_phantom(PhantomType.LINE_PAIR))
        self._btn_add_grid.clicked.connect(
            lambda: ctrl.add_phantom(PhantomType.GRID))
        self._btn_remove.clicked.connect(self._on_remove_clicked)

        # List selection
        self._list.currentRowChanged.connect(self._on_list_selection)

        # Property editors -> controller
        self._spin_y.valueChanged.connect(self._on_y_changed)
        self._combo_material.currentIndexChanged.connect(self._on_material_changed)
        self._chk_enabled.toggled.connect(self._on_enabled_changed)

        # Wire
        self._spin_wire_d.valueChanged.connect(self._on_wire_d_changed)

        # Line-pair
        self._spin_lp_freq.valueChanged.connect(self._on_lp_freq_changed)
        self._spin_lp_thick.valueChanged.connect(self._on_lp_thick_changed)
        self._spin_lp_cycles.valueChanged.connect(self._on_lp_cycles_changed)

        # Grid
        self._spin_grid_pitch.valueChanged.connect(self._on_grid_pitch_changed)
        self._spin_grid_wd.valueChanged.connect(self._on_grid_wd_changed)

    # ------------------------------------------------------------------
    # Retranslation
    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Update all translatable strings after language change."""
        self._btn_add_wire.setText(t("phantom.add_wire", "+ Wire"))
        self._btn_add_lp.setText(t("phantom.add_lp", "+ Line"))
        self._btn_add_grid.setText(t("phantom.add_grid", "+ Grid"))
        self._btn_remove.setText(t("phantom.remove", "- Remove"))

        # Common property labels
        self._lbl_y_position.setText(t("phantom.y_position_mm", "Y Pos (mm):"))
        self._lbl_material.setText(t("phantom.material", "Material:"))
        self._lbl_enabled.setText(t("phantom.enabled", "Enabled:"))

        # Wire
        self._lbl_wire_diameter.setText(t("phantom.diameter_mm", "Dia (mm):"))

        # Line-pair
        self._lbl_frequency.setText(t("phantom.frequency", "Frequency:"))
        self._lbl_thickness.setText(t("phantom.thickness_mm", "Thick (mm):"))
        self._lbl_cycles.setText(t("phantom.cycles", "Cycles:"))

        # Grid
        self._lbl_pitch.setText(t("phantom.pitch_mm", "Pitch (mm):"))
        self._lbl_grid_wire_d.setText(t("phantom.wire_dia_mm", "Wire (mm):"))

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self, *_args) -> None:
        """Rebuild the phantom list and refresh properties."""
        with QSignalBlocker(self._list):
            self._list.clear()
            for phantom in self._controller.geometry.phantoms:
                item = QListWidgetItem(phantom.config.name)
                self._list.addItem(item)

            idx = self._controller.active_phantom_index
            if 0 <= idx < self._list.count():
                self._list.setCurrentRow(idx)

        self._refresh_properties()

    def _on_phantom_changed(self, index: int) -> None:
        phantoms = self._controller.geometry.phantoms
        if 0 <= index < len(phantoms):
            name = phantoms[index].config.name
            item = self._list.item(index)
            if item:
                item.setText(name)
        if index == self._controller.active_phantom_index:
            self._refresh_properties()

    def _on_phantom_selected(self, index: int) -> None:
        with QSignalBlocker(self._list):
            if 0 <= index < self._list.count():
                self._list.setCurrentRow(index)
        self._refresh_properties()

    def _refresh_properties(self) -> None:
        """Update property editors from active phantom."""
        phantom = self._controller.active_phantom

        # Hide all type frames
        self._wire_frame.setVisible(False)
        self._lp_frame.setVisible(False)
        self._grid_frame.setVisible(False)

        if phantom is None:
            return

        cfg = phantom.config

        with QSignalBlocker(self._spin_y):
            self._spin_y.setValue(cfg.position_y)

        with QSignalBlocker(self._combo_material):
            idx = self._combo_material.findData(cfg.material_id)
            if idx >= 0:
                self._combo_material.setCurrentIndex(idx)

        with QSignalBlocker(self._chk_enabled):
            self._chk_enabled.setChecked(cfg.enabled)

        if isinstance(phantom, WirePhantom):
            self._wire_frame.setVisible(True)
            with QSignalBlocker(self._spin_wire_d):
                self._spin_wire_d.setValue(phantom.diameter)

        elif isinstance(phantom, LinePairPhantom):
            self._lp_frame.setVisible(True)
            with QSignalBlocker(self._spin_lp_freq):
                self._spin_lp_freq.setValue(phantom.frequency)
            with QSignalBlocker(self._spin_lp_thick):
                self._spin_lp_thick.setValue(phantom.bar_thickness)
            with QSignalBlocker(self._spin_lp_cycles):
                self._spin_lp_cycles.setValue(phantom.num_cycles)

        elif isinstance(phantom, GridPhantom):
            self._grid_frame.setVisible(True)
            with QSignalBlocker(self._spin_grid_pitch):
                self._spin_grid_pitch.setValue(phantom.pitch)
            with QSignalBlocker(self._spin_grid_wd):
                self._spin_grid_wd.setValue(phantom.wire_diameter)

    # ------------------------------------------------------------------
    # Widget -> controller slots
    # ------------------------------------------------------------------

    def _on_remove_clicked(self) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.remove_phantom(idx)

    def _on_list_selection(self, row: int) -> None:
        if row >= 0:
            self._controller.select_phantom(row)

    def _on_y_changed(self, value: float) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_phantom_position(idx, value)

    def _on_material_changed(self, _combo_idx: int) -> None:
        idx = self._controller.active_phantom_index
        mat = self._combo_material.currentData()
        if idx >= 0 and mat:
            self._controller.set_phantom_material(idx, mat)

    def _on_enabled_changed(self, checked: bool) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_phantom_enabled(idx, checked)

    def _on_wire_d_changed(self, value: float) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_wire_diameter(idx, value)

    def _on_lp_freq_changed(self, value: float) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_line_pair_frequency(idx, value)

    def _on_lp_thick_changed(self, value: float) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_line_pair_thickness(idx, value)

    def _on_lp_cycles_changed(self, value: int) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_line_pair_num_cycles(idx, value)

    def _on_grid_pitch_changed(self, value: float) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_grid_pitch(idx, value)

    def _on_grid_wd_changed(self, value: float) -> None:
        idx = self._controller.active_phantom_index
        if idx >= 0:
            self._controller.set_grid_wire_diameter(idx, value)
