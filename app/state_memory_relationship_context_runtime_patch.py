"""1206 targeted contract-slim state patch.

Fixes ResponseTooLarge after state memory v13 by NOT embedding
relationship/knowledge/history objects directly in turn-contract.

Live state remains available through required-files-manifest / required-files-chunk.
"""
from __future__ import annotations

from typing import Any
from fastapi import Body

import app.lean_context_loading_runtime_patch as lean
from app.start_scene_runtime_patch import app
from app import compact as base

try:
    import app.state_persistence_runtime_patch as persistence  # noqa: F401
except Exception:
    pass

RELATIONSHIP_RULES_FILE = "state/relationship_memory_rules_1206.json"
LIVE_STATE_FILES = [
    RELATIONSHIP_RULES_FILE,
    "state/relationships.json",
    "state/knowledge_state.json",
    "state/scene_history.json",
    "state/last_apply_result.json",
]


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


def _file_exists_for_session(path: str, session_id: str) -> bool:
    try:
        return bool(lean._read_text(path, session_id=session_id))
    except TypeError:
        return bool(lean._read_text(path))
    except Exception:
        return False


def _live_state_files(session_id: str) -> list[str]:
    return [p for p in LIVE_STATE_FILES if _file_exists_for_session(p, session_id)]


_ORIGINAL_REQUIRED_FILES = lean._required_files


def _required_files_with_live_state(session_id: str, user_input: str = "") -> list[str]:
    files = list(_ORIGINAL_REQUIRED_FILES(session_id, user_input=user_input))
    files.extend(_live_state_files(session_id))
    return list(dict.fromkeys(files))


lean._required_files = _required_files_with_live_state

_ORIGINAL_THIN_CONTRACT = lean._thin_contract


def _thin_contract_slim_state(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    contract = _ORIGINAL_THIN_CONTRACT(session_id, user_input=user_input, mode=mode)
    state = _state(session_id)
    focus_ids = focus_ids_from_state(state, user_input=user_input)

    contract["active_character_ids"] = focus_ids
    anchor = contract.setdefault("current_scene_anchor", {})
    if isinstance(anchor, dict):
        anchor["focus_character_ids_for_state"] = focus_ids

    files = list(contract.get("required_files") or [])
    files.extend(_live_state_files(session_id))
    contract["required_files"] = list(dict.fromkeys(files))

    # Tiny summaries only. Never embed full state here.
    contract["relationship_context"] = {
        "_context_filter": {
            "mode": "contract_slim_state_targeted",
            "focus_character_ids": focus_ids,
            "state_files_listed_in_required_files": True,
            "load_via": "required-files-chunk",
            "note": "Full relationship state is not embedded in turn-contract to avoid ResponseTooLarge.",
        }
    }
    contract["knowledge_table"] = {
        "_context_filter": {
            "mode": "contract_slim_state_targeted",
            "focus_character_ids": focus_ids,
            "state_files_listed_in_required_files": True,
            "load_via": "required-files-chunk",
        }
    }
    contract["recent_scene_history"] = {
        "_context_filter": {
            "mode": "contract_slim_state_targeted",
            "state_files_listed_in_required_files": True,
            "load_via": "required-files-chunk",
        }
    }

    story_context = contract.setdefault("story_context", {})
    if isinstance(story_context, dict):
        story_context["state_memory_context"] = "slim: load relationship/knowledge/history via chunks, not contract"
        story_context["relationship_memory_rules_file"] = RELATIONSHIP_RULES_FILE

    checks = list(contract.get("required_checks_before_answer") or [])
    for item in [
        "Do not embed full relationship/knowledge/history in turn-contract.",
        "Use required-files-chunk to read live state files.",
        "Update relationship_changes and knowledge_changes after meaningful interactions.",
        "Do not update absent pairs unless explicitly relevant.",
    ]:
        if item not in checks:
            checks.append(item)
    contract["required_checks_before_answer"] = checks

    contract["prompt_preview"] = "Slim state contract. Load live state via required-files-chunk. Do not continue from memory if chunks unavailable."
    contract["usage_note"] = "ResponseTooLarge guard: relationship/knowledge/history are listed as files, not embedded."
    return contract


lean._thin_contract = _thin_contract_slim_state

try:
    if RELATIONSHIP_RULES_FILE not in lean.ALWAYS_SMALL_FILES:
        lean.ALWAYS_SMALL_FILES.append(RELATIONSHIP_RULES_FILE)
    lean.ALWAYS_SMALL_FILES = list(dict.fromkeys(lean.ALWAYS_SMALL_FILES))
except Exception:
    pass

try:
    lean._remove_route("/api/v1/sessions/{session_id}/turn-contract", "GET")
    lean._remove_route("/api/v1/sessions/{session_id}/turn-contract", "POST")
except Exception:
    pass


@app.get("/api/v1/sessions/{session_id}/turn-contract")
def getSessionTurnContract(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    return _thin_contract_slim_state(session_id, user_input=user_input, mode=mode)


@app.post("/api/v1/sessions/{session_id}/turn-contract")
def postSessionTurnContract(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return _thin_contract_slim_state(
        session_id,
        user_input=str(payload.get("user_input") or payload.get("player_input") or ""),
        mode=str(payload.get("mode") or "play"),
    )


try:
    app.version = "0.3.103-1206-current-targeted-contract-time-fix"
except Exception:
    pass
