"""Pluggable playoff format registry.

Adding a new format = drop a file next to ``balanced_ko4`` and add one
line to ``FORMAT_REGISTRY`` below. The motor (service/repository/router)
never imports any plugin directly — it looks them up via
``competitions.config.format_id``.
"""

from __future__ import annotations

from src.features.competitions.formats.balanced_ko4 import BalancedKo4Plugin
from src.features.competitions.formats.base import FormatPlugin
from src.features.competitions.formats.liga_berger_ko8 import LigaBergerKo8Plugin

FORMAT_REGISTRY: dict[str, FormatPlugin] = {
    "balanced_ko4": BalancedKo4Plugin(),
    "liga_berger_ko8": LigaBergerKo8Plugin(),
}


def get_format(format_id: str) -> FormatPlugin:
    plugin = FORMAT_REGISTRY.get(format_id)
    if plugin is None:
        raise KeyError(f"Unknown playoff format: {format_id!r}")
    return plugin


__all__ = ["FORMAT_REGISTRY", "FormatPlugin", "get_format"]
