"""Time flow runtime fix for Akira 1206 v2.

Fixes two practical issues:
1) start-scene seed patches must not reset time to 02:40 after gameplay already advanced time;
2) applyTurnResult must accept current_state_patch and keep current_time/time synchronized.
"""
from __future__ import annotations

from typing import Any

import app.calendar_scene_runtime_patch as calendar_runtime
import app.start_scene_runtime_patch as start_runtime
from app.start_scene_runtime_patch import app
from app import compact as base

try:
    import app.state_persistence_runtime_patch as persistence
except Exception:  # pragma: no cover
    persistence = None  # type: ignore

CURRENT_STATE_FILE = "state/current_state.json"
START_ANCHOR_TIME = "02:40"

TIME_SAFE_KEYS = [
    "current_time",
    "time",
    "scene_time",
    "time_of_day",
    "last_time_advance_min",
    "last_time_advance_reason",
    "last_time_scene_start",
    "last_time_scene_end",
    "last_scene_duration_min",
]


def _state_has_time_progress(state: dict[str, Any]) -> bool:
    if not isinstance(state, dict):
        return False
    if state.get("last_time_advance_min") is not None or state.get("last_time_advance_reason"):
        return True
    if int(state.get("scene_count") or 0) > 0:
        return True
    return str(state.get("current_time") or state.get("time") or "") not in ("", START_ANCHOR_TIME)


def _sync_time_fields(state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(state, dict):
        return state
    current_time = state.get("current_time") or state.get("time") or state.get("scene_time")
    if current_time:
        state["current_time"] = str(current_time)
        state["time"] = str(current_time)
    return state


# 1) Scene packet time must prefer canonical current_time, not stale time.
def _current_time_from_state_fixed(current: dict[str, Any]) -> str:
    value = (
        current.get("current_time")
        or current.get("time")
        or current.get("scene_time")
        or START_ANCHOR_TIME
    )
    return str(value)

calendar_runtime._current_time_from_state = _current_time_from_state_fixed  # type: ignore[attr-defined]


# 2) applyTurnResult must recognize current_state_patch.
def _patch_state_section_map() -> None:
    state_map = list(getattr(base, "STATE_SECTION_MAP", []) or [])
    patched = []
    seen_current = False
    for path, names in state_map:
        names = list(names or [])
        if path == CURRENT_STATE_FILE:
            seen_current = True
            merged = []
            for n in ["current_state_patch", "current_state_changes", "current_state", "state_changes"] + names:
                if n not in merged:
                    merged.append(n)
            patched.append((path, merged))
        else:
            patched.append((path, names))
    if not seen_current:
        patched.insert(0, (CURRENT_STATE_FILE, ["current_state_patch", "current_state_changes", "current_state", "state_changes"]))
    base.STATE_SECTION_MAP = patched


_patch_state_section_map()


# 3) Normalize time aliases before writing state/current_state.json.
if persistence is not None and hasattr(persistence, "apply_json_section_robust"):
    _orig_apply_json_section_robust = persistence.apply_json_section_robust

    def _apply_json_section_robust_time_fixed(session_id: str, payload: dict[str, Any], path: str, names: list[str], dry_run: bool) -> bool:
        section = persistence.find_section(payload, names)  # type: ignore[attr-defined]
        if path == CURRENT_STATE_FILE and isinstance(section, dict):
            if section.get("current_time") and not section.get("time"):
                section["time"] = section["current_time"]
            elif section.get("time") and not section.get("current_time"):
                section["current_time"] = section["time"]

            # Optional aliases the model sometimes uses when estimating scene end.
            end_time = section.get("scene_end_time") or section.get("new_time") or section.get("time_after_scene")
            if end_time and not section.get("current_time"):
                section["current_time"] = str(end_time)
                section["time"] = str(end_time)

        return _orig_apply_json_section_robust(session_id, payload, path, names, dry_run)

    persistence.apply_json_section_robust = _apply_json_section_robust_time_fixed  # type: ignore[assignment]


# 4) Start-scene ensure must not overwrite already-advanced session time.
_orig_ensure_start_state = start_runtime._ensure_start_state


def _ensure_start_state_time_safe(session_id: str) -> dict[str, Any]:
    try:
        before = base.read_json(CURRENT_STATE_FILE, session_id, default={}) or {}
    except Exception:
        before = {}

    current = _orig_ensure_start_state(session_id)
    current = _sync_time_fields(current)

    if _state_has_time_progress(before):
        for key in TIME_SAFE_KEYS:
            if before.get(key) is not None:
                current[key] = before.get(key)
        current = _sync_time_fields(current)
        try:
            base.write_json(CURRENT_STATE_FILE, current, session_id)
        except Exception:
            pass

    return current


start_runtime._ensure_start_state = _ensure_start_state_time_safe

try:
    app.version = "0.3.106-1206-time-flow-fix"
except Exception:
    pass
