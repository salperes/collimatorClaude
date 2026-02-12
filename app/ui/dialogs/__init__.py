"""Dialogs — modal dialog windows (save, open, export, version history, etc.)."""

from app.ui.dialogs.save_design_dialog import SaveDesignDialog
from app.ui.dialogs.design_manager import DesignManagerDialog
from app.ui.dialogs.export_dialog import ExportDialog
from app.ui.dialogs.version_history_dialog import VersionHistoryDialog
from app.ui.dialogs.about_dialog import AboutDialog
from app.ui.dialogs.simulation_config_dialog import SimulationConfigDialog
from app.ui.dialogs.notes_dialog import NotesDialog

__all__ = [
    "SaveDesignDialog",
    "DesignManagerDialog",
    "ExportDialog",
    "VersionHistoryDialog",
    "AboutDialog",
    "SimulationConfigDialog",
    "NotesDialog",
]
