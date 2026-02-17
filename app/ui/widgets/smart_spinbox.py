"""Smart double spin box — dual decimal separator support.

Accepts both '.' and ',' as decimal separator so users can type
either key on any keyboard layout.  Properly overrides ``validate``,
``valueFromText``, ``textFromValue``, and ``fixup`` so the up/down
arrow buttons (and keyboard arrows) always work correctly.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QValidator
from PyQt6.QtWidgets import QDoubleSpinBox


class SmartDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox that accepts both '.' and ',' as decimal separator.

    Uses the locale decimal separator for display.  Overrides the full
    text↔value pipeline so Qt's internal value stays in sync with
    what the user sees, and stepping (up/down buttons) works correctly.
    """

    # -- display ----------------------------------------------------------

    def textFromValue(self, value: float) -> str:
        """Format *value* using the locale decimal separator."""
        sep = self.locale().decimalPoint()
        return f"{value:.{self.decimals()}f}".replace(".", sep)

    # -- parsing ----------------------------------------------------------

    def valueFromText(self, text: str) -> float:
        """Parse *text* accepting both '.' and ',' as separator."""
        clean = text.strip()
        sfx = self.suffix()
        if sfx and clean.endswith(sfx):
            clean = clean[: -len(sfx)]
        pfx = self.prefix()
        if pfx and clean.startswith(pfx):
            clean = clean[len(pfx) :]
        # Normalise to '.' for Python float()
        clean = clean.strip().replace(",", ".")
        try:
            return float(clean)
        except ValueError:
            return self.minimum()

    # -- validation -------------------------------------------------------

    def validate(self, text: str, pos: int) -> tuple:
        """Accept both separators during input validation."""
        sep = self.locale().decimalPoint()
        alt = "." if sep == "," else ","
        normalized = text.replace(alt, sep)
        return super().validate(normalized, pos)

    def fixup(self, text: str) -> str:
        """Normalise separator before Qt processes the text."""
        sep = self.locale().decimalPoint()
        alt = "." if sep == "," else ","
        return super().fixup(text.replace(alt, sep))

    # -- keyboard ---------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Convert non-locale separator key to the locale separator."""
        sep = self.locale().decimalPoint()
        alt = "." if sep == "," else ","
        if event.text() == alt:
            key = Qt.Key.Key_Comma if sep == "," else Qt.Key.Key_Period
            native = QKeyEvent(
                event.type(), key, event.modifiers(), sep,
            )
            super().keyPressEvent(native)
            return
        super().keyPressEvent(event)
