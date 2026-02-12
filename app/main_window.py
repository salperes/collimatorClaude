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

import numpy as np

from app.constants import (
    APP_NAME, APP_VERSION, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT,
    DEFAULT_NUM_RAYS,
)
from app.core.beam_simulation import BeamSimulation
from app.core.build_up_factors import BuildUpFactors
from app.core.compton_engine import ComptonEngine
from app.core.material_database import MaterialService
from app.core.physics_engine import PhysicsEngine
from app.core.projection_engine import ProjectionEngine
from app.core.ray_tracer import RayTracer
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
from app.models.simulation import SimulationConfig
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
from app.workers.scatter_worker import ScatterWorker
from app.models.simulation import ComptonConfig


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
            "Malzemeler",
            Qt.DockWidgetArea.LeftDockWidgetArea,
            self._material_panel,
        )
        self._left_dock.setMinimumWidth(200)

        # Right panel — Layers + Properties + Results
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet("QScrollArea { border: none; }")

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Layer section
        self._layer_panel = LayerPanel(self._controller)
        layer_section = CollapsibleSection("Katmanlar")
        layer_section.set_content_widget(self._layer_panel)
        right_layout.addWidget(layer_section)

        # Properties section
        self._properties_panel = PropertiesPanel(self._controller)
        props_section = CollapsibleSection("Parametreler")
        props_section.set_content_widget(self._properties_panel)
        right_layout.addWidget(props_section)

        # Phantom panel
        self._phantom_panel = PhantomPanel(self._controller)
        phantom_section = CollapsibleSection("Test Nesneleri")
        phantom_section.set_content_widget(self._phantom_panel)
        right_layout.addWidget(phantom_section)

        # Simulation results section
        self._results_panel = ResultsPanel()
        results_section = CollapsibleSection("Simulasyon Sonuclari")
        results_section.set_content_widget(self._results_panel)
        right_layout.addWidget(results_section)

        right_layout.addStretch()
        right_scroll.setWidget(right_widget)

        self._right_dock = self._create_dock(
            "Katmanlar / Parametreler",
            Qt.DockWidgetArea.RightDockWidgetArea,
            right_scroll,
        )
        self._right_dock.setMinimumWidth(320)

        # Bottom panel — Chart tabs
        self._chart_tabs = self._create_chart_tabs()
        self._bottom_dock = self._create_dock(
            "Grafikler",
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._chart_tabs,
        )

        # LINAC warning label (G-6) — hidden by default
        self._linac_warning = QLabel(
            "  LINAC modu: Build-up ve cift uretim etkileri "
            "yuksek enerjide (>1 MeV) basitlestirilmis modelle hesaplanmaktadir.  "
        )
        self._linac_warning.setStyleSheet(
            "background-color: #92400E; color: #FDE68A; "
            "font-size: 9pt; padding: 4px; border-radius: 3px;"
        )
        self._linac_warning.setVisible(False)
        self.statusBar().addPermanentWidget(self._linac_warning)

        # Status bar
        self.statusBar().showMessage("Hazir")

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
            lambda z: self.statusBar().showMessage(f"Zoom: {z:.0%}")
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

        # Phase 8: Validation
        self._toolbar.validation_requested.connect(self._on_run_validation)

        # Spectrum chart: update when tube config changes
        self._toolbar.tube_config_changed.connect(self._on_tube_config_changed)

        # About dialog
        self._toolbar.about_requested.connect(self._on_about)

        # Phase 6: File menu signals
        self._toolbar.new_requested.connect(self._on_new)
        self._toolbar.open_requested.connect(self._on_open)
        self._toolbar.save_requested.connect(self._on_save)
        self._toolbar.save_as_requested.connect(self._on_save_as)
        self._toolbar.export_requested.connect(self._on_export)
        self._toolbar.version_history_requested.connect(self._on_version_history)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self._on_new)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self._on_open)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._on_save)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self._on_save_as)
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(self._on_export)

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
        tabs.addTab(self._projection_panel, "Projeksiyon")

        # Beam profile panel (Phase 4 — populated on simulation)
        self._beam_profile_panel = self._create_beam_profile_panel()
        tabs.addTab(self._beam_profile_panel, "Isin Profili")

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
        tabs.addTab(self._transmission_chart, "Iletim vs Kalinlik")

        self._compton_widget = ComptonWidget(
            self._compton_engine, material_service=self._material_service,
        )
        tabs.addTab(self._compton_widget, "Compton")

        # Phase 7: SPR profile chart
        self._spr_chart = SprChartWidget()
        tabs.addTab(self._spr_chart, "SPR Profili")

        # X-ray tube spectrum chart
        self._spectrum_chart = SpectrumChartWidget(self._material_service)
        tabs.addTab(self._spectrum_chart, "Spektrum")

        return tabs

    def _create_beam_profile_panel(self) -> QWidget:
        """Create the beam profile chart panel (lazy matplotlib)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        self._beam_profile_placeholder = QLabel(
            "Simulasyon baslatmak icin 'Simule Et' butonuna tiklayin."
        )
        self._beam_profile_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._beam_profile_placeholder.setProperty("cssClass", "secondary")
        layout.addWidget(self._beam_profile_placeholder, stretch=1)

        self._beam_canvas = None
        self._beam_figure = None
        self._beam_ax = None
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
        ax.set_xlabel("Detektor Pozisyon (mm)", color="#94A3B8", fontsize=10)
        ax.set_ylabel("Iletim (T)", color="#94A3B8", fontsize=10)
        ax.set_title("Isin Profili", color="#F8FAFC", fontsize=12)
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

    def _restore_state(self):
        settings = QSettings()
        geometry = settings.value("mainwindow/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = settings.value("mainwindow/state")
        if state:
            self.restoreState(state)

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
            f"Projeksiyon tamamlandi — Kontrast: {result.profile.contrast:.4f}"
        )

    def _on_projection_error(self, error: str) -> None:
        """Handle projection error from worker thread."""
        self.statusBar().showMessage(f"Projeksiyon hatasi: {error}")

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

        self.statusBar().showMessage("Simulasyon baslatiliyor...")
        self._toolbar._btn_simulate.setEnabled(False)

        worker = SimulationWorker(self._beam_sim, self)
        worker.setup(
            geometry=geo,
            energy_keV=energy,
            num_rays=config.num_rays,
            include_buildup=config.include_buildup,
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
        self.statusBar().showMessage(f"Simulasyon: %{pct}...")

    def _on_simulation_result(self, result) -> None:
        """Handle simulation result from worker thread."""
        # Update score card
        self._results_panel.update_result(result)

        # Update beam profile chart
        self._ensure_beam_canvas()
        ax = self._beam_ax
        ax.clear()
        self._setup_beam_axes()

        profile = result.beam_profile
        pos = profile.positions_mm
        ints = profile.intensities

        ax.plot(pos, ints, color="#3B82F6", linewidth=1.5,
                label="Isin Profili")

        # Region fills using edge detection
        qm = result.quality_metrics
        if qm.fwhm_mm > 0 and len(pos) > 2:
            i_max = float(np.max(ints))
            if i_max > 1e-12:
                find = BeamSimulation._find_edges

                # Edge positions
                half_max = i_max / 2.0
                fwhm_l, fwhm_r = find(pos, ints, half_max)
                l20, _ = find(pos, ints, 0.2 * i_max)
                l80, _ = find(pos, ints, 0.8 * i_max)
                _, r80 = find(pos, ints, 0.8 * i_max)
                _, r20 = find(pos, ints, 0.2 * i_max)

                # Useful beam: between FWHM edges (blue)
                mask_useful = (pos >= fwhm_l) & (pos <= fwhm_r)
                ax.fill_between(
                    pos[mask_useful], 0, ints[mask_useful],
                    alpha=0.12, color="#3B82F6",
                    label=f"Faydali isin (FWHM={qm.fwhm_mm:.1f}mm)",
                )

                # Left penumbra: 20%-80% region (yellow)
                mask_pen_l = (pos >= l20) & (pos <= l80)
                if np.any(mask_pen_l):
                    ax.fill_between(
                        pos[mask_pen_l], 0, ints[mask_pen_l],
                        alpha=0.15, color="#F59E0B",
                    )
                # Right penumbra: 80%-20% region (yellow)
                mask_pen_r = (pos >= r80) & (pos <= r20)
                if np.any(mask_pen_r):
                    ax.fill_between(
                        pos[mask_pen_r], 0, ints[mask_pen_r],
                        alpha=0.15, color="#F59E0B",
                        label=f"Penumbra ({qm.penumbra_max_mm:.1f}mm)",
                    )

                # Shielded: outside 20% edges (red)
                mask_shield_l = pos < l20
                mask_shield_r = pos > r20
                if np.any(mask_shield_l):
                    ax.fill_between(
                        pos[mask_shield_l], 0, ints[mask_shield_l],
                        alpha=0.08, color="#EF4444",
                    )
                if np.any(mask_shield_r):
                    ax.fill_between(
                        pos[mask_shield_r], 0, ints[mask_shield_r],
                        alpha=0.08, color="#EF4444",
                        label=f"Zirhlama (sizinti {qm.leakage_avg_pct:.2f}%)",
                    )

                # FWHM horizontal line
                ax.axhline(y=0.5, color="#F59E0B", linewidth=0.5,
                           linestyle="--", alpha=0.5)

        ax.legend(fontsize=9, facecolor="#1E293B", edgecolor="#475569",
                  labelcolor="#F8FAFC")
        ax.set_ylim(-0.05, 1.1)
        self._beam_figure.tight_layout()
        self._beam_canvas.draw()

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

        # G-7/G-8: Per-layer attenuation table with build-up comparison
        geo = self._controller.geometry
        all_layers = []
        for stage in geo.stages:
            all_layers.extend(stage.layers)
        if all_layers:
            attn_with = self._physics_engine.calculate_attenuation(
                all_layers, result.energy_keV, include_buildup=True,
            )
            attn_without = self._physics_engine.calculate_attenuation(
                all_layers, result.energy_keV, include_buildup=False,
            )
            self._results_panel.update_layer_breakdown(attn_with, attn_without)

        self.statusBar().showMessage(
            f"Simulasyon tamamlandi — "
            f"E={result.energy_keV:.0f}keV | "
            f"N={result.num_rays} | "
            f"t={result.elapsed_seconds:.2f}s"
        )

        # Phase 7: Auto-trigger scatter if toggle is checked
        if self._toolbar.scatter_button.isChecked():
            self._run_scatter_simulation(result)

    def _on_simulation_error(self, error: str) -> None:
        """Handle simulation error from worker thread."""
        self.statusBar().showMessage(f"Simulasyon hatasi: {error}")

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

        self.statusBar().showMessage("Scatter simulasyonu baslatiliyor...")
        self._toolbar._btn_simulate.setEnabled(False)

        worker = ScatterWorker(self._scatter_tracer, self)
        worker.setup(
            geometry=geometry,
            energy_keV=energy,
            num_rays=min(DEFAULT_NUM_RAYS, 100),
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
        self.statusBar().showMessage(f"Scatter: %{pct}...")

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
            f"Scatter tamamlandi — "
            f"{result.num_interactions} etkilesim, "
            f"{result.num_reaching_detector} detektore, "
            f"SPR={result.total_scatter_fraction:.4f}, "
            f"t={result.elapsed_seconds:.2f}s"
        )

    def _overlay_scatter_on_beam_profile(self, scatter_result) -> None:
        """Add scatter noise overlay to beam profile chart."""
        if self._beam_ax is None or self._last_simulation_result is None:
            return

        primary = self._last_simulation_result
        pos = primary.beam_profile.positions_mm
        ints = primary.beam_profile.intensities

        spr_pos = scatter_result.spr_positions_mm
        spr_vals = scatter_result.spr_profile

        if len(spr_pos) == 0 or len(spr_vals) == 0:
            return

        # Interpolate SPR onto primary beam positions
        spr_interp = np.interp(pos, spr_pos, spr_vals, left=0.0, right=0.0)

        # Scatter intensity: S(x) = SPR(x) * P(x)
        scatter_ints = spr_interp * ints

        # Combined signal: P(x) + S(x)
        combined = ints + scatter_ints

        ax = self._beam_ax
        ax.fill_between(
            pos, ints, combined,
            alpha=0.25, color="#EF4444",
            label=f"Scatter (SPR={scatter_result.total_scatter_fraction:.4f})",
        )
        ax.plot(
            pos, combined, color="#F8FAFC", linewidth=1.0,
            linestyle="--", alpha=0.8,
            label="Birlesik (P+S)",
        )

        ax.legend(
            fontsize=9, facecolor="#1E293B", edgecolor="#475569",
            labelcolor="#F8FAFC",
        )
        self._beam_figure.tight_layout()
        self._beam_canvas.draw()

    def _on_scatter_error(self, error: str) -> None:
        self.statusBar().showMessage(f"Scatter hatasi: {error}")

    def _on_scatter_finished(self) -> None:
        self._toolbar._btn_simulate.setEnabled(True)

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
            self.statusBar().showMessage("En az 2 enerji secin.")
            return

        geo = self._controller.geometry
        self.statusBar().showMessage(
            f"Karsilastirma: {len(energies)} enerji hesaplaniyor..."
        )
        self._toolbar._btn_simulate.setEnabled(False)

        # Run in worker thread to avoid blocking UI
        from app.workers.compare_worker import CompareWorker
        worker = CompareWorker(self._beam_sim, self)
        worker.setup(geo, energies, num_rays)
        worker.progress.connect(
            lambda p: self.statusBar().showMessage(
                f"Karsilastirma: %{p}..."
            )
        )
        worker.result_ready.connect(self._on_compare_result)
        worker.error_occurred.connect(
            lambda e: self.statusBar().showMessage(f"Karsilastirma hatasi: {e}")
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
        ax.set_title("Enerji Karsilastirmasi", color="#F8FAFC", fontsize=12)

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
            f"Karsilastirma tamamlandi — {len(results)} enerji"
        )

    # ------------------------------------------------------------------
    # G-6: LINAC mode warning
    # ------------------------------------------------------------------

    def _on_energy_mode_changed(self, mode: str) -> None:
        """Show/hide LINAC warning based on energy mode."""
        self._linac_warning.setVisible(mode == "MeV")

    def _on_tube_config_changed(self) -> None:
        """Update spectrum chart when tube parameters change (kVp mode only)."""
        if self._toolbar.energy_mode != "kVp":
            return
        from app.core.spectrum_models import TubeConfig
        config = TubeConfig(
            target_id=self._toolbar.get_target_id(),
            kVp=float(self._toolbar.get_slider_raw()),
            window_type=self._toolbar.get_window_type(),
            window_thickness_mm=self._toolbar.get_window_thickness_mm(),
        )
        self._spectrum_chart.update_spectrum(config)

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
            self.statusBar().showMessage("Esik degerleri guncellendi.")

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
                self.statusBar().showMessage(f"Tasarim yuklendi: {geometry.name}")

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
        self.statusBar().showMessage(f"Kaydedildi: {geometry.name}")

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
            self.statusBar().showMessage(f"Kaydedildi: {name}")

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
                    lambda p: self.statusBar().showMessage(f"PDF olusturuldu: {p}")
                )
                worker.error_occurred.connect(
                    lambda e: self.statusBar().showMessage(f"PDF hatasi: {e}")
                )
                worker.finished.connect(worker.deleteLater)
                worker.start()
                self.statusBar().showMessage("PDF olusturuluyor...")
                return

            self.statusBar().showMessage(f"Disa aktarildi: {path}")
        except Exception as e:
            self.statusBar().showMessage(f"Disa aktarim hatasi: {e}")

    def _on_version_history(self) -> None:
        """Show version history dialog."""
        if self._current_design_id is None:
            self.statusBar().showMessage("Once tasarimi kaydedin.")
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
                f"Versiyon {dlg.restored_version} geri yuklendi"
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
            self.statusBar().showMessage(f"Tasarim yuklendi: {geometry.name}")
        except KeyError:
            self.statusBar().showMessage("Tasarim bulunamadi.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        else:
            super().keyPressEvent(event)
