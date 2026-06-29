"""Calendar-driven character entry and current_state sync for 1206."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import app.compact_context_patch as ccp
import app.fast_context_runtime_patch as fast_context
import app.response_size_guard_runtime_patch as size_guard
import app.state_persistence_runtime_patch as state_persistence
from app import compact as base

app = base.app

CURRENT_STATE_FILE = "state/current_state.json"
SCENE_HISTORY_FILE = "state/scene_history.json"
CALENDAR_RUNTIME_FILE = "state/calendar_runtime.json"
FUTURE_LOCKS_FILE = "state/future_locks_progress.json"

RAIDEN = "raiden"
RAY = "ray"
RAIDEN_EVENT = "raiden_delayed_conditional_arrival"
SAMUEL_PRESSURE = "samuel_people_search_and_pursuit_latency"

RAIDEN_FILES = [
    "characters/raiden/main.yaml",
    "characters/raiden/character.yaml",
    "characters/raiden/knowledge.yaml",
]

PHYSICAL_FIELDS = [
    "active_characters",
    "active_character_ids",
    "nearby_characters",
    "nearby_character_ids",
    "speaking_character_ids",
    "observing_character_ids",
    "addressed_character_ids",
    "looked_at_character_ids",
]

RAIDEN_TRIGGER_WORDS = (
    "мотор", "двигател", "мотоцикл", "фара", "колес", "подъех", "подъезж",
    "у двери", "открой", "впуст", "гост", "кто там", "кто за", "стук",
    "шаги снаруж",
)

JUN_HOUSE_WORDS = ("jun_house", "дом джуна", "дома джуна", "кухн", "кофе", "лестниц")
BASE_WORDS = ("base", "база", "восточный сектор", "east_sector", "главный пост")


def _safe_session_id(session_id: str) -> str:
    try:
        return base.safe_session_id(session_id)
    except Exception:
        safe = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
        return safe or "default"


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default) or default
    except Exception:
        return default


def _write_json(path: str, data: Any, session_id: str) -> None:
    base.write_json(path, data, session_id)


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def _has_any(text: str, words: tuple[str, ...] | list[str]) -> bool:
    hay = _norm(text)
    return any(_norm(word) in hay for word in words)


def _canonical_id(value: Any) -> str:
    s = _norm(value).strip()
    aliases = {
        "рей": RAY,
        "rey": RAY,
        "ray": RAY,
        "рейден": RAIDEN,
        "рейдон": RAIDEN,
        "raiden_sterling": RAIDEN,
        "raiden": RAIDEN,
    }
    return aliases.get(s, str(value or "").strip())


def _unique(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in out:
            out.append(item)
    return out


def _entries(history: Any) -> list[dict[str, Any]]:
    if isinstance(history, list):
        return [x for x in history if isinstance(x, dict)]
    if isinstance(history, dict) and isinstance(history.get("entries"), list):
        return [x for x in history["entries"] if isinstance(x, dict)]
    return []


def _latest_entry(session_id: str) -> dict[str, Any]:
    items = _entries(_read_json(SCENE_HISTORY_FILE, session_id, {"entries": []}))
    return items[-1] if items else {}


def _latest_text(session_id: str, limit: int = 3) -> str:
    items = _entries(_read_json(SCENE_HISTORY_FILE, session_id, {"entries": []}))
    chunks: list[str] = []
    for entry in items[-limit:]:
        for key in ("player_input", "visible_scene_text", "scene_text"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())
    return "\n\n".join(chunks)


def _location_blob(current: dict[str, Any], scene_text: str = "") -> str:
    return "\n".join(str(current.get(key) or "") for key in (
        "current_location_id",
        "current_location_text",
        "current_scene_id",
        "scene_id",
    )) + "\n" + str(scene_text or "")


def _is_jun_house(current: dict[str, Any], scene_text: str = "") -> bool:
    return _has_any(_location_blob(current, scene_text), JUN_HOUSE_WORDS)


def _ray_allowed_here(current: dict[str, Any], scene_text: str = "") -> bool:
    blob = _location_blob(current, scene_text)
    if _is_jun_house(current, scene_text):
        return False
    return _has_any(blob, BASE_WORDS)


def _add_id(current: dict[str, Any], field: str, cid: str) -> bool:
    value = current.get(field)
    if not isinstance(value, list):
        value = []
    if cid not in [_canonical_id(x) for x in value]:
        value.append(cid)
        current[field] = value
        return True
    return False


def _remove_physical_id(current: dict[str, Any], cid: str) -> bool:
    changed = False
    for field in PHYSICAL_FIELDS:
        value = current.get(field)
        if not isinstance(value, list):
            continue
        new = [x for x in value if _canonical_id(x) != cid]
        if new != value:
            current[field] = new
            changed = True
    return changed


def _event_ids(source: Any) -> list[str]:
    ids: list[str] = []
    if isinstance(source, list):
        for item in source:
            if isinstance(item, str):
                ids.append(item)
            elif isinstance(item, dict):
                event_id = item.get("id") or item.get("event_id") or item.get("key")
                if event_id:
                    ids.append(str(event_id))
    elif isinstance(source, dict):
        for key, item in source.items():
            ids.append(str(key))
            if isinstance(item, dict):
                event_id = item.get("id") or item.get("event_id")
                if event_id:
                    ids.append(str(event_id))
    return _unique(ids)


def _all_event_ids(current: dict[str, Any], calendar: dict[str, Any], future: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for source in (current, calendar, future):
        if not isinstance(source, dict):
            continue
        for key in ("pending_events", "active_events", "due_events", "open_events", "conditional_events", "future_locks", "locks"):
            ids.extend(_event_ids(source.get(key)))
    return _unique(ids)


def _raiden_present_or_pending(current: dict[str, Any]) -> bool:
    for field in PHYSICAL_FIELDS + ["pending_character_ids", "scheduled_character_ids", "conditional_character_ids", "mentioned_character_ids"]:
        value = current.get(field)
        if isinstance(value, list) and any(_canonical_id(x) == RAIDEN for x in value):
            return True
    pending = current.get("pending_character_entries")
    return isinstance(pending, dict) and RAIDEN in pending


def _mark_raiden(current: dict[str, Any], *, active: bool) -> bool:
    changed = False
    for field in ("pending_character_ids", "scheduled_character_ids", "conditional_character_ids", "nearby_characters", "nearby_character_ids"):
        changed |= _add_id(current, field, RAIDEN)
    if active:
        changed |= _add_id(current, "active_characters", RAIDEN)
        changed |= _add_id(current, "active_character_ids", RAIDEN)

    pending = current.get("pending_character_entries")
    if not isinstance(pending, dict):
        pending = {}
    entry = {
        "character_id": RAIDEN,
        "event_id": RAIDEN_EVENT,
        "event_type": "character_arrival",
        "known_to_runtime": True,
        "known_to_akira": False,
        "do_not_replace_with_generic_npc": True,
        "required_character_files": RAIDEN_FILES,
    }
    if pending.get(RAIDEN) != entry:
        pending[RAIDEN] = entry
        current["pending_character_entries"] = pending
        changed = True

    locks = current.get("character_identity_locks")
    if not isinstance(locks, dict):
        locks = {}
    lock = {
        "known_to_runtime": True,
        "known_to_akira": False,
        "do_not_replace_with_new_npc": True,
        "source_event": RAIDEN_EVENT,
        "rule": "Calendar-backed arrival. Visible naming still follows POV knowledge.",
    }
    if locks.get(RAIDEN) != lock:
        locks[RAIDEN] = lock
        current["character_identity_locks"] = locks
        changed = True

    current["generic_pressure_events_do_not_spawn_characters"] = True
    blocked = current.get("blocked_generic_pressure_event_ids")
    if not isinstance(blocked, list):
        blocked = []
    if SAMUEL_PRESSURE not in blocked:
        blocked.append(SAMUEL_PRESSURE)
        current["blocked_generic_pressure_event_ids"] = blocked
        changed = True

    resolution = current.get("character_entry_resolution")
    if not isinstance(resolution, dict):
        resolution = {}
    resolution[RAIDEN] = {
        "event_id": RAIDEN_EVENT,
        "character_id": RAIDEN,
        "priority": "character_arrival_over_generic_pressure",
        "blocked_generic_pressure_event": SAMUEL_PRESSURE,
        "updated_at": datetime.utcnow().isoformat(),
    }
    current["character_entry_resolution"] = resolution
    return True if changed else False


def _update_calendar_after_raiden(session_id: str, calendar: dict[str, Any], dry_run: bool) -> bool:
    if not isinstance(calendar, dict):
        return False
    changed = False

    pending = calendar.get("pending_events")
    if isinstance(pending, list) and RAIDEN_EVENT in pending:
        calendar["pending_events"] = [x for x in pending if x != RAIDEN_EVENT]
        changed = True

    activated = calendar.get("activated_events")
    if not isinstance(activated, list):
        activated = []
    if RAIDEN_EVENT not in activated:
        activated.append(RAIDEN_EVENT)
        calendar["activated_events"] = activated
        changed = True

    introduced = calendar.get("introduced_character_ids")
    if not isinstance(introduced, list):
        introduced = []
    if RAIDEN not in introduced:
        introduced.append(RAIDEN)
        calendar["introduced_character_ids"] = introduced
        changed = True

    if changed and not dry_run:
        calendar["last_updated_at"] = datetime.utcnow().isoformat()
        _write_json(CALENDAR_RUNTIME_FILE, calendar, session_id)
    return changed


def _sync_from_scene_history(session_id: str, current: dict[str, Any], dry_run: bool) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(current, dict):
        current = {}
    changed = False
    latest = _latest_entry(session_id)
    text = str(latest.get("visible_scene_text") or latest.get("scene_text") or "")
    player = str(latest.get("player_input") or "")

    if text:
        for key in ("last_visible_scene_text", "visible_scene_text"):
            if current.get(key) != text:
                current[key] = text
                changed = True
    if player and current.get("last_player_input") != player:
        current["last_player_input"] = player
        changed = True

    entries = _entries(_read_json(SCENE_HISTORY_FILE, session_id, {"entries": []}))
    if entries and int(current.get("scene_count") or 0) < len(entries):
        current["scene_count"] = len(entries)
        changed = True

    if text and _is_jun_house(current, text):
        if current.get("current_location_id") != "jun_house":
            current["current_location_id"] = "jun_house"
            changed = True
        if current.get("current_location_text") != "Дом Джуна":
            current["current_location_text"] = "Дом Джуна"
            changed = True

    lower = _norm(text)
    visible = {
        "jun": ("джун",),
        "emma": ("эмма", "эмму", "эмме"),
        "irey": ("ирэй", "ирея", "ирею", "ирей"),
        RAIDEN: ("райден", "рейден"),
    }
    for cid, words in visible.items():
        if any(word in lower for word in words):
            changed |= _add_id(current, "nearby_characters", cid)
            changed |= _add_id(current, "nearby_character_ids", cid)
            changed |= _add_id(current, "active_characters", cid)
            changed |= _add_id(current, "active_character_ids", cid)

    if not _ray_allowed_here(current, text):
        changed |= _remove_physical_id(current, RAY)

    if changed and not dry_run:
        _write_json(CURRENT_STATE_FILE, current, session_id)
        return current, [CURRENT_STATE_FILE]
    return current, []


def _resolve_calendar_entries(session_id: str, current: dict[str, Any], dry_run: bool) -> tuple[dict[str, Any], list[str], str]:
    calendar = _read_json(CALENDAR_RUNTIME_FILE, session_id, {})
    future = _read_json(FUTURE_LOCKS_FILE, session_id, {})
    events = _all_event_ids(current, calendar if isinstance(calendar, dict) else {}, future if isinstance(future, dict) else {})
    text = "\n".join([
        str(current.get("last_player_input") or ""),
        str(current.get("current_scene_goal") or ""),
        str(current.get("current_location_text") or ""),
        _latest_text(session_id),
    ])

    changed = False
    changed_files: list[str] = []
    reason = "no_calendar_character_arrival"

    if not _ray_allowed_here(current, text):
        if _remove_physical_id(current, RAY):
            changed = True
            reason = "removed_ray_until_base"

    due = RAIDEN_EVENT in events
    triggered = _has_any(text, RAIDEN_TRIGGER_WORDS)
    in_house = _is_jun_house(current, text)
    already = _raiden_present_or_pending(current)

    if (due or already) and in_house and (triggered or already):
        active = _has_any(text, ("открой", "впуст", "гост", "у двери", "вош", "появ", "стук"))
        if _mark_raiden(current, active=active):
            changed = True
        if due and isinstance(calendar, dict) and _update_calendar_after_raiden(session_id, calendar, dry_run):
            changed_files.append(CALENDAR_RUNTIME_FILE)
        reason = "activated_raiden_calendar_arrival"

    if changed and not dry_run:
        _write_json(CURRENT_STATE_FILE, current, session_id)
        if CURRENT_STATE_FILE not in changed_files:
            changed_files.append(CURRENT_STATE_FILE)

    return current, _unique(changed_files), reason


def sync_current_and_calendar_entries(session_id: str, dry_run: bool = False) -> tuple[dict[str, Any], list[str], str]:
    sid = _safe_session_id(session_id)
    current = _read_json(CURRENT_STATE_FILE, sid, {})
    if not isinstance(current, dict):
        current = {}
    current, files1 = _sync_from_scene_history(sid, current, dry_run)
    current, files2, reason = _resolve_calendar_entries(sid, current, dry_run)
    return current, _unique(files1 + files2), reason


def _extract_current_state_patch(payload: dict[str, Any]) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    for names in (["current_state_changes", "current_state", "state_changes"], ["current_state_patch", "current_patch"]):
        section = state_persistence.find_section(payload, names)
        if isinstance(section, dict):
            patches.append(section)

    state_patches = state_persistence.find_section(payload, ["state_patches", "patches"])
    if isinstance(state_patches, dict):
        for key in (CURRENT_STATE_FILE, "current_state.json", "current_state"):
            section = state_patches.get(key)
            if isinstance(section, dict):
                patches.append(section)
        direct = {
            "current_location_id", "current_location_text", "current_scene_id", "scene_id",
            "active_characters", "active_character_ids", "nearby_characters", "nearby_character_ids",
            "visible_inventory", "nearby_items", "current_outfit", "last_player_input",
        }
        if any(key in state_patches for key in direct):
            patches.append({key: state_patches[key] for key in direct if key in state_patches})

    merged: dict[str, Any] = {}
    for patch in patches:
        try:
            merged = base.deep_merge(merged, patch)
        except Exception:
            merged.update(patch)
    return merged


def _apply_current_state_patch(session_id: str, payload: dict[str, Any], scene_text: str, dry_run: bool) -> list[str]:
    patch = _extract_current_state_patch(payload)
    if scene_text:
        patch.setdefault("last_visible_scene_text", scene_text)
        patch.setdefault("visible_scene_text", scene_text)
    if not patch:
        return []

    current = _read_json(CURRENT_STATE_FILE, session_id, {})
    if not isinstance(current, dict):
        current = {}

    old = json.dumps(current, ensure_ascii=False, sort_keys=True, default=str)
    try:
        new = base.deep_merge(current, patch)
    except Exception:
        new = dict(current)
        new.update(patch)

    if json.dumps(new, ensure_ascii=False, sort_keys=True, default=str) == old:
        return []
    if not dry_run:
        _write_json(CURRENT_STATE_FILE, new, session_id)
    return [CURRENT_STATE_FILE]


def _to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump()
    if isinstance(response, dict):
        return dict(response)
    return {
        "status": getattr(response, "status", "applied"),
        "session_id": getattr(response, "session_id", None),
        "source": getattr(response, "source", None),
        "dry_run": getattr(response, "dry_run", False),
        "changed_files": list(getattr(response, "changed_files", []) or []),
        "visible_scene_text": getattr(response, "visible_scene_text", ""),
        "final_scene_text": getattr(response, "final_scene_text", ""),
        "render_packet_received": getattr(response, "render_packet_received", False),
    }


def _remove_route(path: str, method: str = "POST") -> None:
    app.router.routes = [
        route for route in app.router.routes
        if not (getattr(route, "path", None) == path and method in (getattr(route, "methods", set()) or set()))
    ]


_ORIGINAL_APPLY = getattr(state_persistence, "apply_turn_result_persistent", None)
_APPLY_PATH = state_persistence.APPLY_TURN_RESULT_PATH

_remove_route(_APPLY_PATH, "POST")


@app.post(_APPLY_PATH, response_model=ccp.ApplyTurnResultWithVisibleSceneResponse, operation_id="applyTurnResult")
def apply_turn_result_calendar_driven(
    session_id: str,
    request: ccp.ApplyTurnResultWithVisibleSceneRequest = ccp.ApplyTurnResultWithVisibleSceneRequest(),
):
    sid = _safe_session_id(session_id)
    if _ORIGINAL_APPLY is not None:
        response = _ORIGINAL_APPLY(sid, request)
    else:
        response = ccp.ApplyTurnResultWithVisibleSceneResponse(
            status="no_changes_detected",
            session_id=sid,
            source="calendar_driven_fallback",
            dry_run=request.dry_run,
            changed_files=[],
            visible_scene_text=request.visible_scene_text or "",
            final_scene_text=request.visible_scene_text or "",
            render_packet_received=isinstance(request.render_packet, dict),
        )

    data = _to_dict(response)
    changed = list(data.get("changed_files") or [])

    try:
        _source, payload = state_persistence._payload_from_request_or_turn_file(sid, request)
    except Exception:
        payload = request.data if isinstance(request.data, dict) else {}

    scene_text = str(data.get("visible_scene_text") or data.get("final_scene_text") or request.visible_scene_text or "")
    if isinstance(payload, dict):
        changed.extend(_apply_current_state_patch(sid, payload, scene_text, request.dry_run))

    _current, sync_files, reason = sync_current_and_calendar_entries(sid, request.dry_run)
    changed.extend(sync_files)
    changed = _unique(changed)

    if not request.dry_run:
        last = _read_json(state_persistence.LAST_APPLY_RESULT_FILE, sid, {})
        if isinstance(last, dict):
            last["changed_files"] = changed
            last["calendar_driven_entry_sync"] = {
                "status": "ok",
                "reason": reason,
                "updated_at": datetime.utcnow().isoformat(),
            }
            _write_json(state_persistence.LAST_APPLY_RESULT_FILE, last, sid)
            if state_persistence.LAST_APPLY_RESULT_FILE not in changed:
                changed.append(state_persistence.LAST_APPLY_RESULT_FILE)

    data["changed_files"] = changed
    data["status"] = "applied" if changed else data.get("status", "no_changes_detected")
    return ccp.ApplyTurnResultWithVisibleSceneResponse(**data)


_ORIGINAL_FAST_REQUIRED = getattr(fast_context, "_required_files_for_session", None)


def _required_files_for_session_calendar_driven(session_id: str):
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)
    current, _changed, _reason = sync_current_and_calendar_entries(sid, dry_run=False)
    future = _read_json(FUTURE_LOCKS_FILE, sid, {})

    try:
        files = list(base.recommended_files_for_context(current, future))
    except Exception:
        if _ORIGINAL_FAST_REQUIRED is not None:
            files, _old_current, future = _ORIGINAL_FAST_REQUIRED(sid)
        else:
            files = []

    if _raiden_present_or_pending(current):
        files.extend(RAIDEN_FILES)

    if not _ray_allowed_here(current, _latest_text(sid)):
        files = [path for path in files if not str(path).startswith("characters/ray/")]

    return _unique(files), current, future


fast_context._required_files_for_session = _required_files_for_session_calendar_driven  # type: ignore[assignment]


_ORIGINAL_SAFE_READ_JSON = size_guard._safe_read_json


def _safe_read_json_calendar_driven(path: str, session_id: str, default: Any) -> Any:
    data = _ORIGINAL_SAFE_READ_JSON(path, session_id, default)
    if path == CURRENT_STATE_FILE and isinstance(data, dict):
        current = dict(data)
        current, _ = _sync_from_scene_history(_safe_session_id(session_id), current, dry_run=True)
        current, _files, _reason = _resolve_calendar_entries(_safe_session_id(session_id), current, dry_run=True)
        return current
    return data


size_guard._safe_read_json = _safe_read_json_calendar_driven  # type: ignore[assignment]

try:
    app.version = "0.3.144-calendar-driven-entry-v1"
except Exception:
    pass
