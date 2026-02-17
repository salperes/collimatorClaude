"""Isodose map worker — background thread for 2D dose computation.

Runs IsodoseEngine.compute off the UI thread.

Reference: Phase 8 — Isodose Map Feature.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from app.core.isodose_engine import IsodoseEngine, IsodoseResult
    from app.models.geometry import CollimatorGeometry


class IsodoseWorker(QThread):
    """Background thread for 2D isodose map computation.

    Usage::

        worker = IsodoseWorker(isodose_engine)
        worker.setup(geometry, energy_keV, nx=120, ny=80)
        worker.progress.connect(on_progress)
        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        worker.start()
    """

    progress = pyqtSignal(int)
    result_ready = pyqtSignal(object)   # IsodoseResult
    error_occurred = pyqtSignal(str)

    def __init__(self, isodose_engine: IsodoseEngine, parent=None):
        super().__init__(parent)
        self._engine = isodose_engine
        self._geometry: CollimatorGeometry | None = None
        self._energy_keV: float = 100.0
        self._nx: int = 120
        self._ny: int = 80
        self._include_buildup: bool = False
        self._include_air: bool = True
        self._include_inverse_sq: bool = True
        self._cancelled = False

    def setup(
        self,
        geometry: CollimatorGeometry,
        energy_keV: float,
        nx: int = 120,
        ny: int = 80,
        include_buildup: bool = False,
        include_air: bool = True,
        include_inverse_sq: bool = True,
    ) -> None:
        """Configure computation parameters before starting.

        Args:
            geometry: Collimator geometry [mm, degree].
            energy_keV: Photon energy [keV].
            nx: X grid resolution.
            ny: Y grid resolution.
            include_buildup: Apply build-up factor correction.
            include_air: Apply air attenuation along ray path.
            include_inverse_sq: Apply 1/r^2 geometric divergence.
        """
        self._geometry = geometry
        self._energy_keV = energy_keV
        self._nx = nx
        self._ny = ny
        self._include_buildup = include_buildup
        self._include_air = include_air
        self._include_inverse_sq = include_inverse_sq
        self._cancelled = False

    def cancel(self) -> None:
        """Request graceful cancellation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute isodose computation in background thread."""
        try:
            if self._geometry is None:
                self.error_occurred.emit("Isodose parametreleri ayarlanmadi.")
                return

            def _progress_callback(pct: int) -> None:
                if self._cancelled:
                    raise InterruptedError("Isodose hesabi iptal edildi.")
                self.progress.emit(pct)

            result = self._engine.compute(
                geometry=self._geometry,
                energy_keV=self._energy_keV,
                nx=self._nx,
                ny=self._ny,
                include_buildup=self._include_buildup,
                include_air=self._include_air,
                include_inverse_sq=self._include_inverse_sq,
                progress_callback=_progress_callback,
            )

            if self._cancelled:
                return

            self.result_ready.emit(result)

        except InterruptedError:
            pass
        except Exception as e:
            self.error_occurred.emit(str(e))
