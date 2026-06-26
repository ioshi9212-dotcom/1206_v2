from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import Query

import app.response_size_guard_runtime_patch as size_guard
from app.response_size_guard_runtime_patch import app
from app import compact as base

CHARACTER_ENTRY_STATE_FILE = "state/character_entry_state.json"
CURRENT_STATE_FILE = "state/current_state.json"
SCENE_HISTORY_FILE = "state/scene_history.json"

RAIDEN_ENTRY_ID = "raiden"
RAIDEN_VISIBLE_DESCRIPTOR = "парень с пирсингом"

RAIDEN_TRIGGER_NEEDLES = [
    "хруст вет", "ветк", "приближа", "кто там", "кто за нами",
    "мотоцикл", "фара", "двигател", "шум двигателя", "колес",
    "рейдер", "смотров", "морск", "к морю", "след эммы", "энергетический след",
    "холод", "иней", "сухой клин", "воздух р", "клин воздуха",
]

RAIDEN_BLOCK_NEEDLES = [
    "райден", "рейден", "парень с пирсингом", "тёмная фигура за рулём",
    "темная фигура за рулем",
]


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _safe_session_id(session_id: str) -> str:
    try:
        return base.safe_session_id(session_id)
    except Exception:
        safe = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
        return safe or "default"


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default)
    except Exception:
        return default


def _write_json(path: str, data: Any, session_id: str) -> None:
    base.write_json(path, data, session_id)


def _entries_root(history: Any) -> list[dict[str, Any]]:
    if isinstance(history, list):
        return [entry for entry in history if isinstance(entry, dict)]
    if isinstance(history, dict):
        entries = history.get("entries")
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _latest_scene_text(session_id: str, limit: int = 5) -> str:
    history = _read_json(SCENE_HISTORY_FILE, session_id, [])
    entries = _entries_root(history)
    texts: list[str] = []
    for entry in reversed(entries[-limit:]):
        text = entry.get("visible_scene_text") or entry.get("scene_text") or ""
        player = entry.get("player_input") or ""
        if text:
            texts.append(str(text))
        if player:
            texts.append(str(player))
    return "\n\n".join(texts)


def _current_text(current: dict[str, Any]) -> str:
    parts = [
        current.get("current_scene_goal"),
        current.get("last_player_input"),
        current.get("current_location_text"),
        current.get("current_location_id"),
        current.get("scene_id"),
        current.get("current_scene_id"),
        " ".join(current.get("scheduled_character_ids", []) or []),
        " ".join(current.get("conditional_character_ids", []) or []),
        " ".join(current.get("mentioned_character_ids", []) or []),
    ]
    return "\n".join(str(part or "") for part in parts)


def _text_has_any(text: str, needles: list[str]) -> bool:
    hay = str(text or "").lower().replace("ё", "е")
    return any(needle.lower().replace("ё", "е") in hay for needle in needles)


def _is_1206_late_night(current: dict[str, Any]) -> bool:
    date = str(current.get("current_date") or current.get("date") or "")
    phase = str(current.get("current_day_phase") or current.get("time_of_day") or current.get("day_phase") or "").lower()
    time = str(current.get("current_time") or current.get("time") or "")
    if date and date != "1206-08-31":
        return False
    if "ноч" in phase:
        return True
    if time.startswith("02:") or time.startswith("03:"):
        return True
    return not phase or phase == "поздняя ночь"


def _pending_entry() -> dict[str, Any]:
    return {
        "character_id": RAIDEN_ENTRY_ID,
        "visible_descriptor_before_name_known": RAIDEN_VISIBLE_DESCRIPTOR,
        "known_to_runtime": True,
        "known_to_akira": False,
        "identity_lock": "runtime_knows_raiden__akira_does_not_know_name_yet",
        "do_not_replace_with_new_npc": True,
        "use_descriptor_until_named_in_scene": True,
        "required_character_files": [
            "characters/raiden/main.yaml",
            "characters/raiden/character.yaml",
            "characters/raiden/knowledge.yaml",
        ],
        "entry_reason": (
            "1206-08-31 late-night conditional entry: Raiden is the calendar-backed source "
            "behind the approaching cue, not a random NPC."
        ),
    }


