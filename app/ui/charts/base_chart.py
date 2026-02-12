"""Base chart widget — pyqtgraph-based with dark theme.

Common API for all chart widgets: add_curve, clear, regions, crosshair.

Reference: Phase-05 spec — Base Chart Class.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from app.ui.styles.colors import BACKGROUND, PANEL_BG, TEXT_SECONDARY, BORDER


class BaseChart(QWidget):
    """pyqtgraph PlotWidget wrapper with dark theme and utility methods."""

    def __init__(
        self,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        log_x: bool = False,
        log_y: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._curves: list[pg.PlotDataItem] = []
        self._regions: list[pg.LinearRegionItem] = []
        self._crosshair_enabled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground(BACKGROUND)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self.plot_widget)

        # Axis styling
        plot_item = self.plot_widget.getPlotItem()
        if title:
            plot_item.setTitle(title, color=TEXT_SECONDARY, size="10pt")
        if x_label:
            plot_item.setLabel("bottom", x_label, color=TEXT_SECONDARY)
        if y_label:
            plot_item.setLabel("left", y_label, color=TEXT_SECONDARY)

        for axis_name in ("bottom", "left", "top", "right"):
            axis = plot_item.getAxis(axis_name)
            axis.setPen(pg.mkPen(BORDER))
            axis.setTextPen(pg.mkPen(TEXT_SECONDARY))

        # Log mode
        self.plot_widget.setLogMode(x=log_x, y=log_y)

        # Legend
        self._legend = plot_item.addLegend(
            offset=(10, 10),
            labelTextColor=TEXT_SECONDARY,
            brush=pg.mkBrush(PANEL_BG),
            pen=pg.mkPen(BORDER),
        )

    def add_curve(
        self,
        x: np.ndarray,
        y: np.ndarray,
        name: str = "",
        color: str = "#3B82F6",
        width: int = 2,
    ) -> pg.PlotDataItem:
        """Add a data curve to the plot."""
        pen = pg.mkPen(color=color, width=width)
        curve = self.plot_widget.plot(x, y, pen=pen, name=name)
        self._curves.append(curve)
        return curve

    def clear_curves(self) -> None:
        """Remove all curves and regions."""
        for curve in self._curves:
            self.plot_widget.removeItem(curve)
        self._curves.clear()
        for region in self._regions:
            self.plot_widget.removeItem(region)
        self._regions.clear()
        if self._legend is not None:
            self._legend.clear()

    def add_region(
        self,
        x_min: float,
        x_max: float,
        color: str = "#3B82F6",
        alpha: float = 0.2,
    ) -> pg.LinearRegionItem:
        """Add a colored vertical region."""
        brush = pg.mkBrush(pg.mkColor(color).lighter(150))
        brush.setStyle(Qt.BrushStyle.SolidPattern)
        c = pg.mkColor(color)
        c.setAlphaF(alpha)
        region = pg.LinearRegionItem(
            values=[x_min, x_max],
            movable=False,
            brush=pg.mkBrush(c),
            pen=pg.mkPen(None),
        )
        self.plot_widget.addItem(region)
        self._regions.append(region)
        return region

    def add_infinite_line(
        self,
        pos: float,
        angle: int = 90,
        color: str = "#F59E0B",
        style: Qt.PenStyle = Qt.PenStyle.DashLine,
        label: str = "",
    ) -> pg.InfiniteLine:
        """Add a vertical or horizontal infinite line."""
        pen = pg.mkPen(color=color, width=1, style=style)
        line = pg.InfiniteLine(
            pos=pos, angle=angle, pen=pen,
            label=label,
            labelOpts={"color": TEXT_SECONDARY, "position": 0.95},
        )
        self.plot_widget.addItem(line)
        return line

    def enable_crosshair(self) -> None:
        """Add crosshair lines that follow mouse cursor."""
        if self._crosshair_enabled:
            return
        self._crosshair_enabled = True
        self._vline = pg.InfiniteLine(angle=90, movable=False,
                                       pen=pg.mkPen(TEXT_SECONDARY, width=1,
                                                     style=Qt.PenStyle.DotLine))
        self._hline = pg.InfiniteLine(angle=0, movable=False,
                                       pen=pg.mkPen(TEXT_SECONDARY, width=1,
                                                     style=Qt.PenStyle.DotLine))
        self.plot_widget.addItem(self._vline, ignoreBounds=True)
        self.plot_widget.addItem(self._hline, ignoreBounds=True)

        self.plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, pos) -> None:
        """Update crosshair position."""
        vb = self.plot_widget.getPlotItem().vb
        if self.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = vb.mapSceneToView(pos)
            self._vline.setPos(mouse_point.x())
            self._hline.setPos(mouse_point.y())

    def set_log_mode(self, x: bool, y: bool) -> None:
        """Toggle logarithmic axes."""
        self.plot_widget.setLogMode(x=x, y=y)
