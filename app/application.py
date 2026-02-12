"""Application factory — QApplication creation, theme loading, font setup.

Reference: FRD §6 — UI/UX Design.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from app.constants import APP_NAME, APP_ORGANIZATION


def _qt_message_handler(msg_type, context, message):
    """Filter Qt debug/warning messages.

    Suppresses harmless QPainter warnings that occur when Qt's style
    engine creates image caches for rounded-corner widgets before they
    have a valid size (common during startup).
    """
    if "QPainter" in message:
        return
    if "Paint device returned engine == 0" in message:
        return

    if msg_type == QtMsgType.QtWarningMsg:
        print(message, file=sys.stderr)
    elif msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        print(message, file=sys.stderr)


def create_application(argv: list[str]) -> QApplication:
    """Create and configure the QApplication instance."""
    qInstallMessageHandler(_qt_message_handler)

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)

    # Font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Dark theme QSS
    qss_path = Path(__file__).parent / "ui" / "styles" / "dark_theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    return app
