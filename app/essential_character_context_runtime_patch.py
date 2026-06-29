"""Essential character context guard for 1206 gameplay.

Purpose:
- full character cards for active / nearby / speaking / observing characters must be
  loaded before long canon, lore, rules or summaries;
- if the context budget is tight, trim long supporting files first, not NPC cards;
- do not restore old required-files chunk protocol.

This module does not add locks or scene examples.
"""
from __future__ import annotations

from typing import Any

import app.fast_context_runtime_patch as fast_context
from app import compact as base

try:
    import app.roster_identity_context_guard_runtime_patch as roster_guard
except Exception:  # pragma: no cover
    roster_guard = None  # type: ignore[assignment]

try:
    import app.past_visibility_guard_runtime_patch as past_visibility_guard
except Exception:  # pragma: no cover
    past_visibility_guard = None  # type: ignore[assignment]

try:
    import app.character_depth_context_runtime_patch as character_depth_context
except Exception:  # pragma: no cover
    character_depth_context = None  # type: ignore[assignment]

app = base.app

_UPSTREAM_REQUIRED_FILES_FOR_SESSION = getattr(fast_context, "_required_files_for_session", None)
_UPSTREAM_BUILD_FAST_LOADED_FILES = getattr(fast_context, "_build_fast_loaded_files", None)

CHARACTER_FIELDS = (
    "active_characters",
    "active_character_ids",
    "nearby_characters",
    "nearby_character_ids",
    "speaking_characters",
    "speaking_character_ids",
    "observing_characters",
    "observing_character_ids",
    "present_characters",
    "present_character_ids",
    "focus_characters",
    "focus_character_ids",
    "scene_character_ids",
    "current_speaker_id",
    "last_speaker_id",
)


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _canonical_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if roster_guard is not None:
        try:
            return roster_guard.canonical_id(raw)
        except Exception:
            pass
    return raw.lower().replace("ё", "е")


def _known_character(cid: str) -> bool:
    if not cid:
        return False
    if roster_guard is not None:
        try:
            return bool(roster_guard._known_character(cid))
        except Exception:
            pass
    return cid not in {"unknown", "none", "null"}


def _character_folder(cid: str) -> str | None:
    if roster_guard is not None:
        try:
            return roster_guard._character_folder(cid)
        except Exception:
            pass
    return cid if cid else None


def _repo_file_exists(path: str) -> bool:
    try:
        return bool(base.repo_file_exists(path))
    except Exception:
        try:
            base.read_text(path)
            return True
        except Exception:
            return False


