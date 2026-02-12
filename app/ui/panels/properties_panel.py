"""Properties panel — numeric property editors for source and detector.

Collapsible sections for source and detector parameters.
All values sync bidirectionally with GeometryController.

Reference: Phase-03 spec — FR-1.3.5, FR-1.5.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox,
    QComboBox, QFrame,
)
from PyQt6.QtCore import QSignalBlocker

from app.models.geometry import FocalSpotDistribution
from app.ui.canvas.geometry_controller import GeometryController


class PropertiesPanel(QWidget):
    """Right dock panel section — numeric property editors.

    Sections: Source, Detector.
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

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # --- Source ---
        layout.addWidget(self._section_label("Kaynak"))
        src_frame = self._make_frame()
        src_layout = QVBoxLayout(src_frame)
        src_layout.setContentsMargins(6, 4, 6, 4)
        src_layout.setSpacing(3)

        row1 = QHBoxLayout()
        row1.addWidget(self._prop_label("Y Pozisyon:"))
        self._spin_src_y = QDoubleSpinBox()
        self._spin_src_y.setRange(-2000, 0)
        self._spin_src_y.setSuffix(" mm")
        self._spin_src_y.setDecimals(1)
        row1.addWidget(self._spin_src_y)
        src_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(self._prop_label("Focal Spot:"))
        self._spin_focal = QDoubleSpinBox()
        self._spin_focal.setRange(0.1, 20.0)
        self._spin_focal.setSuffix(" mm")
        self._spin_focal.setDecimals(1)
        row2.addWidget(self._spin_focal)
        src_layout.addLayout(row2)

        row2b = QHBoxLayout()
        row2b.addWidget(self._prop_label("Dağılım:"))
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

        layout.addWidget(src_frame)

        # --- Detector ---
        layout.addWidget(self._section_label("Detektör"))
        det_frame = self._make_frame()
        det_layout = QVBoxLayout(det_frame)
        det_layout.setContentsMargins(6, 4, 6, 4)
        det_layout.setSpacing(3)

        row3 = QHBoxLayout()
        row3.addWidget(self._prop_label("Y Pozisyon:"))
        self._spin_det_y = QDoubleSpinBox()
        self._spin_det_y.setRange(0, 5000)
        self._spin_det_y.setSuffix(" mm")
        self._spin_det_y.setDecimals(1)
        row3.addWidget(self._spin_det_y)
        det_layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(self._prop_label("Genişlik:"))
        self._spin_det_w = QDoubleSpinBox()
        self._spin_det_w.setRange(10, 2000)
        self._spin_det_w.setSuffix(" mm")
        self._spin_det_w.setDecimals(1)
        row4.addWidget(self._spin_det_w)
        det_layout.addLayout(row4)

        row5 = QHBoxLayout()
        row5.addWidget(self._prop_label("SDD:"))
        self._lbl_sdd = QLabel("— mm")
        self._lbl_sdd.setStyleSheet("color: #F8FAFC; font-size: 8pt;")
        row5.addWidget(self._lbl_sdd)
        det_layout.addLayout(row5)

        layout.addWidget(det_frame)

        layout.addStretch()

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

        self._spin_src_y.valueChanged.connect(self._on_src_y_changed)
        self._spin_focal.valueChanged.connect(self._on_focal_changed)
        self._combo_focal_dist.currentIndexChanged.connect(
            self._on_focal_dist_changed
        )
        self._spin_det_y.valueChanged.connect(self._on_det_y_changed)
        self._spin_det_w.valueChanged.connect(self._on_det_w_changed)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        self._on_source_changed()
        self._on_detector_changed()

    def _on_source_changed(self) -> None:
        src = self._controller.geometry.source
        with QSignalBlocker(self._spin_src_y):
            self._spin_src_y.setValue(src.position.y)
        with QSignalBlocker(self._spin_focal):
            self._spin_focal.setValue(src.focal_spot_size)
        with QSignalBlocker(self._combo_focal_dist):
            for i in range(self._combo_focal_dist.count()):
                if self._combo_focal_dist.itemData(i) == src.focal_spot_distribution:
                    self._combo_focal_dist.setCurrentIndex(i)
                    break

    def _on_detector_changed(self) -> None:
        det = self._controller.geometry.detector
        with QSignalBlocker(self._spin_det_y):
            self._spin_det_y.setValue(det.position.y)
        with QSignalBlocker(self._spin_det_w):
            self._spin_det_w.setValue(det.width)
        self._lbl_sdd.setText(f"{det.distance_from_source:.0f} mm")

    # ------------------------------------------------------------------
    # Widget -> controller slots
    # ------------------------------------------------------------------

    def _on_src_y_changed(self, value: float) -> None:
        src = self._controller.geometry.source
        self._controller.set_source_position(src.position.x, value)

    def _on_focal_changed(self, value: float) -> None:
        self._controller.set_source_focal_spot(value)

    def _on_focal_dist_changed(self, idx: int) -> None:
        dist = self._combo_focal_dist.currentData()
        if dist is not None:
            self._controller.set_source_focal_spot_distribution(dist)

    def _on_det_y_changed(self, value: float) -> None:
        det = self._controller.geometry.detector
        self._controller.set_detector_position(det.position.x, value)

    def _on_det_w_changed(self, value: float) -> None:
        self._controller.set_detector_width(value)
