"""Lightweight i18n module with per-request locale via ContextVar."""
from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_LOCALES_DIR = Path(__file__).parent / "locales"
_DEFAULT_LOCALE = "zh"
_SUPPORTED_LOCALES = ("en", "zh")
_current_locale: ContextVar[str] = ContextVar("locale", default=_DEFAULT_LOCALE)
_messages: dict[str, dict[str, str]] = {}


def _load_locale(locale: str) -> dict[str, str]:
    if locale in _messages:
        return _messages[locale]
    path = _LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        _messages[locale] = {}
        return _messages[locale]
    with path.open(encoding="utf-8") as f:
        _messages[locale] = json.load(f)
    return _messages[locale]


def reload_messages() -> None:
    _messages.clear()
    for locale in _SUPPORTED_LOCALES:
        _load_locale(locale)


def set_locale(locale: str) -> None:
    if locale not in _SUPPORTED_LOCALES:
        locale = _DEFAULT_LOCALE
    _current_locale.set(locale)


def get_locale() -> str:
    return _current_locale.get()


def get_supported_locales() -> tuple[str, ...]:
    return _SUPPORTED_LOCALES


def get_default_locale() -> str:
    return _DEFAULT_LOCALE


def t(key: str, **kwargs: Any) -> str:
    locale = _current_locale.get()
    messages = _load_locale(locale)
    text = messages.get(key)
    if text is None and locale != _DEFAULT_LOCALE:
        text = _load_locale(_DEFAULT_LOCALE).get(key)
    if text is None:
        return key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
