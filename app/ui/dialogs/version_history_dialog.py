"""Version history dialog — view and restore design versions.

Reference: Phase-06 spec — FR-1.6.3.
"""

from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.core.i18n import t
from app.database.design_repository import DesignRepository


class VersionHistoryDialog(QDialog):
    """Dialog showing version list with restore capability."""

    def __init__(
        self,
        repo: DesignRepository,
        design_id: str,
        parent=None,
    ):
        super().__init__(parent)
        self._repo = repo
        self._design_id = design_id
        self.restored_version: int | None = None

        name = repo.get_design_name(design_id)
        self.setWindowTitle(
            t("dialogs.version_history_title", "Version History \u2014 {name}").format(name=name)
        )
        self.setMinimumSize(500, 350)

        layout = QVBoxLayout(self)

        # Version table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            t("dialogs.version_col_version", "Version"),
            t("dialogs.version_col_date", "Date"),
            t("dialogs.version_col_note", "Change Note"),
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_restore = QPushButton(t("dialogs.version_restore", "Restore This Version"))
        self._btn_restore.clicked.connect(self._on_restore)
        btn_layout.addWidget(self._btn_restore)

        self._btn_close = QPushButton(t("common.close", "Close"))
        self._btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_close)

        layout.addLayout(btn_layout)

        self._versions = []
        self._refresh()

    def _refresh(self) -> None:
        """Load version history from DB."""
        self._versions = self._repo.get_version_history(self._design_id)
        self._table.setRowCount(len(self._versions))
        for row, v in enumerate(self._versions):
            self._table.setItem(row, 0, QTableWidgetItem(str(v.version_number)))
            self._table.setItem(row, 1, QTableWidgetItem(v.created_at[:16]))
            self._table.setItem(row, 2, QTableWidgetItem(v.change_note))

    def _on_restore(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            ver = self._versions[row]
            self._repo.restore_version(self._design_id, ver.version_number)
            self.restored_version = ver.version_number
            self.accept()
