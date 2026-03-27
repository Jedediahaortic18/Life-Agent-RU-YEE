"""Locale-aware prompt loader for agent system prompts."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Template
from loguru import logger

from core.i18n import get_locale

_template_cache: dict[tuple[str, str], Template] = {}


def load_prompt(prompts_dir: str | Path, **render_kwargs) -> str:
    prompts_dir = Path(prompts_dir)
    locale = get_locale()
    candidates = [
        prompts_dir / f"system.{locale}.j2",
        prompts_dir / "system.j2",
    ]
    template_path: Path | None = None
    for candidate in candidates:
        if candidate.exists():
            template_path = candidate
            break
    if template_path is None:
        logger.warning(f"No prompt template found in {prompts_dir}")
        return ""
    cache_key = (str(template_path), locale)
    if cache_key not in _template_cache:
        text = template_path.read_text(encoding="utf-8")
        _template_cache[cache_key] = Template(text)
    return _template_cache[cache_key].render(**render_kwargs)


def clear_cache() -> None:
    _template_cache.clear()
