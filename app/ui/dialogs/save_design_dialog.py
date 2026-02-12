"""Save design dialog — name, description, tags input.

Reference: Phase-06 spec — FR-1.6.1.
"""

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit,
)


class SaveDesignDialog(QDialog):
    """Dialog for first-time save: name, description, tags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tasarimi Kaydet")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Tasarim adi")
        layout.addRow("Ad:", self._name_edit)

        self._desc_edit = QTextEdit()
        self._desc_edit.setPlaceholderText("Aciklama (opsiyonel)")
        self._desc_edit.setMaximumHeight(80)
        layout.addRow("Aciklama:", self._desc_edit)

        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("Etiketler (virgul ile ayirin)")
        layout.addRow("Etiketler:", self._tags_edit)

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
        name = self._name_edit.text().strip() or "Yeni Tasarim"
        desc = self._desc_edit.toPlainText().strip()
        tags_text = self._tags_edit.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()] if tags_text else []
        return name, desc, tags