def _load_character_entry_state(session_id: str) -> dict[str, Any]:
    state = _read_json(CHARACTER_ENTRY_STATE_FILE, session_id, {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("schema", "character_entry_state_v1")
    state.setdefault("pending", {})
    state.setdefault("resolved", {})
    state.setdefault("notes", [])
    return state


def _raiden_already_materialized(current: dict[str, Any], entry_state: dict[str, Any]) -> bool:
    fields = [
        "active_characters", "active_character_ids", "nearby_characters", "nearby_character_ids",
        "speaking_character_ids", "observing_character_ids", "addressed_character_ids",
        "looked_at_character_ids",
    ]
    ids: list[str] = []
    for field in fields:
        value = current.get(field)
        if isinstance(value, list):
            ids.extend(str(item) for item in value)
    if RAIDEN_ENTRY_ID in ids:
        return True
    resolved = entry_state.get("resolved")
    return isinstance(resolved, dict) and RAIDEN_ENTRY_ID in resolved


def _should_create_raiden_pending(session_id: str, current: dict[str, Any], entry_state: dict[str, Any], *, force: bool = False) -> tuple[bool, str]:
    pending = entry_state.get("pending") if isinstance(entry_state.get("pending"), dict) else {}
    if RAIDEN_ENTRY_ID in pending:
        return False, "already_pending"

    if _raiden_already_materialized(current, entry_state):
        return False, "already_materialized"

    if force:
        return True, "forced"

    if not _is_1206_late_night(current):
        return False, "not_late_night_1206_0831"

    text = (_current_text(current) + "\n\n" + _latest_scene_text(session_id)).lower().replace("ё", "е")

    explicit_calendar_hint = (
        RAIDEN_ENTRY_ID in (current.get("conditional_character_ids") or [])
        or RAIDEN_ENTRY_ID in (current.get("scheduled_character_ids") or [])
        or RAIDEN_ENTRY_ID in (current.get("mentioned_character_ids") or [])
    )
    if explicit_calendar_hint and _text_has_any(text, RAIDEN_TRIGGER_NEEDLES + RAIDEN_BLOCK_NEEDLES):
        return True, "current_state_calendar_hint"

    if _text_has_any(text, RAIDEN_BLOCK_NEEDLES):
        return True, "raiden_descriptor_or_name_already_in_scene"

    if _text_has_any(text, RAIDEN_TRIGGER_NEEDLES):
        return True, "late_night_approach_cue"

    return False, "no_raiden_entry_cue"


def _inject_pending_into_current(current: dict[str, Any], entry_state: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(current, dict):
        return current

    pending = entry_state.get("pending") if isinstance(entry_state.get("pending"), dict) else {}
    if RAIDEN_ENTRY_ID not in pending:
        return current

    enriched = dict(current)

    pending_entries = enriched.get("pending_character_entries")
    if not isinstance(pending_entries, dict):
        pending_entries = {}
    pending_entries[RAIDEN_ENTRY_ID] = pending[RAIDEN_ENTRY_ID]
    enriched["pending_character_entries"] = pending_entries

    pending_ids = list(enriched.get("pending_character_ids") or [])
    if RAIDEN_ENTRY_ID not in pending_ids:
        pending_ids.append(RAIDEN_ENTRY_ID)
    enriched["pending_character_ids"] = pending_ids

    locks = enriched.get("character_identity_locks")
    if not isinstance(locks, dict):
        locks = {}
    locks[RAIDEN_ENTRY_ID] = {
        "known_to_runtime": True,
        "known_to_akira": False,
        "visible_descriptor": RAIDEN_VISIBLE_DESCRIPTOR,
        "do_not_replace_with_new_npc": True,
        "rule": "Use descriptor until a scene source gives Akira the name.",
    }
    enriched["character_identity_locks"] = locks

    scheduled = list(enriched.get("scheduled_character_ids") or [])
    if RAIDEN_ENTRY_ID not in scheduled:
        scheduled.append(RAIDEN_ENTRY_ID)
    enriched["scheduled_character_ids"] = scheduled

    return enriched


def ensure_character_entries(session_id: str, current: dict[str, Any] | None = None, *, force: bool = False, write_current: bool = False) -> tuple[dict[str, Any], dict[str, Any], list[str], str]:
    sid = _safe_session_id(session_id)
    if current is None:
        current = _read_json(CURRENT_STATE_FILE, sid, {})
    if not isinstance(current, dict):
        current = {}

    entry_state = _load_character_entry_state(sid)
    changed_files: list[str] = []
    should_create, reason = _should_create_raiden_pending(sid, current, entry_state, force=force)

    if should_create:
        pending = entry_state.setdefault("pending", {})
        pending[RAIDEN_ENTRY_ID] = _pending_entry()
        entry_state["updated_at"] = datetime.utcnow().isoformat()
        entry_state["last_reason"] = reason
        _write_json(CHARACTER_ENTRY_STATE_FILE, entry_state, sid)
        changed_files.append(CHARACTER_ENTRY_STATE_FILE)

    enriched = _inject_pending_into_current(current, entry_state)

    if write_current and enriched != current:
        _write_json(CURRENT_STATE_FILE, enriched, sid)
        changed_files.append(CURRENT_STATE_FILE)

    return enriched, entry_state, changed_files, reason


_ORIGINAL_SAFE_READ_JSON = size_guard._safe_read_json
_ORIGINAL_SCENE_CHARS = size_guard._scene_chars
_ORIGINAL_REQUIRED_FILES = size_guard._required_files
_ORIGINAL_CURRENT_STATE_SLICE = size_guard._current_state_slice
_ORIGINAL_READ_REQUIRED_FILE = size_guard._read_required_file


def _safe_read_json_character_entry(path: str, session_id: str, default: Any) -> Any:
    data = _ORIGINAL_SAFE_READ_JSON(path, session_id, default)
    if path == CURRENT_STATE_FILE and isinstance(data, dict):
        enriched, _entry_state, _changed, _reason = ensure_character_entries(session_id, data, force=False, write_current=False)
        return enriched
    return data


def _scene_chars_with_character_entry(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    chars = list(_ORIGINAL_SCENE_CHARS(current, future))
    pending_ids = current.get("pending_character_ids") or []
    if isinstance(pending_ids, list):
        chars.extend(str(item) for item in pending_ids)
    pending_entries = current.get("pending_character_entries")
    if isinstance(pending_entries, dict):
        chars.extend(str(cid) for cid in pending_entries.keys())
    return _unique(chars)


def _required_files_with_character_entry(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files = list(_ORIGINAL_REQUIRED_FILES(current, future))
    pending_entries = current.get("pending_character_entries")
    has_raiden_pending = (
        RAIDEN_ENTRY_ID in (current.get("pending_character_ids") or [])
        or (isinstance(pending_entries, dict) and RAIDEN_ENTRY_ID in pending_entries)
    )
    if has_raiden_pending:
        files.extend([
            "characters/raiden/main.yaml",
            "characters/raiden/character.yaml",
            "characters/raiden/knowledge.yaml",
            CHARACTER_ENTRY_STATE_FILE,
        ])
    return _unique(files)


def _current_state_slice_with_character_entry(current: dict[str, Any]) -> dict[str, Any]:
    data = _ORIGINAL_CURRENT_STATE_SLICE(current)
    for key in ["pending_character_ids", "pending_character_entries", "character_identity_locks"]:
        if key in current:
            data[key] = size_guard._compact(current.get(key), 1400)
    return data


def _read_required_file_with_character_entry(path: str, session_id: str) -> tuple[str | None, str | None]:
    if path == CURRENT_STATE_FILE:
        current = _safe_read_json_character_entry(CURRENT_STATE_FILE, session_id, {})
        if isinstance(current, dict):
            return json.dumps(current, ensure_ascii=False, indent=2) + "\n", "session_runtime_enriched"

    if path == CHARACTER_ENTRY_STATE_FILE:
        state = _load_character_entry_state(session_id)
        return json.dumps(state, ensure_ascii=False, indent=2) + "\n", "session"

    return _ORIGINAL_READ_REQUIRED_FILE(path, session_id)


size_guard._safe_read_json = _safe_read_json_character_entry
size_guard._scene_chars = _scene_chars_with_character_entry
size_guard._required_files = _required_files_with_character_entry
size_guard._current_state_slice = _current_state_slice_with_character_entry
size_guard._read_required_file = _read_required_file_with_character_entry


@app.post("/api/v1/sessions/{session_id}/repair/character-entry", operation_id="repairCharacterEntry")
def repair_character_entry(
    session_id: str,
    force: bool = Query(default=True),
    dry_run: bool = Query(default=False),
) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    current = _read_json(CURRENT_STATE_FILE, sid, {})
    if not isinstance(current, dict):
        current = {}

    if dry_run:
        entry_state = _load_character_entry_state(sid)
        should_create, reason = _should_create_raiden_pending(sid, current, entry_state, force=force)
        preview_state = dict(entry_state)
        if should_create:
            preview_state["pending"] = {**(entry_state.get("pending") or {}), RAIDEN_ENTRY_ID: _pending_entry()}
        preview = _inject_pending_into_current(current, preview_state)
        return {
            "status": "dry_run",
            "session_id": sid,
            "would_create_pending_raiden": should_create,
            "reason": reason,
            "current_state_preview": {
                "pending_character_ids": preview.get("pending_character_ids", []),
                "character_identity_locks": preview.get("character_identity_locks", {}),
            },
        }

    enriched, entry_state, changed_files, reason = ensure_character_entries(sid, current, force=force, write_current=True)
    return {
        "status": "repaired" if changed_files else "already_ok",
        "session_id": sid,
        "changed_files": changed_files,
        "reason": reason,
        "pending": entry_state.get("pending", {}),
        "current_state_pending_character_ids": enriched.get("pending_character_ids", []),
    }


app.version = "0.3.120-character-entry-v1"
