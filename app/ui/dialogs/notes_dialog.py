"""Notes dialog — view, add, delete notes for a design or simulation.

Backend: DesignRepository.add_note / get_notes / delete_note (already implemented).

Reference: Phase-06 spec.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from app.core.i18n import t
from app.database.design_repository import DesignRepository


class NotesDialog(QDialog):
    """Dialog for managing notes attached to a design or simulation."""

    def __init__(
        self,
        repo: DesignRepository,
        parent_type: str,
        parent_id: str,
        parent=None,
    ):
        super().__init__(parent)
        self._repo = repo
        self._parent_type = parent_type
        self._parent_id = parent_id
        self.setWindowTitle(t("dialogs.notes_title", "Notes"))
        self.setMinimumSize(450, 400)
        self._build_ui()
        self._load_notes()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Input area
        input_layout = QHBoxLayout()
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(t("dialogs.notes_placeholder", "Write a new note..."))
        self._text_edit.setMaximumHeight(80)
        input_layout.addWidget(self._text_edit)

        self._btn_add = QPushButton(t("dialogs.notes_add", "Add"))
        self._btn_add.setFixedWidth(60)
        self._btn_add.clicked.connect(self._add_note)
        input_layout.addWidget(self._btn_add, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(input_layout)

        # Notes list
        layout.addWidget(QLabel(t("dialogs.notes_existing", "Existing Notes:")))
        self._list = QListWidget()
        layout.addWidget(self._list)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_notes(self) -> None:
        """Reload notes from database."""
        self._list.clear()
        notes = self._repo.get_notes(self._parent_type, self._parent_id)
        for note in notes:
            item = QListWidgetItem()
            widget = self._create_note_widget(note)
            item.setSizeHint(widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)

    def _create_note_widget(self, note: dict) -> QWidget:
        """Create a widget for a single note with delete button."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)

        text = QLabel(f"<b>{note['created_at'][:16]}</b>  {note['content']}")
        text.setWordWrap(True)
        text.setStyleSheet("color: #F8FAFC; font-size: 9pt;")
        layout.addWidget(text, 1)

        btn_del = QPushButton("\u2715")
        btn_del.setFixedSize(24, 24)
        btn_del.setToolTip(t("dialogs.notes_delete_tooltip", "Delete note"))
        btn_del.setStyleSheet(
            "QPushButton { color: #EF4444; border: none; font-weight: bold; }"
            "QPushButton:hover { color: #F87171; }"
        )
        note_id = note["id"]
        btn_del.clicked.connect(lambda _, nid=note_id: self._delete_note(nid))
        layout.addWidget(btn_del)

        return widget

    def _add_note(self) -> None:
        """Add a new note from the text input."""
        content = self._text_edit.toPlainText().strip()
        if not content:
            return
        self._repo.add_note(self._parent_type, self._parent_id, content)
        self._text_edit.clear()
        self._load_notes()

    def _delete_note(self, note_id: str) -> None:
        """Delete a note by ID and refresh."""
        self._repo.delete_note(note_id)
        self._load_notes()
