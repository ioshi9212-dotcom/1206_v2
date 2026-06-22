"""Current-scene-only context filter for 1206 v2.

Fixes two runtime problems:
1) Required files must load Akira + only characters physically/actively present in
   the current scene. Mentioned/scheduled/delayed/future characters are not loaded.
2) Live state must be a focused scene slice, not full relationship/knowledge/history
   JSON for the whole story.

This patch is intentionally loaded late from production_runtime_patch, after
character_registry, lean_context, state_memory and time_flow patches.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from fastapi import Body

import app.lean_context_loading_runtime_patch as lean
import app.state_memory_relationship_context_runtime_patch as state_memory
from app.start_scene_runtime_patch import app
from app import compact as base

try:
    import app.compact_context_patch as compact_context
except Exception:  # pragma: no cover
    compact_context = None  # type: ignore[assignment]

VIRTUAL_SCENE_STATE_SLICE = "runtime/current_scene_state_slice.json"
GAMEPLAY_RESPONSE_GATE_FILE = "gpt/locks/gameplay_response_gate.md"
PLAYER_INPUT_ANCHOR_LOCK_FILE = "gpt/locks/player_input_anchor_lock.md"
VISIBLE_SCENE_LOCK_FILE = "gpt/locks/gameplay_visible_scene_before_state_and_no_status_summary.md"

PRESENT_ROSTER_FIELDS = [
    "pov_character_id",
    "pov_character",
    "active_character_ids",
    "active_characters",
    "nearby_character_ids",
    "nearby_characters",
    "speaking_character_ids",
    "speaking_characters",
    "observing_character_ids",
    "observing_characters",
    "addressed_character_ids",
    "addressed_characters",
    "looked_at_character_ids",
    "looked_at_characters",
    "present_character_ids",
    "present_characters",
    "characters_in_scene",
    "scene_character_ids",
]

EXCLUDED_ROSTER_FIELDS = [
    "mentioned_character_ids",
    "mentioned_characters",
    "scheduled_character_ids",
    "scheduled_characters",
    "delayed_character_ids",
    "delayed_characters",
    "conditional_character_ids",
    "conditional_characters",
    "allowed_main_characters",
]

ALWAYS_SMALL_FILES = [
    "state/player_input_parsing_rules.json",
    "state/narrative_director_rules.json",
    "state/context_loading_rules_1206.json",
    "state/time_flow_rules_1206.json",
    "state/relationship_memory_rules_1206.json",
    "calendar/east_sector_1206_calendar.yaml",
    GAMEPLAY_RESPONSE_GATE_FILE,
    PLAYER_INPUT_ANCHOR_LOCK_FILE,
    VISIBLE_SCENE_LOCK_FILE,
]


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    return text


def _cid(value: Any) -> str:
    raw = _clean(value)
    if not raw:
        return ""
    try:
        return lean.CHARACTER_ALIASES.get(raw, raw)
    except Exception:
        return raw


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        cid = _cid(value)
        if cid and cid not in result:
            result.append(cid)
    return result


def _values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []


def _state(session_id: str) -> dict[str, Any]:
    try:
        return lean._safe_state(session_id)
    except Exception:
        try:
            return base.read_json("state/current_state.json", session_id, default={}) or {}
        except Exception:
            return {}


def present_character_ids_from_state(state: dict[str, Any] | None) -> list[str]:
    state = state or {}
    raw: list[Any] = ["akira"]
    for key in PRESENT_ROSTER_FIELDS:
        raw.extend(_values(state.get(key)))
    return _unique(raw)


def _scene_id(state: dict[str, Any]) -> str:
    try:
        return lean._scene_id(state)
    except Exception:
        return str(state.get("current_scene_id") or state.get("scene_id") or "start_scene")


def _exists(path: str, session_id: str | None = None) -> bool:
    if path == VIRTUAL_SCENE_STATE_SLICE:
        return True
    try:
        return bool(lean._read_text(path, session_id=session_id))
    except TypeError:
        return bool(lean._read_text(path))
    except Exception:
        return False


def _character_files(cid: str, *, include_past: bool = False) -> list[str]:
    cid = _cid(cid)
    files = list(lean.CHARACTER_FILES.get(cid, []))
    if include_past:
        past = lean.PAST_FILES.get(cid)
        if past:
            files.append(past)
    return [p for p in files if _exists(p)]


def _text_has(text: str, needles: list[str]) -> bool:
    low = str(text or "").lower().replace("ё", "е")
    return any(n.lower().replace("ё", "е") in low for n in needles)


def _past_needed_for(cid: str, trigger_text: str) -> bool:
    cid = _cid(cid)
    if cid == "akira":
        return _text_has(trigger_text, [
            "память", "шрам", "кольцо", "пирсинг", "кот", "животн", "пространств", "ребен", "ребён", "беремен", "самуэл", "самуэль",
        ])
    if cid == "raiden":
        return _text_has(trigger_text, ["райден", "рейден", "кольц", "ar", "сигарет", "холод", "хвоя", "пирсинг"])
    if cid == "irey":
        return _text_has(trigger_text, ["ирэй", "ирей", "якор", "касани", "след", "самуэл", "самуэль", "похорон"])
    if cid == "yuna":
        return _text_has(trigger_text, ["юна", "медик", "медблок", "рана", "ранение", "кров", "осмотр", "ребен", "ребён", "самуэл", "самуэль"])
    if cid in {"jun", "ray", "miki", "emma", "haru"}:
        return _text_has(trigger_text, [cid, "прошл", "память", "самуэл", "самуэль"])
    return False


def _trigger_text(state: dict[str, Any], user_input: str = "") -> str:
    return " ".join(
        [
            str(user_input or ""),
            str(state.get("current_scene_goal") or ""),
            str(state.get("last_player_action") or ""),
            str(state.get("current_location_text") or state.get("location") or ""),
        ]
    )


def required_files_current_scene(session_id: str, user_input: str = "") -> list[str]:
    state = _state(session_id)
    present_ids = present_character_ids_from_state(state)
    trigger_text = _trigger_text(state, user_input=user_input)
    files: list[str] = []

    for path in ALWAYS_SMALL_FILES:
        if _exists(path, session_id):
            files.append(path)

    for path in lean.CURRENT_SCENE_FILES.get(_scene_id(state), []):
        if _exists(path, session_id):
            files.append(path)

    # Focused scene state replaces full relationships/knowledge/history files.
    files.append(VIRTUAL_SCENE_STATE_SLICE)

    for cid in present_ids:
        files.extend(_character_files(cid, include_past=_past_needed_for(cid, trigger_text)))

    return list(dict.fromkeys(files))


def _keep_by_focus_key(key: Any, focus: set[str]) -> bool:
    text = str(key or "").lower().replace("ё", "е")
    if not text:
        return False
    return any(fid.lower() in text for fid in focus)


def _slice_relationships(data: Any, focus_ids: list[str]) -> Any:
    if not isinstance(data, dict):
        return {}
    focus = set(focus_ids)
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"schema", "project"}:
            result[key] = value
        elif key == "relationships" and isinstance(value, dict):
            result[key] = {k: v for k, v in value.items() if _keep_by_focus_key(k, focus)}
        elif key == "notes" and isinstance(value, list):
            result[key] = [n for n in value if _keep_by_focus_key(n, focus)][:20]
        elif _keep_by_focus_key(key, focus):
            result[key] = value
    return result


def _slice_knowledge(data: Any, focus_ids: list[str]) -> Any:
    if not isinstance(data, dict):
        return {}
    focus = set(focus_ids)
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"schema", "project"}:
            result[key] = value
        elif key in {"known_facts", "npc_knowledge_overrides"} and isinstance(value, dict):
            result[key] = {k: v for k, v in value.items() if _keep_by_focus_key(k, focus)}
        elif key == "unknown_to_player" and isinstance(value, list):
            result[key] = [n for n in value if _keep_by_focus_key(n, focus)][:30]
        elif _keep_by_focus_key(key, focus):
            result[key] = value
    return result


def _slice_scene_history(data: Any, focus_ids: list[str]) -> Any:
    if not isinstance(data, dict):
        return {}
    history = data.get("history") or data.get("entries") or data.get("scenes") or []
    if not isinstance(history, list):
        return {"note": "scene_history exists but has non-list structure", "focus_character_ids": focus_ids}
    focus = set(focus_ids)
    filtered = [item for item in history if _keep_by_focus_key(item, focus)]
    return {"recent_relevant_entries": filtered[-5:], "focus_character_ids": focus_ids}


def build_current_scene_state_slice(session_id: str, user_input: str = "") -> dict[str, Any]:
    state = _state(session_id)
    present_ids = present_character_ids_from_state(state)

    relationships = base.read_json("state/relationships.json", session_id, default={}) or {}
    knowledge = base.read_json("state/knowledge_state.json", session_id, default={}) or {}
    inventory = base.read_json("state/inventory_state.json", session_id, default={}) or {}
    history = base.read_json("state/scene_history.json", session_id, default={}) or {}

    character_state: dict[str, Any] = {}
    for cid in present_ids:
        key = f"{cid}_state"
        if isinstance(state.get(key), dict):
            character_state[key] = state.get(key)
    if "akira" in present_ids and isinstance(state.get("akira_state"), dict):
        character_state["akira_state"] = state.get("akira_state")

    return {
        "schema": "current_scene_state_slice_v1",
        "context_filter": {
            "mode": "current_scene_only",
            "present_character_ids": present_ids,
            "excluded_roster_fields": EXCLUDED_ROSTER_FIELDS,
            "rule": "Load only POV Akira plus characters currently present/active in the scene. Do not load merely mentioned/scheduled/delayed/future characters.",
        },
        "current_scene": {
            "date": state.get("current_date") or state.get("date"),
            "time": state.get("current_time") or state.get("time"),
            "scene_id": _scene_id(state),
            "location_id": state.get("current_location_id") or state.get("location_id"),
            "location_text": state.get("current_location_text") or state.get("location"),
            "weather": state.get("weather"),
            "current_outfit": state.get("current_outfit"),
            "visible_inventory": state.get("visible_inventory", []),
            "nearby_items": state.get("nearby_items", []),
            "current_scene_goal": state.get("current_scene_goal"),
            "last_player_input": user_input or state.get("last_player_input"),
            "scene_count": state.get("scene_count"),
        },
        "character_state": character_state,
        "relationships_slice": _slice_relationships(relationships, present_ids),
        "knowledge_slice": _slice_knowledge(knowledge, present_ids),
        "inventory_slice": {
            "visible_inventory": state.get("visible_inventory", []),
            "nearby_items": state.get("nearby_items", []),
            "akira_inventory_state": inventory.get("akira", {}) if isinstance(inventory, dict) else {},
        },
        "recent_scene_history_slice": _slice_scene_history(history, present_ids),
    }


_ORIGINAL_LEAN_READ_TEXT = lean._read_text


def _read_text_current_scene(path: str, session_id: str | None = None) -> str:
    safe = str(path or "").replace("\\", "/").strip().lstrip("/")
    if safe == VIRTUAL_SCENE_STATE_SLICE:
        sid = session_id or "default"
        return json.dumps(build_current_scene_state_slice(sid), ensure_ascii=False, indent=2)
    return _ORIGINAL_LEAN_READ_TEXT(path, session_id=session_id)


lean._read_text = _read_text_current_scene  # type: ignore[assignment]
lean._required_files = required_files_current_scene  # type: ignore[assignment]
lean._active_ids = lambda state: present_character_ids_from_state(state)  # type: ignore[assignment]

# State-memory patch used to append full state files; replace that with the virtual slice.
state_memory.LIVE_STATE_FILES = [VIRTUAL_SCENE_STATE_SLICE]
state_memory._live_state_files = lambda session_id: [VIRTUAL_SCENE_STATE_SLICE]  # type: ignore[assignment]
state_memory.focus_ids_from_state = lambda state, user_input="": present_character_ids_from_state(state)  # type: ignore[assignment]

if compact_context is not None:
    compact_context.active_scene_characters = lambda current, future=None: present_character_ids_from_state(current)  # type: ignore[attr-defined]
    compact_context.recommended_files_for_context = lambda current=None, future=None: required_files_current_scene("default")  # type: ignore[attr-defined]


def _remove_route(path: str, method: str | None = None) -> None:
    method_upper = method.upper() if method else None
    for route in list(app.router.routes):
        if getattr(route, "path", None) != path:
            continue
        methods = set(getattr(route, "methods", set()) or set())
        if method_upper is None or method_upper in methods:
            app.router.routes.remove(route)


for _path in [
    "/api/v1/sessions/{session_id}/required-files-manifest",
    "/api/v1/sessions/{session_id}/required-files-chunk",
    "/api/v1/sessions/{session_id}/required-files-bundle",
    "/api/v1/sessions/{session_id}/turn-contract",
]:
    _remove_route(_path)


def _chunk_files(files: list[str], *, max_items: int) -> list[list[str]]:
    max_items = max(1, min(int(max_items or lean.DEFAULT_CHUNK_MAX_ITEMS), 6))
    return [files[i:i + max_items] for i in range(0, len(files), max_items)] or [[]]


@app.get("/api/v1/sessions/{session_id}/required-files-manifest")
def getRequiredFilesManifest(session_id: str, user_input: str = "") -> dict[str, Any]:
    files = required_files_current_scene(session_id, user_input=user_input)
    chunks_total = len(_chunk_files(files, max_items=lean.DEFAULT_CHUNK_MAX_ITEMS))
    return {
        "session_id": session_id,
        "required_files": files,
        "files": [
            {
                "path": p,
                "exists": True,
                "source": "current_scene_virtual" if p == VIRTUAL_SCENE_STATE_SLICE else "project_or_session",
                "chars": len(lean._read_text(p, session_id=session_id)),
                "loaded_by": "current_scene_only_filter_v1",
                "content_in_contract": False,
            }
            for p in files
        ],
        "missing_files": [],
        "chunks_total": chunks_total,
        "loaded_count": len(files),
        "missing_count": 0,
        "usage_note": "Load chunks. Context is filtered to present characters and current-scene state slice only.",
    }


@app.get("/api/v1/sessions/{session_id}/required-files-chunk")
def getRequiredFilesChunk(
    session_id: str,
    chunk_index: int = 0,
    max_chars: int = lean.DEFAULT_CHUNK_MAX_CHARS,
    max_items: int = lean.DEFAULT_CHUNK_MAX_ITEMS,
    user_input: str = "",
) -> dict[str, Any]:
    files = required_files_current_scene(session_id, user_input=user_input)
    max_items = max(1, min(int(max_items or lean.DEFAULT_CHUNK_MAX_ITEMS), 6))
    max_chars = max(1000, min(int(max_chars or lean.DEFAULT_CHUNK_MAX_CHARS), 24000))
    chunks = _chunk_files(files, max_items=max_items)
    safe_index = max(0, min(int(chunk_index or 0), len(chunks) - 1))
    batch = chunks[safe_index]
    per_file_limit = max(1000, max_chars // max(1, len(batch) or 1))
    loaded = []
    used = 0
    for path in batch:
        raw = lean._read_text(path, session_id=session_id)
        cut = raw if len(raw) <= per_file_limit else raw[:per_file_limit]
        used += len(cut)
        loaded.append({"path": path, "content": cut, "truncated": len(cut) < len(raw), "chars": len(cut)})
    has_more = safe_index < len(chunks) - 1
    return {
        "session_id": session_id,
        "required_files": files,
        "chunk_index": safe_index,
        "chunks_total": len(chunks),
        "has_more": has_more,
        "next_chunk_index": safe_index + 1 if has_more else None,
        "loaded_files": loaded,
        "missing_files": [],
        "loaded_count": len(loaded),
        "missing_count": 0,
        "total_loaded_parts": used,
    }


@app.get("/api/v1/sessions/{session_id}/required-files-bundle")
def getRequiredFilesBundle(
    session_id: str,
    chunk_index: int = 0,
    max_chars: int = lean.DEFAULT_CHUNK_MAX_CHARS,
    max_items: int = lean.DEFAULT_CHUNK_MAX_ITEMS,
    user_input: str = "",
) -> dict[str, Any]:
    return getRequiredFilesChunk(
        session_id=session_id,
        chunk_index=chunk_index,
        max_chars=max_chars,
        max_items=max_items,
        user_input=user_input,
    )


@app.get("/api/v1/sessions/{session_id}/turn-contract")
def getSessionTurnContract(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    state = _state(session_id)
    present_ids = present_character_ids_from_state(state)
    files = required_files_current_scene(session_id, user_input=user_input)
    return {
        "success": True,
        "session_id": session_id,
        "mode": mode,
        "current_scene_anchor": {
            "date": state.get("current_date") or state.get("date"),
            "time": state.get("current_time") or state.get("time"),
            "scene_id": _scene_id(state),
            "location": state.get("current_location_id") or state.get("location_id") or state.get("location"),
            "present_character_ids": present_ids,
            "context_filter": "current_scene_only",
        },
        "active_character_ids": present_ids,
        "nearby_character_ids": [cid for cid in _values(state.get("nearby_character_ids") or state.get("nearby_characters"))],
        "required_files": files,
        "required_file_contents": {},
        "output_format_contract": {
            "scene_only_for_play": True,
            "no_technical_comment_before_scene": True,
            "no_author_comments": True,
            "player_controls_only_akira": True,
            "final_answer_must_not_include": [
                "API status",
                "contract summary",
                "saving log",
                "debug commentary",
                "author note",
                "Комментарий",
                "Технически",
                "Я загрузил/проверил/сохранил",
            ],
        },
        "required_checks_before_answer": [
            "Load required-files chunks before rendering.",
            "Use only present_character_ids from current_scene_anchor for character behavior.",
            "Do not load or act as merely mentioned/scheduled/delayed/future characters.",
            "Use runtime/current_scene_state_slice.json instead of full state files.",
            "Final gameplay answer must be scene only: no comments, no status, no explanations.",
        ],
        "relationship_context": {"load_from": VIRTUAL_SCENE_STATE_SLICE, "scope": "present characters only"},
        "knowledge_table": {"load_from": VIRTUAL_SCENE_STATE_SLICE, "scope": "present characters only"},
        "inventory_contract": {"load_from": VIRTUAL_SCENE_STATE_SLICE},
        "story_context": {"context_loading": "current_scene_only_filter_v1"},
        "prompt_preview": "Render only the gameplay scene. Use Akira + present characters only. Use current_scene_state_slice for state. Do not write technical/commentary text.",
        "usage_note": "Context is filtered: present characters only, focused current-scene state slice only.",
    }


@app.post("/api/v1/sessions/{session_id}/turn-contract")
def postSessionTurnContract(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return getSessionTurnContract(
        session_id,
        user_input=str(payload.get("user_input") or payload.get("player_input") or ""),
        mode=str(payload.get("mode") or "play"),
    )


try:
    app.version = "0.3.107-1206-current-scene-context-filter"
except Exception:
    pass
