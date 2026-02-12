"""Material selector widget — checkboxes for multi-material comparison.

Compact horizontal layout with colored checkboxes.

Reference: Phase-05 spec — MaterialSelector.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QCheckBox
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from app.core.material_database import MaterialService
from app.ui.styles.colors import MATERIAL_COLORS


class MaterialSelector(QWidget):
    """Compact checkbox row for selecting materials to compare on charts."""

    selection_changed = pyqtSignal(list)  # list[str] of material_ids

    def __init__(
        self,
        material_service: MaterialService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        for mat in material_service.get_all_materials():
            cb = QCheckBox(mat.symbol or mat.id)
            color = MATERIAL_COLORS.get(mat.id, "#B0BEC5")
            cb.setStyleSheet(
                f"QCheckBox {{ color: {color}; font-weight: bold; }}"
            )
            # Default: Pb checked
            if mat.id == "Pb":
                cb.setChecked(True)
            cb.toggled.connect(lambda _: self._on_changed())
            layout.addWidget(cb)
            self._checkboxes[mat.id] = cb

        layout.addStretch()

    def selected_materials(self) -> list[str]:
        """Return list of currently checked material IDs."""
        return [mid for mid, cb in self._checkboxes.items() if cb.isChecked()]

    def _on_changed(self) -> None:
        self.selection_changed.emit(self.selected_materials())
