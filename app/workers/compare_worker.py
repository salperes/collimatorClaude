"""Compare worker — background thread for multi-energy beam simulation.

Runs BeamSimulation.compare_energies off the UI thread.

Reference: FRD §4.2 FR-2.2 — Energy comparison.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from app.core.beam_simulation import BeamSimulation
    from app.models.geometry import CollimatorGeometry


class CompareWorker(QThread):
    """Background thread for multi-energy beam profile comparison.

    Emits progress (0-100), result_ready with dict[float, SimulationResult],
    error_occurred on failure.
    """

    progress = pyqtSignal(int)
    result_ready = pyqtSignal(object)  # dict[float, SimulationResult]
    error_occurred = pyqtSignal(str)

    def __init__(self, beam_sim: BeamSimulation, parent=None):
        super().__init__(parent)
        self._beam_sim = beam_sim
        self._geometry: CollimatorGeometry | None = None
        self._energies: list[float] = []
        self._num_rays: int = 360

    def setup(
        self,
        geometry: CollimatorGeometry,
        energies_keV: list[float],
        num_rays: int = 360,
    ) -> None:
        """Configure comparison parameters before starting."""
        self._geometry = geometry
        self._energies = energies_keV
        self._num_rays = num_rays

    def run(self) -> None:
        """Execute multi-energy comparison in background thread."""
        try:
            if self._geometry is None:
                self.error_occurred.emit("Geometri ayarlanmadi.")
                return

            results = self._beam_sim.compare_energies(
                geometry=self._geometry,
                energies_keV=self._energies,
                num_rays=self._num_rays,
                include_buildup=True,
                progress_callback=lambda p: self.progress.emit(p),
            )

            self.result_ready.emit(results)

        except Exception as e:
            self.error_occurred.emit(str(e))
