"""Validation dialog — run physics validation tests and show results.

Displays progress during execution, then a results table with PASS/FAIL
status and a button to export as PDF report.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.validation_runner import ValidationSummary
from app.workers.validation_worker import ValidationWorker


_PASS_COLOR = QColor("#DCFCE7")
_FAIL_COLOR = QColor("#FEE2E2")
_SKIP_COLOR = QColor("#FEF9C3")


class ValidationDialog(QDialog):
    """Dialog for running validation tests and displaying results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fizik Motoru Dogrulama")
        self.setMinimumSize(800, 600)
        self.resize(900, 650)

        self._summary: ValidationSummary | None = None
        self._worker: ValidationWorker | None = None
        self._build_ui()
        self._start_validation()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Progress section
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        layout.addWidget(self._progress_bar)

        self._lbl_status = QLabel("Dogrulama testleri baslatiliyor...")
        layout.addWidget(self._lbl_status)

        # Results table (hidden until complete)
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "Test ID", "Grup", "Bizim", "Referans", "Fark%", "Tolerans%", "Durum",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setVisible(False)
        layout.addWidget(self._table)

        # Summary label
        self._lbl_summary = QLabel("")
        self._lbl_summary.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self._lbl_summary)

        # Buttons
        btn_layout = QHBoxLayout()

        self._btn_pdf = QPushButton("PDF Rapor Kaydet")
        self._btn_pdf.setEnabled(False)
        self._btn_pdf.clicked.connect(self._on_save_pdf)
        btn_layout.addWidget(self._btn_pdf)

        btn_layout.addStretch()

        self._btn_close = QPushButton("Kapat")
        self._btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self._btn_close)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Validation execution
    # ------------------------------------------------------------------

    def _start_validation(self) -> None:
        self._worker = ValidationWorker(self)
        self._worker.progress.connect(self._on_progress)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_progress(self, pct: int, test_id: str) -> None:
        self._progress_bar.setValue(pct)
        self._lbl_status.setText(f"Calisan test: {test_id}")

    def _on_result(self, summary: ValidationSummary) -> None:
        self._summary = summary
        self._progress_bar.setValue(100)
        self._progress_bar.setVisible(False)

        # Update status
        if summary.failed == 0:
            self._lbl_status.setText(
                f"Dogrulama tamamlandi — TUM TESTLER BASARILI ({summary.duration_s:.1f}s)"
            )
            self._lbl_status.setStyleSheet("color: #166534; font-weight: bold;")
        else:
            self._lbl_status.setText(
                f"Dogrulama tamamlandi — {summary.failed} TEST BASARISIZ ({summary.duration_s:.1f}s)"
            )
            self._lbl_status.setStyleSheet("color: #991B1B; font-weight: bold;")

        # Summary
        self._lbl_summary.setText(
            f"Toplam: {summary.total}  |  Basarili: {summary.passed}  |  "
            f"Basarisiz: {summary.failed}  |  Atlanan: {summary.skipped}  |  "
            f"xraylib: {'v' + summary.xraylib_version if summary.xraylib_available else 'yok'}"
        )

        # Populate table
        self._table.setRowCount(len(summary.results))
        for row, r in enumerate(summary.results):
            # Test ID
            self._table.setItem(row, 0, QTableWidgetItem(r.test_id))
            self._table.setItem(row, 1, QTableWidgetItem(r.group))

            # Values
            ours_s = self._fmt(r.our_value)
            ref_s = self._fmt(r.ref_value)
            diff_s = f"{r.diff_pct:.2f}" if not r.skipped else "-"
            tol_s = f"{r.tolerance_pct:.1f}" if r.tolerance_pct > 0 else "exact"

            self._table.setItem(row, 2, self._aligned_item(ours_s))
            self._table.setItem(row, 3, self._aligned_item(ref_s))
            self._table.setItem(row, 4, self._aligned_item(diff_s))
            self._table.setItem(row, 5, self._aligned_item(tol_s))

            # Status with color
            if r.skipped:
                status_item = QTableWidgetItem("SKIP")
                bg = _SKIP_COLOR
            elif r.passed:
                status_item = QTableWidgetItem("PASS")
                bg = _PASS_COLOR
            else:
                status_item = QTableWidgetItem("FAIL")
                bg = _FAIL_COLOR

            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setBackground(bg)
            self._table.setItem(row, 6, status_item)

        self._table.resizeColumnsToContents()
        self._table.setVisible(True)
        self._btn_pdf.setEnabled(True)

    def _on_error(self, error: str) -> None:
        self._progress_bar.setVisible(False)
        self._lbl_status.setText(f"Hata: {error}")
        self._lbl_status.setStyleSheet("color: #991B1B;")

    # ------------------------------------------------------------------
    # PDF export
    # ------------------------------------------------------------------

    def _on_save_pdf(self) -> None:
        if self._summary is None:
            return

        from datetime import datetime as dt
        default_name = f"CDT_Validation_{dt.now().strftime('%Y%m%d_%H%M')}.pdf"

        path, _ = QFileDialog.getSaveFileName(
            self, "PDF Rapor Kaydet", default_name,
            "PDF Files (*.pdf)",
        )
        if not path:
            return

        try:
            from app.export.validation_report import ValidationReportExporter
            exporter = ValidationReportExporter()
            exporter.generate_report(self._summary, path)
            QMessageBox.information(
                self, "Basarili",
                f"Dogrulama raporu kaydedildi:\n{path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Hata",
                f"PDF olusturulamadi:\n{e}",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(val: float) -> str:
        if val == 0:
            return "0"
        if abs(val) < 0.001 or abs(val) > 1e4:
            return f"{val:.4e}"
        return f"{val:.4f}"

    @staticmethod
    def _aligned_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
