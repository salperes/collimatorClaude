"""Collimator canvas view — QGraphicsView with zoom/pan controls.

Zoom: mouse wheel (anchored under cursor), range 10% – 1000%.
Pan: middle-click drag or Ctrl+left-click drag.

Reference: Phase-03 spec — FR-1.1.3.
"""

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QMouseEvent, QWheelEvent

from app.constants import DEFAULT_ZOOM, MIN_ZOOM, MAX_ZOOM, RULER_WIDTH
from app.ui.styles.colors import BACKGROUND, TEXT_SECONDARY, SURFACE


class CollimatorView(QGraphicsView):
    """QGraphicsView with zoom (wheel), pan (drag), rulers, and fit-to-content.

    Zoom range: MIN_ZOOM (0.1x = 10%) to MAX_ZOOM (10x = 1000%).
    Zoom anchored under mouse cursor.
    """

    zoom_changed = pyqtSignal(float)

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self._zoom_level: float = DEFAULT_ZOOM
        self._panning: bool = False
        self._pan_start: QPointF = QPointF()

        self._setup_view()

    def _setup_view(self) -> None:
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
        )
        self.setBackgroundBrush(QColor(BACKGROUND))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        # Large scene rect so user can pan freely
        self.setSceneRect(-5000, -5000, 10000, 10000)

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom in/out with mouse wheel, anchored under cursor."""
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._apply_zoom(factor)

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = self._zoom_level * factor
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, new_zoom))
        actual_factor = new_zoom / self._zoom_level
        self._zoom_level = new_zoom
        self.scale(actual_factor, actual_factor)
        self.zoom_changed.emit(self._zoom_level)
        self.viewport().update()

    def set_zoom(self, level: float) -> None:
        """Programmatic zoom to specific level."""
        level = max(MIN_ZOOM, min(MAX_ZOOM, level))
        factor = level / self._zoom_level
        self._zoom_level = level
        self.resetTransform()
        self.scale(level, level)
        self.zoom_changed.emit(self._zoom_level)

    def fit_to_content(self) -> None:
        """Auto-zoom to show all content with 10% margin.

        Uses CollimatorScene.content_rect() (excludes background grid)
        to compute correct zoom level.
        """
        scene = self.scene()
        # Use content_rect if available (excludes grid's huge boundingRect)
        if hasattr(scene, 'content_rect'):
            items_rect = scene.content_rect()
        else:
            items_rect = scene.itemsBoundingRect()
        if items_rect.isEmpty():
            return
        margin = max(items_rect.width(), items_rect.height()) * 0.1
        items_rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(items_rect, Qt.AspectRatioMode.KeepAspectRatio)
        # Compute new zoom level from transform
        transform = self.transform()
        self._zoom_level = transform.m11()
        self._zoom_level = max(MIN_ZOOM, min(MAX_ZOOM, self._zoom_level))
        self.zoom_changed.emit(self._zoom_level)

    @property
    def zoom_level(self) -> float:
        return self._zoom_level

    # ------------------------------------------------------------------
    # Pan
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Right-click drag or middle-click or Ctrl+left-click → pan
        if (event.button() == Qt.MouseButton.RightButton
                or event.button() == Qt.MouseButton.MiddleButton
                or (event.button() == Qt.MouseButton.LeftButton
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        # Left-click on empty area → also pan
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item is None:
                self._panning = True
                self._pan_start = event.position()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        # Suppress right-click context menu
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Rulers (drawn as foreground overlay in viewport coords)
    # ------------------------------------------------------------------

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        """Draw rulers along top and left edges in viewport coordinates."""
        painter.save()
        painter.resetTransform()

        vp = self.viewport().rect()
        ruler_w = RULER_WIDTH

        # Ruler background
        ruler_bg = QColor(BACKGROUND)
        ruler_bg.setAlpha(230)

        # Top ruler
        painter.fillRect(ruler_w, 0, vp.width() - ruler_w, ruler_w, ruler_bg)
        # Left ruler
        painter.fillRect(0, ruler_w, ruler_w, vp.height() - ruler_w, ruler_bg)
        # Corner square
        painter.fillRect(0, 0, ruler_w, ruler_w, ruler_bg)

        # Tick marks
        pen = QPen(QColor(TEXT_SECONDARY))
        pen.setWidth(1)
        painter.setPen(pen)

        font = QFont("Segoe UI", 7)
        painter.setFont(font)

        # Determine tick spacing based on zoom
        base_spacing = self._ruler_tick_spacing()

        # Top ruler — horizontal ticks
        left_scene = self.mapToScene(ruler_w, 0).x()
        right_scene = self.mapToScene(vp.width(), 0).x()
        self._draw_ruler_ticks(
            painter, left_scene, right_scene, base_spacing,
            is_horizontal=True, ruler_w=ruler_w, vp=vp,
        )

        # Left ruler — vertical ticks
        top_scene = self.mapToScene(0, ruler_w).y()
        bottom_scene = self.mapToScene(0, vp.height()).y()
        self._draw_ruler_ticks(
            painter, top_scene, bottom_scene, base_spacing,
            is_horizontal=False, ruler_w=ruler_w, vp=vp,
        )

        painter.restore()

    def _ruler_tick_spacing(self) -> float:
        """Determine ruler tick spacing [mm] based on zoom level."""
        # Target ~50px between major ticks on screen
        target_px = 50.0
        scene_per_px = 1.0 / max(self._zoom_level, 0.01)
        raw_spacing = target_px * scene_per_px

        # Snap to nice values: 1, 2, 5, 10, 20, 50, 100, 200, 500 mm
        nice = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
        for n in nice:
            if n >= raw_spacing:
                return n
        return 1000.0

    def _draw_ruler_ticks(
        self, painter: QPainter,
        start_scene: float, end_scene: float, spacing: float,
        is_horizontal: bool, ruler_w: int, vp,
    ) -> None:
        """Draw tick marks and labels for one ruler axis."""
        import math
        first = math.floor(start_scene / spacing) * spacing

        tick = first
        while tick <= end_scene:
            if is_horizontal:
                vp_pos = self.mapFromScene(QPointF(tick, 0)).x()
                if ruler_w <= vp_pos <= vp.width():
                    is_major = abs(tick % (spacing * 5)) < 0.01
                    tick_len = ruler_w * 0.6 if is_major else ruler_w * 0.3
                    painter.drawLine(
                        int(vp_pos), int(ruler_w - tick_len),
                        int(vp_pos), int(ruler_w),
                    )
                    if is_major:
                        label = self._format_ruler_label(tick)
                        painter.drawText(int(vp_pos + 2), int(ruler_w - tick_len - 2), label)
            else:
                vp_pos = self.mapFromScene(QPointF(0, tick)).y()
                if ruler_w <= vp_pos <= vp.height():
                    is_major = abs(tick % (spacing * 5)) < 0.01
                    tick_len = ruler_w * 0.6 if is_major else ruler_w * 0.3
                    painter.drawLine(
                        int(ruler_w - tick_len), int(vp_pos),
                        int(ruler_w), int(vp_pos),
                    )
                    if is_major:
                        label = self._format_ruler_label(tick)
                        painter.save()
                        painter.translate(int(ruler_w - tick_len - 2), int(vp_pos + 2))
                        painter.rotate(-90)
                        painter.drawText(0, 0, label)
                        painter.restore()
            tick += spacing

    @staticmethod
    def _format_ruler_label(value_mm: float) -> str:
        """Format ruler label — mm for small values, cm for large."""
        if abs(value_mm) >= 100:
            cm = value_mm / 10.0
            return f"{cm:.0f}cm" if cm == int(cm) else f"{cm:.1f}cm"
        return f"{value_mm:.0f}" if value_mm == int(value_mm) else f"{value_mm:.1f}"

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F:
            self.fit_to_content()
        elif event.key() == Qt.Key.Key_Plus or event.key() == Qt.Key.Key_Equal:
            self._apply_zoom(1.15)
        elif event.key() == Qt.Key.Key_Minus:
            self._apply_zoom(1.0 / 1.15)
        else:
            super().keyPressEvent(event)
