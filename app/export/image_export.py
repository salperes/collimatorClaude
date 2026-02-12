"""Image export — canvas PNG and thumbnail generation.

Uses QGraphicsScene.render() for high-quality output.

Reference: Phase-06 spec — FR-4.3.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QGraphicsScene


class ImageExporter:
    """Canvas image export operations."""

    def export_canvas_png(
        self,
        scene: QGraphicsScene,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        """Render scene to high-resolution PNG.

        Args:
            scene: The QGraphicsScene to render.
            output_path: Destination file path (.png).
            width: Image width in pixels.
            height: Image height in pixels.
        """
        image = self._render_scene(scene, width, height)
        image.save(output_path, "PNG")

    def generate_thumbnail(
        self,
        scene: QGraphicsScene,
        width: int = 200,
        height: int = 150,
    ) -> bytes:
        """Render scene to thumbnail PNG bytes.

        Args:
            scene: The QGraphicsScene to render.
            width: Thumbnail width in pixels.
            height: Thumbnail height in pixels.

        Returns:
            PNG image data as bytes.
        """
        from PyQt6.QtCore import QBuffer, QIODevice

        image = self._render_scene(scene, width, height)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(buffer.data())

    def export_canvas_svg(
        self,
        scene: QGraphicsScene,
        output_path: str,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        """Render scene to SVG file.

        Args:
            scene: The QGraphicsScene to render.
            output_path: Destination file path (.svg).
            width: SVG width in pixels.
            height: SVG height in pixels.
        """
        from PyQt6.QtCore import QRectF
        from PyQt6.QtSvg import QSvgGenerator

        generator = QSvgGenerator()
        generator.setFileName(output_path)
        generator.setSize(QRectF(0, 0, width, height).size().toSize())
        generator.setViewBox(QRectF(0, 0, width, height))
        generator.setTitle("Collimator Design")

        painter = QPainter(generator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if hasattr(scene, "content_rect"):
            source_rect = scene.content_rect()
        else:
            source_rect = scene.sceneRect()
        if source_rect.isEmpty():
            source_rect = scene.itemsBoundingRect()

        margin = max(source_rect.width(), source_rect.height()) * 0.05
        source_rect.adjust(-margin, -margin, margin, margin)

        scene.render(painter, QRectF(0, 0, width, height), source_rect)
        painter.end()

    def _render_scene(
        self,
        scene: QGraphicsScene,
        width: int,
        height: int,
    ) -> QImage:
        """Render the scene to a QImage."""
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.white)

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use content rect if available, otherwise scene rect
        if hasattr(scene, "content_rect"):
            source_rect = scene.content_rect()
        else:
            source_rect = scene.sceneRect()

        if source_rect.isEmpty():
            source_rect = scene.itemsBoundingRect()

        # Add margin
        margin = max(source_rect.width(), source_rect.height()) * 0.05
        source_rect.adjust(-margin, -margin, margin, margin)

        scene.render(painter, QRectF(0, 0, width, height), source_rect)
        painter.end()
        return image
