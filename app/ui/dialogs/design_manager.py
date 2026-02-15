"""Design manager dialog — browse, search, open/delete designs.

Reference: Phase-06 spec — FR-1.6.2.
"""

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

from app.core.i18n import t
from app.database.design_repository import DesignRepository


class DesignManagerDialog(QDialog):
    """Design browser / open dialog (Ctrl+O)."""

    def __init__(self, repo: DesignRepository, parent=None):
        super().__init__(parent)
        self._repo = repo
        self.selected_design_id: str | None = None

        self.setWindowTitle(t("dialogs.open_title", "Open Design"))
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        # Filter bar
        filter_layout = QHBoxLayout()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(t("dialogs.open_search", "Search..."))
        self._search_edit.textChanged.connect(self._refresh)
        filter_layout.addWidget(self._search_edit)

        self._type_combo = QComboBox()
        self._type_combo.addItem(t("dialogs.open_all_types", "All Types"), "")
        self._type_combo.addItem("Fan Beam", "fan_beam")
        self._type_combo.addItem("Pencil Beam", "pencil_beam")
        self._type_combo.addItem("Slit", "slit")
        self._type_combo.currentIndexChanged.connect(self._refresh)
        filter_layout.addWidget(self._type_combo)

        self._fav_check = QCheckBox(t("dialogs.open_favorites", "Favorites"))
        self._fav_check.toggled.connect(self._refresh)
        filter_layout.addWidget(self._fav_check)

        layout.addLayout(filter_layout)

        # Design table
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            t("dialogs.open_col_name", "Name"),
            t("dialogs.open_col_type", "Type"),
            t("dialogs.open_col_tags", "Tags"),
            t("dialogs.open_col_updated", "Updated"),
            t("dialogs.open_col_favorite", "Favorite"),
        ])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.doubleClicked.connect(self._on_open)
        layout.addWidget(self._table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_delete = QPushButton(t("dialogs.open_delete", "Delete"))
        self._btn_delete.clicked.connect(self._on_delete)
        btn_layout.addWidget(self._btn_delete)

        self._btn_fav = QPushButton(t("dialogs.open_favorite", "Favorite"))
        self._btn_fav.clicked.connect(self._on_toggle_favorite)
        btn_layout.addWidget(self._btn_fav)

        self._btn_open = QPushButton(t("dialogs.open_open", "Open"))
        self._btn_open.setDefault(True)
        self._btn_open.clicked.connect(self._on_open)
        btn_layout.addWidget(self._btn_open)

        self._btn_cancel = QPushButton(t("common.cancel", "Cancel"))
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        layout.addLayout(btn_layout)

        self._designs = []
        self._refresh()

    def _refresh(self) -> None:
        """Reload design list with current filters."""
        search = self._search_edit.text().strip() or None
        filter_type = self._type_combo.currentData() or None
        fav_only = self._fav_check.isChecked()

        self._designs = self._repo.list_designs(
            filter_type=filter_type,
            favorites_only=fav_only,
            search_text=search,
        )

        self._table.setRowCount(len(self._designs))
        for row, d in enumerate(self._designs):
            self._table.setItem(row, 0, QTableWidgetItem(d.name))
            self._table.setItem(row, 1, QTableWidgetItem(d.collimator_type))
            self._table.setItem(row, 2, QTableWidgetItem(", ".join(d.tags)))
            self._table.setItem(row, 3, QTableWidgetItem(d.updated_at[:16]))
            fav_text = "\u2605" if d.is_favorite else ""
            item = QTableWidgetItem(fav_text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, item)

    def _selected_row(self) -> int | None:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _on_open(self) -> None:
        row = self._selected_row()
        if row is not None:
            self.selected_design_id = self._designs[row].id
            self.accept()

    def _on_delete(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._repo.delete_design(self._designs[row].id)
            self._refresh()

    def _on_toggle_favorite(self) -> None:
        row = self._selected_row()
        if row is not None:
            self._repo.toggle_favorite(self._designs[row].id)
            self._refresh()
