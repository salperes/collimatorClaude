"""Compton analysis widget — KN polar plot, energy spectrum, angle-energy map.

Four sub-tabs:
  1. Klein-Nishina polar plot (matplotlib) + σ_KN display (G-14)
  2. Scattered photon energy spectrum (pyqtgraph) + Compton edge (G-15)
  3. Angle vs energy / recoil energy + Δλ display (G-16)
  4. Material Compton fractions (G-17)

Includes energy slider (G-12) and preset buttons (G-13).
Thomson comparison curve already present (G-11).

Reference: Phase-05 spec — FR-3.5.1, FR-3.5.2, FR-3.5.3, FR-5.4.
"""

import math

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QSlider, QPushButton,
)
from PyQt6.QtCore import Qt

from app.core.compton_engine import ComptonEngine
from app.core.units import rad_to_deg
from app.ui.charts.base_chart import BaseChart
from app.ui.styles.colors import (
    BACKGROUND, PANEL_BG, TEXT_SECONDARY, BORDER,
    ACCENT, WARNING, ERROR,
)


# G-13: Energy presets for Compton charts
_COMPTON_PRESETS: list[tuple[str, float]] = [
    ("80", 80.0),
    ("160", 160.0),
    ("320", 320.0),
    ("1M", 1000.0),
    ("3.5M", 3500.0),
    ("6M", 6000.0),
]