def _ids_from_state_fields(current: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for field in CHARACTER_FIELDS:
        value = current.get(field)
        if isinstance(value, list):
            ids.extend(_canonical_id(item) for item in value)
        elif isinstance(value, str):
            ids.append(_canonical_id(value))

    for key in ("open_threads", "active_threads", "scene_threads"):
        value = current.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            if item.get("status") in {None, "", "active", "due", "triggered", "open"}:
                ids.extend(_canonical_id(x) for x in item.get("participants", []) or [])

    return [cid for cid in _unique(ids) if _known_character(cid)]


def _ids_from_future(future: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    locks = future.get("locks") if isinstance(future, dict) else None
    if isinstance(locks, dict):
        iterable = locks.values()
    elif isinstance(locks, list):
        iterable = locks
    else:
        iterable = []

    for item in iterable:
        if not isinstance(item, dict):
            continue
        if item.get("status") in {"active", "due", "triggered", "open"}:
            ids.extend(_canonical_id(x) for x in item.get("participants", []) or [])

    return [cid for cid in _unique(ids) if _known_character(cid)]


def active_scene_character_ids(session_id: str, current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    ids: list[str] = []
    if roster_guard is not None:
        try:
            ids.extend(roster_guard.infer_scene_character_ids(session_id, current))
        except Exception:
            pass
    ids.extend(_ids_from_state_fields(current))
    if isinstance(future, dict):
        ids.extend(_ids_from_future(future))
    return [cid for cid in _unique(ids) if _known_character(cid)]


def character_core_files(cid: str) -> list[str]:
    folder = _character_folder(_canonical_id(cid))
    if not folder:
        return []
    files = [
        f"characters/{folder}/main.yaml",
        f"characters/{folder}/character.yaml",
        f"characters/{folder}/knowledge.yaml",
    ]
    return [path for path in files if _repo_file_exists(path)]


def essential_character_files(session_id: str, current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    files: list[str] = []
    for cid in active_scene_character_ids(session_id, current, future):
        files.extend(character_core_files(cid))
    return _unique(files)


def _support_priority_files(required_files: list[str]) -> list[str]:
    preferred = [
        "runtime/scene_context_digest.md",
        "state/current_state.json",
        "state/scene_continuity_state.json",
        "characters/character_id_index.md",
    ]
    return [path for path in preferred if path in required_files or _repo_file_exists(path) or path.startswith("state/")]


def reorder_required_files(session_id: str, required_files: list[str], current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    required = _unique(list(required_files or []))
    essential = essential_character_files(session_id, current, future)
    support = _support_priority_files(required)
    rest = [path for path in required if path not in support and path not in essential]
    return _unique(support + essential + rest)


def required_files_for_session_guard(session_id: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    sid = base.safe_session_id(session_id)
    if _UPSTREAM_REQUIRED_FILES_FOR_SESSION is not None:
        try:
            files, current, future = _UPSTREAM_REQUIRED_FILES_FOR_SESSION(sid)
        except Exception:
            files, current, future = [], {}, {}
    else:
        current = base.read_json("state/current_state.json", sid, default={}) or {}
        future = base.read_json("state/future_locks_progress.json", sid, default={}) or {}
        try:
            files = list(base.recommended_files_for_context(current, future))
        except Exception:
            files = []

    if roster_guard is not None:
        try:
            current = roster_guard._sync_current_for_context(sid, current)
        except Exception:
            pass

    files = reorder_required_files(sid, files, current, future)
    return files, current, future


def _is_essential_path(path: str, session_id: str, current: dict[str, Any]) -> bool:
    return path in set(essential_character_files(session_id, current))


def build_fast_loaded_files_guard(
    session_id: str,
    required_files: list[str],
    current: dict[str, Any],
    *,
    max_total_chars: int,
    per_file_chars: int,
    include_past: bool | None,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    if _UPSTREAM_BUILD_FAST_LOADED_FILES is None:
        return [], list(required_files or []), True

    sid = base.safe_session_id(session_id)
    required = reorder_required_files(sid, required_files, current)
    essential = [path for path in required if _is_essential_path(path, sid, current)]

    try:
        max_total = max(24000, min(int(max_total_chars or 45000), 70000))
    except Exception:
        max_total = 45000
    try:
        per_file = max(2500, min(int(per_file_chars or 8000), 14000))
    except Exception:
        per_file = 8000

    if not essential:
        return _UPSTREAM_BUILD_FAST_LOADED_FILES(
            sid,
            required,
            current,
            max_total_chars=max_total,
            per_file_chars=per_file,
            include_past=include_past,
        )

    essential_budget = min(max_total, max(12000, int(max_total * 0.70)))
    essential_cap = max(1800, min(per_file, max(1800, essential_budget // max(1, len(essential)))))

    essential_loaded, essential_skipped, essential_truncated = _UPSTREAM_BUILD_FAST_LOADED_FILES(
        sid,
        essential,
        current,
        max_total_chars=essential_budget,
        per_file_chars=essential_cap,
        include_past=False,
    )

    loaded_paths = {str(item.get("path")) for item in essential_loaded}
    remaining_budget = max(4000, max_total - sum(len(str(item.get("content") or "")) for item in essential_loaded))
    remaining_files = [path for path in required if path not in loaded_paths and path not in essential]

    rest_loaded, rest_skipped, rest_truncated = _UPSTREAM_BUILD_FAST_LOADED_FILES(
        sid,
        remaining_files,
        current,
        max_total_chars=remaining_budget,
        per_file_chars=per_file,
        include_past=include_past,
    )

    skipped = [path for path in _unique(essential_skipped + rest_skipped) if path not in loaded_paths]
    return essential_loaded + rest_loaded, skipped, bool(essential_truncated or rest_truncated)


fast_context._required_files_for_session = required_files_for_session_guard  # type: ignore[assignment]
fast_context._build_fast_loaded_files = build_fast_loaded_files_guard  # type: ignore[assignment]

if roster_guard is not None:
    roster_guard._required_files_for_session_guard = required_files_for_session_guard  # type: ignore[attr-defined]

if past_visibility_guard is not None:
    past_visibility_guard.required_files_for_session_guard = required_files_for_session_guard  # type: ignore[attr-defined]

if character_depth_context is not None:
    character_depth_context.required_files_for_session_guard = required_files_for_session_guard  # type: ignore[attr-defined]

app.version = "0.3.142-essential-character-context-v1"
