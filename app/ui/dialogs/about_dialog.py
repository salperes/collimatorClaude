"""About dialog — application info and credits.

Reference: Phase-06 spec.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
)
from PyQt6.QtCore import Qt

from app.constants import APP_NAME, APP_VERSION, APP_ORGANIZATION


class AboutDialog(QDialog):
    """Simple 'About' dialog showing app info and tech stack."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hakkinda")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # App name
        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #3B82F6;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        ver = QLabel(f"Versiyon {APP_VERSION}")
        ver.setStyleSheet("font-size: 11pt; color: #94A3B8;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        # Organization
        org = QLabel(APP_ORGANIZATION)
        org.setStyleSheet("font-size: 10pt; color: #F8FAFC;")
        org.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(org)

        layout.addSpacing(12)

        # Tech stack
        tech = QLabel(
            "Python {py_ver} | PyQt6 | NumPy | SciPy\n"
            "pyqtgraph | matplotlib | ReportLab | SQLite".format(
                py_ver=f"{sys.version_info.major}.{sys.version_info.minor}",
            )
        )
        tech.setStyleSheet("font-size: 9pt; color: #94A3B8;")
        tech.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tech)

        layout.addSpacing(8)

        # Copyright
        copy_label = QLabel(
            "X-Ray TIR kolimator tasarim, analiz ve\n"
            "optimizasyon araci."
        )
        copy_label.setStyleSheet("font-size: 9pt; color: #64748B;")
        copy_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copy_label)

        layout.addStretch()

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
