"""Character depth context patch for 1206.

Loads the canon rule for living NPC behavior as world/canon context, not as a
new lock. Also keeps speaking/nearby/observing character cards early in the
fast context file order so important NPCs are less likely to become scene
functions when token budget is tight.
"""
from __future__ import annotations

from typing import Any

import app.fast_context_runtime_patch as fast_context
import app.roster_identity_context_guard_runtime_patch as roster_guard

try:
    import app.past_visibility_guard_runtime_patch as past_visibility_guard
except Exception:  # pragma: no cover - optional in older builds
    past_visibility_guard = None  # type: ignore[assignment]

from app import compact as base

app = base.app

CHARACTER_DEPTH_FILE = "canon/character_depth_and_rotation.md"

_ORIGINAL_RECOMMENDED = None
if past_visibility_guard is not None:
    _ORIGINAL_RECOMMENDED = getattr(past_visibility_guard, "recommended_files_for_context", None)
if _ORIGINAL_RECOMMENDED is None:
    _ORIGINAL_RECOMMENDED = getattr(roster_guard, "recommended_files_for_context", None)


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _character_ids_from_current(current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    ids: list[str] = []
    try:
        ids.extend(roster_guard._recommended_scene_ids_from_current(current, future or {}))
    except Exception:
        ids.append("akira")

    for key in (
        "active_characters",
        "active_character_ids",
        "nearby_characters",
        "nearby_character_ids",
        "speaking_character_ids",
        "speaking_characters",
        "observing_character_ids",
        "observing_characters",
        "present_character_ids",
        "present_characters",
        "focus_character_ids",
        "focus_characters",
    ):
        value = current.get(key)
        if isinstance(value, list):
            for item in value:
                try:
                    cid = roster_guard.canonical_id(item)
                except Exception:
                    cid = str(item or "").strip()
                if cid:
                    ids.append(cid)

    return [cid for cid in _unique(ids) if getattr(roster_guard, "_known_character", lambda x: bool(x))(cid)]


def _character_files(cid: str) -> list[str]:
    try:
        return roster_guard.character_files_for_context(cid, include_past=False)
    except Exception:
        folder = cid
        return [
            f"characters/{folder}/main.yaml",
            f"characters/{folder}/character.yaml",
            f"characters/{folder}/knowledge.yaml",
        ]


def _reorder_with_character_depth(files: list[str], current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    ids = _character_ids_from_current(current, future)
    priority: list[str] = [
        "runtime/scene_context_digest.md",
        "state/current_state.json",
        "state/calendar_runtime.json",
        "state/scene_continuity_state.json",
        "gpt/locks/runtime_scene_rules_digest.md",
        "gpt/scene_format.md",
        "characters/character_id_index.md",
        CHARACTER_DEPTH_FILE,
    ]
    for cid in ids:
        priority.extend(_character_files(cid))

    ordered = _unique(priority + list(files or []))
    return [path for path in ordered if base.repo_file_exists(path) or path.startswith("state/") or path == "runtime/scene_context_digest.md"]


def recommended_files_for_context(current: dict[str, Any] | None = None, future: dict[str, Any] | None = None) -> list[str]:
    current = current or {}
    future = future or {}
    if _ORIGINAL_RECOMMENDED is not None:
        try:
            files = list(_ORIGINAL_RECOMMENDED(current, future) or [])
        except TypeError:
            files = list(_ORIGINAL_RECOMMENDED(current) or [])
        except Exception:
            files = []
    else:
        files = []
    return _reorder_with_character_depth(files, current, future)


def required_files_for_session_guard(session_id: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    sid = base.safe_session_id(session_id)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    try:
        current = roster_guard._sync_current_for_context(sid, current)
    except Exception:
        pass
    future = base.read_json("state/future_locks_progress.json", sid, default={}) or {}
    return recommended_files_for_context(current, future), current, future


# Patch context selectors after roster/past guards are loaded.
if past_visibility_guard is not None:
    past_visibility_guard.recommended_files_for_context = recommended_files_for_context  # type: ignore[assignment]
    past_visibility_guard.required_files_for_session_guard = required_files_for_session_guard  # type: ignore[assignment]

roster_guard.recommended_files_for_context = recommended_files_for_context  # type: ignore[assignment]
roster_guard._required_files_for_session_guard = required_files_for_session_guard  # type: ignore[assignment]
fast_context._required_files_for_session = required_files_for_session_guard  # type: ignore[assignment]
base.recommended_files_for_context = recommended_files_for_context

try:
    fast_context.FAST_ALWAYS_FILES.add(CHARACTER_DEPTH_FILE)
except Exception:
    pass

app.version = "0.3.141-live-character-depth-v1"
