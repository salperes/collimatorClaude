"""Export dialog — format selection, PDF options, output path.

Reference: Phase-06 spec — FR-4.1.5.
"""

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QVBoxLayout,
)


class ExportDialog(QDialog):
    """Universal export dialog with format selection and options."""

    def __init__(
        self,
        has_simulation: bool = False,
        has_compton: bool = False,
        has_validation: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Disa Aktar")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Format selection
        fmt_group = QGroupBox("Format")
        fmt_layout = QVBoxLayout(fmt_group)

        self._radio_pdf = QRadioButton("PDF Rapor")
        self._radio_pdf.setChecked(True)
        self._radio_pdf.toggled.connect(self._on_format_changed)
        fmt_layout.addWidget(self._radio_pdf)

        self._radio_csv = QRadioButton("CSV (Isin Profili)")
        self._radio_csv.setEnabled(has_simulation)
        fmt_layout.addWidget(self._radio_csv)

        self._radio_json = QRadioButton("JSON (Geometri)")
        fmt_layout.addWidget(self._radio_json)

        self._radio_png = QRadioButton("PNG (Canvas Goruntsu)")
        fmt_layout.addWidget(self._radio_png)

        self._radio_svg = QRadioButton("SVG (Vektor Goruntu)")
        fmt_layout.addWidget(self._radio_svg)

        self._radio_cdt = QRadioButton("CDT Proje Dosyasi")
        fmt_layout.addWidget(self._radio_cdt)

        layout.addWidget(fmt_group)

        # PDF sections
        self._pdf_group = QGroupBox("PDF Bolumleri")
        pdf_layout = QVBoxLayout(self._pdf_group)

        self._section_checks: dict[str, QCheckBox] = {}
        sections = [
            ("A", "Geometri Ozeti"),
            ("B", "Stage & Katman Yapisi"),
            ("C", "Zayiflama Analizi"),
            ("D", "Build-up Analizi"),
            ("E", "Isin Profili"),
            ("F", "Kalite Metrikleri"),
            ("G", "Compton Analizi"),
            ("H", "Model Varsayimlari"),
            ("I", "Dogrulama Ozeti"),
        ]
        for code, label in sections:
            cb = QCheckBox(f"{code} — {label}")
            cb.setChecked(True)
            if code in ("E", "F") and not has_simulation:
                cb.setChecked(False)
                cb.setEnabled(False)
            if code == "G" and not has_compton:
                cb.setChecked(False)
                cb.setEnabled(False)
            if code == "I" and not has_validation:
                cb.setChecked(False)
                cb.setEnabled(False)
            self._section_checks[code] = cb
            pdf_layout.addWidget(cb)

        layout.addWidget(self._pdf_group)

        # Output path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Kayit Yeri:"))
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        path_layout.addWidget(self._path_edit)
        self._btn_browse = QPushButton("Gozat...")
        self._btn_browse.clicked.connect(self._browse)
        path_layout.addWidget(self._btn_browse)
        layout.addLayout(path_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_format_changed()

    def _on_format_changed(self) -> None:
        """Show/hide PDF options based on format selection."""
        self._pdf_group.setVisible(self._radio_pdf.isChecked())

    def _browse(self) -> None:
        """Open file dialog for output path."""
        if self._radio_pdf.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "PDF Kaydet", "", "PDF Dosyalari (*.pdf)"
            )
        elif self._radio_csv.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "CSV Kaydet", "", "CSV Dosyalari (*.csv)"
            )
        elif self._radio_json.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "JSON Kaydet", "", "JSON Dosyalari (*.json)"
            )
        elif self._radio_png.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "PNG Kaydet", "", "PNG Dosyalari (*.png)"
            )
        elif self._radio_svg.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "SVG Kaydet", "", "SVG Dosyalari (*.svg)"
            )
        elif self._radio_cdt.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "CDT Kaydet", "", "CDT Dosyalari (*.cdt)"
            )
        else:
            return

        if path:
            self._path_edit.setText(path)

    def _on_accept(self) -> None:
        if self._path_edit.text():
            self.accept()

    def get_format(self) -> str:
        """Return selected format: 'pdf', 'csv', 'json', 'png', 'cdt'."""
        if self._radio_pdf.isChecked():
            return "pdf"
        if self._radio_csv.isChecked():
            return "csv"
        if self._radio_json.isChecked():
            return "json"
        if self._radio_png.isChecked():
            return "png"
        if self._radio_svg.isChecked():
            return "svg"
        if self._radio_cdt.isChecked():
            return "cdt"
        return "pdf"

    def get_output_path(self) -> str:
        """Return selected output file path."""
        return self._path_edit.text()

    def get_pdf_sections(self) -> list[str]:
        """Return list of selected PDF section codes."""
        return [code for code, cb in self._section_checks.items() if cb.isChecked()]
