"""Material panel — left dock panel showing material library.

Displays all 8 materials with color swatch, name, Z, density.
Click to expand detail card.

Reference: Phase-03 spec — Sol Panel, Malzeme Listesi.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QColor, QDrag

from app.constants import MATERIAL_IDS, MATERIAL_MIME_TYPE
from app.ui.styles.colors import MATERIAL_COLORS


# Material properties (name, symbol, Z, density g/cm3)
_MATERIAL_INFO: dict[str, tuple[str, str, float, float]] = {
    "Pb": ("Kurşun", "Pb", 82, 11.35),
    "W": ("Tungsten", "W", 74, 19.3),
    "SS304": ("Paslanmaz Çelik 304", "SS304", 26, 8.0),
    "SS316": ("Paslanmaz Çelik 316", "SS316", 26, 8.0),
    "Bi": ("Bizmut", "Bi", 83, 9.78),
    "Al": ("Alüminyum", "Al", 13, 2.7),
    "Cu": ("Bakır", "Cu", 29, 8.96),
    "Bronze": ("Bronz", "CuSn", 29, 8.8),
}


class MaterialCard(QFrame):
    """Single material card with color swatch, name, Z, density."""

    clicked = pyqtSignal(str)

    def __init__(self, material_id: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._material_id = material_id
        self._expanded = False
        self._drag_start = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            MaterialCard {
                background: #1E293B;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px;
            }
            MaterialCard:hover {
                border: 1px solid #3B82F6;
            }
        """)

        info = _MATERIAL_INFO.get(material_id, ("?", "?", 0, 0))
        color_hex = MATERIAL_COLORS.get(material_id, "#64748B")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Top row: swatch + name
        top = QHBoxLayout()
        top.setSpacing(8)

        swatch = QLabel()
        swatch.setFixedSize(16, 16)
        swatch.setStyleSheet(
            f"background: {color_hex}; border-radius: 2px; border: 1px solid #475569;"
        )
        top.addWidget(swatch)

        name_label = QLabel(f"<b>{material_id}</b> — {info[0]}")
        name_label.setStyleSheet("color: #F8FAFC; font-size: 8pt;")
        top.addWidget(name_label, 1)

        layout.addLayout(top)

        # Detail row (always visible, compact)
        detail = QLabel(f"Z={info[2]}  |  \u03C1={info[3]:.2f} g/cm\u00B3")
        detail.setStyleSheet("color: #94A3B8; font-size: 8pt; padding-left: 24px;")
        layout.addWidget(detail)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        self.clicked.emit(self._material_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < 10:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MATERIAL_MIME_TYPE, self._material_id.encode())
        drag.setMimeData(mime)
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaledToWidth(min(pixmap.width(), 150)))
        drag.setHotSpot(event.pos())
        drag.exec(Qt.DropAction.CopyAction)


class MaterialPanel(QWidget):
    """Left dock panel — material library list.

    Shows all 8 materials with color swatch, name, Z, density.
    """

    material_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cards: list[MaterialCard] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Header
        header = QLabel("Malzeme Kütüphanesi")
        header.setStyleSheet("color: #F8FAFC; font-weight: bold; font-size: 10pt; padding: 4px;")
        layout.addWidget(header)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        card_layout = QVBoxLayout(container)
        card_layout.setContentsMargins(0, 4, 0, 4)
        card_layout.setSpacing(4)

        for mat_id in MATERIAL_IDS:
            card = MaterialCard(mat_id)
            card.clicked.connect(self._on_card_clicked)
            card_layout.addWidget(card)
            self._cards.append(card)

        card_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_card_clicked(self, material_id: str) -> None:
        self.material_selected.emit(material_id)
