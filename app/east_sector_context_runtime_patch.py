"""Ensure East Sector lore/location files stay available in current 1206 context.

This is a rule/context patch, not a log. It does not create locations. It makes
existing East Sector base/location files load when the current scene is at or
near the base, so the renderer stops inventing extra checkpoints/posts/rooms.
"""
from __future__ import annotations

from typing import Any

from app import compact as base
import app.response_size_guard_runtime_patch as size_guard
from app.response_size_guard_runtime_patch import app

try:
    import app.fast_context_runtime_patch as fast_context
except Exception:  # pragma: no cover
    fast_context = None  # type: ignore[assignment]

EAST_SECTOR_CONTEXT_FILES = [
    "canon_lore/core/world_background.yaml",
    "canon_lore/world/energy_system.yaml",
    "canon_lore/east_sector/east_sector_base.yaml",
    "locations/east_sector_locations.yaml",
    "state/east_sector_1206_context.json",
    "calendar/east_sector_1206_calendar.yaml",
]

_ORIGINAL_REQUIRED_FILES = getattr(size_guard, "_required_files", None)


def _unique(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in out:
            out.append(item)
    return out


def _exists(path: str) -> bool:
    if path.startswith("state/"):
        return True
    try:
        return bool(base.repo_file_exists(path))
    except Exception:
        return False


def _scene_text(current: dict[str, Any]) -> str:
    parts = [
        current.get("current_location_id"),
        current.get("current_location_text"),
        current.get("current_scene_goal"),
        current.get("last_player_input"),
        current.get("time_of_day"),
        current.get("current_day_phase"),
    ]
    return "\n".join(str(p or "") for p in parts).lower().replace("ё", "е")


def _is_east_sector_context(current: dict[str, Any]) -> bool:
    text = _scene_text(current or {})
    needles = [
        "east_sector", "восточный сектор", "восточную баз", "восточной баз",
        "база рэя", "территория базы", "главные ворота", "ворота",
        "общежит", "комната акиры", "столов", "медпункт", "кабинет рэя",
        "трениров", "спортзал", "крыша", "корт", "парковк", "двор",
    ]
    return any(n in text for n in needles)


def _required_files_with_east_sector(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files: list[str] = []
    if callable(_ORIGINAL_REQUIRED_FILES):
        try:
            files.extend(_ORIGINAL_REQUIRED_FILES(current, future) or [])
        except Exception:
            pass
    if _is_east_sector_context(current or {}):
        files.extend(EAST_SECTOR_CONTEXT_FILES)
    return [p for p in _unique(files) if _exists(p)]


size_guard._required_files = _required_files_with_east_sector  # type: ignore[attr-defined]
base.recommended_files_for_context = _required_files_with_east_sector

if fast_context is not None:
    try:
        fast_context.FAST_ALWAYS_FILES.update(EAST_SECTOR_CONTEXT_FILES)
    except Exception:
        pass

app.version = "0.3.123-east-sector-context-v2"