class ComptonWidget(QWidget):
    """Tabbed container for all Compton analysis charts."""

    def __init__(
        self,
        compton_engine: ComptonEngine,
        material_service=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._engine = compton_engine
        self._material_service = material_service
        self._energy: float = 1000.0  # keV default

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # G-12: Energy slider + G-13: preset buttons
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(4)

        self._energy_label = QLabel(f"Enerji: {self._energy:.0f} keV")
        self._energy_label.setStyleSheet(
            "color: #B0BEC5; font-size: 9pt; padding: 4px;"
        )
        ctrl_layout.addWidget(self._energy_label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(10)
        self._slider.setMaximum(6000)
        self._slider.setSingleStep(10)
        self._slider.setValue(int(self._energy))
        self._slider.setFixedWidth(200)
        self._slider.valueChanged.connect(self._on_slider_changed)
        ctrl_layout.addWidget(self._slider)

        # Preset buttons
        for label, keV in _COMPTON_PRESETS:
            btn = QPushButton(label)
            btn.setFixedWidth(40)
            btn.setToolTip(f"{keV:.0f} keV")
            btn.clicked.connect(lambda _, e=keV: self._apply_preset(e))
            ctrl_layout.addWidget(btn)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Sub-tab 1: Klein-Nishina polar plot (matplotlib)
        self._kn_chart = KleinNishinaChart(compton_engine)
        self._tabs.addTab(self._kn_chart, "Klein-Nishina")

        # Sub-tab 2: Scattered energy spectrum (pyqtgraph)
        self._spectrum_chart = ComptonEnergyChart(compton_engine)
        self._tabs.addTab(self._spectrum_chart, "Enerji Spektrumu")

        # Sub-tab 3: Angle vs energy map (pyqtgraph)
        self._angle_chart = AngleEnergyChart(compton_engine)
        self._tabs.addTab(self._angle_chart, "Aci-Enerji")

        # Sub-tab 4: Material Compton fractions (G-17)
        if material_service is not None:
            self._fractions_chart = ComptonFractionsChart(material_service)
            self._tabs.addTab(self._fractions_chart, "Compton Oranlari")

        self._update_all()

    def _on_slider_changed(self, value: int) -> None:
        self._energy = float(value)
        self._energy_label.setText(f"Enerji: {self._energy:.0f} keV")
        self._update_all()

    def _apply_preset(self, energy_keV: float) -> None:
        self._slider.setValue(int(energy_keV))

    def set_energy(self, energy_keV: float) -> None:
        """Update energy from external source (toolbar)."""
        self._slider.blockSignals(True)
        self._slider.setValue(int(energy_keV))
        self._slider.blockSignals(False)
        self._energy = energy_keV
        self._energy_label.setText(f"Enerji: {energy_keV:.0f} keV")
        self._update_all()

    def _update_all(self) -> None:
        self._kn_chart.set_energy(self._energy)
        self._spectrum_chart.set_energy(self._energy)
        self._angle_chart.set_energy(self._energy)


# =====================================================================
# Sub-chart 1: Klein-Nishina polar plot (matplotlib)
# =====================================================================


class KleinNishinaChart(QWidget):
    """Klein-Nishina differential cross-section as a polar plot.

    Includes Thomson comparison (G-11) and σ_KN total display (G-14).
    """

    def __init__(
        self,
        compton_engine: ComptonEngine,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._engine = compton_engine
        self._canvas = None
        self._figure = None
        self._ax = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # G-14: σ_KN value label
        self._sigma_label = QLabel("")
        self._sigma_label.setStyleSheet(
            "color: #B0BEC5; font-size: 9pt; font-family: monospace; padding: 2px;"
        )
        layout.addWidget(self._sigma_label)

        # Lazy canvas creation
        self._placeholder = QLabel("Klein-Nishina polar grafigi yukleniyor...")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #64748B; font-size: 10pt;")
        layout.addWidget(self._placeholder, stretch=1)
        self._layout = layout

    def _ensure_canvas(self) -> None:
        if self._canvas is not None:
            return

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self._figure = Figure(figsize=(5, 5), dpi=80)
        self._figure.patch.set_facecolor(BACKGROUND)
        self._ax = self._figure.add_subplot(111, projection="polar")
        self._setup_axes()

        self._canvas = FigureCanvasQTAgg(self._figure)

        self._layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._placeholder = None
        self._layout.addWidget(self._canvas, stretch=1)

    def _setup_axes(self) -> None:
        ax = self._ax
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
        ax.set_theta_zero_location("N")  # 0 degrees at top (forward)
        ax.set_theta_direction(-1)
        ax.spines["polar"].set_color(BORDER)
        ax.grid(True, alpha=0.2, color=BORDER)

    def set_energy(self, energy_keV: float) -> None:
        """Compute and plot KN distribution + Thomson limit."""
        self._ensure_canvas()
        ax = self._ax
        ax.clear()
        self._setup_axes()

        # Klein-Nishina data
        kn = self._engine.klein_nishina_distribution(energy_keV, angular_bins=360)
        angles = np.array(kn.angles_rad)
        dsigma = np.array(kn.dsigma_domega)

        # Thomson limit: d_sigma/d_Omega = r_e^2/2 * (1 + cos^2(theta))
        r_e = self._engine.CLASSICAL_ELECTRON_RADIUS
        thomson = (r_e ** 2 / 2.0) * (1.0 + np.cos(angles) ** 2)

        # Plot Thomson (dashed, reference) — G-11
        ax.plot(angles, thomson, color="#64748B", linewidth=1,
                linestyle="--", label="Thomson", alpha=0.7)

        # Plot KN (solid)
        ax.plot(angles, dsigma, color=ACCENT, linewidth=2,
                label=f"KN ({energy_keV:.0f} keV)")

        # Region fills: forward (0-90°) and backward (90-180°)
        forward_mask = angles <= math.pi / 2
        backward_mask = angles >= math.pi / 2

        ax.fill_between(
            angles[forward_mask], 0, dsigma[forward_mask],
            alpha=0.1, color=ACCENT,
        )
        ax.fill_between(
            angles[backward_mask], 0, dsigma[backward_mask],
            alpha=0.1, color=ERROR,
        )

        ax.set_title(
            f"Klein-Nishina ({energy_keV:.0f} keV)",
            color=TEXT_SECONDARY, fontsize=10, pad=15,
        )
        ax.legend(
            loc="lower right", fontsize=8,
            facecolor=PANEL_BG, edgecolor=BORDER,
            labelcolor=TEXT_SECONDARY,
        )

        self._figure.tight_layout()
        self._canvas.draw()

        # G-14: Update σ_KN total value display
        sigma_kn = self._engine.total_cross_section(energy_keV)
        sigma_t = self._engine.THOMSON_CROSS_SECTION
        ratio = sigma_kn / sigma_t if sigma_t > 0 else 0
        self._sigma_label.setText(
            f"sigma_KN = {sigma_kn:.4e} cm2/e  "
            f"({ratio:.3f} x sigma_T)  |  "
            f"sigma_T = {sigma_t:.4e} cm2/e"
        )


# =====================================================================
# Sub-chart 2: Compton energy spectrum (pyqtgraph)
# =====================================================================


class ComptonEnergyChart(BaseChart):
    """Scattered photon energy spectrum with Compton edge marker (G-15)."""

    def __init__(
        self,
        compton_engine: ComptonEngine,
        parent: QWidget | None = None,
    ):
        super().__init__(
            title="Sacilmis Foton Enerji Spektrumu",
            x_label="Enerji [keV]",
            y_label="Olasilik Yogunlugu",
            parent=parent,
        )
        self._engine = compton_engine
        self._edge_line = None
        self.enable_crosshair()

    def set_energy(self, energy_keV: float) -> None:
        """Compute and plot energy spectrum."""
        self.clear_curves()
        if self._edge_line is not None:
            self.plot_widget.removeItem(self._edge_line)
            self._edge_line = None

        spectrum = self._engine.scattered_energy_spectrum(energy_keV, num_bins=200)
        energies = np.array(spectrum.energy_bins_keV)
        weights = np.array(spectrum.weights)

        self.add_curve(energies, weights, name=f"E0={energy_keV:.0f} keV",
                       color=ACCENT)

        # Compton edge marker (G-15)
        e_min, t_max = self._engine.compton_edge(energy_keV)
        self._edge_line = self.add_infinite_line(
            pos=e_min, angle=90, color=WARNING,
            style=Qt.PenStyle.DashLine,
            label=f"Compton Edge {e_min:.1f} keV",
        )


# =====================================================================
# Sub-chart 3: Angle vs energy map (pyqtgraph, dual-axis)
# =====================================================================


class AngleEnergyChart(QWidget):
    """Scattering angle vs scattered/recoil energy + Δλ display (G-16)."""

    def __init__(
        self,
        compton_engine: ComptonEngine,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._engine = compton_engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # G-16: Δλ info label
        self._delta_label = QLabel("")
        self._delta_label.setStyleSheet(
            "color: #B0BEC5; font-size: 9pt; font-family: monospace; padding: 2px;"
        )
        layout.addWidget(self._delta_label)

        # Primary chart for scattered energy
        self._chart = BaseChart(
            title="Aci vs Enerji",
            x_label="Sacilma Acisi [derece]",
            y_label="Enerji [keV]",
        )
        self._chart.enable_crosshair()
        layout.addWidget(self._chart)

    def set_energy(self, energy_keV: float) -> None:
        """Compute and plot angle-energy map with Δλ info."""
        self._chart.clear_curves()

        data = self._engine.angle_energy_map(energy_keV, angular_steps=361)
        angles_deg = np.array([float(rad_to_deg(a)) for a in data.angles_rad])
        scattered = np.array(data.scattered_energies_keV)
        recoil = np.array(data.recoil_energies_keV)
        wavelength_shifts = np.array(data.wavelength_shifts_angstrom)

        # Scattered photon energy (primary)
        self._chart.add_curve(
            angles_deg, scattered,
            name="E' (sacilmis foton)", color=ACCENT, width=2,
        )

        # Recoil electron energy (secondary)
        self._chart.add_curve(
            angles_deg, recoil,
            name="T (geri sekme elektron)", color=ERROR, width=2,
        )

        # G-16: Δλ info at key angles
        delta_90 = self._engine.wavelength_shift(math.pi / 2)
        delta_180 = self._engine.wavelength_shift(math.pi)
        lambda_c = self._engine.COMPTON_WAVELENGTH
        self._delta_label.setText(
            f"lambda_C = {lambda_c:.5f} A  |  "
            f"Delta_lambda(90) = {delta_90:.5f} A  |  "
            f"Delta_lambda(180) = {delta_180:.5f} A  |  "
            f"Maks Delta_lambda = 2*lambda_C = {2*lambda_c:.5f} A"
        )


# =====================================================================
# Sub-chart 4: Material Compton fractions (G-17)
# =====================================================================


class ComptonFractionsChart(BaseChart):
    """Material Compton/total attenuation ratio vs energy.

    Shows what fraction of total attenuation is due to Compton scattering
    for common shielding materials. Useful for evaluating scatter significance.

    Reference: FRD §5.4 — material_compton_fractions().
    """

    def __init__(
        self,
        material_service,
        parent: QWidget | None = None,
    ):
        super().__init__(
            title="Compton / Toplam Oran",
            x_label="Enerji [keV]",
            y_label="Compton Orani",
            log_x=True,
            parent=parent,
        )
        self._material_service = material_service
        self.enable_crosshair()
        self._plot_fractions()

    def _plot_fractions(self) -> None:
        """Plot Compton fraction for each material."""
        from app.ui.styles.colors import MATERIAL_COLORS

        energies = np.geomspace(10, 6000, 200)
        materials = ["Pb", "W", "Cu", "Al"]

        for mat_id in materials:
            try:
                fractions = []
                for E in energies:
                    mu_total = self._material_service.get_mu_rho(mat_id, float(E))
                    mu_compton = self._material_service.get_compton_mu_rho(mat_id, float(E))
                    frac = mu_compton / mu_total if mu_total > 1e-20 else 0
                    fractions.append(min(frac, 1.0))

                color = MATERIAL_COLORS.get(mat_id, "#B0BEC5")
                self.add_curve(
                    energies, np.array(fractions),
                    name=mat_id, color=color, width=2,
                )
            except (KeyError, ValueError):
                continue

        # Reference lines
        self.add_infinite_line(
            pos=0.5, angle=0, color=WARNING,
            style=Qt.PenStyle.DashLine,
            label="50%",
        )
