"""Live state memory / relationship context patch for 1206 v13.

Keeps relationships and knowledge visible only for current active/nearby characters.
This patch does not write the turn result itself; state_persistence_runtime_patch does.
It enriches the lean turn-contract with compact live relationship and knowledge context.
"""
from __future__ import annotations

from typing import Any
from pathlib import Path
import json

from fastapi import Body

import app.lean_context_loading_runtime_patch as lean
from app.start_scene_runtime_patch import app
from app import compact as base

try:
    import app.state_persistence_runtime_patch as persistence  # noqa: F401
except Exception:
    # If import order already imported it elsewhere, keep running.
    pass

RELATIONSHIP_RULES_FILE = "state/relationship_memory_rules_1206.json"
RECENT_SCENE_HISTORY_LIMIT = 5


def _cid(raw: Any) -> str:
    try:
        return lean.CHARACTER_ALIASES.get(str(raw or "").strip(), str(raw or "").strip())
    except Exception:
        return str(raw or "").strip()


def _unique(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        cid = _cid(item)
        if cid and cid not in out:
            out.append(cid)
    return out


def _state(session_id: str) -> dict[str, Any]:
    try:
        return lean._safe_state(session_id)
    except Exception:
        try:
            return base.read_json("state/current_state.json", session_id, default={}) or {}
        except Exception:
            return {}


def focus_ids_from_state(state: dict[str, Any], user_input: str = "") -> list[str]:
    raw: list[Any] = ["akira"]
    for key in [
        "active_character_ids", "active_characters",
        "nearby_character_ids", "nearby_characters",
        "speaking_character_ids", "observing_character_ids",
    ]:
        value = state.get(key)
        if isinstance(value, list):
            raw.extend(value)

    # User explicit mentions allow loading absent relationship/knowledge.
    text = str(user_input or "").lower().replace("ё", "е")
    mention_map = {
        "raiden": ["райден", "рейден", "стэрлинг", "стерлинг"],
        "ray": ["рэй", "рей картер", "восточный сектор"],
        "jun": ["джун"],
        "irey": ["ирэй", "ирей"],
        "emma": ["эмма"],
        "yuna": ["юна", "медик"],
        "miki": ["мики"],
    }
    for cid, needles in mention_map.items():
        if any(n in text for n in needles):
            raw.append(cid)

    return _unique(raw)


def pair_in_focus(pair_id: str, focus: set[str]) -> bool:
    parts = [_cid(x) for x in str(pair_id).split("__") if x]
    if len(parts) != 2:
        return False
    # Keep pair if any participant is in current focus, but do not expand to all hidden pairs
    # unless one side is active/explicit.
    return bool(set(parts) & focus)


def compact_relationship_context(session_id: str, focus_ids: list[str]) -> dict[str, Any]:
    state = base.read_json("state/relationships.json", session_id, default={}) or {}
    pairs = state.get("pairs") if isinstance(state, dict) else None
    focus = set(focus_ids or ["akira"])
    if not isinstance(pairs, dict):
        return {"pairs": {}, "_context_filter": {"mode": "no_relationship_state", "focus_character_ids": sorted(focus)}}

    filtered: dict[str, Any] = {}
    for pair_id, rel in pairs.items():
        if not pair_in_focus(str(pair_id), focus):
            continue
        if isinstance(rel, dict):
            filtered[str(pair_id)] = {
                "affection": rel.get("affection", 0),
                "trust": rel.get("trust", 0),
                "tension": rel.get("tension", 0),
                "jealousy": rel.get("jealousy", 0),
                "respect": rel.get("respect", 0),
                "curiosity": rel.get("curiosity", 0),
                "resentment": rel.get("resentment", 0),
                "status": rel.get("status"),
                "notes": (rel.get("notes") or [])[-6:] if isinstance(rel.get("notes"), list) else rel.get("notes"),
                "memory": (rel.get("memory") or [])[-8:] if isinstance(rel.get("memory"), list) else rel.get("memory"),
                "open_threads": (rel.get("open_threads") or [])[-6:] if isinstance(rel.get("open_threads"), list) else rel.get("open_threads"),
                "behavior_next": (rel.get("behavior_next") or [])[-6:] if isinstance(rel.get("behavior_next"), list) else rel.get("behavior_next"),
                "triggers": (rel.get("triggers") or [])[-6:] if isinstance(rel.get("triggers"), list) else rel.get("triggers"),
                "last_interaction": rel.get("last_interaction"),
            }

    return {
        "pairs": filtered,
        "_context_filter": {
            "mode": "active_nearby_or_explicit_pairs_only_v13",
            "focus_character_ids": sorted(focus),
            "visible_pairs": len(filtered),
            "total_pairs": len(pairs),
            "rule": "Do not load absent pairs such as Akira/Raiden when Raiden is not in scene unless explicitly mentioned/triggered.",
        },
    }


def compact_knowledge_context(session_id: str, focus_ids: list[str]) -> dict[str, Any]:
    state = base.read_json("state/knowledge_state.json", session_id, default={}) or {}
    focus = set(focus_ids or ["akira"])
    if not isinstance(state, dict):
        return {"_context_filter": {"mode": "no_knowledge_state", "focus_character_ids": sorted(focus)}}

    filtered: dict[str, Any] = {}
    for cid, data in state.items():
        canon = _cid(cid)
        if canon not in focus and str(cid) not in focus:
            continue
        if isinstance(data, dict):
            compacted = {}
            for key, value in data.items():
                if isinstance(value, list):
                    compacted[key] = value[-10:]
                elif isinstance(value, dict):
                    # avoid huge nested objects
                    compacted[key] = {k: v for i, (k, v) in enumerate(value.items()) if i < 12}
                else:
                    compacted[key] = value
            filtered[canon] = compacted
        else:
            filtered[canon] = data

    return {
        **filtered,
        "_context_filter": {
            "mode": "active_nearby_or_explicit_knowledge_only_v13",
            "focus_character_ids": sorted(focus),
            "visible_characters": len(filtered),
            "total_characters": len(state),
        },
    }


def recent_scene_history(session_id: str, limit: int = RECENT_SCENE_HISTORY_LIMIT) -> dict[str, Any]:
    hist = base.read_json("state/scene_history.json", session_id, default={}) or {}
    entries = hist.get("entries") if isinstance(hist, dict) else hist if isinstance(hist, list) else []
    if not isinstance(entries, list):
        entries = []
    recent = []
    for item in entries[-limit:]:
        if not isinstance(item, dict):
            continue
        text = item.get("visible_scene_text") or item.get("scene_text") or ""
        if isinstance(text, str) and len(text) > 1200:
            text = text[-1200:]
        recent.append({
            "id": item.get("id"),
            "turn_number": item.get("turn_number"),
            "current_date": item.get("current_date"),
            "current_time": item.get("current_time"),
            "location_id": item.get("location_id"),
            "active_characters": item.get("active_characters", []),
            "player_input": item.get("player_input", ""),
            "scene_text_tail": text,
        })
    return {
        "entries": recent,
        "_context_filter": {
            "mode": "recent_scene_history_only_v13",
            "visible_entries": len(recent),
            "total_entries": len(entries),
        },
    }


def _read_rules() -> dict[str, Any]:
    try:
        return json.loads(lean._read_text(RELATIONSHIP_RULES_FILE) or "{}")
    except Exception:
        return {}


_ORIGINAL_THIN_CONTRACT = lean._thin_contract


def _thin_contract_with_live_state(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    contract = _ORIGINAL_THIN_CONTRACT(session_id, user_input=user_input, mode=mode)
    state = _state(session_id)
    focus_ids = focus_ids_from_state(state, user_input=user_input)

    contract["active_character_ids"] = focus_ids
    anchor = contract.setdefault("current_scene_anchor", {})
    if isinstance(anchor, dict):
        anchor["focus_character_ids_for_state"] = focus_ids

    contract["relationship_context"] = compact_relationship_context(session_id, focus_ids)
    contract["knowledge_table"] = compact_knowledge_context(session_id, focus_ids)
    contract["recent_scene_history"] = recent_scene_history(session_id)
    story_context = contract.setdefault("story_context", {})
    if isinstance(story_context, dict):
        story_context["relationship_memory_rules"] = _read_rules()
        story_context["state_memory_context"] = "v13 active/nearby/explicit only"
    contract["required_checks_before_answer"] = list(contract.get("required_checks_before_answer") or []) + [
        "Update relationship_changes for every meaningful interaction between present characters.",
        "Update knowledge_changes only for characters who actually saw/heard/learned something.",
        "Do not load or update absent relationship pairs unless explicitly relevant.",
        "Do not let NPCs know Akira's unspoken thoughts.",
        "Use recent_scene_history to preserve continuity.",
    ]
    return contract


# Patch lean contract builders and routes.
lean._thin_contract = _thin_contract_with_live_state


try:
    lean.ALWAYS_SMALL_FILES.append(RELATIONSHIP_RULES_FILE)
    lean.ALWAYS_SMALL_FILES = list(dict.fromkeys(lean.ALWAYS_SMALL_FILES))
except Exception:
    pass


# Replace existing lean turn-contract routes so they use the enriched contract.
try:
    lean._remove_route("/api/v1/sessions/{session_id}/turn-contract", "GET")
    lean._remove_route("/api/v1/sessions/{session_id}/turn-contract", "POST")
except Exception:
    pass


@app.get("/api/v1/sessions/{session_id}/turn-contract")
def getSessionTurnContract(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    return _thin_contract_with_live_state(session_id, user_input=user_input, mode=mode)


@app.post("/api/v1/sessions/{session_id}/turn-contract")
def postSessionTurnContract(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return _thin_contract_with_live_state(
        session_id,
        user_input=str(payload.get("user_input") or payload.get("player_input") or ""),
        mode=str(payload.get("mode") or "play"),
    )


try:
    app.version = "0.3.101-1206-state-memory-relationship-v13"
except Exception:
    pass
