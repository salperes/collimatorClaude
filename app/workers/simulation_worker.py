"""Simulation worker — background thread for ray-tracing simulation.

Runs BeamSimulation.calculate_beam_profile off the UI thread
to prevent blocking.

Reference: Phase 4 spec — SimulationWorker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from app.core.beam_simulation import BeamSimulation
    from app.models.geometry import CollimatorGeometry
    from app.models.simulation import SimulationResult


class SimulationWorker(QThread):
    """Background thread for beam profile simulation.

    Emits progress (0-100), result_ready on success,
    error_occurred on failure.

    Usage:
        worker = SimulationWorker(beam_sim)
        worker.setup(geometry, energy_keV, num_rays, include_buildup)
        worker.progress.connect(on_progress)
        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        worker.start()
    """

    progress = pyqtSignal(int)            # 0-100%
    result_ready = pyqtSignal(object)     # SimulationResult
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        beam_sim: BeamSimulation,
        parent=None,
    ):
        super().__init__(parent)
        self._beam_sim = beam_sim
        self._geometry: CollimatorGeometry | None = None
        self._energy_keV: float = 100.0
        self._num_rays: int = 360
        self._include_buildup: bool = True
        self._cancelled = False

    def setup(
        self,
        geometry: CollimatorGeometry,
        energy_keV: float,
        num_rays: int = 360,
        include_buildup: bool = True,
    ) -> None:
        """Configure simulation parameters before starting.

        Must be called before start().
        """
        self._geometry = geometry
        self._energy_keV = energy_keV
        self._num_rays = num_rays
        self._include_buildup = include_buildup
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the running simulation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute beam simulation in background thread."""
        try:
            if self._geometry is None:
                self.error_occurred.emit("Geometri ayarlanmadi.")
                return

            def _progress_callback(pct: int) -> None:
                if self._cancelled:
                    raise InterruptedError("Simulasyon iptal edildi.")
                self.progress.emit(pct)

            result = self._beam_sim.calculate_beam_profile(
                geometry=self._geometry,
                energy_keV=self._energy_keV,
                num_rays=self._num_rays,
                include_buildup=self._include_buildup,
                progress_callback=_progress_callback,
            )

            if self._cancelled:
                return

            self.result_ready.emit(result)

        except InterruptedError:
            pass  # cancelled silently
        except Exception as e:
            self.error_occurred.emit(str(e))
