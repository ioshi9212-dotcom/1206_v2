"""Memory-safe scene contract layer for 1206_v2.

This patch keeps the compact Actions flow, but adds a focused memory-retention
slice to /api/v2/sessions/{session_id}/scene-contract so GPT does not lose
important session facts between turns.

It does NOT return full loaded_files. It returns curated state/history/knowledge
summaries that are small enough for GPT Actions and strong enough for gameplay.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import Query

from app import compact as base
import app.compact_scene_contract_runtime_patch as scene_contract_base

app = base.app
RUNTIME_VERSION = "0.3.150-memory-safe-scene-contract-v1"

SCENE_HISTORY_FILE = "state/scene_history.json"
LAST_APPLY_RESULT_FILE = "state/last_apply_result.json"
RELATIONSHIPS_FILE = "state/relationships.json"
SCENE_CONTINUITY_FILE = "state/scene_continuity_state.json"

PRIORITY_KNOWLEDGE_FIELDS = [
    "знает",
    "не знает",
    "ошибочно считает",
    "видел",
    "слышал",
    "произошло при нём",
    "произошло при нем",
    "важное от Акиры",
    "важное сказанное Акире",
    "выводы",
    "скрывает от",
    "жёсткие запреты знания",
    "жесткие запреты знания",
    "правило_понимания_амнезии",
    "правило_понимания_закрытого_потока",
    "knows",
    "does_not_know",
    "wrong_beliefs",
    "observed",
    "heard",
    "conclusions",
    "hides_from",
    "hard_knowledge_bans",
]


def _safe_session_id(session_id: str) -> str:
    try:
        return base.safe_session_id(session_id)
    except Exception:
        cleaned = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
        return cleaned or "default"


def _trim(value: Any, limit: int = 700) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 18)].rstrip() + "\n...[truncated]"


def _compact(value: Any, *, max_chars: int = 900, max_items: int = 8, depth: int = 2) -> Any:
    if depth <= 0:
        if isinstance(value, str):
            return _trim(value, max_chars)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return _trim(json.dumps(value, ensure_ascii=False, separators=(",", ":")), max_chars)
    if isinstance(value, str):
        return _trim(value, max_chars)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_compact(item, max_chars=max_chars, max_items=max_items, depth=depth - 1) for item in value[:max_items]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        keys = [key for key in PRIORITY_KNOWLEDGE_FIELDS if key in value]
        keys += [key for key in value.keys() if key not in keys]
        for key in keys[:max_items]:
            result[str(key)] = _compact(value[key], max_chars=max_chars, max_items=max_items, depth=depth - 1)
        return result
    return _trim(str(value), max_chars)


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        value = base.read_json(path, session_id=session_id, default=default)
        return default if value is None else value
    except Exception:
        return default


def _history_entries(history: Any) -> list[dict[str, Any]]:
    if isinstance(history, list):
        return [entry for entry in history if isinstance(entry, dict)]
    if isinstance(history, dict):
        entries = history.get("entries", [])
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
    return []


def _recent_scene_memory(session_id: str) -> list[dict[str, Any]]:
    entries = _history_entries(_read_json(SCENE_HISTORY_FILE, session_id, []))[-3:]
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        is_last = index == len(entries) - 1
        result.append({
            "id": entry.get("id") or entry.get("scene_id"),
            "turn_number": entry.get("turn_number"),
            "current_date": entry.get("current_date"),
            "current_time": entry.get("current_time"),
            "location_text": entry.get("location_text"),
            "active_characters": entry.get("active_characters", []),
            "nearby_characters": entry.get("nearby_characters", []),
            "player_input": _trim(entry.get("player_input"), 260),
            "visible_scene_text": _trim(entry.get("visible_scene_text") or entry.get("scene_text"), 1250 if is_last else 700),
            "changed_files_snapshot": entry.get("changed_files_snapshot", []),
        })
    return result


def _expanded_dynamic_knowledge(session_id: str, scene_ids: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for cid in scene_ids[:6]:
        per_char = _read_json(f"state/character_knowledge/{cid}.json", session_id, {})
        if isinstance(per_char, dict) and per_char:
            result[cid] = _compact(per_char, max_chars=1000, max_items=10, depth=2)
            continue
        state = _read_json("state/knowledge_state.json", session_id, {})
        value = {}
        if isinstance(state, dict):
            value = state.get(cid) or state.get(f"char_{cid}") or {}
            if not value and isinstance(state.get("character_knowledge"), dict):
                value = state["character_knowledge"].get(cid) or state["character_knowledge"].get(f"char_{cid}") or {}
        if isinstance(value, dict) and value:
            result[cid] = _compact(value, max_chars=1000, max_items=10, depth=2)
    return result


def _expanded_relationship_memory(session_id: str, scene_ids: list[str]) -> dict[str, Any]:
    state = _read_json(RELATIONSHIPS_FILE, session_id, {})
    if not isinstance(state, dict):
        return {}
    pairs = state.get("pairs") if isinstance(state.get("pairs"), dict) else state
    if not isinstance(pairs, dict):
        return {}
    focus = set(scene_ids)
    result: dict[str, Any] = {}
    for key, value in pairs.items():
        low = str(key).lower()
        if not any(cid in low for cid in focus):
            continue
        if isinstance(value, dict):
            result[str(key)] = _compact(value, max_chars=650, max_items=9, depth=2)
        if len(result) >= 12:
            break
    return result


def _continuity_memory(session_id: str) -> Any:
    data = _read_json(SCENE_CONTINUITY_FILE, session_id, {})
    if not isinstance(data, dict):
        return {}
    return _compact(data, max_chars=850, max_items=8, depth=2)


def _last_apply_result(session_id: str) -> Any:
    data = _read_json(LAST_APPLY_RESULT_FILE, session_id, {})
    if not isinstance(data, dict):
        return {}
    return _compact(data, max_chars=650, max_items=8, depth=2)


def _build_memory_retention_slice(session_id: str, contract: dict[str, Any], scene_ids: list[str]) -> dict[str, Any]:
    return {
        "purpose": "Do not lose session facts. This slice is more important than generic character/card prose for the current turn.",
        "recent_scene_memory": _recent_scene_memory(session_id),
        "expanded_dynamic_knowledge_by_character": _expanded_dynamic_knowledge(session_id, scene_ids),
        "expanded_relationship_memory": _expanded_relationship_memory(session_id, scene_ids),
        "scene_continuity_memory": _continuity_memory(session_id),
        "last_apply_result": _last_apply_result(session_id),
        "anti_loss_rules": [
            "Treat recent_scene_memory and expanded_dynamic_knowledge_by_character as active memory, not optional background.",
            "If an NPC learned, saw, heard, suspected, hid, promised, suffered, or chose something in previous turns, it must affect this turn unless current_state explicitly changed it.",
            "Never overwrite state/current_state facts with generic defaults from a character card.",
            "Character cards define baseline personality; session memory overrides baseline for what happened in this playthrough.",
            "If current player input is only in parentheses, Akira does not speak new dialogue.",
            "Known-name is temporal: do not use a name in visible POV until it was revealed to that POV.",
        ],
        "apply_turn_result_required_after_scene": {
            "rule": "If the scene changes anything meaningful, call applyTurnResult before finalizing the turn.",
            "minimum_sections_to_consider": [
                "current_state_changes",
                "scene_continuity_changes",
                "relationship_changes",
                "knowledge_changes / character_knowledge_changes",
                "inventory_changes",
                "calendar_runtime_changes",
            ],
            "warning": "If these changes are not sent, the next turn will lose the information even if the visible scene was correct.",
        },
    }


def _cap_response(response: dict[str, Any], max_total_chars: int) -> dict[str, Any]:
    try:
        limit = max(9000, min(int(max_total_chars or 12000), 18000))
    except Exception:
        limit = 12000
    estimated = len(json.dumps(response, ensure_ascii=False))
    if estimated <= limit:
        return response
    contract = response.get("scene_contract", {}) if isinstance(response.get("scene_contract"), dict) else {}
    memory = contract.get("memory_retention_slice", {}) if isinstance(contract.get("memory_retention_slice"), dict) else {}
    # Keep the newest scene, but cut older history first.
    recent = memory.get("recent_scene_memory")
    if isinstance(recent, list) and len(recent) > 1:
        memory["recent_scene_memory"] = recent[-2:]
    for entry in memory.get("recent_scene_memory", []) if isinstance(memory.get("recent_scene_memory"), list) else []:
        if isinstance(entry, dict):
            entry["visible_scene_text"] = _trim(entry.get("visible_scene_text"), 700)
    # Then compact expanded memory, but keep the keys.
    if isinstance(memory.get("expanded_dynamic_knowledge_by_character"), dict):
        for cid, value in list(memory["expanded_dynamic_knowledge_by_character"].items()):
            memory["expanded_dynamic_knowledge_by_character"][cid] = _compact(value, max_chars=520, max_items=7, depth=1)
    if isinstance(memory.get("expanded_relationship_memory"), dict):
        for key, value in list(memory["expanded_relationship_memory"].items()):
            memory["expanded_relationship_memory"][key] = _compact(value, max_chars=420, max_items=7, depth=1)
    response.setdefault("context_audit", {})["memory_safe_compacted_after_estimate"] = estimated
    return response


def build_memory_safe_scene_contract_response(session_id: str, *, max_total_chars: int = 12000, include_debug: bool = False) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    response = scene_contract_base.build_scene_contract_response(
        sid,
        max_total_chars=max(max_total_chars, 12000),
        include_debug=include_debug,
    )
    contract = response.get("scene_contract", {}) if isinstance(response.get("scene_contract"), dict) else {}
    scene_ids = response.get("scene_character_ids") or contract.get("current_frame", {}).get("scene_character_ids") or ["akira"]
    scene_ids = [str(cid) for cid in scene_ids if cid]
    contract["memory_retention_slice"] = _build_memory_retention_slice(sid, contract, scene_ids)
    contract.setdefault("render_rules", [])
    if isinstance(contract["render_rules"], list):
        contract["render_rules"] = [
            "Before writing, read memory_retention_slice first; it overrides generic card defaults for this session.",
            "Preserve recent_scene_memory, expanded_dynamic_knowledge_by_character, relationship memory and continuity memory.",
            "After the visible scene, call applyTurnResult with explicit changes or the next turn will lose them.",
        ] + contract["render_rules"]
    response["runtime_version"] = RUNTIME_VERSION
    response["mode"] = "scene_contract_memory_safe"
    response["created_at"] = datetime.utcnow().isoformat()
    response.setdefault("context_audit", {})["memory_safe_enabled"] = True
    response["context_audit"]["memory_safe_contract_chars_estimate"] = len(json.dumps(response, ensure_ascii=False))
    return _cap_response(response, max_total_chars)


def _remove_route(path: str, method: str | None = None) -> None:
    method_upper = method.upper() if method else None
    for route in list(app.router.routes):
        if getattr(route, "path", None) != path:
            continue
        methods = set(getattr(route, "methods", set()) or set())
        if method_upper is None or method_upper in methods:
            app.router.routes.remove(route)


_remove_route("/api/v2/sessions/{session_id}/scene-contract", "GET")
_remove_route("/api/v2/sessions/{session_id}/turn-packet", "GET")


@app.get("/api/v2/sessions/{session_id}/scene-contract", operation_id="getSceneContract")
def get_scene_contract_memory_safe(
    session_id: str,
    max_total_chars: int = Query(default=12000, ge=9000, le=18000),
    include_debug: bool = Query(default=False),
) -> dict[str, Any]:
    return build_memory_safe_scene_contract_response(session_id, max_total_chars=max_total_chars, include_debug=include_debug)


@app.get("/api/v2/sessions/{session_id}/turn-packet", operation_id="getTurnPacket")
def get_turn_packet_memory_safe(
    session_id: str,
    max_total_chars: int = Query(default=12000, ge=9000, le=18000),
    include_debug: bool = Query(default=False),
) -> dict[str, Any]:
    response = build_memory_safe_scene_contract_response(session_id, max_total_chars=max_total_chars, include_debug=include_debug)
    response["mode"] = "turn_packet_compat_returns_memory_safe_scene_contract"
    return response


try:
    app.version = RUNTIME_VERSION
except Exception:
    pass
