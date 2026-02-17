"""Main window — QMainWindow with canvas, dock panels, toolbar, status bar.

Layout:
  Top:    MainToolBar
  Left:   Materials panel (QDockWidget)
  Center: CollimatorView (QGraphicsView with canvas scene)
  Right:  Layers / Properties / Simulation Results (QDockWidget)
  Bottom: Chart tabs (QTabWidget inside QDockWidget)
  Footer: QStatusBar

Reference: FRD §6 — UI/UX Design, Phase-01/03/04 specs.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QWidget, QLabel,
    QVBoxLayout, QTabWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

import json
import logging

import numpy as np

from app.constants import (
    APP_NAME, APP_VERSION, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    DEFAULT_NUM_RAYS,
)
from app.core.beam_simulation import BeamSimulation
from app.core.serializers import geometry_to_dict, dict_to_geometry
from app.core.build_up_factors import BuildUpFactors
from app.core.dose_calculator import DoseCalculator
from app.core.i18n import t, TranslationManager
from app.core.compton_engine import ComptonEngine
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.projection_engine import ProjectionEngine
from app.core.ray_tracer import RayTracer
from app.core.units import Gy_h_to_µSv_h
from app.ui.toolbar import MainToolBar
from app.ui.canvas.geometry_controller import GeometryController
from app.ui.canvas.collimator_scene import CollimatorScene
from app.ui.canvas.collimator_view import CollimatorView
from app.database.db_manager import DatabaseManager
from app.database.design_repository import DesignRepository
from app.export.csv_export import CsvExporter
from app.export.image_export import ImageExporter
from app.export.json_export import JsonExporter
from app.export.cdt_export import CdtExporter
from app.models.simulation import DoseDisplayUnit, SimulationConfig
from app.ui.charts.attenuation_chart import AttenuationChartWidget
from app.ui.charts.compton_widget import ComptonWidget
from app.ui.charts.hvl_chart import HvlChartWidget
from app.ui.charts.spectrum_chart import SpectrumChartWidget
from app.ui.charts.spr_chart import SprChartWidget
from app.ui.charts.transmission_chart import TransmissionChartWidget
from app.ui.dialogs.compare_dialog import CompareDialog
from app.ui.dialogs.threshold_dialog import ThresholdDialog
from app.ui.dialogs.save_design_dialog import SaveDesignDialog
from app.ui.dialogs.design_manager import DesignManagerDialog
from app.ui.dialogs.export_dialog import ExportDialog
from app.ui.dialogs.version_history_dialog import VersionHistoryDialog
from app.ui.panels.material_panel import MaterialPanel
from app.ui.panels.layer_panel import LayerPanel
from app.ui.panels.phantom_panel import PhantomPanel
from app.ui.panels.properties_panel import PropertiesPanel
from app.ui.panels.projection_results_panel import ProjectionResultsPanel
from app.ui.panels.results_panel import ResultsPanel
from app.ui.widgets.collapsible_section import CollapsibleSection
from app.workers.projection_worker import ProjectionWorker
from app.workers.simulation_worker import SimulationWorker
from app.core.klein_nishina_sampler import KleinNishinaSampler
from app.core.scatter_tracer import ScatterTracer
from app.core.isodose_engine import IsodoseEngine
from app.workers.scatter_worker import ScatterWorker
from app.workers.isodose_worker import IsodoseWorker
from app.models.simulation import ComptonConfig
from app.ui.charts.isodose_chart import IsodoseChartWidget


class MainWindow(QMainWindow):
    """Application main window with canvas, side panels, and toolbar."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        # Core services
        self._controller = GeometryController()
        self._material_service = MaterialService()
        self._physics_engine = PhysicsEngine(self._material_service)
        self._projection_engine = ProjectionEngine(self._physics_engine)
        from app.core.spectrum_models import XRaySpectrum
        self._xray_spectrum = XRaySpectrum(self._material_service)
        self._projection_worker: ProjectionWorker | None = None

        # Phase 4: Ray-tracing services
        self._buildup_service = BuildUpFactors()
        self._ray_tracer = RayTracer()
        self._beam_sim = BeamSimulation(
            self._physics_engine,
            self._ray_tracer,
            self._buildup_service,
        )
        self._simulation_worker: SimulationWorker | None = None
        self._dose_calculator = DoseCalculator()

        # Phase 5: Compton engine
        self._compton_engine = ComptonEngine()

        # Phase 7: Scatter ray-tracing
        self._kn_sampler = KleinNishinaSampler()
        self._scatter_tracer = ScatterTracer(
            self._physics_engine,
            self._ray_tracer,
            self._compton_engine,
            self._kn_sampler,
        )
        self._scatter_worker: ScatterWorker | None = None
        self._last_scatter_result = None

        # Phase 8: Isodose map
        self._isodose_engine = IsodoseEngine(self._physics_engine)
        self._isodose_worker: IsodoseWorker | None = None

        # Phase 6: Database and design state
        self._db_manager = DatabaseManager()
        self._db_manager.initialize_database()
        self._design_repo = DesignRepository(self._db_manager)
        self._image_exporter = ImageExporter()
        self._current_design_id: str | None = None
        self._is_dirty: bool = False
        self._last_simulation_result: SimulationResult | None = None

        self._build_ui()
        self._connect_signals()
        self._restore_state()
        self._restore_session()
        self._initial_fit_done = False
        self._update_title()

    def _build_ui(self):
        # Toolbar
        self._toolbar = MainToolBar(self)
        self._toolbar.setObjectName("MainToolBar")
        self.addToolBar(self._toolbar)

        # Central widget — Canvas
        self._scene = CollimatorScene(self._controller)
        self._view = CollimatorView(self._scene)
        self.setCentralWidget(self._view)

        # Left panel — Materials
        self._material_panel = MaterialPanel()
        self._left_dock = self._create_dock(
            t("panels.materials", "Materials"),
            Qt.DockWidgetArea.LeftDockWidgetArea,
            self._material_panel,
        )
        self._left_dock.setMinimumWidth(200)

        # Right panel — Layers + Properties + Results
        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._right_scroll.setStyleSheet("QScrollArea { border: none; }")

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Layer section
        self._layer_panel = LayerPanel(self._controller)
        self._layer_section = CollapsibleSection(t("panels.layers", "Layers"))
        self._layer_section.set_content_widget(self._layer_panel)
        right_layout.addWidget(self._layer_section)

        # Properties section
        self._properties_panel = PropertiesPanel(self._controller)
        self._props_section = CollapsibleSection(t("panels.properties", "Properties"))
        self._props_section.set_content_widget(self._properties_panel)
        right_layout.addWidget(self._props_section)

        # Phantom panel
        self._phantom_panel = PhantomPanel(self._controller)
        self._phantom_section = CollapsibleSection(t("panels.test_objects", "Test Objects"))
        self._phantom_section.set_content_widget(self._phantom_panel)
        right_layout.addWidget(self._phantom_section)

        # Simulation results section
        self._results_panel = ResultsPanel()
        self._results_section = CollapsibleSection(t("panels.simulation_results", "Simulation Results"))
        self._results_section.set_content_widget(self._results_panel)
        right_layout.addWidget(self._results_section)

        right_layout.addStretch()
        self._right_scroll.setWidget(right_widget)

        self._right_dock = self._create_dock(
            t("panels.layers_properties", "Layers / Properties"),
            Qt.DockWidgetArea.RightDockWidgetArea,
            self._right_scroll,
        )
        self._right_dock.setMinimumWidth(320)

        # Bottom panel — Chart tabs
        self._chart_tabs = self._create_chart_tabs()
        self._bottom_dock = self._create_dock(
            t("panels.charts", "Charts"),
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._chart_tabs,
        )

        # LINAC warning label (G-6) — hidden by default
        self._linac_warning = QLabel(
            "  " + t("status.linac_warning",
                     "LINAC mode: Build-up and pair production effects are calculated "
                     "with a simplified model at high energies (>1 MeV).") + "  "
        )
        self._linac_warning.setStyleSheet(
            "background-color: #92400E; color: #FDE68A; "
            "font-size: 9pt; padding: 4px; border-radius: 3px;"
        )
        self._linac_warning.setVisible(False)
        self.statusBar().addPermanentWidget(self._linac_warning)

        # Right-click "Show Properties" on canvas items
        self._scene.show_properties_requested.connect(self._show_panel_for_object)

        # Status bar
        self.statusBar().showMessage(t("status.ready", "Ready"))

        # Register for language changes
        TranslationManager.on_language_changed(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        """Update all translatable UI strings on language change."""
        self._left_dock.setWindowTitle(t("panels.materials", "Materials"))
        self._right_dock.setWindowTitle(t("panels.layers_properties", "Layers / Properties"))
        self._bottom_dock.setWindowTitle(t("panels.charts", "Charts"))

        self._layer_section.set_title(t("panels.layers", "Layers"))
        self._props_section.set_title(t("panels.properties", "Properties"))
        self._phantom_section.set_title(t("panels.test_objects", "Test Objects"))
        self._results_section.set_title(t("panels.simulation_results", "Simulation Results"))

        # Chart tab labels
        self._chart_tabs.setTabText(0, t("charts.projection", "Projection"))
        self._chart_tabs.setTabText(1, t("charts.beam_profile", "Beam Profile"))
        self._chart_tabs.setTabText(2, "mu/rho")
        self._chart_tabs.setTabText(3, "HVL/TVL")
        self._chart_tabs.setTabText(4, t("charts.transmission", "Transmission vs Thickness"))
        self._chart_tabs.setTabText(5, t("charts.compton", "Compton"))
        self._chart_tabs.setTabText(6, t("charts.spr_tab", "SPR Profile"))
        self._chart_tabs.setTabText(7, t("charts.spectrum", "Spectrum"))
        self._chart_tabs.setTabText(8, t("charts.isodose", "Isodose"))

        # LINAC warning
        self._linac_warning.setText(
            "  " + t("status.linac_warning",
                     "LINAC mode: Build-up and pair production effects are calculated "
                     "with a simplified model at high energies (>1 MeV).") + "  "
        )

        # Beam profile placeholder
        if self._beam_profile_placeholder is not None:
            self._beam_profile_placeholder.setText(
                t("charts.beam_profile_placeholder", "Click 'Simulate' to start the simulation.")
            )

        # Beam profile axes (if canvas exists)
        if self._beam_ax is not None:
            self._setup_beam_axes()
            self._beam_figure.tight_layout()
            self._beam_canvas.draw()

        self.statusBar().showMessage(t("status.ready", "Ready"))

    def _show_panel_for_object(self, object_type: str) -> None:
        """Open and scroll to the relevant panel for a canvas object.

        Args:
            object_type: "stage", "source", "detector", or "phantom".
        """
        # Ensure right dock is visible
        if not self._right_dock.isVisible():
            self._right_dock.show()
        self._right_dock.raise_()

        # Map object type to the collapsible section to expand
        section_map = {
            "stage": self._layer_section,
            "source": self._props_section,
            "detector": self._props_section,
            "phantom": self._phantom_section,
        }
        target_section = section_map.get(object_type)
        if target_section is None:
            return

        # Expand the target section
        target_section.expand()

        # Scroll to make the section visible
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._right_scroll.ensureWidgetVisible(
            target_section, 0, 50,
        ))

    def _connect_signals(self):
        # Toolbar -> controller
        self._toolbar.collimator_type_changed.connect(
            self._controller.set_collimator_type
        )
        self._toolbar.custom_template_requested.connect(
            self._controller.create_blank_geometry
        )

        # Fit button
        self._toolbar.fit_button.clicked.connect(self._view.fit_to_content)

        # Dimensions toggle
        self._toolbar.dimensions_button.toggled.connect(
            self._scene.set_dimensions_visible
        )

        # Grid spacing
        self._toolbar.grid_button.menu().triggered.connect(
            lambda action: self._on_grid_changed(action.text())
        )

        # Zoom display in status bar
        self._view.zoom_changed.connect(
            lambda z: self.statusBar().showMessage(
                t("status.zoom", "Zoom: {pct}").format(pct=f"{z:.0%}")
            )
        )

        # After type change, fit to new content
        self._controller.geometry_changed.connect(
            lambda: self._view.fit_to_content()
        )

        # Source/detector drag → update controller
        self._scene._source_item.setFlag(
            self._scene._source_item.GraphicsItemFlag.ItemSendsGeometryChanges,
            True,
        )

        # Phantom change → auto-calculate projection
        self._controller.phantom_added.connect(self._run_projection)
        self._controller.phantom_changed.connect(self._run_projection)
        self._controller.phantom_selected.connect(self._run_projection)
        self._controller.source_changed.connect(self._run_projection_if_phantom)
        self._controller.detector_changed.connect(self._run_projection_if_phantom)
        self._toolbar.energy_changed.connect(
            lambda _: self._run_projection_if_phantom()
        )

        # Phase 5: Energy slider → chart widgets
        self._toolbar.energy_changed.connect(
            lambda e: self._transmission_chart.set_energy(e)
        )
        self._toolbar.energy_changed.connect(
            lambda e: self._compton_widget.set_energy(e)
        )

        # Simulate button → run ray-tracing simulation
        self._toolbar._btn_simulate.clicked.connect(self._run_simulation)

        # G-3: Compare button → multi-energy overlay
        self._toolbar.compare_requested.connect(self._run_compare)

        # G-6: Energy mode change → LINAC warning visibility
        self._toolbar.energy_mode_changed.connect(self._on_energy_mode_changed)

        # G-10: Threshold edit
        self._toolbar.threshold_edit_requested.connect(self._on_edit_thresholds)

        # Phase 8: Isodose toggle → canvas overlay visibility
        self._toolbar.isodose_button.toggled.connect(
            self._scene.set_isodose_visible
        )

        # Phase 8: Validation
        self._toolbar.validation_requested.connect(self._on_run_validation)

        # Spectrum chart: update when tube config changes
        self._toolbar.tube_config_changed.connect(self._on_tube_config_changed)

        # About dialog
        self._toolbar.about_requested.connect(self._on_about)

        # Phase 6: File menu signals
        self._toolbar.new_requested.connect(self._on_new)
        self._toolbar.open_requested.connect(self._on_open)
        self._toolbar.import_external_requested.connect(self._on_import_external)
        self._toolbar.save_requested.connect(self._on_save)
        self._toolbar.save_as_requested.connect(self._on_save_as)
        self._toolbar.export_requested.connect(self._on_export)
        self._toolbar.version_history_requested.connect(self._on_version_history)

        # Edit menu signals
        self._toolbar.undo_requested.connect(self._on_undo)
        self._toolbar.redo_requested.connect(self._on_redo)
        self._toolbar.cut_requested.connect(self._on_cut)
        self._toolbar.copy_requested.connect(self._on_copy)
        self._toolbar.paste_requested.connect(self._on_paste)
        self._toolbar.delete_requested.connect(self._on_delete)

        # Undo state → toolbar enable/disable
        self._controller.undo_state_changed.connect(self._update_edit_menu_state)

        # Keyboard shortcuts — file
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_new)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._on_open)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self._on_save_as)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._on_export)

        # Keyboard shortcuts — edit (Ctrl+C/X/V omitted: conflict with text fields)
        QShortcut(QKeySequence("Ctrl+U"), self).activated.connect(self._on_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._on_redo)

        # Dirty tracking
        self._controller.geometry_changed.connect(self._mark_dirty)
        self._controller.stage_changed.connect(lambda _: self._mark_dirty())
        self._controller.source_changed.connect(self._mark_dirty)
        self._controller.detector_changed.connect(self._mark_dirty)

    def _on_grid_changed(self, text: str) -> None:
        """Parse grid menu text and update grid."""
        try:
            spacing = float(text.replace(" mm", ""))
            self._scene._grid_item.set_grid_spacing(spacing)
        except ValueError:
            pass

    def _create_dock(self, title: str, area, widget: QWidget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(title)
        dock.setWidget(widget)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(area, dock)
        return dock

    def _create_chart_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        # Projection results panel (first tab for visibility)
        self._projection_panel = ProjectionResultsPanel()
        tabs.addTab(self._projection_panel, t("charts.projection", "Projection"))

        # Beam profile panel (Phase 4 — populated on simulation)
        self._beam_profile_panel = self._create_beam_profile_panel()
        tabs.addTab(self._beam_profile_panel, t("charts.beam_profile", "Beam Profile"))

        # Phase 5: Interactive chart widgets
        self._attenuation_chart = AttenuationChartWidget(self._material_service)
        tabs.addTab(self._attenuation_chart, "mu/rho")

        self._hvl_chart = HvlChartWidget(
            self._material_service, self._physics_engine,
        )
        tabs.addTab(self._hvl_chart, "HVL/TVL")

        self._transmission_chart = TransmissionChartWidget(
            self._material_service, self._physics_engine,
        )
        tabs.addTab(self._transmission_chart, t("charts.transmission", "Transmission vs Thickness"))

        self._compton_widget = ComptonWidget(
            self._compton_engine, material_service=self._material_service,
        )
        tabs.addTab(self._compton_widget, t("charts.compton", "Compton"))

        # Phase 7: SPR profile chart
        self._spr_chart = SprChartWidget()
        tabs.addTab(self._spr_chart, t("charts.spr_tab", "SPR Profile"))

        # X-ray tube spectrum chart
        self._spectrum_chart = SpectrumChartWidget(self._material_service)
        tabs.addTab(self._spectrum_chart, t("charts.spectrum", "Spectrum"))

        # Phase 8: Isodose map chart
        self._isodose_chart = IsodoseChartWidget()
        tabs.addTab(self._isodose_chart, t("charts.isodose", "Isodose"))

        return tabs

    def _create_beam_profile_panel(self) -> QWidget:
        """Create the beam profile chart panel (lazy matplotlib)."""
        from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # Controls row: dose unit + visibility checkboxes
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 2)

        unit_label = QLabel(t("charts.y_axis_unit", "Y-Axis:"))
        unit_label.setStyleSheet("color: #94A3B8; font-size: 8pt;")
        ctrl_row.addWidget(unit_label)
        self._combo_dose_unit = QComboBox()
        self._combo_dose_unit.setStyleSheet("font-size: 8pt;")
        self._combo_dose_unit.addItem(
            "Relative (%)", DoseDisplayUnit.RELATIVE_PCT,
        )
        self._combo_dose_unit.addItem(
            "Gy/h", DoseDisplayUnit.GY_PER_HOUR,
        )
        self._combo_dose_unit.addItem(
            "\u00b5Sv/h", DoseDisplayUnit.MICROSV_PER_HOUR,
        )
        self._combo_dose_unit.addItem(
            "dB", DoseDisplayUnit.DB,
        )
        self._combo_dose_unit.currentIndexChanged.connect(
            self._on_dose_unit_changed,
        )
        ctrl_row.addWidget(self._combo_dose_unit)

        ctrl_row.addStretch()

        # Curve visibility checkboxes
        cb_style = "color: #94A3B8; font-size: 8pt;"
        self._cb_show_primary = QCheckBox(t("charts.show_primary", "Primary"))
        self._cb_show_primary.setStyleSheet(cb_style)
        self._cb_show_primary.setChecked(True)
        self._cb_show_primary.toggled.connect(self._on_beam_visibility_changed)
        ctrl_row.addWidget(self._cb_show_primary)

        self._cb_show_scatter = QCheckBox(t("charts.show_scatter", "Scatter"))
        self._cb_show_scatter.setStyleSheet(cb_style)
        self._cb_show_scatter.setChecked(True)
        self._cb_show_scatter.toggled.connect(self._on_beam_visibility_changed)
        ctrl_row.addWidget(self._cb_show_scatter)

        self._cb_show_combined = QCheckBox(t("charts.show_combined", "P+S"))
        self._cb_show_combined.setStyleSheet(cb_style)
        self._cb_show_combined.setChecked(True)
        self._cb_show_combined.toggled.connect(self._on_beam_visibility_changed)
        ctrl_row.addWidget(self._cb_show_combined)

        layout.addLayout(ctrl_row)

        self._beam_profile_placeholder = QLabel(
            t("charts.beam_profile_placeholder", "Click 'Simulate' to start the simulation.")
        )
        self._beam_profile_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._beam_profile_placeholder.setProperty("cssClass", "secondary")
        layout.addWidget(self._beam_profile_placeholder, stretch=1)

        # Coordinate readout label (below chart)
        self._beam_coord_label = QLabel("")
        self._beam_coord_label.setStyleSheet(
            "color: #94A3B8; font-size: 8pt; font-family: monospace; padding: 2px 4px;"
        )
        layout.addWidget(self._beam_coord_label)

        self._beam_canvas = None
        self._beam_figure = None
        self._beam_ax = None

        # CTRL+click measurement state
        self._beam_measure_point = None  # (x, y) of first CTRL+click
        self._beam_measure_artists = []  # matplotlib artists for cleanup

        # Cursor dot on curve
        self._beam_cursor_dot = None  # matplotlib Line2D artist
        self._beam_plot_pos = None  # NDArray — current X positions
        self._beam_plot_ydata = None  # NDArray — current Y data (unit-transformed)

        return widget

    def _ensure_beam_canvas(self) -> None:
        """Create beam profile matplotlib canvas on first use."""
        if self._beam_canvas is not None:
            return

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self._beam_figure = Figure(figsize=(6, 3), dpi=80)
        self._beam_figure.patch.set_facecolor("#0F172A")
        self._beam_ax = self._beam_figure.add_subplot(111)
        self._setup_beam_axes()

        self._beam_canvas = FigureCanvasQTAgg(self._beam_figure)
        self._beam_canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Connect mouse events for cursor readout + CTRL measurement
        self._beam_canvas.mpl_connect("motion_notify_event", self._on_beam_mouse_move)
        self._beam_canvas.mpl_connect("button_press_event", self._on_beam_mouse_click)

        # Replace placeholder
        layout = self._beam_profile_panel.layout()
        layout.removeWidget(self._beam_profile_placeholder)
        self._beam_profile_placeholder.deleteLater()
        self._beam_profile_placeholder = None
        layout.addWidget(self._beam_canvas, stretch=1)

    def _setup_beam_axes(self) -> None:
        """Configure beam profile plot axes."""
        ax = self._beam_ax
        ax.set_facecolor("#1E293B")
        ax.set_xlabel(t("charts.detector_position", "Detector Position (mm)"), color="#94A3B8", fontsize=10)
        ax.set_ylabel(t("charts.transmission_axis", "Transmission (T)"), color="#94A3B8", fontsize=10)
        ax.set_title(t("charts.beam_profile", "Beam Profile"), color="#F8FAFC", fontsize=12)
        ax.tick_params(colors="#64748B", labelsize=9)
        for spine in ax.spines.values():
            spine.set_color("#475569")
        ax.grid(True, alpha=0.2, color="#475569")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_fit_done:
            self._initial_fit_done = True
            # Defer fit_to_content so viewport has valid dimensions
            QTimer.singleShot(50, self._view.fit_to_content)

    def closeEvent(self, event):
        self._save_state()
        self._db_manager.close()
        super().closeEvent(event)

    def _save_state(self):
        settings = QSettings()
        settings.setValue("mainwindow/geometry", self.saveGeometry())
        settings.setValue("mainwindow/state", self.saveState())

        # Save current geometry to DB for session restore
        try:
            geo_dict = geometry_to_dict(self._controller.geometry)
            self._design_repo.set_setting(
                "last_session_geometry", json.dumps(geo_dict)
            )
            # Save current design ID (if any) so reopening links back
            self._design_repo.set_setting(
                "last_session_design_id",
                self._current_design_id or "",
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to save session geometry", exc_info=True
            )

    def _restore_state(self):
        settings = QSettings()
        geometry = settings.value("mainwindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("mainwindow/state")
        if state:
            self.restoreState(state)

    def _restore_session(self):
        """Restore last session geometry from DB on startup."""
        try:
            geo_json = self._design_repo.get_setting("last_session_geometry")
            if not geo_json:
                return
            geo_dict = json.loads(geo_json)
            geometry = dict_to_geometry(geo_dict)
            self._controller.set_geometry(geometry)
            self._controller.clear_undo()

            # Restore linked design ID
            design_id = self._design_repo.get_setting(
                "last_session_design_id", ""
            )
            self._current_design_id = design_id or None
            self._is_dirty = False
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to restore session geometry", exc_info=True
            )

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    def _run_projection_if_phantom(self) -> None:
        """Run projection only if there is an active phantom."""
        if self._controller.active_phantom is not None:
            self._run_projection()

    def _run_projection(self, *_args) -> None:
        """Run projection for the active phantom in a background thread."""
        phantom = self._controller.active_phantom
        if phantom is None or not phantom.config.enabled:
            self._projection_panel.clear()
            return

        geo = self._controller.geometry
        src_y = geo.source.position.y
        det_y = geo.detector.position.y
        focal_mm = geo.source.focal_spot_size
        focal_dist = geo.source.focal_spot_distribution
        energy = self._toolbar.get_energy_keV()

        worker = ProjectionWorker(self._projection_engine, self)
        worker.setup(phantom, src_y, det_y, focal_mm, focal_dist, energy)
        worker.result_ready.connect(self._on_projection_result)
        worker.error_occurred.connect(self._on_projection_error)
        worker.finished.connect(worker.deleteLater)
        self._projection_worker = worker
        worker.start()

    def _on_projection_result(self, result) -> None:
        """Handle projection result from worker thread."""
        self._projection_panel.update_result(result)
        self.statusBar().showMessage(
            t("status.projection_done", "Projection complete — Contrast: {contrast}").format(
                contrast=f"{result.profile.contrast:.4f}"
            )
        )

    def _on_projection_error(self, error: str) -> None:
        """Handle projection error from worker thread."""
        self.statusBar().showMessage(
            t("status.projection_error", "Projection error: {error}").format(error=error)
        )

    # ------------------------------------------------------------------
    # Simulation (Phase 4)
    # ------------------------------------------------------------------

    def _run_simulation(self) -> None:
        """Launch ray-tracing simulation in background thread."""
        from app.ui.dialogs.simulation_config_dialog import SimulationConfigDialog

        dlg = SimulationConfigDialog(
            current=getattr(self, "_last_sim_config", None),
            parent=self,
        )
        if not dlg.exec():
            return

        config = dlg.get_config()
        self._last_sim_config = config

        geo = self._controller.geometry
        energy = self._toolbar.get_energy_keV()

        self.statusBar().showMessage(t("status.simulation_starting", "Starting simulation..."))
        self._toolbar._btn_simulate.setEnabled(False)

        worker = SimulationWorker(self._beam_sim, self)
        worker.setup(
            geometry=geo,
            energy_keV=energy,
            num_rays=config.num_rays,
            include_buildup=config.include_buildup,
            include_air=config.include_air,
            include_inverse_sq=config.include_inverse_sq,
        )
        worker.progress.connect(self._on_simulation_progress)
        worker.result_ready.connect(self._on_simulation_result)
        worker.error_occurred.connect(self._on_simulation_error)
        worker.finished.connect(self._on_simulation_finished)
        worker.finished.connect(worker.deleteLater)
        self._simulation_worker = worker
        worker.start()

    def _on_simulation_progress(self, pct: int) -> None:
        """Update status bar with simulation progress."""
        self.statusBar().showMessage(
            t("status.simulation_progress", "Simulation: {pct}%...").format(pct=pct)
        )

    def _on_simulation_result(self, result) -> None:
        """Handle simulation result from worker thread."""
        # Compute absolute dose rate at detector
        geo = self._controller.geometry
        sdd_mm = geo.detector.distance_from_source

        # For spectral method, build TubeConfig with current filtration
        spectrum_gen = None
        tube_config = None
        if (geo.source.tube_output_method == "spectral"
                and self._toolbar.energy_mode == "kVp"):
            from app.core.spectrum_models import TubeConfig
            spectrum_gen = self._xray_spectrum
            tube_config = TubeConfig(
                target_id=self._toolbar.get_target_id(),
                kVp=float(self._toolbar.get_slider_raw()),
                window_type=self._toolbar.get_window_type(),
                window_thickness_mm=self._toolbar.get_window_thickness_mm(),
                added_filtration=self._toolbar.get_added_filtration(),
            )

        result.unattenuated_dose_rate_Gy_h = (
            self._dose_calculator.calculate_unattenuated_dose(
                geo.source, sdd_mm,
                spectrum_gen=spectrum_gen,
                tube_config=tube_config,
            )
        )

        # Update score card
        self._results_panel.update_result(result)

        # Update beam profile chart
        self._replot_beam_profile(result)

        # Switch to beam profile tab
        self._chart_tabs.setCurrentIndex(1)

        # Store result reference and persist to DB
        self._last_simulation_result = result
        if self._current_design_id:
            config = SimulationConfig(
                geometry_id=self._current_design_id,
                energy_points=[result.energy_keV],
                num_rays=result.num_rays,
                include_buildup=result.include_buildup,
            )
            self._design_repo.save_simulation_result(
                self._current_design_id, config, result,
            )

        # G-7/G-8: Per-stage attenuation table with build-up comparison
        geo = self._controller.geometry
        if geo.stages:
            attn_with = self._physics_engine.calculate_attenuation(
                geo.stages, result.energy_keV, include_buildup=True,
                ctype=geo.type,
            )
            attn_without = self._physics_engine.calculate_attenuation(
                geo.stages, result.energy_keV, include_buildup=False,
                ctype=geo.type,
            )
            self._results_panel.update_layer_breakdown(attn_with, attn_without)

        self.statusBar().showMessage(
            t("status.simulation_done", "Simulation complete — E={energy}keV | N={rays} | t={time}s").format(
                energy=f"{result.energy_keV:.0f}",
                rays=result.num_rays,
                time=f"{result.elapsed_seconds:.2f}",
            )
        )

        # Phase 7: Auto-trigger scatter if toggle is checked
        if self._toolbar.scatter_button.isChecked():
            self._run_scatter_simulation(result)

        # Phase 8: Auto-trigger isodose if toggle is checked
        if self._toolbar.isodose_button.isChecked():
            self._run_isodose(result)

    def _replot_beam_profile(self, result) -> None:
        """Plot beam profile with current dose display unit."""
        self._ensure_beam_canvas()
        ax = self._beam_ax
        ax.clear()
        self._setup_beam_axes()
        # Reset measurement state (artists cleared by ax.clear())
        self._beam_measure_point = None
        self._beam_measure_artists.clear()
        self._beam_coord_label.setText("")

        profile = result.beam_profile
        pos = profile.positions_mm
        raw = profile.intensities  # 0-1 transmission

        # Transform Y data based on dose unit selection
        unit = self._combo_dose_unit.currentData()
        unatt = result.unattenuated_dose_rate_Gy_h

        match unit:
            case DoseDisplayUnit.GY_PER_HOUR if unatt > 0:
                y_data = raw * unatt
                y_label = t("charts.dose_rate_gy", "Dose Rate (Gy/h)")
                y_max = None
                fwhm_ref = float(np.max(y_data)) / 2.0 if len(y_data) > 0 else 0.5
            case DoseDisplayUnit.MICROSV_PER_HOUR if unatt > 0:
                y_data = raw * Gy_h_to_µSv_h(unatt)
                y_label = t("charts.dose_rate_usv", "Dose Rate (\u00b5Sv/h)")
                y_max = None
                fwhm_ref = float(np.max(y_data)) / 2.0 if len(y_data) > 0 else 0.5
            case DoseDisplayUnit.DB:
                with np.errstate(divide="ignore", invalid="ignore"):
                    y_data = np.where(
                        raw > 1e-30,
                        10.0 * np.log10(np.maximum(raw, 1e-30)),
                        -300.0,
                    )
                y_label = t("charts.attenuation_db", "Attenuation (dB)")
                y_max = 5.0
                fwhm_ref = -3.0  # -3 dB = half power
            case _:
                y_data = raw * 100.0
                y_label = t("charts.transmission_pct", "Transmission (%)")
                y_max = 110.0
                fwhm_ref = 50.0

        ax.set_ylabel(y_label, color="#94A3B8", fontsize=10)

        show_primary = self._cb_show_primary.isChecked()
        qm = result.quality_metrics

        if show_primary:
            ax.plot(pos, y_data, color="#3B82F6", linewidth=1.5,
                    label=t("charts.beam_profile", "Beam Profile"))

            # Region fills using edge detection (skip for dB)
            if qm.fwhm_mm > 0 and len(pos) > 2 and unit != DoseDisplayUnit.DB:
                y_max_val = float(np.max(y_data))
                if y_max_val > 1e-12:
                    find = BeamSimulation._find_edges

                    half_max = y_max_val / 2.0
                    fwhm_l, fwhm_r = find(pos, y_data, half_max)
                    l20, _ = find(pos, y_data, 0.2 * y_max_val)
                    l80, _ = find(pos, y_data, 0.8 * y_max_val)
                    _, r80 = find(pos, y_data, 0.8 * y_max_val)
                    _, r20 = find(pos, y_data, 0.2 * y_max_val)

                    mask_useful = (pos >= fwhm_l) & (pos <= fwhm_r)
                    ax.fill_between(
                        pos[mask_useful], 0, y_data[mask_useful],
                        alpha=0.12, color="#3B82F6",
                        label=f"{t('charts.useful_beam', 'Useful beam')} (FWHM={qm.fwhm_mm:.1f}mm)",
                    )

                    mask_pen_l = (pos >= l20) & (pos <= l80)
                    if np.any(mask_pen_l):
                        ax.fill_between(
                            pos[mask_pen_l], 0, y_data[mask_pen_l],
                            alpha=0.15, color="#F59E0B",
                        )
                    mask_pen_r = (pos >= r80) & (pos <= r20)
                    if np.any(mask_pen_r):
                        ax.fill_between(
                            pos[mask_pen_r], 0, y_data[mask_pen_r],
                            alpha=0.15, color="#F59E0B",
                            label=f"{t('charts.penumbra', 'Penumbra')} ({qm.penumbra_max_mm:.1f}mm)",
                        )

                    mask_shield_l = pos < l20
                    mask_shield_r = pos > r20
                    if np.any(mask_shield_l):
                        ax.fill_between(
                            pos[mask_shield_l], 0, y_data[mask_shield_l],
                            alpha=0.08, color="#EF4444",
                        )
                    if np.any(mask_shield_r):
                        ax.fill_between(
                            pos[mask_shield_r], 0, y_data[mask_shield_r],
                            alpha=0.08, color="#EF4444",
                            label=f"{t('charts.shielding_leakage', 'Shielding leakage')} ({qm.leakage_avg_pct:.2f}%)",
                        )

                    ax.axhline(y=fwhm_ref, color="#F59E0B", linewidth=0.5,
                               linestyle="--", alpha=0.5)

            if unit == DoseDisplayUnit.DB and qm.fwhm_mm > 0:
                ax.axhline(y=-3.0, color="#F59E0B", linewidth=0.7,
                           linestyle="--", alpha=0.6, label="-3 dB (FWHM)")
                ax.plot([], [], " ",
                        label=f"FWHM={qm.fwhm_mm:.1f}mm  |  "
                              f"{t('charts.shielding_leakage', 'Leakage')}={qm.leakage_avg_pct:.2f}%")

        if ax.get_legend_handles_labels()[1]:
            ax.legend(fontsize=9, facecolor="#1E293B", edgecolor="#475569",
                      labelcolor="#F8FAFC")
        if unit == DoseDisplayUnit.DB:
            # dB: show 0 dB at top, auto-scale bottom to min data
            y_min_db = float(np.min(y_data[y_data > -300])) if np.any(y_data > -300) else -60.0
            ax.set_ylim(max(y_min_db * 1.1, -80.0), y_max)
        elif y_max is not None:
            ax.set_ylim(-y_max * 0.05, y_max)

        # Store data for cursor dot interpolation
        self._beam_plot_pos = pos
        self._beam_plot_ydata = y_data
        # Create invisible cursor dot (will be shown on hover)
        (self._beam_cursor_dot,) = ax.plot(
            [], [], "o", color="#FBBF24", markersize=7,
            markeredgecolor="#FFFFFF", markeredgewidth=1.2, zorder=10,
        )

        self._beam_figure.tight_layout()
        self._beam_canvas.draw()

    def _on_dose_unit_changed(self, idx: int) -> None:
        """Replot beam profile with new dose display unit."""
        self._full_replot_beam()

    def _on_beam_visibility_changed(self, _checked: bool) -> None:
        """Replot beam profile when curve visibility checkboxes change."""
        self._full_replot_beam()

    def _full_replot_beam(self) -> None:
        """Replot primary beam + scatter overlay respecting visibility."""
        if self._last_simulation_result is not None and self._beam_ax is not None:
            self._beam_measure_point = None
            self._beam_measure_artists.clear()
            self._replot_beam_profile(self._last_simulation_result)
            # Re-overlay scatter if present
            scatter = getattr(self, "_last_scatter_result", None)
            if scatter is not None:
                self._overlay_scatter_on_beam_profile(scatter)

    # ------------------------------------------------------------------
    # Beam profile cursor readout + CTRL measurement
    # ------------------------------------------------------------------

    def _beam_y_unit_label(self) -> str:
        """Current Y-axis unit short label for coordinate display."""
        unit = self._combo_dose_unit.currentData()
        match unit:
            case DoseDisplayUnit.GY_PER_HOUR:
                return "Gy/h"
            case DoseDisplayUnit.MICROSV_PER_HOUR:
                return "\u00b5Sv/h"
            case DoseDisplayUnit.DB:
                return "dB"
            case _:
                return "%"

    def _on_beam_mouse_move(self, event) -> None:
        """Show cursor X/Y coordinates + dot on beam profile curve."""
        if event.inaxes != self._beam_ax:
            self._beam_coord_label.setText("")
            # Hide cursor dot when outside axes
            if self._beam_cursor_dot is not None:
                self._beam_cursor_dot.set_data([], [])
                self._beam_canvas.draw_idle()
            return

        x = event.xdata
        unit_str = self._beam_y_unit_label()

        # Interpolate Y on the curve at mouse X
        if (
            self._beam_plot_pos is not None
            and self._beam_plot_ydata is not None
            and len(self._beam_plot_pos) > 1
        ):
            y_on_curve = float(np.interp(x, self._beam_plot_pos, self._beam_plot_ydata))
            # Update cursor dot position
            if self._beam_cursor_dot is not None:
                self._beam_cursor_dot.set_data([x], [y_on_curve])
                self._beam_canvas.draw_idle()
        else:
            y_on_curve = event.ydata

        text = f"X: {x:.2f} mm   Y: {y_on_curve:.4g} {unit_str}"

        # If measurement point exists, also show delta
        if self._beam_measure_point is not None:
            x0, y0 = self._beam_measure_point
            dx = x - x0
            dy = y_on_curve - y0
            text += f"   |   \u0394X: {dx:.2f} mm   \u0394Y: {dy:.4g} {unit_str}"

        self._beam_coord_label.setText(text)

    def _on_beam_mouse_click(self, event) -> None:
        """CTRL+click to measure delta between two points."""
        if event.inaxes != self._beam_ax:
            return

        # Check for CTRL modifier
        from PyQt6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()
        is_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        if not is_ctrl:
            return

        x = event.xdata
        # Snap Y to curve value
        if (
            self._beam_plot_pos is not None
            and self._beam_plot_ydata is not None
            and len(self._beam_plot_pos) > 1
        ):
            y = float(np.interp(x, self._beam_plot_pos, self._beam_plot_ydata))
        else:
            y = event.ydata

        # Remove old measurement artists
        for artist in self._beam_measure_artists:
            try:
                artist.remove()
            except ValueError:
                pass
        self._beam_measure_artists.clear()

        if self._beam_measure_point is None:
            # First CTRL+click — place anchor point
            self._beam_measure_point = (x, y)
            marker = self._beam_ax.plot(
                x, y, "o", color="#22D3EE", markersize=7, zorder=10,
            )[0]
            vline = self._beam_ax.axvline(
                x=x, color="#22D3EE", linewidth=0.7, linestyle=":", alpha=0.6,
            )
            hline = self._beam_ax.axhline(
                y=y, color="#22D3EE", linewidth=0.7, linestyle=":", alpha=0.6,
            )
            self._beam_measure_artists.extend([marker, vline, hline])
            self._beam_canvas.draw_idle()
        else:
            # Second CTRL+click — show delta and reset
            x0, y0 = self._beam_measure_point
            dx = x - x0
            dy = y - y0
            unit_str = self._beam_y_unit_label()

            # Draw line between two points
            line = self._beam_ax.plot(
                [x0, x], [y0, y], "-", color="#22D3EE", linewidth=1.2,
                zorder=10,
            )[0]
            marker2 = self._beam_ax.plot(
                x, y, "o", color="#22D3EE", markersize=7, zorder=10,
            )[0]

            # Delta annotation at midpoint
            mid_x = (x0 + x) / 2.0
            mid_y = (y0 + y) / 2.0
            ann = self._beam_ax.annotate(
                f"\u0394X={dx:.2f} mm\n\u0394Y={dy:.4g} {unit_str}",
                xy=(mid_x, mid_y),
                fontsize=9, color="#22D3EE",
                bbox=dict(facecolor="#0F172A", edgecolor="#22D3EE",
                          alpha=0.85, boxstyle="round,pad=0.3"),
                ha="center", va="bottom",
                zorder=11,
            )
            self._beam_measure_artists.extend([line, marker2, ann])
            self._beam_canvas.draw_idle()

            # Reset anchor for next measurement pair
            self._beam_measure_point = None

    def _on_simulation_error(self, error: str) -> None:
        """Handle simulation error from worker thread."""
        self.statusBar().showMessage(
            t("status.simulation_error", "Simulation error: {error}").format(error=error)
        )

    def _on_simulation_finished(self) -> None:
        """Re-enable simulate button after worker finishes."""
        self._toolbar._btn_simulate.setEnabled(True)

    # ------------------------------------------------------------------
    # Phase 7: Scatter Simulation
    # ------------------------------------------------------------------

    def _run_scatter_simulation(self, primary_result) -> None:
        """Launch scatter simulation after primary completes."""
        geometry = self._controller.geometry
        energy = self._toolbar.get_energy_keV()
        config = ComptonConfig(enabled=True, max_scatter_order=1)

        self.statusBar().showMessage(t("status.scatter_starting", "Starting scatter simulation..."))
        self._toolbar._btn_simulate.setEnabled(False)

        worker = ScatterWorker(self._scatter_tracer, self)
        worker.setup(
            geometry=geometry,
            energy_keV=energy,
            num_rays=primary_result.num_rays,
            config=config,
            primary_result=primary_result,
        )
        worker.progress.connect(self._on_scatter_progress)
        worker.result_ready.connect(self._on_scatter_result)
        worker.error_occurred.connect(self._on_scatter_error)
        worker.finished.connect(self._on_scatter_finished)
        worker.finished.connect(worker.deleteLater)
        self._scatter_worker = worker
        worker.start()

    def _on_scatter_progress(self, pct: int) -> None:
        self.statusBar().showMessage(
            t("status.scatter_progress", "Scatter: {pct}%...").format(pct=pct)
        )

    def _on_scatter_result(self, result) -> None:
        """Handle scatter simulation result."""
        self._last_scatter_result = result

        # Update scatter overlay on canvas
        det_y_mm = self._controller.geometry.detector.position.y
        self._scene.set_scatter_data(result.interactions, det_y_mm)

        # Update results panel with scatter metrics
        self._results_panel.update_scatter_result(result)

        # G-4: Update SPR chart tab
        self._spr_chart.update_scatter_result(result)

        # Overlay scatter on beam profile chart
        self._overlay_scatter_on_beam_profile(result)

        self.statusBar().showMessage(
            t("status.scatter_done",
              "Scatter complete — {interactions} interactions, {detector} to detector, "
              "SPR={spr}, t={time}s").format(
                interactions=result.num_interactions,
                detector=result.num_reaching_detector,
                spr=f"{result.total_scatter_fraction:.4f}",
                time=f"{result.elapsed_seconds:.2f}",
            )
        )

    def _overlay_scatter_on_beam_profile(self, scatter_result) -> None:
        """Add scatter / combined overlay to beam profile chart."""
        if self._beam_ax is None or self._last_simulation_result is None:
            return

        show_scatter = self._cb_show_scatter.isChecked()
        show_combined = self._cb_show_combined.isChecked()
        if not show_scatter and not show_combined:
            # Nothing to overlay — just redraw
            self._beam_figure.tight_layout()
            self._beam_canvas.draw()
            return

        primary = self._last_simulation_result
        pos = primary.beam_profile.positions_mm
        ints = primary.beam_profile.intensities

        spr_pos = scatter_result.spr_positions_mm
        spr_vals = scatter_result.spr_profile

        if len(spr_pos) == 0 or len(spr_vals) == 0:
            return

        # Apply dose unit scaling
        unit = self._combo_dose_unit.currentData()
        unatt = primary.unattenuated_dose_rate_Gy_h
        is_db = unit == DoseDisplayUnit.DB
        match unit:
            case DoseDisplayUnit.GY_PER_HOUR if unatt > 0:
                scale = unatt
            case DoseDisplayUnit.MICROSV_PER_HOUR if unatt > 0:
                scale = Gy_h_to_µSv_h(unatt)
            case DoseDisplayUnit.DB:
                scale = 1.0  # dB uses raw transmission
            case _:
                scale = 100.0  # relative %

        scaled_ints = ints * scale

        # Interpolate SPR onto primary beam positions
        spr_interp = np.interp(pos, spr_pos, spr_vals, left=0.0, right=0.0)

        # Scatter intensity: S(x) = SPR(x) * P(x)
        scatter_scaled = spr_interp * scaled_ints

        # Combined signal: P(x) + S(x)
        combined_raw = scaled_ints + scatter_scaled

        ax = self._beam_ax
        show_primary = self._cb_show_primary.isChecked()
        spr_label = f"Scatter (SPR={scatter_result.total_scatter_fraction:.4f})"

        if is_db:
            with np.errstate(divide="ignore", invalid="ignore"):
                primary_db = np.where(
                    ints > 1e-30, 10.0 * np.log10(np.maximum(ints, 1e-30)), -300.0,
                )
                scatter_only_t = spr_interp * ints
                scatter_only_db = np.where(
                    scatter_only_t > 1e-30, 10.0 * np.log10(np.maximum(scatter_only_t, 1e-30)), -300.0,
                )
                combined_t = ints + spr_interp * ints
                combined_db = np.where(
                    combined_t > 1e-30, 10.0 * np.log10(np.maximum(combined_t, 1e-30)), -300.0,
                )

            if show_scatter and show_primary:
                ax.fill_between(
                    pos, primary_db, combined_db,
                    alpha=0.25, color="#EF4444", label=spr_label,
                )
            if show_scatter:
                ax.plot(
                    pos, scatter_only_db, color="#EF4444", linewidth=1.0,
                    linestyle=":", alpha=0.7,
                    label=t("charts.scatter_only", "Scatter Only") if not show_primary else None,
                )
            if show_combined:
                ax.plot(
                    pos, combined_db, color="#F8FAFC", linewidth=1.0,
                    linestyle="--", alpha=0.8,
                    label=t("charts.combined_ps", "Combined (P+S)"),
                )
        else:
            if show_scatter and show_primary:
                ax.fill_between(
                    pos, scaled_ints, combined_raw,
                    alpha=0.25, color="#EF4444", label=spr_label,
                )
            if show_scatter:
                ax.plot(
                    pos, scatter_scaled, color="#EF4444", linewidth=1.0,
                    linestyle=":", alpha=0.7,
                    label=t("charts.scatter_only", "Scatter Only") if not show_primary else None,
                )
            if show_combined:
                ax.plot(
                    pos, combined_raw, color="#F8FAFC", linewidth=1.0,
                    linestyle="--", alpha=0.8,
                    label=t("charts.combined_ps", "Combined (P+S)"),
                )

        if ax.get_legend_handles_labels()[1]:
            ax.legend(
                fontsize=9, facecolor="#1E293B", edgecolor="#475569",
                labelcolor="#F8FAFC",
            )
        self._beam_figure.tight_layout()
        self._beam_canvas.draw()

    def _on_scatter_error(self, error: str) -> None:
        self.statusBar().showMessage(
            t("status.scatter_error", "Scatter error: {error}").format(error=error)
        )

    def _on_scatter_finished(self) -> None:
        self._toolbar._btn_simulate.setEnabled(True)

    # ------------------------------------------------------------------
    # Phase 8: Isodose Map
    # ------------------------------------------------------------------

    def _run_isodose(self, primary_result) -> None:
        """Launch isodose computation after primary simulation completes."""
        geometry = self._controller.geometry
        energy = self._toolbar.get_energy_keV()
        cfg = getattr(self, "_last_sim_config", None)

        self.statusBar().showMessage(
            t("status.isodose_starting", "Starting isodose computation...")
        )

        worker = IsodoseWorker(self._isodose_engine, self)
        worker.setup(
            geometry=geometry,
            energy_keV=energy,
            nx=cfg.isodose_nx if cfg else 120,
            ny=cfg.isodose_ny if cfg else 80,
            include_buildup=cfg.include_buildup if cfg else True,
            include_air=cfg.isodose_include_air if cfg else self._toolbar.isodose_include_air,
            include_inverse_sq=cfg.isodose_include_inverse_sq if cfg else self._toolbar.isodose_include_inverse_sq,
        )
        worker.progress.connect(self._on_isodose_progress)
        worker.result_ready.connect(self._on_isodose_result)
        worker.error_occurred.connect(self._on_isodose_error)
        worker.finished.connect(self._on_isodose_finished)
        worker.finished.connect(worker.deleteLater)
        self._isodose_worker = worker
        worker.start()

    def _on_isodose_progress(self, pct: int) -> None:
        self.statusBar().showMessage(
            t("status.isodose_progress", "Isodose: {pct}%...").format(pct=pct)
        )

    def _on_isodose_result(self, result) -> None:
        """Handle isodose computation result."""
        # Update canvas overlay
        self._scene.set_isodose_data(result)

        # Update chart tab
        self._isodose_chart.update_result(result)

        # Switch to isodose chart tab
        self._chart_tabs.setCurrentWidget(self._isodose_chart)

        self.statusBar().showMessage(
            t("status.isodose_done",
              "Isodose complete — {nx}x{ny} grid, E={energy}keV, t={time}s").format(
                nx=result.nx,
                ny=result.ny,
                energy=f"{result.energy_keV:.0f}",
                time=f"{result.elapsed_seconds:.2f}",
            )
        )

    def _on_isodose_error(self, error: str) -> None:
        self.statusBar().showMessage(
            t("status.isodose_error", "Isodose error: {error}").format(error=error)
        )

    def _on_isodose_finished(self) -> None:
        pass

    # ------------------------------------------------------------------
    # G-3: Multi-energy comparison
    # ------------------------------------------------------------------

    def _run_compare(self) -> None:
        """Open compare dialog and run multi-energy overlay."""
        dlg = CompareDialog(self)
        if not dlg.exec():
            return

        energies = dlg.get_energies_keV()
        num_rays = dlg.get_num_rays()
        if len(energies) < 2:
            self.statusBar().showMessage(t("status.compare_min_energies", "Select at least 2 energies."))
            return

        geo = self._controller.geometry
        self.statusBar().showMessage(
            t("status.compare_calculating", "Comparing: calculating {count} energies...").format(
                count=len(energies)
            )
        )
        self._toolbar._btn_simulate.setEnabled(False)

        # Run in worker thread to avoid blocking UI
        from app.workers.compare_worker import CompareWorker
        worker = CompareWorker(self._beam_sim, self)
        worker.setup(geo, energies, num_rays)
        worker.progress.connect(
            lambda p: self.statusBar().showMessage(
                t("status.compare_progress", "Comparison: {pct}%...").format(pct=p)
            )
        )
        worker.result_ready.connect(self._on_compare_result)
        worker.error_occurred.connect(
            lambda e: self.statusBar().showMessage(
                t("status.compare_error", "Comparison error: {error}").format(error=e)
            )
        )
        worker.finished.connect(lambda: self._toolbar._btn_simulate.setEnabled(True))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_compare_result(self, results: dict) -> None:
        """Plot multi-energy overlay on beam profile chart."""
        self._ensure_beam_canvas()
        ax = self._beam_ax
        ax.clear()
        self._setup_beam_axes()
        ax.set_title(t("charts.energy_comparison", "Energy Comparison"), color="#F8FAFC", fontsize=12)

        colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]

        for idx, (energy_keV, result) in enumerate(sorted(results.items())):
            profile = result.beam_profile
            color = colors[idx % len(colors)]
            ax.plot(
                profile.positions_mm,
                profile.intensities,
                color=color,
                linewidth=1.5,
                label=f"{energy_keV:.0f} keV",
            )

        ax.legend(
            fontsize=9, facecolor="#1E293B", edgecolor="#475569",
            labelcolor="#F8FAFC",
        )
        ax.set_ylim(-0.05, 1.1)
        self._beam_figure.tight_layout()
        self._beam_canvas.draw()

        self._chart_tabs.setCurrentIndex(1)
        self.statusBar().showMessage(
            t("status.compare_done_count", "Comparison completed — {count} energies").format(
                count=len(results)
            )
        )

    # ------------------------------------------------------------------
    # G-6: LINAC mode warning
    # ------------------------------------------------------------------

    def _on_energy_mode_changed(self, mode: str) -> None:
        """Show/hide LINAC warning and update dose panel based on energy mode."""
        self._linac_warning.setVisible(mode == "MeV")
        self._properties_panel.set_energy_mode(mode)

    def _on_tube_config_changed(self) -> None:
        """Update spectrum chart and toolbar effective energy (kVp mode only)."""
        if self._toolbar.energy_mode != "kVp":
            return
        from app.core.spectrum_models import TubeConfig
        config = TubeConfig(
            target_id=self._toolbar.get_target_id(),
            kVp=float(self._toolbar.get_slider_raw()),
            window_type=self._toolbar.get_window_type(),
            window_thickness_mm=self._toolbar.get_window_thickness_mm(),
            added_filtration=self._toolbar.get_added_filtration(),
        )
        self._spectrum_chart.update_spectrum(config)
        eff = self._xray_spectrum.effective_energy(config)
        self._toolbar.set_effective_energy(eff)

    # ------------------------------------------------------------------
    # G-10: Customizable quality thresholds
    # ------------------------------------------------------------------

    def _on_edit_thresholds(self) -> None:
        """Open threshold configuration dialog."""
        dlg = ThresholdDialog(
            current=self._beam_sim._custom_thresholds, parent=self,
        )
        if dlg.exec():
            thresholds = dlg.get_thresholds()
            self._beam_sim.set_custom_thresholds(thresholds)
            self.statusBar().showMessage(t("status.thresholds_updated", "Thresholds updated"))

    # ------------------------------------------------------------------
    # Phase 8: Physics Validation
    # ------------------------------------------------------------------

    def _on_run_validation(self) -> None:
        """Open validation dialog and run physics engine tests."""
        from app.ui.dialogs.validation_dialog import ValidationDialog
        dlg = ValidationDialog(self)
        dlg.exec()

    def _on_about(self) -> None:
        """Show about dialog."""
        from app.ui.dialogs.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Phase 6: Design Management
    # ------------------------------------------------------------------

    def _update_title(self) -> None:
        """Update window title with design name and dirty indicator."""
        name = self._controller.geometry.name
        dirty = " *" if self._is_dirty else ""
        self.setWindowTitle(f"{name}{dirty} — {APP_NAME} v{APP_VERSION}")

    def _mark_dirty(self) -> None:
        """Mark current design as having unsaved changes."""
        if not self._is_dirty:
            self._is_dirty = True
            self._update_title()

    # ------------------------------------------------------------------
    # Edit menu handlers
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        self._controller.undo()

    def _on_redo(self) -> None:
        self._controller.redo()

    def _on_cut(self) -> None:
        target = self._resolve_edit_target()
        if target:
            self._controller.cut_selected(target_type=target[0])

    def _on_copy(self) -> None:
        target = self._resolve_edit_target()
        if target:
            self._controller.copy_selected(target_type=target[0])
            self._update_edit_menu_state()

    def _on_paste(self) -> None:
        self._controller.paste()

    def _on_delete(self) -> None:
        target = self._resolve_edit_target()
        if target:
            self._controller.delete_selected(target_type=target[0])

    def _resolve_edit_target(self) -> tuple[str, int] | None:
        """Determine edit target: canvas selection first, then panel fallback."""
        # Canvas selection
        sel = self._scene.get_selected_editable()
        if sel:
            return sel
        # Fallback: controller's active selections
        if self._controller.active_stage_index >= 0:
            return ("stage", self._controller.active_stage_index)
        return None

    def _update_edit_menu_state(self) -> None:
        """Sync Edit menu enabled/disabled state with controller."""
        self._toolbar.set_undo_enabled(self._controller.can_undo)
        self._toolbar.set_redo_enabled(self._controller.can_redo)
        self._toolbar.set_paste_enabled(self._controller.has_clipboard)
        # Cut/Copy/Delete available when an editable item is selected
        has_target = self._resolve_edit_target() is not None
        self._toolbar.set_edit_actions_enabled(has_target)

    # ------------------------------------------------------------------
    # File menu handlers
    # ------------------------------------------------------------------

    def _on_new(self) -> None:
        """Create a new blank design."""
        self._controller.create_blank_geometry()
        self._current_design_id = None
        self._is_dirty = False
        self._last_simulation_result = None
        self._update_title()

    def _on_open(self) -> None:
        """Open design from database."""
        dlg = DesignManagerDialog(self._design_repo, self)
        if dlg.exec():
            design_id = dlg.selected_design_id
            if design_id:
                geometry = self._design_repo.load_design(design_id)
                self._controller.set_geometry(geometry)
                self._current_design_id = design_id
                self._is_dirty = False
                self._last_simulation_result = None
                self._update_title()
                self._update_recent_menu()
                self.statusBar().showMessage(
                    t("status.design_loaded", "Design loaded: {name}").format(name=geometry.name)
                )

    def _on_import_external(self) -> None:
        """Import design from external application JSON format."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from app.export.external_import import ExternalFormatImporter

        path, _ = QFileDialog.getOpenFileName(
            self,
            t("dialogs.import_external_title", "Import External Format"),
            "",
            t("dialogs.import_external_filter", "JSON Files (*.json)"),
        )
        if not path:
            return

        importer = ExternalFormatImporter()
        try:
            geometry = importer.import_file(path)
            self._controller.set_geometry(geometry)
            self._current_design_id = None
            self._is_dirty = True
            self._last_simulation_result = None
            self._update_title()
            self._view.fit_to_content()
            self.statusBar().showMessage(
                t("status.import_done", "External format loaded: {name} ({stages} stages)").format(
                    name=geometry.name, stages=geometry.stage_count
                )
            )
        except Exception as e:
            QMessageBox.warning(
                self, t("status.import_error_title", "Import Error"), str(e)
            )

    def _on_save(self) -> None:
        """Save current design (or Save As if first time)."""
        if self._current_design_id is None:
            self._on_save_as()
            return

        geometry = self._controller.geometry
        thumbnail = self._image_exporter.generate_thumbnail(self._scene)
        self._design_repo.update_design(self._current_design_id, geometry)
        self._design_repo.update_thumbnail(self._current_design_id, thumbnail)
        self._is_dirty = False
        self._update_title()
        self.statusBar().showMessage(
            t("status.saved", "Saved: {name}").format(name=geometry.name)
        )

    def _on_save_as(self) -> None:
        """Save current design with new name."""
        dlg = SaveDesignDialog(self)
        dlg.set_name(self._controller.geometry.name)
        if dlg.exec():
            name, desc, tags = dlg.get_values()
            geometry = self._controller.geometry
            geometry.name = name
            thumbnail = self._image_exporter.generate_thumbnail(self._scene)
            design_id = self._design_repo.save_design(
                geometry, name, desc, tags,
            )
            self._design_repo.update_thumbnail(design_id, thumbnail)
            self._current_design_id = design_id
            self._is_dirty = False
            self._update_title()
            self._update_recent_menu()
            self.statusBar().showMessage(
                t("status.saved", "Saved: {name}").format(name=name)
            )

    def _on_export(self) -> None:
        """Show export dialog and execute export."""
        has_sim = self._last_simulation_result is not None
        dlg = ExportDialog(has_simulation=has_sim, parent=self)
        if not dlg.exec():
            return

        fmt = dlg.get_format()
        path = dlg.get_output_path()
        geometry = self._controller.geometry

        try:
            if fmt == "json":
                JsonExporter().export_geometry(geometry, path)
            elif fmt == "csv" and self._last_simulation_result:
                CsvExporter().export_beam_profile(self._last_simulation_result, path)
            elif fmt == "png":
                self._image_exporter.export_canvas_png(self._scene, path)
            elif fmt == "svg":
                self._image_exporter.export_canvas_svg(self._scene, path)
            elif fmt == "cdt" and self._current_design_id:
                thumbnail = self._image_exporter.generate_thumbnail(self._scene)
                CdtExporter().export_project(
                    self._current_design_id, self._design_repo, path, thumbnail,
                )
            elif fmt == "pdf":
                from app.workers.export_worker import ExportWorker
                sections = dlg.get_pdf_sections()
                canvas_img = self._image_exporter.generate_thumbnail(
                    self._scene, width=800, height=450,
                )
                worker = ExportWorker(self)
                worker.setup_pdf(
                    geometry, self._last_simulation_result, path,
                    sections, {}, canvas_img,
                )
                worker.result_ready.connect(
                    lambda p: self.statusBar().showMessage(
                        t("status.pdf_created", "PDF created: {path}").format(path=p)
                    )
                )
                worker.error_occurred.connect(
                    lambda e: self.statusBar().showMessage(
                        t("status.pdf_error", "PDF error: {error}").format(error=e)
                    )
                )
                worker.finished.connect(worker.deleteLater)
                worker.start()
                self.statusBar().showMessage(t("status.pdf_creating", "Creating PDF..."))
                return

            self.statusBar().showMessage(
                t("status.exported", "Exported: {path}").format(path=path)
            )
        except Exception as e:
            self.statusBar().showMessage(
                t("status.export_error", "Export error: {error}").format(error=e)
            )

    def _on_version_history(self) -> None:
        """Show version history dialog."""
        if self._current_design_id is None:
            self.statusBar().showMessage(t("status.save_first", "Save the design first"))
            return

        dlg = VersionHistoryDialog(
            self._design_repo, self._current_design_id, self,
        )
        if dlg.exec() and dlg.restored_version is not None:
            geometry = self._design_repo.load_design(self._current_design_id)
            self._controller.set_geometry(geometry)
            self._is_dirty = False
            self._update_title()
            self.statusBar().showMessage(
                t("status.version_restored", "Version {version} restored").format(
                    version=dlg.restored_version
                )
            )

    def _update_recent_menu(self) -> None:
        """Refresh the recent designs submenu."""
        menu = self._toolbar.recent_menu
        menu.clear()
        for ds in self._design_repo.get_recent_designs(limit=8):
            action = menu.addAction(ds.name)
            did = ds.id
            action.triggered.connect(
                lambda checked, d=did: self._open_recent(d)
            )

    def _open_recent(self, design_id: str) -> None:
        """Open a design from the recent menu."""
        try:
            geometry = self._design_repo.load_design(design_id)
            self._controller.set_geometry(geometry)
            self._current_design_id = design_id
            self._is_dirty = False
            self._last_simulation_result = None
            self._update_title()
            self.statusBar().showMessage(
                t("status.design_loaded", "Design loaded: {name}").format(name=geometry.name)
            )
        except KeyError:
            self.statusBar().showMessage(t("status.design_not_found", "Design not found"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)
