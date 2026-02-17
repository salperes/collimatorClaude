"""Isodose chart widget — 2D dose heatmap with contour lines.

pyqtgraph-based visualization showing IsodoseResult as a colored
heatmap with isodose contour lines and colorbar.

Reference: Phase 8 — Isodose Map Feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.core.i18n import t
from app.ui.styles.colors import BACKGROUND, TEXT_SECONDARY, BORDER

if TYPE_CHECKING:
    from app.core.isodose_engine import IsodoseResult


# Contour line colors (from high to low dose)
_CONTOUR_COLORS = {
    1.0: "#FFFFFF",   # white — max
    0.8: "#E0E0FF",   # light blue
    0.5: "#FFD700",   # gold
    0.2: "#FF8C00",   # dark orange
    0.1: "#FF4500",   # orange-red
    0.05: "#FF0000",  # red — leakage
}


class IsodoseChartWidget(QWidget):
    """2D isodose map visualization with heatmap + contour lines.

    Uses pyqtgraph ImageItem for the dose map and IsocurveItem
    for isodose contour lines.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._result: IsodoseResult | None = None
        self._contour_items: list[pg.IsocurveItem] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main plot
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground(BACKGROUND)
        self._plot_widget.setAspectLocked(True)

        plot_item = self._plot_widget.getPlotItem()
        plot_item.setLabel(
            "bottom",
            t("charts.isodose_x_axis", "Lateral Position (mm)"),
            color=TEXT_SECONDARY,
        )
        plot_item.setLabel(
            "left",
            t("charts.isodose_y_axis", "Beam Direction (mm)"),
            color=TEXT_SECONDARY,
        )
        for axis_name in ("bottom", "left", "top", "right"):
            axis = plot_item.getAxis(axis_name)
            axis.setPen(pg.mkPen(BORDER))
            axis.setTextPen(pg.mkPen(TEXT_SECONDARY))

        # Image item for heatmap
        self._image_item = pg.ImageItem()
        self._plot_widget.addItem(self._image_item)

        # Colorbar
        self._colormap = pg.colormap.get("CET-L9")
        self._colorbar = pg.ColorBarItem(
            values=(0, 100),
            colorMap=self._colormap,
            label=t("charts.isodose_colorbar", "Relative Dose (%)"),
        )
        self._colorbar.setImageItem(self._image_item, insert_in=plot_item)

        layout.addWidget(self._plot_widget)

        # Info bar
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(4, 2, 4, 2)
        self._lbl_info = QLabel(
            t("charts.isodose_waiting", "Run simulation with isodose enabled...")
        )
        self._lbl_info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 9pt;")
        info_layout.addWidget(self._lbl_info)
        info_layout.addStretch()
        layout.addLayout(info_layout)

    def update_result(self, result: IsodoseResult) -> None:
        """Display a new isodose result.

        Args:
            result: IsodoseResult from IsodoseEngine.
        """
        self._result = result

        # Remove old contour items
        for item in self._contour_items:
            self._plot_widget.removeItem(item)
        self._contour_items.clear()

        dose_pct = result.dose_map * 100.0  # 0-100 for display

        # Compute image rect in mm
        x_mm = result.x_positions_mm
        y_mm = result.y_positions_mm
        x_min, x_max = float(x_mm[0]), float(x_mm[-1])
        y_min, y_max = float(y_mm[0]), float(y_mm[-1])
        x_range = x_max - x_min
        y_range = y_max - y_min

        # pyqtgraph ImageItem expects [x, y] array ordering
        # Our dose_map is [y, x], so transpose
        self._image_item.setImage(dose_pct.T)
        self._image_item.setRect(x_min, y_min, x_range, y_range)

        # Update colorbar
        self._colorbar.setLevels(values=(0, 100))

        # Add isodose contour lines
        for level in result.contour_levels:
            level_pct = level * 100.0
            color = _CONTOUR_COLORS.get(level, "#AAAAAA")
            pen = pg.mkPen(color=color, width=1.5)
            iso = pg.IsocurveItem(
                data=dose_pct.T,
                level=level_pct,
                pen=pen,
            )
            # Scale and position the isocurve to match image coordinates
            # ImageItem maps pixel indices to rect, so isocurve uses same indices
            # We need to transform from pixel to scene coords
            sx = x_range / result.nx if result.nx > 1 else 1.0
            sy = y_range / result.ny if result.ny > 1 else 1.0
            iso.setTransform(
                pg.QtGui.QTransform().translate(x_min, y_min).scale(sx, sy)
            )
            self._plot_widget.addItem(iso)
            self._contour_items.append(iso)

        # Auto-range
        self._plot_widget.setRange(
            xRange=(x_min, x_max),
            yRange=(y_min, y_max),
        )

        # Update info label
        self._lbl_info.setText(
            t("charts.isodose_info",
              "E={energy} keV | Resolution: {nx}x{ny} | t={time}s").format(
                energy=f"{result.energy_keV:.0f}",
                nx=result.nx,
                ny=result.ny,
                time=f"{result.elapsed_seconds:.1f}",
            )
        )

    def clear(self) -> None:
        """Remove all isodose data."""
        self._result = None
        self._image_item.clear()
        for item in self._contour_items:
            self._plot_widget.removeItem(item)
        self._contour_items.clear()
        self._lbl_info.setText(
            t("charts.isodose_waiting", "Run simulation with isodose enabled...")
        )

    def retranslate_ui(self) -> None:
        """Update labels for language change."""
        plot_item = self._plot_widget.getPlotItem()
        plot_item.setLabel(
            "bottom",
            t("charts.isodose_x_axis", "Lateral Position (mm)"),
            color=TEXT_SECONDARY,
        )
        plot_item.setLabel(
            "left",
            t("charts.isodose_y_axis", "Beam Direction (mm)"),
            color=TEXT_SECONDARY,
        )
        if self._result is None:
            self._lbl_info.setText(
                t("charts.isodose_waiting", "Run simulation with isodose enabled...")
            )
