"""Tests for internationalization (i18n) system."""

import json
from pathlib import Path

import pytest

from app.core.i18n import TranslationManager, _flatten, t

TRANSLATIONS_DIR = Path(__file__).parent.parent / "translations"


@pytest.fixture(autouse=True)
def reset_manager():
    """Reset TranslationManager singleton between tests."""
    TranslationManager.reset()
    yield
    TranslationManager.reset()


class TestFlatten:
    def test_flat_dict(self):
        d = {"a": "1", "b": "2"}
        assert _flatten(d) == {"a": "1", "b": "2"}

    def test_nested_dict(self):
        d = {"toolbar": {"file": "Dosya", "save": "Kaydet"}}
        result = _flatten(d)
        assert result == {"toolbar.file": "Dosya", "toolbar.save": "Kaydet"}

    def test_deeply_nested(self):
        d = {"a": {"b": {"c": "deep"}}}
        assert _flatten(d) == {"a.b.c": "deep"}

    def test_mixed(self):
        d = {"top": "val", "nested": {"inner": "val2"}}
        result = _flatten(d)
        assert result == {"top": "val", "nested.inner": "val2"}

    def test_non_string_values(self):
        d = {"num": 42, "bool": True}
        result = _flatten(d)
        assert result == {"num": "42", "bool": "True"}


class TestTranslationManager:
    def test_init_tr(self):
        mgr = TranslationManager.init("tr")
        assert mgr.lang == "tr"
        assert mgr.get("toolbar.file") == "Dosya"

    def test_init_en(self):
        mgr = TranslationManager.init("en")
        assert mgr.lang == "en"
        assert mgr.get("toolbar.file") == "File"

    def test_init_de(self):
        mgr = TranslationManager.init("de")
        assert mgr.lang == "de"
        assert mgr.get("toolbar.file") == "Datei"

    def test_fallback_to_default(self):
        mgr = TranslationManager.init("tr")
        result = mgr.get("nonexistent.key", "fallback_value")
        assert result == "fallback_value"

    def test_missing_key_empty_default(self):
        mgr = TranslationManager.init("tr")
        result = mgr.get("nonexistent.key")
        assert result == ""

    def test_singleton(self):
        TranslationManager.init("tr")
        instance1 = TranslationManager.instance()
        instance2 = TranslationManager.instance()
        assert instance1 is instance2

    def test_nonexistent_language(self):
        mgr = TranslationManager.init("xx")
        assert mgr.get("toolbar.file", "fallback") == "fallback"

    def test_language_switch(self):
        mgr = TranslationManager.init("tr")
        assert mgr.get("toolbar.file") == "Dosya"

        mgr.set_language("en")
        assert mgr.lang == "en"
        assert mgr.get("toolbar.file") == "File"

        mgr.set_language("de")
        assert mgr.lang == "de"
        assert mgr.get("toolbar.file") == "Datei"

    def test_listener_callback(self):
        mgr = TranslationManager.init("tr")
        callback_count = [0]

        def on_change():
            callback_count[0] += 1

        TranslationManager.on_language_changed(on_change)
        mgr.set_language("en")
        assert callback_count[0] == 1

        mgr.set_language("de")
        assert callback_count[0] == 2

    def test_remove_listener(self):
        mgr = TranslationManager.init("tr")
        callback_count = [0]

        def on_change():
            callback_count[0] += 1

        TranslationManager.on_language_changed(on_change)
        mgr.set_language("en")
        assert callback_count[0] == 1

        TranslationManager.remove_listener(on_change)
        mgr.set_language("de")
        assert callback_count[0] == 1  # not called again


class TestGlobalTFunction:
    def test_t_function(self):
        TranslationManager.init("tr")
        assert t("toolbar.file", "File") == "Dosya"

    def test_t_fallback(self):
        TranslationManager.init("tr")
        assert t("nonexistent", "fallback") == "fallback"

    def test_t_format_string(self):
        TranslationManager.init("tr")
        result = t("status.zoom", "Zoom: {pct}").format(pct="150%")
        assert "150%" in result


class TestTranslationFileConsistency:
    """Ensure all translation files have the same keys."""

    def _load_keys(self, lang: str) -> set[str]:
        path = TRANSLATIONS_DIR / f"{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(_flatten(data).keys())

    def test_tr_file_exists(self):
        assert (TRANSLATIONS_DIR / "tr.json").exists()

    def test_en_file_exists(self):
        assert (TRANSLATIONS_DIR / "en.json").exists()

    def test_de_file_exists(self):
        assert (TRANSLATIONS_DIR / "de.json").exists()

    def test_all_tr_keys_exist_in_en(self):
        tr_keys = self._load_keys("tr")
        en_keys = self._load_keys("en")
        missing = tr_keys - en_keys
        assert not missing, f"Keys in TR but not EN: {missing}"

    def test_all_en_keys_exist_in_tr(self):
        tr_keys = self._load_keys("tr")
        en_keys = self._load_keys("en")
        missing = en_keys - tr_keys
        assert not missing, f"Keys in EN but not TR: {missing}"

    def test_all_tr_keys_exist_in_de(self):
        tr_keys = self._load_keys("tr")
        de_keys = self._load_keys("de")
        missing = tr_keys - de_keys
        assert not missing, f"Keys in TR but not DE: {missing}"

    def test_all_de_keys_exist_in_tr(self):
        tr_keys = self._load_keys("tr")
        de_keys = self._load_keys("de")
        missing = de_keys - tr_keys
        assert not missing, f"Keys in DE but not TR: {missing}"

    def test_no_empty_values_tr(self):
        tr_keys = self._load_keys("tr")
        mgr = TranslationManager("tr")
        empty = [k for k in tr_keys if not mgr.get(k)]
        assert not empty, f"Empty values in TR: {empty}"

    def test_no_empty_values_en(self):
        en_keys = self._load_keys("en")
        mgr = TranslationManager("en")
        empty = [k for k in en_keys if not mgr.get(k)]
        assert not empty, f"Empty values in EN: {empty}"

    def test_format_placeholders_match(self):
        """Ensure format placeholders are consistent across languages."""
        import re

        tr_data = _flatten(
            json.loads((TRANSLATIONS_DIR / "tr.json").read_text(encoding="utf-8"))
        )
        en_data = _flatten(
            json.loads((TRANSLATIONS_DIR / "en.json").read_text(encoding="utf-8"))
        )

        placeholder_re = re.compile(r"\{(\w+)\}")

        for key in tr_data:
            if key not in en_data:
                continue
            tr_ph = set(placeholder_re.findall(tr_data[key]))
            en_ph = set(placeholder_re.findall(en_data[key]))
            if tr_ph or en_ph:
                assert tr_ph == en_ph, (
                    f"Key '{key}': TR placeholders {tr_ph} != EN placeholders {en_ph}"
                )
