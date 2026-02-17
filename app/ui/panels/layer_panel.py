"""Layer panel — right dock panel for stage management.

Top: Stage selector (combo + add/remove/move buttons)
Middle: Stage properties (name, purpose, dimensions, gap, material, wall thickness)
Bottom: Aperture configuration

Reference: Phase-03 spec — FR-1.4, Stage/Layer Management.
"""

import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QFrame,
)

from app.ui.widgets.smart_spinbox import SmartDoubleSpinBox
from PyQt6.QtCore import Qt, QSignalBlocker

from app.constants import MATERIAL_IDS, MAX_STAGES, MIN_STAGES, MATERIAL_MIME_TYPE
from app.core.i18n import t, TranslationManager
from app.models.geometry import (
    StagePurpose, ApertureConfig, CollimatorType,
)
from app.ui.canvas.geometry_controller import GeometryController
from app.ui.styles.colors import MATERIAL_COLORS


# Stage purpose English fallback names (keyed by StagePurpose enum name)
_PURPOSE_DEFAULTS: dict[str, str] = {
    "PRIMARY_SHIELDING": "Primary Shielding",
    "SECONDARY_SHIELDING": "Secondary Shielding",
    "FAN_DEFINITION": "Fan Definition",
    "PENUMBRA_TRIMMER": "Penumbra Trimmer",
    "FILTER": "Filter",
    "CUSTOM": "Custom",
}


def _get_purpose_name(purpose: StagePurpose) -> str:
    default = _PURPOSE_DEFAULTS.get(purpose.name, purpose.name)
    return t(f"stage_purpose.{purpose.name}", default)


