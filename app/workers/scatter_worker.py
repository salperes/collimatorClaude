"""Scatter simulation worker — background thread for scatter ray-tracing.

Runs ScatterTracer.simulate_scatter off the UI thread.

Reference: Phase-07 spec — ScatterWorker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from app.core.scatter_tracer import ScatterResult, ScatterTracer
    from app.models.geometry import CollimatorGeometry
    from app.models.simulation import ComptonConfig, SimulationResult


class ScatterWorker(QThread):
    """Background thread for Compton scatter simulation.

    Usage::

        worker = ScatterWorker(scatter_tracer)
        worker.setup(geometry, energy_keV, num_rays, config, primary_result)
        worker.progress.connect(on_progress)
        worker.result_ready.connect(on_result)
        worker.error_occurred.connect(on_error)
        worker.start()
    """

    progress = pyqtSignal(int)
    result_ready = pyqtSignal(object)   # ScatterResult
    error_occurred = pyqtSignal(str)

    def __init__(self, scatter_tracer: ScatterTracer, parent=None):
        super().__init__(parent)
        self._scatter_tracer = scatter_tracer
        self._geometry: CollimatorGeometry | None = None
        self._energy_keV: float = 100.0
        self._num_rays: int = 100
        self._config: ComptonConfig | None = None
        self._primary_result: SimulationResult | None = None
        self._step_size_cm: float = 0.1
        self._cancelled = False

    def setup(
        self,
        geometry: CollimatorGeometry,
        energy_keV: float,
        num_rays: int,
        config: ComptonConfig,
        primary_result: SimulationResult | None = None,
        step_size_cm: float = 0.1,
    ) -> None:
        """Configure simulation parameters before starting.

        Args:
            geometry: Collimator geometry [mm, degree].
            energy_keV: Photon energy [keV].
            num_rays: Number of primary rays.
            config: Compton configuration.
            primary_result: Pre-computed primary simulation for SPR.
            step_size_cm: Material walk step size [cm].
        """
        self._geometry = geometry
        self._energy_keV = energy_keV
        self._num_rays = num_rays
        self._config = config
        self._primary_result = primary_result
        self._step_size_cm = step_size_cm
        self._cancelled = False

    def cancel(self) -> None:
        """Request graceful cancellation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute scatter simulation in background thread."""
        try:
            if self._geometry is None or self._config is None:
                self.error_occurred.emit("Scatter parametreleri ayarlanmadi.")
                return

            def _progress_callback(pct: int) -> None:
                if self._cancelled:
                    raise InterruptedError("Scatter simulasyonu iptal edildi.")
                self.progress.emit(pct)

            result = self._scatter_tracer.simulate_scatter(
                geometry=self._geometry,
                energy_keV=self._energy_keV,
                num_primary_rays=self._num_rays,
                config=self._config,
                primary_result=self._primary_result,
                step_size_cm=self._step_size_cm,
                progress_callback=_progress_callback,
            )

            if self._cancelled:
                return

            self.result_ready.emit(result)

        except InterruptedError:
            pass
        except Exception as e:
            self.error_occurred.emit(str(e))
