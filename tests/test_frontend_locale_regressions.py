from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_JS_PATH = REPO_ROOT / "app" / "static" / "app.js"
LOCALES_JS_PATH = REPO_ROOT / "app" / "static" / "locales.js"
SUPPORTED_LOCALES = ("zh-CN", "ja-JP", "en")
REQUIRED_CORE_KEYS = (
    "settings.locale",
    "settings.locale.zh-CN",
    "settings.locale.ja-JP",
    "settings.locale.en",
    "settings.provider",
    "settings.model_preset",
    "settings.model_name",
    "settings.collaboration_mode",
    "settings.response_style",
    "buttons.save",
    "tabs.settings",
)
REQUIRED_LIST_KEYS = ("starter.prompts",)


def _extract_object_body(content: str, marker: str) -> str:
    start = content.index(marker) + len(marker)
    depth = 1
    in_string = False
    escaped = False

    for index in range(start, len(content)):
        char = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return content[start:index]
    raise AssertionError(f"Could not extract object body for marker: {marker}")


def _locale_entry_types() -> dict[str, dict[str, str]]:
    content = LOCALES_JS_PATH.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    for locale in SUPPORTED_LOCALES:
        marker = f'"{locale}": {{'
        if marker not in content:
            marker = f"{locale}: {{"
        body = _extract_object_body(content, marker)
        entries[locale] = {
            match.group("key"): match.group("value_type")
            for match in re.finditer(r'"(?P<key>[^"]+)":\s*(?P<value_type>\[|")', body)
        }
    return entries


def test_settings_handlers_do_not_read_current_target_inside_state_updaters() -> None:
    lines = APP_JS_PATH.read_text(encoding="utf-8").splitlines()
    offenders = [
        f"{line_no}: {line.strip()}"
        for line_no, line in enumerate(lines, start=1)
        if "setChatSettings((prev)" in line and "event.currentTarget" in line
    ]
    assert offenders == []


def test_locale_catalog_contains_required_settings_keys() -> None:
    entries = _locale_entry_types()

    for locale in SUPPORTED_LOCALES:
        locale_entries = entries[locale]
        for key in REQUIRED_CORE_KEYS:
            assert locale_entries.get(key) == '"', f"{locale} is missing string key {key}"
        for key in REQUIRED_LIST_KEYS:
            assert locale_entries.get(key) == "[", f"{locale} is missing array key {key}"