class LayerPanel(QWidget):
    """Right dock panel — stage selector + stage properties."""

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

        # --- Stage selector ---
        self._lbl_stage_header = QLabel(t("panels.stage_selection", "Stage Selection"))
        self._lbl_stage_header.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 8pt;")
        layout.addWidget(self._lbl_stage_header)

        stage_row = QHBoxLayout()
        stage_row.setSpacing(4)

        self._stage_combo = QComboBox()
        self._stage_combo.setStyleSheet("font-size: 8pt;")
        stage_row.addWidget(self._stage_combo, 1)

        self._btn_add_stage = QPushButton("+")
        self._btn_add_stage.setFixedSize(24, 24)
        self._btn_add_stage.setToolTip(t("panels.add_stage", "Add stage"))
        self._btn_add_stage.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_add_stage)

        self._btn_remove_stage = QPushButton("\u2212")
        self._btn_remove_stage.setFixedSize(24, 24)
        self._btn_remove_stage.setToolTip(t("panels.remove_stage", "Remove stage"))
        self._btn_remove_stage.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_remove_stage)

        self._btn_move_up = QPushButton("\u25B2")
        self._btn_move_up.setFixedSize(24, 24)
        self._btn_move_up.setToolTip(t("panels.move_up", "Move up"))
        self._btn_move_up.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_move_up)

        self._btn_move_down = QPushButton("\u25BC")
        self._btn_move_down.setFixedSize(24, 24)
        self._btn_move_down.setToolTip(t("panels.move_down", "Move down"))
        self._btn_move_down.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_move_down)

        layout.addLayout(stage_row)

        # --- Stage properties ---
        props = QFrame()
        props.setProperty("cssClass", "prop-frame")
        props_layout = QVBoxLayout(props)
        props_layout.setContentsMargins(6, 4, 6, 4)
        props_layout.setSpacing(3)

        # Name
        name_row = QHBoxLayout()
        self._lbl_name = self._make_label(t("panels.name", "Name:"))
        name_row.addWidget(self._lbl_name)
        self._edit_name = QLineEdit()
        self._edit_name.setStyleSheet("font-size: 8pt;")
        name_row.addWidget(self._edit_name)
        props_layout.addLayout(name_row)

        # Purpose
        purpose_row = QHBoxLayout()
        self._lbl_purpose = self._make_label(t("panels.purpose", "Purpose:"))
        purpose_row.addWidget(self._lbl_purpose)
        self._combo_purpose = QComboBox()
        self._combo_purpose.setStyleSheet("font-size: 8pt;")
        for p in StagePurpose:
            self._combo_purpose.addItem(_get_purpose_name(p), p)
        purpose_row.addWidget(self._combo_purpose)
        props_layout.addLayout(purpose_row)

        # Dimensions sub-header
        self._lbl_dim_header = QLabel(t("panels.dimensions_mm", "Dimensions (mm)"))
        self._lbl_dim_header.setStyleSheet(
            "color: #94A3B8; font-size: 7pt; font-weight: bold; margin-top: 2px;"
        )
        props_layout.addWidget(self._lbl_dim_header)

        # Dimensions row (G = width, T = thickness/height)
        dim_row = QHBoxLayout()
        self._lbl_width = self._make_label(t("panels.outer_width", "W (width):"))
        dim_row.addWidget(self._lbl_width)
        self._spin_width = SmartDoubleSpinBox()
        self._spin_width.setRange(0.5, 1000)
        self._spin_width.setSingleStep(0.5)
        self._spin_width.setDecimals(2)
        dim_row.addWidget(self._spin_width)

        self._lbl_height = self._make_label(t("panels.outer_height", "T (thickness):"))
        dim_row.addWidget(self._lbl_height)
        self._spin_height = SmartDoubleSpinBox()
        self._spin_height.setRange(0.5, 1000)
        self._spin_height.setSingleStep(0.5)
        self._spin_height.setDecimals(2)
        dim_row.addWidget(self._spin_height)
        props_layout.addLayout(dim_row)

        # Position row (X = offset, Y = position)
        pos_row = QHBoxLayout()
        self._lbl_x = self._make_label(t("panels.x_offset", "X:"))
        pos_row.addWidget(self._lbl_x)
        self._spin_x_offset = SmartDoubleSpinBox()
        self._spin_x_offset.setRange(-2000, 2000)
        self._spin_x_offset.setSingleStep(1.0)
        self._spin_x_offset.setDecimals(2)
        pos_row.addWidget(self._spin_x_offset)

        self._lbl_y = self._make_label(t("panels.y_pos", "Y:"))
        pos_row.addWidget(self._lbl_y)
        self._spin_y_position = SmartDoubleSpinBox()
        self._spin_y_position.setRange(-2000, 2000)
        self._spin_y_position.setSingleStep(1.0)
        self._spin_y_position.setDecimals(2)
        pos_row.addWidget(self._spin_y_position)
        props_layout.addLayout(pos_row)

        # Material
        mat_row = QHBoxLayout()
        self._lbl_material = self._make_label(t("panels.material", "Material:"))
        mat_row.addWidget(self._lbl_material)
        self._combo_material = QComboBox()
        self._combo_material.setStyleSheet("font-size: 8pt;")
        for mid in MATERIAL_IDS:
            self._combo_material.addItem(mid, mid)
        mat_row.addWidget(self._combo_material)

        # Material color swatch
        self._mat_swatch = QLabel()
        self._mat_swatch.setFixedSize(14, 14)
        self._mat_swatch.setStyleSheet("background: #64748B; border-radius: 2px;")
        mat_row.addWidget(self._mat_swatch)
        props_layout.addLayout(mat_row)

        layout.addWidget(props)

        # --- Aperture ---
        self._lbl_aperture_header = QLabel(t("panels.aperture_mm", "Aperture (mm)"))
        self._lbl_aperture_header.setStyleSheet(
            "color: #F8FAFC; font-weight: bold; font-size: 8pt;"
        )
        layout.addWidget(self._lbl_aperture_header)

        ap_frame = QFrame()
        ap_frame.setProperty("cssClass", "prop-frame")
        ap_layout = QVBoxLayout(ap_frame)
        ap_layout.setContentsMargins(6, 4, 6, 4)
        ap_layout.setSpacing(3)

        # Fan angle
        self._fan_row = QHBoxLayout()
        self._fan_row_label = self._make_label(t("aperture.angle", "Angle:"))
        self._fan_row.addWidget(self._fan_row_label)
        self._spin_fan_angle = SmartDoubleSpinBox()
        self._spin_fan_angle.setRange(1, 90)
        self._spin_fan_angle.setSuffix("\u00B0")
        self._spin_fan_angle.setDecimals(2)
        self._spin_fan_angle.setSingleStep(0.5)
        self._fan_row.addWidget(self._spin_fan_angle)
        ap_layout.addLayout(self._fan_row)

        # Fan slit width
        self._fan_sw_row = QHBoxLayout()
        self._fan_sw_label = self._make_label(t("aperture.slit_width", "Slit:"))
        self._fan_sw_row.addWidget(self._fan_sw_label)
        self._spin_fan_slit = SmartDoubleSpinBox()
        self._spin_fan_slit.setRange(0.1, 100)
        self._spin_fan_slit.setDecimals(2)
        self._spin_fan_slit.setSingleStep(0.5)
        self._fan_sw_row.addWidget(self._spin_fan_slit)
        ap_layout.addLayout(self._fan_sw_row)

        # Pencil diameter
        self._pencil_row = QHBoxLayout()
        self._pencil_label = self._make_label(t("aperture.diameter", "Diameter:"))
        self._pencil_row.addWidget(self._pencil_label)
        self._spin_pencil_d = SmartDoubleSpinBox()
        self._spin_pencil_d.setRange(0.1, 100)
        self._spin_pencil_d.setDecimals(2)
        self._spin_pencil_d.setSingleStep(0.5)
        self._pencil_row.addWidget(self._spin_pencil_d)
        ap_layout.addLayout(self._pencil_row)

        # Slit input width (source side)
        self._slit_in_row = QHBoxLayout()
        self._slit_in_label = self._make_label(t("aperture.entry", "Entry:"))
        self._slit_in_row.addWidget(self._slit_in_label)
        self._spin_slit_in = SmartDoubleSpinBox()
        self._spin_slit_in.setRange(0.1, 200)
        self._spin_slit_in.setDecimals(2)
        self._spin_slit_in.setSingleStep(0.5)
        self._slit_in_row.addWidget(self._spin_slit_in)
        ap_layout.addLayout(self._slit_in_row)

        # Slit output width (detector side)
        self._slit_out_row = QHBoxLayout()
        self._slit_out_label = self._make_label(t("aperture.exit", "Exit:"))
        self._slit_out_row.addWidget(self._slit_out_label)
        self._spin_slit_out = SmartDoubleSpinBox()
        self._spin_slit_out.setRange(0.1, 200)
        self._spin_slit_out.setDecimals(2)
        self._spin_slit_out.setSingleStep(0.5)
        self._slit_out_row.addWidget(self._spin_slit_out)
        ap_layout.addLayout(self._slit_out_row)

        layout.addWidget(ap_frame)
        layout.addStretch()

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("cssClass", "prop-label")
        lbl.setFixedWidth(40)
        return lbl

    def _connect_signals(self) -> None:
        ctrl = self._controller

        # Controller -> panel
        ctrl.geometry_changed.connect(self._refresh_all)
        ctrl.stage_changed.connect(self._on_stage_changed)
        ctrl.stage_added.connect(lambda _: self._refresh_all())
        ctrl.stage_removed.connect(lambda _: self._refresh_all())
        ctrl.stage_selected.connect(self._on_stage_selected)
        ctrl.stage_position_changed.connect(self._on_stage_position_changed)

        # Panel widgets -> controller
        self._stage_combo.currentIndexChanged.connect(self._on_stage_combo_changed)
        self._btn_add_stage.clicked.connect(self._on_add_stage)
        self._btn_remove_stage.clicked.connect(self._on_remove_stage)
        self._btn_move_up.clicked.connect(self._on_move_up)
        self._btn_move_down.clicked.connect(self._on_move_down)
        self._edit_name.editingFinished.connect(self._on_name_changed)
        self._combo_purpose.currentIndexChanged.connect(self._on_purpose_changed)
        self._spin_width.valueChanged.connect(self._on_width_changed)
        self._spin_height.valueChanged.connect(self._on_height_changed)
        self._spin_x_offset.valueChanged.connect(self._on_x_offset_changed)
        self._spin_y_position.valueChanged.connect(self._on_y_position_changed)
        self._combo_material.currentIndexChanged.connect(self._on_material_changed)

        # Aperture
        self._spin_fan_angle.valueChanged.connect(self._on_aperture_changed)
        self._spin_fan_slit.valueChanged.connect(self._on_aperture_changed)
        self._spin_pencil_d.valueChanged.connect(self._on_aperture_changed)
        self._spin_slit_in.valueChanged.connect(self._on_aperture_changed)
        self._spin_slit_out.valueChanged.connect(self._on_aperture_changed)

        ctrl.stage_changed.connect(lambda _: self._refresh_aperture())
        ctrl.collimator_type_changed.connect(lambda _: self._refresh_aperture())

    # ------------------------------------------------------------------
    # Retranslation
    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Update all translatable strings after language change."""
        self._lbl_stage_header.setText(t("panels.stage_selection", "Stage Selection"))
        self._btn_add_stage.setToolTip(t("panels.add_stage", "Add stage"))
        self._btn_remove_stage.setToolTip(t("panels.remove_stage", "Remove stage"))
        self._btn_move_up.setToolTip(t("panels.move_up", "Move up"))
        self._btn_move_down.setToolTip(t("panels.move_down", "Move down"))
        self._lbl_name.setText(t("panels.name", "Name:"))
        self._lbl_width.setText(t("panels.outer_width", "W (width):"))
        self._lbl_height.setText(t("panels.outer_height", "T (thickness):"))
        self._lbl_x.setText(t("panels.x_offset", "X:"))
        self._lbl_y.setText(t("panels.y_pos", "Y:"))
        self._lbl_material.setText(t("panels.material", "Material:"))

        # Purpose combo — repopulate with translated names
        self._lbl_purpose.setText(t("panels.purpose", "Purpose:"))
        current_purpose = self._combo_purpose.currentData()
        with QSignalBlocker(self._combo_purpose):
            self._combo_purpose.clear()
            for p in StagePurpose:
                self._combo_purpose.addItem(_get_purpose_name(p), p)
            if current_purpose is not None:
                for i in range(self._combo_purpose.count()):
                    if self._combo_purpose.itemData(i) == current_purpose:
                        self._combo_purpose.setCurrentIndex(i)
                        break

        self._lbl_dim_header.setText(t("panels.dimensions_mm", "Dimensions (mm)"))
        self._lbl_aperture_header.setText(t("panels.aperture_mm", "Aperture (mm)"))

        # Aperture labels
        self._fan_row_label.setText(t("aperture.angle", "Angle:"))
        self._fan_sw_label.setText(t("aperture.slit_width", "Slit:"))
        self._pencil_label.setText(t("aperture.diameter", "Diameter:"))
        self._slit_in_label.setText(t("aperture.entry", "Entry:"))
        self._slit_out_label.setText(t("aperture.exit", "Exit:"))

        # Refresh stage combo text (names may include translated parts)
        self._refresh_all()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        """Full refresh of stage combo and properties."""
        geo = self._controller.geometry
        with QSignalBlocker(self._stage_combo):
            self._stage_combo.clear()
            for i, stage in enumerate(geo.stages):
                label = f"{i}: {stage.name}" if stage.name else f"Stage {i}"
                self._stage_combo.addItem(label, i)
            self._stage_combo.setCurrentIndex(self._controller.active_stage_index)

        self._refresh_stage_props()
        self._update_stage_buttons()
        self._refresh_aperture()

    def _update_stage_buttons(self) -> None:
        """Enable/disable stage buttons based on current state."""
        geo = self._controller.geometry
        idx = self._controller.active_stage_index
        count = geo.stage_count

        self._btn_add_stage.setEnabled(count < MAX_STAGES)
        self._btn_remove_stage.setEnabled(count > MIN_STAGES)
        self._btn_move_up.setEnabled(idx > 0)
        self._btn_move_down.setEnabled(idx < count - 1)

    def _refresh_stage_props(self) -> None:
        """Refresh stage property widgets from active stage."""
        stage = self._controller.active_stage
        if not stage:
            return

        with QSignalBlocker(self._edit_name):
            self._edit_name.setText(stage.name)
        with QSignalBlocker(self._combo_purpose):
            for i in range(self._combo_purpose.count()):
                if self._combo_purpose.itemData(i) == stage.purpose:
                    self._combo_purpose.setCurrentIndex(i)
                    break
        with QSignalBlocker(self._spin_width):
            self._spin_width.setValue(stage.outer_width)
        with QSignalBlocker(self._spin_height):
            self._spin_height.setValue(stage.outer_height)
        with QSignalBlocker(self._spin_x_offset):
            self._spin_x_offset.setValue(stage.x_offset)
        with QSignalBlocker(self._spin_y_position):
            self._spin_y_position.setValue(stage.y_position)
        with QSignalBlocker(self._combo_material):
            idx = MATERIAL_IDS.index(stage.material_id) if stage.material_id in MATERIAL_IDS else 0
            self._combo_material.setCurrentIndex(idx)
        self._update_material_swatch(stage.material_id)

    def _update_material_swatch(self, material_id: str) -> None:
        """Update material color swatch."""
        color_hex = MATERIAL_COLORS.get(material_id, "#64748B")
        self._mat_swatch.setStyleSheet(
            f"background: {color_hex}; border-radius: 2px;"
        )

    # ------------------------------------------------------------------
    # Slots from controller
    # ------------------------------------------------------------------

    def _on_stage_changed(self, index: int) -> None:
        if index == self._controller.active_stage_index:
            self._refresh_stage_props()

    def _on_stage_selected(self, index: int) -> None:
        with QSignalBlocker(self._stage_combo):
            self._stage_combo.setCurrentIndex(index)
        self._refresh_stage_props()
        self._update_stage_buttons()
        self._refresh_aperture()

    # ------------------------------------------------------------------
    # Slots from widgets
    # ------------------------------------------------------------------

    def _on_stage_combo_changed(self, index: int) -> None:
        if index >= 0:
            self._controller.select_stage(index)

    def _on_add_stage(self) -> None:
        self._controller.add_stage(after_index=self._controller.active_stage_index)

    def _on_remove_stage(self) -> None:
        self._controller.remove_stage(self._controller.active_stage_index)

    def _on_move_up(self) -> None:
        idx = self._controller.active_stage_index
        if idx > 0:
            self._controller.move_stage(idx, idx - 1)

    def _on_move_down(self) -> None:
        idx = self._controller.active_stage_index
        if idx < self._controller.geometry.stage_count - 1:
            self._controller.move_stage(idx, idx + 1)

    def _on_name_changed(self) -> None:
        self._controller.set_stage_name(
            self._controller.active_stage_index, self._edit_name.text(),
        )

    def _on_purpose_changed(self, idx: int) -> None:
        purpose = self._combo_purpose.currentData()
        if purpose:
            self._controller.set_stage_purpose(
                self._controller.active_stage_index, purpose,
            )

    def _on_width_changed(self, value: float) -> None:
        self._controller.set_stage_dimensions(
            self._controller.active_stage_index, width=value,
        )

    def _on_height_changed(self, value: float) -> None:
        self._controller.set_stage_dimensions(
            self._controller.active_stage_index, height=value,
        )

    def _on_x_offset_changed(self, value: float) -> None:
        self._controller.set_stage_x_offset(
            self._controller.active_stage_index, value,
        )

    def _on_y_position_changed(self, value: float) -> None:
        self._controller.set_stage_y_position(
            self._controller.active_stage_index, value,
        )

    def _on_material_changed(self, idx: int) -> None:
        mat_id = self._combo_material.currentData()
        if mat_id:
            self._update_material_swatch(mat_id)
            self._controller.set_stage_material(
                self._controller.active_stage_index, mat_id,
            )

    def _on_stage_position_changed(self, index: int) -> None:
        """Update X/Y spinners when stage is dragged on canvas."""
        if index == self._controller.active_stage_index:
            stage = self._controller.active_stage
            if stage:
                with QSignalBlocker(self._spin_x_offset):
                    self._spin_x_offset.setValue(stage.x_offset)
                with QSignalBlocker(self._spin_y_position):
                    self._spin_y_position.setValue(stage.y_position)

    # ------------------------------------------------------------------
    # Aperture
    # ------------------------------------------------------------------

    @staticmethod
    def _set_row_visible(
        label: QLabel, spin: SmartDoubleSpinBox, visible: bool,
    ) -> None:
        label.setVisible(visible)
        spin.setVisible(visible)

    def _refresh_aperture(self) -> None:
        """Show/hide aperture fields based on collimator type."""
        ctype = self._controller.geometry.type
        stage = self._controller.active_stage

        # Hide all
        self._set_row_visible(self._fan_row_label, self._spin_fan_angle, False)
        self._set_row_visible(self._fan_sw_label, self._spin_fan_slit, False)
        self._set_row_visible(self._pencil_label, self._spin_pencil_d, False)
        self._set_row_visible(self._slit_in_label, self._spin_slit_in, False)
        self._set_row_visible(self._slit_out_label, self._spin_slit_out, False)

        if not stage:
            return

        ap = stage.aperture

        match ctype:
            case CollimatorType.FAN_BEAM:
                self._set_row_visible(
                    self._fan_row_label, self._spin_fan_angle, True,
                )
                self._set_row_visible(
                    self._fan_sw_label, self._spin_fan_slit, True,
                )
                with QSignalBlocker(self._spin_fan_angle):
                    self._spin_fan_angle.setValue(ap.fan_angle or 30)
                with QSignalBlocker(self._spin_fan_slit):
                    self._spin_fan_slit.setValue(ap.fan_slit_width or 2)

            case CollimatorType.PENCIL_BEAM:
                self._set_row_visible(
                    self._pencil_label, self._spin_pencil_d, True,
                )
                with QSignalBlocker(self._spin_pencil_d):
                    self._spin_pencil_d.setValue(ap.pencil_diameter or 5)

            case CollimatorType.SLIT:
                self._set_row_visible(
                    self._slit_in_label, self._spin_slit_in, True,
                )
                self._set_row_visible(
                    self._slit_out_label, self._spin_slit_out, True,
                )
                output_w = ap.slit_width or 2.0
                if ap.taper_angle and ap.taper_angle > 0 and stage:
                    input_w = output_w + 2.0 * stage.outer_height * math.tan(
                        math.radians(ap.taper_angle)
                    )
                else:
                    input_w = output_w
                with QSignalBlocker(self._spin_slit_in):
                    self._spin_slit_in.setValue(input_w)
                with QSignalBlocker(self._spin_slit_out):
                    self._spin_slit_out.setValue(output_w)

    def _on_aperture_changed(self) -> None:
        """Aperture spinbox changed — build new ApertureConfig."""
        ctype = self._controller.geometry.type
        stage_idx = self._controller.active_stage_index

        match ctype:
            case CollimatorType.FAN_BEAM:
                ap = ApertureConfig(
                    fan_angle=self._spin_fan_angle.value(),
                    fan_slit_width=self._spin_fan_slit.value(),
                )
            case CollimatorType.PENCIL_BEAM:
                ap = ApertureConfig(
                    pencil_diameter=self._spin_pencil_d.value(),
                )
            case CollimatorType.SLIT:
                input_w = self._spin_slit_in.value()
                output_w = self._spin_slit_out.value()
                if input_w < output_w:
                    input_w = output_w
                stage = self._controller.active_stage
                stage_h = stage.outer_height if stage else 50.0
                if input_w > output_w and stage_h > 0:
                    taper = math.degrees(math.atan(
                        (input_w - output_w) / (2.0 * stage_h)
                    ))
                else:
                    taper = 0.0
                ap = ApertureConfig(
                    slit_width=output_w,
                    taper_angle=taper,
                )
            case _:
                return

        self._controller.set_stage_aperture(stage_idx, ap)
