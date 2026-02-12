"""Layer panel — right dock panel for stage/layer management.

Top: Stage selector (combo + add/remove/move buttons)
Middle: Stage properties (name, purpose, dimensions, gap)
Bottom: Layer list (material, thickness, purpose, delete)

Reference: Phase-03 spec — FR-1.4, Stage/Layer Management.
"""

import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QDoubleSpinBox, QLineEdit, QScrollArea,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSignalBlocker, QMimeData
from PyQt6.QtGui import QColor, QDrag

from app.constants import MATERIAL_IDS, MAX_STAGES, MIN_STAGES, LAYER_MIME_TYPE, MATERIAL_MIME_TYPE
from app.models.geometry import (
    StagePurpose, LayerPurpose, ApertureConfig, CollimatorType,
)
from app.ui.canvas.geometry_controller import GeometryController
from app.ui.styles.colors import MATERIAL_COLORS



# Stage purpose display names
_STAGE_PURPOSE_NAMES = {
    StagePurpose.PRIMARY_SHIELDING: "Birincil Koruma",
    StagePurpose.SECONDARY_SHIELDING: "İkincil Koruma",
    StagePurpose.FAN_DEFINITION: "Yelpaze Tanımlama",
    StagePurpose.PENUMBRA_TRIMMER: "Penumbra Budama",
    StagePurpose.FILTER: "Filtre",
    StagePurpose.CUSTOM: "Özel",
}

_LAYER_PURPOSE_NAMES = {
    LayerPurpose.PRIMARY_SHIELDING: "Birincil Koruma",
    LayerPurpose.SECONDARY_SHIELDING: "İkincil Koruma",
    LayerPurpose.STRUCTURAL: "Yapısal",
    LayerPurpose.FILTER: "Filtre",
}


