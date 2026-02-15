"""Save design dialog — name, description, tags input.

Reference: Phase-06 spec — FR-1.6.1.
"""

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit,
)

from app.core.i18n import t


class SaveDesignDialog(QDialog):
    """Dialog for first-time save: name, description, tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dialogs.save_title", "Save Design"))
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(t("dialogs.save_name_placeholder", "Design name"))
        layout.addRow(t("dialogs.save_name", "Name:"), self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText(t("dialogs.save_desc_placeholder", "Description (optional)"))
        self._desc_edit.setMaximumHeight(80)
        layout.addRow(t("dialogs.save_desc", "Description:"), self._desc_edit)

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText(t("dialogs.save_tags_placeholder", "Tags (comma separated)"))
        layout.addRow(t("dialogs.save_tags", "Tags:"), self._tags_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def set_name(self, name: str) -> None:
        """Pre-fill the name field."""
        self._name_edit.setText(name)

    def get_values(self) -> tuple[str, str, list[str]]:
        """Return (name, description, tags)."""
        name = self._name_edit.text().strip() or t("dialogs.save_default_name", "New Design")
        desc = self._desc_edit.toPlainText().strip()
        tags_text = self._tags_edit.text().strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()] if tags_text else []
        return name, desc, tags
