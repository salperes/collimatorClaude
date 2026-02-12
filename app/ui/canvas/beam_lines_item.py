"""Beam lines graphics item — symbolic beam paths.

Semi-transparent blue lines from source through apertures to detector.
Shape depends on collimator type (fan/pencil/slit).

Reference: Phase-03 spec — FR-1.5.3.
"""

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, QLineF
from PyQt6.QtGui import QPainter, QColor, QPen

from app.constants import BEAM_LINE_OPACITY
from app.ui.styles.colors import ACCENT


class BeamLinesItem(QGraphicsItem):
    """Symbolic beam path lines from source to detector.

    Color: ACCENT (#3B82F6) at 40% opacity.
    Lines are computed externally and set via set_lines().
    """

    def __init__(self, parent: QGraphicsItem | None = None):
        super().__init__(parent)
        self._lines: list[QLineF] = []
        self._bounding = QRectF()
        self.setZValue(-10)

    def set_lines(self, lines: list[QLineF]) -> None:
        """Set beam path lines (in scene coordinates)."""
        self.prepareGeometryChange()
        self._lines = lines
        if lines:
            xs = []
            ys = []
            for line in lines:
                xs.extend([line.x1(), line.x2()])
                ys.extend([line.y1(), line.y2()])
            self._bounding = QRectF(
                min(xs) - 5, min(ys) - 5,
                max(xs) - min(xs) + 10,
                max(ys) - min(ys) + 10,
            )
        else:
            self._bounding = QRectF()

    def boundingRect(self) -> QRectF:
        return self._bounding

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        if not self._lines:
            return

        color = QColor(ACCENT)
        color.setAlpha(int(255 * BEAM_LINE_OPACITY))
        pen = QPen(color, 1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        for line in self._lines:
            painter.drawLine(line)
