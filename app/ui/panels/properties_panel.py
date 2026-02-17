"""Properties panel — numeric property editors for source and detector.

Collapsible sections for source, dose/intensity, and detector parameters.
All values sync bidirectionally with GeometryController.

Reference: Phase-03 spec — FR-1.3.5, FR-1.5.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QComboBox, QFrame,
)

from app.ui.widgets.smart_spinbox import SmartDoubleSpinBox
from PyQt6.QtCore import QSignalBlocker

from app.core.i18n import t, TranslationManager
from app.models.geometry import FocalSpotDistribution
from app.ui.canvas.geometry_controller import GeometryController


class PropertiesPanel(QWidget):
    """Right dock panel section — numeric property editors.

    Sections: Source, Dose / Intensity, Detector.
    """

    def __init__(
        self,
        controller: GeometryController,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._energy_mode = "kVp"
        self._dose_per_pulse = 0.8 / 260.0  # Gy/min per pulse calibration
        self._build_ui()
        self._connect_signals()
        self._refresh_all()
        TranslationManager.on_language_changed(self.retranslate_ui)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # --- Source ---
        self._lbl_source_header = self._section_label(t("panels.source_mm", "Source (mm)"))
        layout.addWidget(self._lbl_source_header)
        src_frame = self._make_frame()
        src_layout = QVBoxLayout(src_frame)
        src_layout.setContentsMargins(6, 4, 6, 4)
        src_layout.setSpacing(3)

        row2 = QHBoxLayout()
        self._lbl_focal = self._prop_label(t("panels.focal_spot", "Focal Spot:"))
        row2.addWidget(self._lbl_focal)
        self._spin_focal = SmartDoubleSpinBox()
        self._spin_focal.setRange(0.1, 20.0)
        self._spin_focal.setDecimals(2)
        self._spin_focal.setSingleStep(0.1)
        row2.addWidget(self._spin_focal)
        src_layout.addLayout(row2)

        row2b = QHBoxLayout()
        self._lbl_distribution = self._prop_label(t("panels.distribution", "Distribution:"))
        row2b.addWidget(self._lbl_distribution)
        self._combo_focal_dist = QComboBox()
        self._combo_focal_dist.setStyleSheet("font-size: 8pt;")
        self._combo_focal_dist.addItem(
            "Uniform", FocalSpotDistribution.UNIFORM
        )
        self._combo_focal_dist.addItem(
            "Gaussian", FocalSpotDistribution.GAUSSIAN
        )
        row2b.addWidget(self._combo_focal_dist)
        src_layout.addLayout(row2b)

        row2c = QHBoxLayout()
        self._lbl_beam_angle = self._prop_label(t("panels.beam_angle", "Beam Angle:"))
        row2c.addWidget(self._lbl_beam_angle)
        self._spin_beam_angle = SmartDoubleSpinBox()
        self._spin_beam_angle.setRange(0.0, 180.0)
        self._spin_beam_angle.setSuffix("\u00B0")
        self._spin_beam_angle.setDecimals(2)
        self._spin_beam_angle.setSingleStep(1.0)
        self._spin_beam_angle.setSpecialValueText(t("panels.automatic", "Automatic"))
        row2c.addWidget(self._spin_beam_angle)
        src_layout.addLayout(row2c)

        layout.addWidget(src_frame)

        # --- Dose / Intensity ---
        self._lbl_dose_header = self._section_label(
            t("panels.dose_intensity", "Dose / Intensity")
        )
        layout.addWidget(self._lbl_dose_header)
        dose_frame = self._make_frame()
        dose_layout = QVBoxLayout(dose_frame)
        dose_layout.setContentsMargins(6, 4, 6, 4)
        dose_layout.setSpacing(3)

        # Tube mode: current [mA]
        row_mA = QHBoxLayout()
        self._lbl_tube_current = self._prop_label(
            t("panels.tube_current", "Tube Current:")
        )
        row_mA.addWidget(self._lbl_tube_current)
        self._spin_tube_current = SmartDoubleSpinBox()
        self._spin_tube_current.setRange(0.1, 20.0)
        self._spin_tube_current.setSuffix(" mA")
        self._spin_tube_current.setDecimals(1)
        self._spin_tube_current.setSingleStep(0.1)
        self._spin_tube_current.setValue(8.0)
        row_mA.addWidget(self._spin_tube_current)
        dose_layout.addLayout(row_mA)

        # Tube mode: output method
        row_method = QHBoxLayout()
        self._lbl_tube_method = self._prop_label(
            t("panels.output_method", "Output:")
        )
        row_method.addWidget(self._lbl_tube_method)
        self._combo_tube_method = QComboBox()
        self._combo_tube_method.setStyleSheet("font-size: 8pt;")
        self._combo_tube_method.addItem(
            t("panels.empirical", "Empirical"), "empirical"
        )
        self._combo_tube_method.addItem(
            t("panels.spectral", "Spectral"), "spectral"
        )
        self._combo_tube_method.addItem(
            t("panels.lookup_table", "Lookup"), "lookup"
        )
        row_method.addWidget(self._combo_tube_method)
        dose_layout.addLayout(row_method)

        # LINAC mode: PPS
        row_pps = QHBoxLayout()
        self._lbl_pps = self._prop_label("PPS:")
        row_pps.addWidget(self._lbl_pps)
        self._spin_pps = QSpinBox()
        self._spin_pps.setRange(50, 1600)
        self._spin_pps.setSuffix(" PPS")
        self._spin_pps.setSingleStep(10)
        self._spin_pps.setValue(260)
        row_pps.addWidget(self._spin_pps)
        dose_layout.addLayout(row_pps)

        # LINAC mode: dose rate [Gy/min]
        row_dose = QHBoxLayout()
        self._lbl_linac_dose = self._prop_label(
            t("panels.dose_rate", "Dose Rate:")
        )
        row_dose.addWidget(self._lbl_linac_dose)
        self._spin_linac_dose = SmartDoubleSpinBox()
        self._spin_linac_dose.setRange(0.01, 100.0)
        self._spin_linac_dose.setSuffix(" Gy/min")
        self._spin_linac_dose.setDecimals(3)
        self._spin_linac_dose.setSingleStep(0.1)
        self._spin_linac_dose.setValue(0.8)
        row_dose.addWidget(self._spin_linac_dose)
        dose_layout.addLayout(row_dose)

        layout.addWidget(dose_frame)

        # Store row widgets for visibility toggling
        self._tube_widgets = [
            self._lbl_tube_current, self._spin_tube_current,
            self._lbl_tube_method, self._combo_tube_method,
        ]
        self._linac_widgets = [
            self._lbl_pps, self._spin_pps,
            self._lbl_linac_dose, self._spin_linac_dose,
        ]

        # --- Detector ---
        self._lbl_detector_header = self._section_label(t("panels.detector_mm", "Detector (mm)"))
        layout.addWidget(self._lbl_detector_header)
        det_frame = self._make_frame()
        det_layout = QVBoxLayout(det_frame)
        det_layout.setContentsMargins(6, 4, 6, 4)
        det_layout.setSpacing(3)

        row3 = QHBoxLayout()
        self._lbl_y_position = self._prop_label(t("panels.y_position", "Y Position:"))
        row3.addWidget(self._lbl_y_position)
        self._spin_det_y = SmartDoubleSpinBox()
        self._spin_det_y.setRange(0, 5000)
        self._spin_det_y.setDecimals(2)
        self._spin_det_y.setSingleStep(1.0)
        row3.addWidget(self._spin_det_y)
        det_layout.addLayout(row3)

        row4 = QHBoxLayout()
        self._lbl_width = self._prop_label(t("panels.width", "Width:"))
        row4.addWidget(self._lbl_width)
        self._spin_det_w = SmartDoubleSpinBox()
        self._spin_det_w.setRange(10, 2000)
        self._spin_det_w.setDecimals(2)
        self._spin_det_w.setSingleStep(1.0)
        row4.addWidget(self._spin_det_w)
        det_layout.addLayout(row4)

        row5 = QHBoxLayout()
        self._lbl_sdd_label = self._prop_label(t("panels.sdd", "SDD:"))
        row5.addWidget(self._lbl_sdd_label)
        self._lbl_sdd = QLabel("\u2014")
        self._lbl_sdd.setStyleSheet("color: #F8FAFC; font-size: 8pt;")
        row5.addWidget(self._lbl_sdd)
        det_layout.addLayout(row5)

        layout.addWidget(det_frame)

        layout.addStretch()

        # Initial visibility
        self._update_dose_visibility()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 8pt;")
        return lbl

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
        ctrl.source_changed.connect(self._on_source_changed)
        ctrl.detector_changed.connect(self._on_detector_changed)
        ctrl.geometry_changed.connect(self._refresh_all)
        ctrl.collimator_type_changed.connect(lambda _: self._refresh_all())

        self._spin_focal.valueChanged.connect(self._on_focal_changed)
        self._combo_focal_dist.currentIndexChanged.connect(
            self._on_focal_dist_changed
        )
        self._spin_beam_angle.valueChanged.connect(self._on_beam_angle_changed)
        self._spin_det_y.valueChanged.connect(self._on_det_y_changed)
        self._spin_det_w.valueChanged.connect(self._on_det_w_changed)

        # Dose widgets
        self._spin_tube_current.valueChanged.connect(self._on_tube_current_changed)
        self._combo_tube_method.currentIndexChanged.connect(
            self._on_tube_method_changed
        )
        self._spin_pps.valueChanged.connect(self._on_pps_changed)
        self._spin_linac_dose.valueChanged.connect(self._on_linac_dose_changed)

    # ------------------------------------------------------------------
    # Energy mode (called by MainWindow when toolbar mode changes)
    # ------------------------------------------------------------------

    def set_energy_mode(self, mode: str) -> None:
        """Switch between kVp (tube) and MeV (LINAC) dose inputs.

        Args:
            mode: "kVp" or "MeV".
        """
        self._energy_mode = mode
        self._update_dose_visibility()

    def _update_dose_visibility(self) -> None:
        """Show tube widgets for kVp, LINAC widgets for MeV."""
        is_tube = self._energy_mode == "kVp"
        for w in self._tube_widgets:
            w.setVisible(is_tube)
        for w in self._linac_widgets:
            w.setVisible(not is_tube)

    # ------------------------------------------------------------------
    # Retranslation
    # ------------------------------------------------------------------

    def retranslate_ui(self) -> None:
        """Update all translatable strings after language change."""
        self._lbl_source_header.setText(t("panels.source_mm", "Source (mm)"))
        self._lbl_focal.setText(t("panels.focal_spot", "Focal Spot:"))
        self._lbl_distribution.setText(t("panels.distribution", "Distribution:"))
        self._lbl_beam_angle.setText(t("panels.beam_angle", "Beam Angle:"))
        self._spin_beam_angle.setSpecialValueText(t("panels.automatic", "Automatic"))
        self._lbl_detector_header.setText(t("panels.detector_mm", "Detector (mm)"))
        self._lbl_y_position.setText(t("panels.y_position", "Y Position:"))
        self._lbl_width.setText(t("panels.width", "Width:"))
        self._lbl_sdd_label.setText(t("panels.sdd", "SDD:"))
        self._lbl_dose_header.setText(t("panels.dose_intensity", "Dose / Intensity"))
        self._lbl_tube_current.setText(t("panels.tube_current", "Tube Current:"))
        self._lbl_tube_method.setText(t("panels.output_method", "Output:"))
        from PyQt6.QtCore import QSignalBlocker
        with QSignalBlocker(self._combo_tube_method):
            self._combo_tube_method.setItemText(0, t("panels.empirical", "Empirical"))
            self._combo_tube_method.setItemText(1, t("panels.spectral", "Spectral"))
            self._combo_tube_method.setItemText(2, t("panels.lookup_table", "Lookup"))
        self._lbl_linac_dose.setText(t("panels.dose_rate", "Dose Rate:"))

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        self._on_source_changed()
        self._on_detector_changed()

    def _on_source_changed(self) -> None:
        src = self._controller.geometry.source
        with QSignalBlocker(self._spin_focal):
            self._spin_focal.setValue(src.focal_spot_size)
        with QSignalBlocker(self._combo_focal_dist):
            for i in range(self._combo_focal_dist.count()):
                if self._combo_focal_dist.itemData(i) == src.focal_spot_distribution:
                    self._combo_focal_dist.setCurrentIndex(i)
                    break
        with QSignalBlocker(self._spin_beam_angle):
            self._spin_beam_angle.setValue(src.beam_angle)

        # Dose fields
        with QSignalBlocker(self._spin_tube_current):
            self._spin_tube_current.setValue(src.tube_current_mA)
        with QSignalBlocker(self._combo_tube_method):
            idx = self._combo_tube_method.findData(src.tube_output_method)
            if idx >= 0:
                self._combo_tube_method.setCurrentIndex(idx)
        with QSignalBlocker(self._spin_pps):
            self._spin_pps.setValue(src.linac_pps)
        with QSignalBlocker(self._spin_linac_dose):
            self._spin_linac_dose.setValue(src.linac_dose_rate_Gy_min)

        # Recalibrate dose_per_pulse from model
        if src.linac_ref_pps > 0:
            self._dose_per_pulse = src.linac_dose_rate_Gy_min / src.linac_ref_pps

    def _on_detector_changed(self) -> None:
        det = self._controller.geometry.detector
        with QSignalBlocker(self._spin_det_y):
            self._spin_det_y.setValue(det.position.y)
        with QSignalBlocker(self._spin_det_w):
            self._spin_det_w.setValue(det.width)
        self._lbl_sdd.setText(f"{det.distance_from_source:.0f}")

    # ------------------------------------------------------------------
    # Widget -> controller slots
    # ------------------------------------------------------------------

    def _on_focal_changed(self, value: float) -> None:
        self._controller.set_source_focal_spot(value)

    def _on_focal_dist_changed(self, idx: int) -> None:
        dist = self._combo_focal_dist.currentData()
        if dist is not None:
            self._controller.set_source_focal_spot_distribution(dist)

    def _on_beam_angle_changed(self, value: float) -> None:
        self._controller.set_source_beam_angle(value)

    def _on_det_y_changed(self, value: float) -> None:
        det = self._controller.geometry.detector
        self._controller.set_detector_position(det.position.x, value)

    def _on_det_w_changed(self, value: float) -> None:
        self._controller.set_detector_width(value)

    # -- Dose slots --

    def _on_tube_current_changed(self, value: float) -> None:
        self._controller.set_tube_current(value)

    def _on_tube_method_changed(self, idx: int) -> None:
        method = self._combo_tube_method.currentData()
        if method is not None:
            self._controller.set_tube_output_method(method)

    def _on_pps_changed(self, value: int) -> None:
        """PPS changed → update Gy/min proportionally."""
        new_dose = self._dose_per_pulse * value
        with QSignalBlocker(self._spin_linac_dose):
            self._spin_linac_dose.setValue(new_dose)
        self._controller.set_linac_pps(value)
        self._controller.set_linac_dose_rate(new_dose, ref_pps=value)

    def _on_linac_dose_changed(self, value: float) -> None:
        """Gy/min changed → recalibrate dose_per_pulse."""
        pps = self._spin_pps.value()
        if pps > 0:
            self._dose_per_pulse = value / pps
        self._controller.set_linac_dose_rate(value, ref_pps=pps)
