"""Projection worker — background thread for projection calculations.

Runs ProjectionEngine methods off the UI thread to prevent blocking.

Reference: Phase-03.5 spec — Worker Thread.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from app.core.projection_engine import ProjectionEngine
    from app.models.geometry import FocalSpotDistribution
    from app.models.phantom import AnyPhantom
    from app.models.projection import ProjectionResult


class ProjectionWorker(QThread):
    """Background thread for running projection calculations.

    Emits result_ready with the ProjectionResult on success,
    error_occurred with an error message on failure.

    Usage:
        worker = ProjectionWorker(engine)
        worker.setup(phantom, src_y, det_y, focal_mm, focal_dist, energy)
        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        worker.start()
    """

    result_ready = pyqtSignal(object)  # ProjectionResult
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        engine: ProjectionEngine,
        parent=None,
    ):
        super().__init__(parent)
        self._engine = engine
        self._phantom: AnyPhantom | None = None
        self._src_y_mm: float = 0.0
        self._det_y_mm: float = 0.0
        self._focal_spot_mm: float = 1.0
        self._focal_spot_dist: FocalSpotDistribution | None = None
        self._energy_keV: float = 100.0

    def setup(
        self,
        phantom: AnyPhantom,
        src_y_mm: float,
        det_y_mm: float,
        focal_spot_mm: float,
        focal_spot_dist: FocalSpotDistribution,
        energy_keV: float,
    ) -> None:
        """Configure parameters before starting the thread.

        Must be called before start().
        """
        self._phantom = phantom
        self._src_y_mm = src_y_mm
        self._det_y_mm = det_y_mm
        self._focal_spot_mm = focal_spot_mm
        self._focal_spot_dist = focal_spot_dist
        self._energy_keV = energy_keV

    def run(self) -> None:
        """Execute projection calculation in background thread."""
        try:
            if self._phantom is None or self._focal_spot_dist is None:
                self.error_occurred.emit("Phantom veya parametreler ayarlanmadi.")
                return

            result = self._engine.project(
                self._phantom,
                self._src_y_mm,
                self._det_y_mm,
                self._focal_spot_mm,
                self._focal_spot_dist,
                self._energy_keV,
            )
            self.result_ready.emit(result)

        except Exception as e:
            self.error_occurred.emit(str(e))
