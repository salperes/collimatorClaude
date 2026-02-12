"""Dialogs — modal dialog windows (save, open, export, version history)."""

from app.ui.dialogs.save_design_dialog import SaveDesignDialog
from app.ui.dialogs.design_manager import DesignManagerDialog
from app.ui.dialogs.export_dialog import ExportDialog
from app.ui.dialogs.version_history_dialog import VersionHistoryDialog

__all__ = [
    "SaveDesignDialog",
    "DesignManagerDialog",
    "ExportDialog",
    "VersionHistoryDialog",
]
