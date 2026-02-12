"""Export worker — QThread for heavy export operations (PDF, CDT).

Follows the same pattern as SimulationWorker / ProjectionWorker.

Reference: Phase-06 spec.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from app.export.pdf_report import PdfReportExporter
from app.models.geometry import CollimatorGeometry
from app.models.simulation import SimulationResult


class ExportWorker(QThread):
    """Background thread for PDF report generation.

    Signals:
        progress(int): 0-100%.
        result_ready(str): Output file path on success.
        error_occurred(str): Error message on failure.
    """

    progress = pyqtSignal(int)
    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._geometry: CollimatorGeometry | None = None
        self._result: SimulationResult | None = None
        self._output_path: str = ""
        self._sections: list[str] = []
        self._chart_images: dict[str, bytes] = {}
        self._canvas_image: bytes | None = None

    def setup_pdf(
        self,
        geometry: CollimatorGeometry,
        result: SimulationResult | None,
        output_path: str,
        sections: list[str],
        chart_images: dict[str, bytes],
        canvas_image: bytes | None = None,
    ) -> None:
        """Configure PDF export parameters.

        Args:
            geometry: Collimator design.
            result: Simulation result (or None).
            output_path: Destination file path.
            sections: Section codes to include.
            chart_images: Pre-rendered chart images.
            canvas_image: Pre-rendered canvas screenshot.
        """
        self._geometry = geometry
        self._result = result
        self._output_path = output_path
        self._sections = sections
        self._chart_images = chart_images
        self._canvas_image = canvas_image

    def run(self) -> None:
        """Execute PDF generation in background thread."""
        try:
            self.progress.emit(10)
            exporter = PdfReportExporter()
            self.progress.emit(30)

            exporter.generate_report(
                geometry=self._geometry,
                simulation_result=self._result,
                output_path=self._output_path,
                include_sections=self._sections,
                chart_images=self._chart_images,
                canvas_image=self._canvas_image,
            )

            self.progress.emit(100)
            self.result_ready.emit(self._output_path)

        except Exception as e:
            self.error_occurred.emit(str(e))