class LayerRowWidget(QFrame):
    """Single layer row in the layer list.

    Shows material, thickness, and an optional composite (K) toggle.
    When composite is active, a second row appears with inner material
    and inner width controls.
    """

    material_changed = pyqtSignal(int, str)
    thickness_changed = pyqtSignal(int, float)
    purpose_changed = pyqtSignal(int, object)
    delete_clicked = pyqtSignal(int)
    row_clicked = pyqtSignal(int)
    layer_dropped = pyqtSignal(int, int)  # from_idx, to_idx
    composite_toggled = pyqtSignal(int, bool)
    inner_material_changed = pyqtSignal(int, str)
    inner_width_changed = pyqtSignal(int, float)

    def __init__(
        self, layer_index: int, material_id: str,
        thickness: float, purpose: LayerPurpose,
        inner_material_id: str | None = None,
        inner_width: float = 0.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._layer_index = layer_index
        self._drag_start = None
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            LayerRowWidget {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 3px;
            }
            LayerRowWidget:hover {
                border: 1px solid #3B82F6;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 3, 4, 3)
        main_layout.setSpacing(2)

        # --- Top row: order, swatch, material, thickness, K, delete ---
        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        # Order label
        self._order_label = QLabel(f"{layer_index}")
        self._order_label.setFixedWidth(16)
        self._order_label.setStyleSheet("color: #64748B; font-size: 8pt;")
        top_row.addWidget(self._order_label)

        # Color swatch
        color_hex = MATERIAL_COLORS.get(material_id, "#64748B")
        self._swatch = QLabel()
        self._swatch.setFixedSize(12, 12)
        self._swatch.setStyleSheet(
            f"background: {color_hex}; border-radius: 2px;"
        )
        top_row.addWidget(self._swatch)

        # Material combo
        self._mat_combo = QComboBox()
        self._mat_combo.setFixedWidth(65)
        self._mat_combo.setStyleSheet("font-size: 8pt;")
        for mid in MATERIAL_IDS:
            self._mat_combo.addItem(mid, mid)
        idx = MATERIAL_IDS.index(material_id) if material_id in MATERIAL_IDS else 0
        self._mat_combo.setCurrentIndex(idx)
        self._mat_combo.currentIndexChanged.connect(self._on_mat_changed)
        top_row.addWidget(self._mat_combo)

        # Thickness spin
        self._thick_spin = QDoubleSpinBox()
        self._thick_spin.setRange(0.1, 500.0)
        self._thick_spin.setDecimals(1)
        self._thick_spin.setSuffix(" mm")
        self._thick_spin.setValue(thickness)
        self._thick_spin.setFixedWidth(80)
        self._thick_spin.setStyleSheet("font-size: 8pt;")
        self._thick_spin.valueChanged.connect(self._on_thick_changed)
        top_row.addWidget(self._thick_spin)

        # Composite toggle button
        self._btn_composite = QPushButton("K")
        self._btn_composite.setCheckable(True)
        self._btn_composite.setFixedSize(20, 20)
        self._btn_composite.setToolTip("Kompozit katman (İç/Dış zon)")
        self._btn_composite.setProperty("cssClass", "composite-toggle")
        is_composite = inner_material_id is not None and inner_width > 0
        self._btn_composite.setChecked(is_composite)
        self._btn_composite.toggled.connect(self._on_composite_toggled)
        top_row.addWidget(self._btn_composite)

        # Delete button
        del_btn = QPushButton("\u2715")
        del_btn.setFixedSize(20, 20)
        del_btn.setProperty("cssClass", "inline-delete")
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._layer_index))
        top_row.addWidget(del_btn)

        main_layout.addLayout(top_row)

        # --- Bottom row: composite controls (hidden by default) ---
        self._composite_row = QWidget()
        comp_layout = QHBoxLayout(self._composite_row)
        comp_layout.setContentsMargins(20, 0, 0, 0)
        comp_layout.setSpacing(4)

        lbl_ic = QLabel("İç:")
        lbl_ic.setStyleSheet("color: #F59E0B; font-size: 7pt;")
        lbl_ic.setFixedWidth(16)
        comp_layout.addWidget(lbl_ic)

        # Inner material combo
        self._inner_mat_combo = QComboBox()
        self._inner_mat_combo.setFixedWidth(60)
        self._inner_mat_combo.setStyleSheet("font-size: 8pt;")
        for mid in MATERIAL_IDS:
            self._inner_mat_combo.addItem(mid, mid)
        if inner_material_id and inner_material_id in MATERIAL_IDS:
            self._inner_mat_combo.setCurrentIndex(
                MATERIAL_IDS.index(inner_material_id),
            )
        self._inner_mat_combo.currentIndexChanged.connect(
            self._on_inner_mat_changed,
        )
        comp_layout.addWidget(self._inner_mat_combo)

        lbl_w = QLabel("Gen:")
        lbl_w.setStyleSheet("color: #F59E0B; font-size: 7pt;")
        lbl_w.setFixedWidth(22)
        comp_layout.addWidget(lbl_w)

        # Inner width spin
        self._inner_width_spin = QDoubleSpinBox()
        self._inner_width_spin.setRange(0.1, 200.0)
        self._inner_width_spin.setDecimals(1)
        self._inner_width_spin.setSuffix(" mm")
        self._inner_width_spin.setValue(inner_width if inner_width > 0 else 1.0)
        self._inner_width_spin.setFixedWidth(70)
        self._inner_width_spin.setStyleSheet("font-size: 8pt;")
        self._inner_width_spin.valueChanged.connect(self._on_inner_width_changed)
        comp_layout.addWidget(self._inner_width_spin)

        comp_layout.addStretch()

        self._composite_row.setVisible(is_composite)
        main_layout.addWidget(self._composite_row)

    def _on_mat_changed(self, idx: int) -> None:
        mat_id = self._mat_combo.currentData()
        if mat_id:
            color_hex = MATERIAL_COLORS.get(mat_id, "#64748B")
            self._swatch.setStyleSheet(
                f"background: {color_hex}; border-radius: 2px;"
            )
            self.material_changed.emit(self._layer_index, mat_id)

    def _on_thick_changed(self, value: float) -> None:
        self.thickness_changed.emit(self._layer_index, value)

    def _on_composite_toggled(self, checked: bool) -> None:
        self._composite_row.setVisible(checked)
        self.composite_toggled.emit(self._layer_index, checked)

    def _on_inner_mat_changed(self, idx: int) -> None:
        mat_id = self._inner_mat_combo.currentData()
        if mat_id:
            self.inner_material_changed.emit(self._layer_index, mat_id)

    def _on_inner_width_changed(self, value: float) -> None:
        self.inner_width_changed.emit(self._layer_index, value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        self.row_clicked.emit(self._layer_index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < 10:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(LAYER_MIME_TYPE, str(self._layer_index).encode())
        drag.setMimeData(mime)
        pixmap = self.grab()
        pixmap.setDevicePixelRatio(1.0)
        drag.setPixmap(pixmap.scaledToWidth(min(pixmap.width(), 200)))
        drag.setHotSpot(event.pos())
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasFormat(LAYER_MIME_TYPE) or md.hasFormat(MATERIAL_MIME_TYPE):
            event.acceptProposedAction()
            self._set_drop_highlight(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_highlight(False)
        super().dragLeaveEvent(event)

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        self._set_drop_highlight(False)
        md = event.mimeData()
        if md.hasFormat(LAYER_MIME_TYPE):
            from_idx = int(md.data(LAYER_MIME_TYPE).data().decode())
            if from_idx != self._layer_index:
                self.layer_dropped.emit(from_idx, self._layer_index)
            event.acceptProposedAction()
        elif md.hasFormat(MATERIAL_MIME_TYPE):
            mat_id = md.data(MATERIAL_MIME_TYPE).data().decode()
            self.material_changed.emit(self._layer_index, mat_id)
            event.acceptProposedAction()

    def _set_drop_highlight(self, active: bool) -> None:
        if active:
            self.setStyleSheet("""
                LayerRowWidget {
                    background: #1E293B;
                    border: 2px solid #3B82F6;
                    border-radius: 3px;
                }
            """)
        else:
            self.setStyleSheet("""
                LayerRowWidget {
                    background: #1E293B;
                    border: 1px solid #334155;
                    border-radius: 3px;
                }
                LayerRowWidget:hover {
                    border: 1px solid #3B82F6;
                }
            """)

    def set_highlighted(self, highlighted: bool) -> None:
        border = "#3B82F6" if highlighted else "#334155"
        bg = "#1E3A5F" if highlighted else "#1E293B"
        self.setStyleSheet(f"""
            LayerRowWidget {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 3px;
            }}
        """)


class LayerPanel(QWidget):
    """Right dock panel — stage selector + layer management."""

    def __init__(
        self,
        controller: GeometryController,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._layer_rows: list[LayerRowWidget] = []
        self._build_ui()
        self._connect_signals()
        self._refresh_all()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # --- Stage selector ---
        stage_header = QLabel("Stage Seçimi")
        stage_header.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 8pt;")
        layout.addWidget(stage_header)

        stage_row = QHBoxLayout()
        stage_row.setSpacing(4)

        self._stage_combo = QComboBox()
        self._stage_combo.setStyleSheet("font-size: 8pt;")
        stage_row.addWidget(self._stage_combo, 1)

        self._btn_add_stage = QPushButton("+")
        self._btn_add_stage.setFixedSize(24, 24)
        self._btn_add_stage.setToolTip("Stage ekle")
        self._btn_add_stage.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_add_stage)

        self._btn_remove_stage = QPushButton("\u2212")
        self._btn_remove_stage.setFixedSize(24, 24)
        self._btn_remove_stage.setToolTip("Stage sil")
        self._btn_remove_stage.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_remove_stage)

        self._btn_move_up = QPushButton("\u25B2")
        self._btn_move_up.setFixedSize(24, 24)
        self._btn_move_up.setToolTip("Yukarı taşı")
        self._btn_move_up.setProperty("cssClass", "small-icon")
        stage_row.addWidget(self._btn_move_up)

        self._btn_move_down = QPushButton("\u25BC")
        self._btn_move_down.setFixedSize(24, 24)
        self._btn_move_down.setToolTip("Aşağı taşı")
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
        name_row.addWidget(self._make_label("Ad:"))
        self._edit_name = QLineEdit()
        self._edit_name.setStyleSheet("font-size: 8pt;")
        name_row.addWidget(self._edit_name)
        props_layout.addLayout(name_row)

        # Purpose
        purpose_row = QHBoxLayout()
        purpose_row.addWidget(self._make_label("Amaç:"))
        self._combo_purpose = QComboBox()
        self._combo_purpose.setStyleSheet("font-size: 8pt;")
        for p, name in _STAGE_PURPOSE_NAMES.items():
            self._combo_purpose.addItem(name, p)
        purpose_row.addWidget(self._combo_purpose)
        props_layout.addLayout(purpose_row)

        # Dimensions row
        dim_row = QHBoxLayout()
        dim_row.addWidget(self._make_label("G:"))
        self._spin_width = QDoubleSpinBox()
        self._spin_width.setRange(10, 1000)
        self._spin_width.setSuffix(" mm")
        self._spin_width.setDecimals(1)
        self._spin_width.setStyleSheet("font-size: 8pt;")
        dim_row.addWidget(self._spin_width)

        dim_row.addWidget(self._make_label("Y:"))
        self._spin_height = QDoubleSpinBox()
        self._spin_height.setRange(10, 1000)
        self._spin_height.setSuffix(" mm")
        self._spin_height.setDecimals(1)
        self._spin_height.setStyleSheet("font-size: 8pt;")
        dim_row.addWidget(self._spin_height)
        props_layout.addLayout(dim_row)

        # Gap
        gap_row = QHBoxLayout()
        gap_row.addWidget(self._make_label("Boşluk:"))
        self._spin_gap = QDoubleSpinBox()
        self._spin_gap.setRange(0, 500)
        self._spin_gap.setSuffix(" mm")
        self._spin_gap.setDecimals(1)
        self._spin_gap.setStyleSheet("font-size: 8pt;")
        gap_row.addWidget(self._spin_gap)
        gap_row.addStretch()
        props_layout.addLayout(gap_row)

        layout.addWidget(props)

        # --- Layer list ---
        layer_header_row = QHBoxLayout()
        layer_lbl = QLabel("Katmanlar")
        layer_lbl.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 8pt;")
        layer_header_row.addWidget(layer_lbl)
        layer_header_row.addStretch()
        self._btn_add_layer = QPushButton("+ Katman")
        self._btn_add_layer.setProperty("cssClass", "small")
        layer_header_row.addWidget(self._btn_add_layer)
        layout.addLayout(layer_header_row)

        # Scroll area for layer rows
        self._layer_scroll = QScrollArea()
        self._layer_scroll.setWidgetResizable(True)
        self._layer_scroll.setMinimumHeight(120)
        self._layer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._layer_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._layer_container = QWidget()
        self._layer_layout = QVBoxLayout(self._layer_container)
        self._layer_layout.setContentsMargins(0, 0, 0, 0)
        self._layer_layout.setSpacing(3)
        self._layer_layout.addStretch()
        self._layer_scroll.setWidget(self._layer_container)
        layout.addWidget(self._layer_scroll, 1)

        # --- Aperture ---
        ap_header = QLabel("Aperture")
        ap_header.setStyleSheet(
            "color: #F8FAFC; font-weight: bold; font-size: 8pt;"
        )
        layout.addWidget(ap_header)

        ap_frame = QFrame()
        ap_frame.setProperty("cssClass", "prop-frame")
        ap_layout = QVBoxLayout(ap_frame)
        ap_layout.setContentsMargins(6, 4, 6, 4)
        ap_layout.setSpacing(3)

        # Fan angle
        self._fan_row = QHBoxLayout()
        self._fan_row_label = self._make_label("Açı:")
        self._fan_row.addWidget(self._fan_row_label)
        self._spin_fan_angle = QDoubleSpinBox()
        self._spin_fan_angle.setRange(1, 90)
        self._spin_fan_angle.setSuffix(" \u00B0")
        self._spin_fan_angle.setDecimals(1)
        self._spin_fan_angle.setStyleSheet("font-size: 8pt;")
        self._fan_row.addWidget(self._spin_fan_angle)
        ap_layout.addLayout(self._fan_row)

        # Fan slit width
        self._fan_sw_row = QHBoxLayout()
        self._fan_sw_label = self._make_label("Yarık:")
        self._fan_sw_row.addWidget(self._fan_sw_label)
        self._spin_fan_slit = QDoubleSpinBox()
        self._spin_fan_slit.setRange(0.1, 100)
        self._spin_fan_slit.setSuffix(" mm")
        self._spin_fan_slit.setDecimals(1)
        self._spin_fan_slit.setStyleSheet("font-size: 8pt;")
        self._fan_sw_row.addWidget(self._spin_fan_slit)
        ap_layout.addLayout(self._fan_sw_row)

        # Pencil diameter
        self._pencil_row = QHBoxLayout()
        self._pencil_label = self._make_label("Çap:")
        self._pencil_row.addWidget(self._pencil_label)
        self._spin_pencil_d = QDoubleSpinBox()
        self._spin_pencil_d.setRange(0.1, 100)
        self._spin_pencil_d.setSuffix(" mm")
        self._spin_pencil_d.setDecimals(1)
        self._spin_pencil_d.setStyleSheet("font-size: 8pt;")
        self._pencil_row.addWidget(self._spin_pencil_d)
        ap_layout.addLayout(self._pencil_row)

        # Slit input width (source side)
        self._slit_in_row = QHBoxLayout()
        self._slit_in_label = self._make_label("Giriş:")
        self._slit_in_row.addWidget(self._slit_in_label)
        self._spin_slit_in = QDoubleSpinBox()
        self._spin_slit_in.setRange(0.1, 200)
        self._spin_slit_in.setSuffix(" mm")
        self._spin_slit_in.setDecimals(2)
        self._spin_slit_in.setStyleSheet("font-size: 8pt;")
        self._slit_in_row.addWidget(self._spin_slit_in)
        ap_layout.addLayout(self._slit_in_row)

        # Slit output width (detector side)
        self._slit_out_row = QHBoxLayout()
        self._slit_out_label = self._make_label("Çıkış:")
        self._slit_out_row.addWidget(self._slit_out_label)
        self._spin_slit_out = QDoubleSpinBox()
        self._spin_slit_out.setRange(0.1, 200)
        self._spin_slit_out.setSuffix(" mm")
        self._spin_slit_out.setDecimals(2)
        self._spin_slit_out.setStyleSheet("font-size: 8pt;")
        self._slit_out_row.addWidget(self._spin_slit_out)
        ap_layout.addLayout(self._slit_out_row)

        layout.addWidget(ap_frame)

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
        ctrl.layer_changed.connect(self._on_layer_changed)
        ctrl.layer_added.connect(lambda s, l: self._rebuild_layer_rows())
        ctrl.layer_removed.connect(lambda s, l: self._rebuild_layer_rows())
        ctrl.layer_selected.connect(self._on_layer_selected)

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
        self._spin_gap.valueChanged.connect(self._on_gap_changed)
        self._btn_add_layer.clicked.connect(self._on_add_layer)

        # Aperture
        self._spin_fan_angle.valueChanged.connect(self._on_aperture_changed)
        self._spin_fan_slit.valueChanged.connect(self._on_aperture_changed)
        self._spin_pencil_d.valueChanged.connect(self._on_aperture_changed)
        self._spin_slit_in.valueChanged.connect(self._on_aperture_changed)
        self._spin_slit_out.valueChanged.connect(self._on_aperture_changed)

        ctrl.stage_changed.connect(lambda _: self._refresh_aperture())
        ctrl.collimator_type_changed.connect(lambda _: self._refresh_aperture())

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        """Full refresh of stage combo and layer list."""
        geo = self._controller.geometry
        with QSignalBlocker(self._stage_combo):
            self._stage_combo.clear()
            for i, stage in enumerate(geo.stages):
                label = f"{i}: {stage.name}" if stage.name else f"Stage {i}"
                self._stage_combo.addItem(label, i)
            self._stage_combo.setCurrentIndex(self._controller.active_stage_index)

        self._refresh_stage_props()
        self._rebuild_layer_rows()
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
        with QSignalBlocker(self._spin_gap):
            self._spin_gap.setValue(stage.gap_after)

    def _rebuild_layer_rows(self) -> None:
        """Recreate layer row widgets from active stage."""
        # Clear existing rows
        for row in self._layer_rows:
            row.setParent(None)
        self._layer_rows.clear()

        stage = self._controller.active_stage
        if not stage:
            return

        # Insert before the stretch
        for i, layer in enumerate(stage.layers):
            row = LayerRowWidget(
                i, layer.material_id, layer.thickness, layer.purpose,
                inner_material_id=layer.inner_material_id,
                inner_width=layer.inner_width,
            )
            row.material_changed.connect(self._on_layer_mat_changed)
            row.thickness_changed.connect(self._on_layer_thick_changed)
            row.delete_clicked.connect(self._on_layer_delete)
            row.row_clicked.connect(self._on_layer_row_clicked)
            row.layer_dropped.connect(self._on_layer_dropped)
            row.composite_toggled.connect(self._on_layer_composite_toggled)
            row.inner_material_changed.connect(self._on_layer_inner_mat_changed)
            row.inner_width_changed.connect(self._on_layer_inner_width_changed)
            self._layer_layout.insertWidget(
                self._layer_layout.count() - 1, row,
            )
            self._layer_rows.append(row)

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
        self._rebuild_layer_rows()
        self._update_stage_buttons()
        self._refresh_aperture()

    def _on_layer_changed(self, stage_idx: int, layer_idx: int) -> None:
        if stage_idx == self._controller.active_stage_index:
            self._rebuild_layer_rows()

    def _on_layer_selected(self, stage_idx: int, layer_idx: int) -> None:
        for row in self._layer_rows:
            row.set_highlighted(row._layer_index == layer_idx)

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

    def _on_gap_changed(self, value: float) -> None:
        self._controller.set_stage_gap_after(
            self._controller.active_stage_index, value,
        )

    def _on_add_layer(self) -> None:
        self._controller.add_layer(self._controller.active_stage_index)

    def _on_layer_mat_changed(self, layer_idx: int, mat_id: str) -> None:
        self._controller.set_layer_material(
            self._controller.active_stage_index, layer_idx, mat_id,
        )

    def _on_layer_thick_changed(self, layer_idx: int, thickness: float) -> None:
        self._controller.set_layer_thickness(
            self._controller.active_stage_index, layer_idx, thickness,
        )

    def _on_layer_delete(self, layer_idx: int) -> None:
        self._controller.remove_layer(
            self._controller.active_stage_index, layer_idx,
        )

    def _on_layer_dropped(self, from_idx: int, to_idx: int) -> None:
        self._controller.move_layer(
            self._controller.active_stage_index, from_idx, to_idx,
        )

    def _on_layer_row_clicked(self, layer_idx: int) -> None:
        self._controller.select_layer(
            self._controller.active_stage_index, layer_idx,
        )

    def _on_layer_composite_toggled(self, layer_idx: int, enabled: bool) -> None:
        self._controller.set_layer_composite(
            self._controller.active_stage_index, layer_idx, enabled,
        )

    def _on_layer_inner_mat_changed(self, layer_idx: int, mat_id: str) -> None:
        self._controller.set_layer_inner_material(
            self._controller.active_stage_index, layer_idx, mat_id,
        )

    def _on_layer_inner_width_changed(self, layer_idx: int, width: float) -> None:
        self._controller.set_layer_inner_width(
            self._controller.active_stage_index, layer_idx, width,
        )

    # ------------------------------------------------------------------
    # Aperture
    # ------------------------------------------------------------------

    @staticmethod
    def _set_row_visible(
        label: QLabel, spin: QDoubleSpinBox, visible: bool,
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
