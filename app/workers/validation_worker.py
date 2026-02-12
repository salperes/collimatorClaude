"""Validation worker — background thread for physics validation tests.

Runs ValidationRunner off the UI thread to prevent blocking.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class ValidationWorker(QThread):
    """Background thread for validation test execution.

    Signals:
        progress(int, str): 0-100% and current test id.
        result_ready(object): ValidationSummary on success.
        error_occurred(str): Error message on failure.
    """

    progress = pyqtSignal(int, str)
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    def run(self) -> None:
        """Execute validation checks in background thread."""
        try:
            from app.core.validation_runner import ValidationRunner

            runner = ValidationRunner(
                progress_callback=self._on_progress,
                cancelled_check=lambda: self._cancelled,
            )
            summary = runner.run_all()

            if not self._cancelled:
                self.result_ready.emit(summary)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _on_progress(self, pct: int, test_id: str) -> None:
        if not self._cancelled:
            self.progress.emit(pct, test_id)
