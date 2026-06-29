"""1206 v2 context loading budget patch.

Keeps stable world/base context available through the runtime digest, while
reducing the separate required-file list for normal gameplay turns.

Principles:
- runtime digest carries compact background/state slices;
- character files are loaded only for scene/focus characters;
- past.yaml / hidden lore loads only by explicit trigger;
- East Sector full files load only when the scene is at/near the base.
"""
from __future__ import annotations

import json
from typing import Any

from app import compact as base
import app.response_size_guard_runtime_patch as size_guard

try:
    import app.fast_context_runtime_patch as fast_context  # type: ignore
except Exception:
    fast_context = None  # type: ignore[assignment]

_ORIGINAL_REQUIRED_FILES = getattr(size_guard, "_required_files", None)
_ORIGINAL_RUNTIME_DIGEST = getattr(size_guard, "_runtime_digest", None)

DIGEST_ONLY_STATE_FILES = {
    "state/story_lines.json",
    "state/relationships.json",
    "state/knowledge_state.json",
    "state/inventory_state.json",
    "state/power_state.json",
    "state/future_locks_progress.json",
    "state/session_npcs.json",
}

CORE_BACKGROUND_FILES = [
    "canon_lore/index.yaml",
    "canon_lore/core/world_background.yaml",
    "canon_lore/core/story_background.yaml",
    "canon_lore/hidden/hidden_lore_policy.yaml",
    "canon_lore/world/energy_system.yaml",
]

EAST_SECTOR_FILES = [
    "canon_lore/east_sector/east_sector_base.yaml",
    "locations/east_sector_locations.yaml",
    "state/east_sector_1206_context.json",
    "calendar/east_sector_1206_calendar.yaml",
]

RULE_FILES_ALWAYS = [
    "gpt/locks/runtime_scene_rules_digest.md",
    "gpt/scene_format.md",
    "state/narrative_director_rules.json",
    "state/player_input_parsing_rules.json",
    "gpt/locks/story_truth_and_private_pov_rules.md",
    "gpt/locks/east_sector_arrival_time_rules.md",
    "gpt/locks/lore_usage_lock.md",
]


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


def _read_text(path: str, session_id: str | None = None) -> str:
    try:
        if path.startswith("state/") and session_id:
            return base.read_text(path, session_id=session_id)
        return base.read_text(path)
    except Exception:
        return ""


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default) or default
    except Exception:
        return default


def _cut(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def _scene_text(current: dict[str, Any]) -> str:
    parts = [
        current.get("current_location_id"),
        current.get("current_location_text"),
        current.get("current_scene_goal"),
        current.get("last_player_input"),
        current.get("time_of_day"),
        current.get("current_day_phase"),
        current.get("scene_focus"),
        current.get("focus_tags"),
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


def _compact_json(value: Any, limit: int) -> Any:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        text = str(value)
    if len(text) <= limit:
        return value
    if isinstance(value, dict):
        return {
            "_context_filter": "compact_summary",
            "total_keys": len(value),
            "keys": list(value.keys())[:30],
            "sample": _cut(text, limit),
        }
    if isinstance(value, list):
        return {
            "_context_filter": "compact_list_summary",
            "total_items": len(value),
            "sample": value[:12],
        }
    return _cut(text, limit)


def _background_slice(session_id: str, current: dict[str, Any]) -> dict[str, Any]:
    files = [p for p in CORE_BACKGROUND_FILES if _exists(p)]
    if _is_east_sector_context(current):
        files.extend([p for p in EAST_SECTOR_FILES if _exists(p)])
    compact_files = []
    for path in _unique(files):
        limit = 2400 if path in EAST_SECTOR_FILES else 1600
        compact_files.append({"path": path, "content": _cut(_read_text(path, session_id), limit)})
    return {
        "mode": "compact_background_digest",
        "note": "Stable lore/base context is carried here so normal turns do not need separate full-file loads.",
        "files": compact_files,
    }


def _runtime_digest_budgeted(session_id: str) -> str:
    if callable(_ORIGINAL_RUNTIME_DIGEST):
        try:
            base_digest = str(_ORIGINAL_RUNTIME_DIGEST(session_id) or "")
        except Exception:
            base_digest = "# Runtime scene context digest\n"
    else:
        base_digest = "# Runtime scene context digest\n"

    current = _read_json("state/current_state.json", session_id, {})
    inventory = _read_json("state/inventory_state.json", session_id, {})
    scene_continuity = _read_json("state/scene_continuity_state.json", session_id, {})
    future = _read_json("state/future_locks_progress.json", session_id, {})

    budget_payload = {
        "context_budget_mode": "normal_turn_compact_background_v1",
        "background": _background_slice(session_id, current),
        "inventory_compact": _compact_json(inventory, 1800),
        "scene_continuity_compact": _compact_json(scene_continuity, 1800),
        "future_locks_compact": _compact_json(future, 1200),
        "loading_policy": [
            "Character main/character/knowledge files are loaded only for scene/focus characters.",
            "past.yaml and hidden lore require explicit memory/past/lab/Samuel/Echo/Kairos/reveal trigger or include_past=true.",
            "Stable world/East Sector context is available as compact background digest; full East Sector files load only at/near the base.",
            "Heavy state files are summarized here and should not be loaded as separate files on ordinary turns.",
        ],
    }
    return base_digest + "\n## Context loading budget slice\n```json\n" + json.dumps(budget_payload, ensure_ascii=False, indent=2) + "\n```\n"


def _required_files_budgeted(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files: list[str] = []
    if callable(_ORIGINAL_REQUIRED_FILES):
        try:
            files.extend(_ORIGINAL_REQUIRED_FILES(current, future) or [])
        except Exception:
            pass

    # Keep the tiny current-state file visible; move other heavy state slices into runtime digest.
    filtered: list[str] = []
    for path in _unique(files):
        if path in DIGEST_ONLY_STATE_FILES:
            continue
        if path == "state/session_npcs.json" and not current.get("session_npcs_active"):
            continue
        filtered.append(path)

    for path in RULE_FILES_ALWAYS:
        if _exists(path):
            filtered.append(path)

    # Do not force full lore files on every ordinary turn; they are carried as compact digest.
    # East Sector full files remain if the scene is actually at/near the base.
    if not _is_east_sector_context(current or {}):
        filtered = [p for p in filtered if p not in EAST_SECTOR_FILES]

    return _unique([p for p in filtered if _exists(p) or p == "runtime/scene_context_digest.md"])


size_guard._runtime_digest = _runtime_digest_budgeted  # type: ignore[attr-defined]
size_guard._required_files = _required_files_budgeted  # type: ignore[attr-defined]
base.recommended_files_for_context = _required_files_budgeted

if fast_context is not None:
    try:
        fast_context.FAST_ALWAYS_FILES.difference_update(DIGEST_ONLY_STATE_FILES)
        fast_context.FAST_ALWAYS_FILES.update({
            "runtime/scene_context_digest.md",
            "state/current_state.json",
            "gpt/locks/runtime_scene_rules_digest.md",
            "gpt/scene_format.md",
        })
    except Exception:
        pass

try:
    size_guard.app.version = "0.3.136-context-loading-budget-v1"
except Exception:
    pass
