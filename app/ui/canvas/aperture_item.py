"""Aperture graphics item — central channel through a collimator stage.

Shape depends on CollimatorType:
  FAN_BEAM:    trapezoid (wider at detector side)
  PENCIL_BEAM: rectangle or ellipse
  SLIT:        narrow rectangle

Reference: Phase-03 spec — FR-1.2, Canvas Hierarchy.
"""

import math

from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QPolygonF

from app.models.geometry import ApertureConfig, CollimatorType
from app.ui.styles.colors import BACKGROUND


class ApertureItem(QGraphicsItem):
    """Aperture channel rendered in the center of a stage.

    The aperture is the empty space at the stage center.
    Rendered as a dark fill (canvas background color).
    """

    def __init__(
        self,
        stage_index: int,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self._stage_index = stage_index
        self._path = QPainterPath()
        self._bounding = QRectF()

    def update_shape(
        self,
        aperture: ApertureConfig,
        collimator_type: CollimatorType,
        stage_width: float,
        stage_height: float,
        inner_offset: float,
    ) -> None:
        """Recompute aperture path from config.

        Args:
            aperture: Aperture configuration.
            collimator_type: Beam type (determines shape).
            stage_width: Stage outer width [mm].
            stage_height: Stage outer height [mm].
            inner_offset: Total layer thickness per side [mm].
                          Aperture sits inside all layers.
        """
        self.prepareGeometryChange()
        self._path = QPainterPath()

        cx = stage_width / 2.0
        cy = stage_height / 2.0

        match collimator_type:
            case CollimatorType.FAN_BEAM:
                self._build_fan_path(aperture, stage_height, cx, inner_offset)
            case CollimatorType.PENCIL_BEAM:
                self._build_pencil_path(aperture, cx, cy, inner_offset)
            case CollimatorType.SLIT:
                self._build_slit_path(aperture, stage_height, cx, inner_offset)

        self._bounding = self._path.boundingRect().adjusted(-1, -1, 1, 1)

    def _build_fan_path(
        self, aperture: ApertureConfig, stage_height: float,
        cx: float, inner_offset: float,
    ) -> None:
        """Trapezoid: narrow at top (source side), wider at bottom."""
        fan_angle = aperture.fan_angle or 30.0
        slit_w = aperture.fan_slit_width or 2.0

        half_angle_rad = math.radians(fan_angle / 2.0)
        top_half = slit_w / 2.0
        bottom_half = top_half + stage_height * math.tan(half_angle_rad)

        # Clamp to stay within layers
        max_half = cx - inner_offset
        top_half = min(top_half, max_half)
        bottom_half = min(bottom_half, max_half)

        polygon = QPolygonF([
            QPointF(cx - top_half, 0),
            QPointF(cx + top_half, 0),
            QPointF(cx + bottom_half, stage_height),
            QPointF(cx - bottom_half, stage_height),
        ])
        self._path.addPolygon(polygon)
        self._path.closeSubpath()

    def _build_pencil_path(
        self, aperture: ApertureConfig,
        cx: float, cy: float, inner_offset: float,
    ) -> None:
        """Circle/ellipse centered in the stage."""
        diameter = aperture.pencil_diameter or 5.0
        radius = min(diameter / 2.0, cx - inner_offset)
        self._path.addEllipse(QPointF(cx, cy), radius, radius)

    def _build_slit_path(
        self, aperture: ApertureConfig, stage_height: float,
        cx: float, inner_offset: float,
    ) -> None:
        """Narrow rectangle or trapezoid centered in the stage."""
        slit_w = aperture.slit_width or 2.0
        slit_h = aperture.slit_height or stage_height
        max_half = cx - inner_offset

        half_h = min(slit_h / 2.0, stage_height / 2.0)
        y_top = stage_height / 2.0 - half_h
        y_bot = stage_height / 2.0 + half_h

        if aperture.taper_angle and aperture.taper_angle != 0.0:
            # Trapezoid: wider at source (top), narrower at detector (bottom)
            taper_rad = math.radians(aperture.taper_angle)
            bot_half = min(slit_w / 2.0, max_half)
            top_half = min(bot_half + slit_h * math.tan(taper_rad), max_half)

            polygon = QPolygonF([
                QPointF(cx - top_half, y_top),
                QPointF(cx + top_half, y_top),
                QPointF(cx + bot_half, y_bot),
                QPointF(cx - bot_half, y_bot),
            ])
            self._path.addPolygon(polygon)
            self._path.closeSubpath()
        else:
            half_w = min(slit_w / 2.0, max_half)
            self._path.addRect(cx - half_w, y_top, half_w * 2, half_h * 2)

    def boundingRect(self) -> QRectF:
        return self._bounding

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget=None,
    ) -> None:
        if self._path.isEmpty():
            return
        # Fill with canvas background color (the "hole")
        painter.fillPath(self._path, QColor(BACKGROUND))
        # Thin border
        pen = QPen(QColor("#475569"), 1, )
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawPath(self._path)
