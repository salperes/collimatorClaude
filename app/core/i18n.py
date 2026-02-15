"""Internationalization — lightweight JSON-based translation system.

Loads translations from translations/{lang}.json files.
Supports nested JSON (flattened to dot-notation keys at load time).
Provides global t() function for string lookup with English fallback.

Usage:
    from app.core.i18n import t, TranslationManager

    # Initialize (once, at app startup)
    TranslationManager.init("tr")

    # Translate
    label.setText(t("toolbar.file", "File"))

    # Format strings
    msg = t("status.zoom", "Zoom: {pct}").format(pct="150%")

    # Switch language at runtime
    TranslationManager.instance().set_language("en")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

_TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "translations"


class TranslationManager:
    """Singleton translation manager with JSON backend."""

    _instance: TranslationManager | None = None
    _listeners: list[Callable[[], None]] = []

    def __init__(self, lang: str = "tr"):
        self.lang = lang
        self._strings: dict[str, str] = {}
        self._load(lang)

    def _load(self, lang: str) -> None:
        """Load flat key-value dict from translations/{lang}.json."""
        path = _TRANSLATIONS_DIR / f"{lang}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self._strings = _flatten(data)
        else:
            self._strings = {}

    def get(self, key: str, default: str = "") -> str:
        """Get translated string by dot-key. Falls back to default (English)."""
        return self._strings.get(key, default)

    def set_language(self, lang: str) -> None:
        """Switch language and notify all listeners."""
        self.lang = lang
        self._load(lang)
        for cb in self._listeners:
            cb()

    @classmethod
    def instance(cls) -> TranslationManager:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls("tr")
        return cls._instance

    @classmethod
    def init(cls, lang: str = "tr") -> TranslationManager:
        """Initialize the singleton with given language."""
        cls._instance = cls(lang)
        return cls._instance

    @classmethod
    def on_language_changed(cls, callback: Callable[[], None]) -> None:
        """Register a callback for language change events."""
        cls._listeners.append(callback)

    @classmethod
    def remove_listener(cls, callback: Callable[[], None]) -> None:
        """Unregister a language change callback."""
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._listeners.clear()


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dict to dot-notation keys.

    {"toolbar": {"file": "Dosya"}} -> {"toolbar.file": "Dosya"}
    """
    result: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        else:
            result[key] = str(v)
    return result


def t(key: str, default: str = "") -> str:
    """Global translate function.

    Args:
        key: Dot-notation key (e.g. "toolbar.file").
        default: Fallback string if key not found (English).

    Returns:
        Translated string or default.
    """
    return TranslationManager.instance().get(key, default)
