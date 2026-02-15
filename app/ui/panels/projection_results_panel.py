"""Projection results panel — detector profile and MTF charts.

Displays the output of analytic projection calculations:
  1. Detector intensity profile (positions vs intensities)
  2. MTF curve (frequency vs modulation)
  3. Numeric summary (SOD, ODD, M, Ug, contrast, MTF@50%, MTF@10%)

The matplotlib canvas is created lazily on first use to avoid
QPainter errors from zero-size QImage rendering during startup.

Reference: Phase-03.5 spec — Projection Results.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt

from app.core.i18n import t, TranslationManager
from app.core.units import cm_to_mm
from app.models.projection import ProjectionResult


class ProjectionResultsPanel(QWidget):
    """Panel showing projection calculation results.

    Two matplotlib subplots: detector profile + MTF curve.
    Info label with numeric summary.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._canvas = None
        self._figure = None
        self._ax_profile = None
        self._ax_mtf = None
        self._build_ui()
        TranslationManager.on_language_changed(self.retranslate_ui)

    def _build_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        # Placeholder — replaced by matplotlib canvas on first use
        self._placeholder = QLabel(
            t(
                "phantom.placeholder",
                "Add a test object (phantom) from\nthe right panel for projection.",
            )
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #64748B; font-size: 10pt;")
        self._main_layout.addWidget(self._placeholder, stretch=1)

        # Info label
        self._info_label = QLabel(t("phantom.waiting", "Waiting for calculation..."))
        self._info_label.setStyleSheet(
            "color: #94A3B8; font-size: 9pt; padding: 4px;"
        )
        self._info_label.setWordWrap(True)
        self._main_layout.addWidget(self._info_label)

    def retranslate_ui(self) -> None:
        """Update translatable strings after language change."""
        if self._placeholder is not None:
            self._placeholder.setText(
                t(
                    "phantom.placeholder",
                    "Add a test object (phantom) from\nthe right panel for projection.",
                )
            )
        # Info label: only update if still in waiting state (no result)
        if self._canvas is None:
            self._info_label.setText(t("phantom.waiting", "Waiting for calculation..."))

        # Re-label axes if canvas exists
        if self._canvas is not None:
            self._apply_axis_labels()
            self._canvas.draw()

    def _ensure_canvas(self) -> None:
        """Create matplotlib figure + canvas on first use."""
        if self._canvas is not None:
            return

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        self._figure = Figure(figsize=(6, 3), dpi=80)
        self._figure.patch.set_facecolor("#0F172A")

        self._ax_profile = self._figure.add_subplot(121)
        self._ax_mtf = self._figure.add_subplot(122)
        self._setup_axes()

        self._canvas = FigureCanvasQTAgg(self._figure)

        # Replace placeholder with canvas
        idx = self._main_layout.indexOf(self._placeholder)
        self._main_layout.removeWidget(self._placeholder)
        self._placeholder.deleteLater()
        self._placeholder = None
        self._main_layout.insertWidget(idx, self._canvas, stretch=1)

    def _setup_axes(self) -> None:
        """Configure axes styling for dark theme."""
        for ax in [self._ax_profile, self._ax_mtf]:
            ax.set_facecolor("#1E293B")
            ax.tick_params(colors="#94A3B8", labelsize=9)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            for spine in ax.spines.values():
                spine.set_color("#475569")

        self._apply_axis_labels()
        self._figure.tight_layout()

    def _apply_axis_labels(self) -> None:
        """Set axis labels and titles using current translation."""
        self._ax_profile.set_xlabel(
            t("charts.detector_position", "Detector Position (mm)"),
            color="#94A3B8", fontsize=9,
        )
        self._ax_profile.set_ylabel(
            t("charts.relative_intensity", "Relative Intensity"),
            color="#94A3B8", fontsize=9,
        )
        self._ax_profile.set_title("Detector Profile", color="#F8FAFC", fontsize=10)

        self._ax_mtf.set_xlabel("Frekans [lp/mm]", color="#94A3B8", fontsize=9)
        self._ax_mtf.set_ylabel("MTF", color="#94A3B8", fontsize=9)
        self._ax_mtf.set_title("MTF Curve", color="#F8FAFC", fontsize=10)

    def update_result(self, result: ProjectionResult) -> None:
        """Update charts and info from a projection result."""
        self._ensure_canvas()
        self._plot_profile(result)
        self._plot_mtf(result)
        self._update_info(result)
        self._canvas.draw()

    def clear(self) -> None:
        """Clear all charts and info."""
        if self._canvas is not None:
            self._ax_profile.cla()
            self._ax_mtf.cla()
            self._setup_axes()
            self._canvas.draw()
        self._info_label.setText(t("phantom.waiting", "Waiting for calculation..."))

    def _plot_profile(self, result: ProjectionResult) -> None:
        """Plot detector intensity profile."""
        self._ax_profile.cla()
        ax = self._ax_profile

        ax.set_facecolor("#1E293B")
        ax.tick_params(colors="#94A3B8", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_color("#475569")

        prof = result.profile
        if len(prof.positions_mm) > 0 and len(prof.intensities) > 0:
            ax.plot(prof.positions_mm, prof.intensities, color="#3B82F6", linewidth=1)
            ax.set_ylim(-0.05, 1.15)

        ax.set_xlabel(
            t("charts.detector_position", "Detector Position (mm)"),
            color="#94A3B8", fontsize=9,
        )
        ax.set_ylabel(
            t("charts.relative_intensity", "Relative Intensity"),
            color="#94A3B8", fontsize=9,
        )
        ax.set_title("Detector Profile", color="#F8FAFC", fontsize=10)

    def _plot_mtf(self, result: ProjectionResult) -> None:
        """Plot MTF curve."""
        self._ax_mtf.cla()
        ax = self._ax_mtf

        ax.set_facecolor("#1E293B")
        ax.tick_params(colors="#94A3B8", labelsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_color("#475569")

        mtf = result.mtf
        if mtf is not None and len(mtf.frequencies_lpmm) > 0:
            ax.plot(mtf.frequencies_lpmm, mtf.mtf_values, color="#EF4444", linewidth=1)
            ax.axhline(y=0.5, color="#F59E0B", linestyle="--", linewidth=0.5, alpha=0.5)
            ax.axhline(y=0.1, color="#F59E0B", linestyle=":", linewidth=0.5, alpha=0.5)
            ax.set_ylim(-0.05, 1.15)

            # Limit x-axis to meaningful range
            max_freq = mtf.frequencies_lpmm[-1] if len(mtf.frequencies_lpmm) > 0 else 10
            # Show up to where MTF is still > 0.01 or 20% of range
            above_thresh = mtf.mtf_values > 0.01
            if above_thresh.any():
                last_idx = max(i for i, v in enumerate(above_thresh) if v)
                x_max = min(mtf.frequencies_lpmm[min(last_idx + 10, len(mtf.frequencies_lpmm) - 1)], max_freq)
                ax.set_xlim(0, max(x_max, 1))

        ax.set_xlabel("Frekans [lp/mm]", color="#94A3B8", fontsize=9)
        ax.set_ylabel("MTF", color="#94A3B8", fontsize=9)
        ax.set_title("MTF Curve", color="#F8FAFC", fontsize=10)

        self._figure.tight_layout()

    def _update_info(self, result: ProjectionResult) -> None:
        """Update info label with numeric summary."""
        geo = result.geometry
        prof = result.profile

        sod_mm = float(cm_to_mm(geo.sod_cm))
        odd_mm = float(cm_to_mm(geo.odd_cm))
        ug_mm = float(cm_to_mm(geo.geometric_unsharpness_cm))

        parts = [
            f"SOD: {sod_mm:.1f} mm",
            f"ODD: {odd_mm:.1f} mm",
            f"M: {geo.magnification:.3f}",
            f"Ug: {ug_mm:.3f} mm",
            f"Contrast: {prof.contrast:.4f}",
        ]

        if result.mtf is not None:
            mtf = result.mtf
            if mtf.mtf_50_freq > 0:
                parts.append(f"MTF@50%: {mtf.mtf_50_freq:.2f} lp/mm")
            if mtf.mtf_10_freq > 0:
                parts.append(f"MTF@10%: {mtf.mtf_10_freq:.2f} lp/mm")

        self._info_label.setText("  |  ".join(parts))
