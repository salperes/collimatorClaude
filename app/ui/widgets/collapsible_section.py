"""Collapsible section widget — expandable/collapsible panel section.

Clickable header with expand/collapse chevron.
Used in the right panel to organize Layers, Properties, Quick Results.

Reference: Phase-03 spec — UI Panel Details.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve


class CollapsibleSection(QWidget):
    """A section with a clickable header that shows/hides content."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self._header = QPushButton(f"  \u25BC  {title}")
        self._header.setCheckable(True)
        self._header.setChecked(True)
        self._header.setProperty("cssClass", "section-header")
        self._header.clicked.connect(self.toggle)
        layout.addWidget(self._header)

        # Content container
        self._content_frame = QFrame()
        self._content_layout = QVBoxLayout(self._content_frame)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._content_frame)

        self._title = title

    def set_content_widget(self, widget: QWidget) -> None:
        """Set the widget to show inside the collapsible section."""
        # Remove old content
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._content_layout.addWidget(widget)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._content_frame.setVisible(self._expanded)
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._header.setText(f"  {arrow}  {self._title}")

    def expand(self) -> None:
        self._expanded = True
        self._content_frame.setVisible(True)
        self._header.setText(f"  \u25BC  {self._title}")

    def collapse(self) -> None:
        self._expanded = False
        self._content_frame.setVisible(False)
        self._header.setText(f"  \u25B6  {self._title}")
