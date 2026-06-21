from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

import app.calendar_scene_runtime_patch as calendar_runtime
from app.calendar_scene_runtime_patch import app
from app import compact as base
import app.compact_context_patch as ccp

CONTEXT_PATH = "/api/v1/sessions/{session_id}/context"
TURN_CONTRACT_PATH = "/api/v1/sessions/{session_id}/turn-contract"

START_REQUIRED_FILES = [
    "scenes/start_scene.md",
    "scenes/start_scene_logic.md",
    "calendar/days/1206-08-31.yaml",
    "gpt/scene_format.md",
    "gpt/locks/runtime_scene_rules_digest.md",
    "characters/character_id_index.md",
]

CHARACTER_FILE_MAP = {
    "akira": [
        "characters/akira/akira_main_profile.yaml",
        "characters/akira/akira_knowledge_connections.yaml",
        "characters/akira/akira_hidden_past.yaml",
        "characters/akira/akira_thought_triggers.yaml",
    ],
    "jun": [
        "characters/jun/jun_main_profile.yaml",
        "characters/jun/jun_knowledge_connections.yaml",
        "characters/jun/jun_hidden_past.yaml",
    ],
    "irey": [
        "characters/irey/irey_main_profile.yaml",
        "characters/irey/irey_knowledge_connections.yaml",
        "characters/irey/irey_hidden_past.yaml",
    ],
    "emma": [
        "characters/emma/emma_main_profile.yaml",
        "characters/emma/emma_knowledge_connections.yaml",
        "characters/emma/emma_hidden_past.yaml",
    ],
    "raiden": [
        "characters/raiden/raiden_main_profile.yaml",
        "characters/raiden/raiden_knowledge_connections.yaml",
        "characters/raiden/raiden_hidden_past.yaml",
    ],
    "ray": [
        "characters/ray/ray_main_profile.yaml",
        "characters/ray/ray_knowledge_connections.yaml",
        "characters/ray/ray_hidden_past.yaml",
    ],
}


def _remove_routes(path: str, methods: set[str] | None = None, operation_id: str | None = None) -> None:
    keep = []
    for route in app.router.routes:
        route_path = getattr(route, "path", None)
        route_methods = set(getattr(route, "methods", set()) or set())
        route_operation_id = getattr(route, "operation_id", None)
        match_path = route_path == path
        match_methods = methods is None or bool(route_methods & methods)
        match_operation = operation_id is None or route_operation_id == operation_id
        if match_path and match_methods and match_operation:
            continue
        keep.append(route)
    app.router.routes = keep


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _ensure_session(session_id: str) -> str:
    sid = base.safe_session_id(session_id)
    try:
        base.ensure_session(sid)
    except Exception:
        base.seed()
        root = base.session_dir(sid)
        root.mkdir(parents=True, exist_ok=True)
        try:
            base.copy_missing(base.DATA / "state", root / "state")
        except Exception:
            pass
        if not (root / "session.json").exists():
            import json
            from datetime import datetime
            meta = {"session_id": sid, "title": "Akira 1206 v2 Session", "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()}
            (root / "session.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sid


def _safe_read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default) or default
    except Exception:
        return default


def _compact(value: Any, limit: int = 900) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text if len(text) <= limit else text[:limit].rstrip() + "...<truncated>"
    if isinstance(value, list):
        return [_compact(item, limit) for item in value[:20]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 30:
                out["..."] = "truncated"
                break
            out[str(key)] = _compact(item, limit)
        return out
    return str(value)[:limit]


def _scene_chars(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    values: list[Any] = ["akira"]
    for field in [
        "active_characters", "nearby_characters", "speaking_character_ids", "observing_character_ids",
        "addressed_character_ids", "looked_at_character_ids", "mentioned_character_ids", "scheduled_character_ids",
        "delayed_character_ids", "active_character_ids", "nearby_character_ids",
    ]:
        field_values = current.get(field, []) or []
        if isinstance(field_values, list):
            values.extend(field_values)
    for lock in (future.get("locks") or {}).values():
        if isinstance(lock, dict) and lock.get("status") in {"due", "active", "triggered"}:
            values.extend(lock.get("participants", []) or [])
    return _unique([str(v).strip() for v in values if str(v).strip()])


def _required_files(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files = list(START_REQUIRED_FILES)
    for cid in _scene_chars(current, future):
        files.extend(CHARACTER_FILE_MAP.get(cid, []))
    for path in [
        "state/current_state.json", "state/story_lines.json", "state/knowledge_state.json", "state/relationships.json",
        "state/inventory_state.json", "state/power_state.json", "state/future_locks_progress.json",
    ]:
        files.append(path)
    return _unique([path for path in files if path.startswith("state/") or base.repo_file_exists(path)])


def _current_state_slice(current: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "current_date", "date", "current_time", "time", "time_of_day", "current_location_id", "location_id",
        "current_location_text", "current_scene_goal", "akira_state", "current_outfit", "visible_inventory",
        "nearby_items", "active_characters", "nearby_characters", "speaking_character_ids", "observing_character_ids",
        "addressed_character_ids", "looked_at_character_ids", "mentioned_character_ids", "scheduled_character_ids",
        "delayed_character_ids", "voice_identity_map_hidden", "start_scene_file", "start_scene_logic_file",
    ]
    return {key: _compact(current.get(key), 1000) for key in keys if key in current}


class SizeGuardContextResponse(BaseModel):
    session_id: str
    mode: str = "1206_size_guard_context"
    current_state: dict[str, Any] = Field(default_factory=dict)
    active_character_ids: list[str] = Field(default_factory=list)
    nearby_character_ids: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    usage_note: str = "Compact context only. Load manifest/chunks before rendering gameplay."


class TurnContractWithPromptPreview(BaseModel):
    session_id: str
    mode: str = "1206_size_guard_turn_contract"
    active_character_ids: list[str] = Field(default_factory=list)
    nearby_character_ids: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    output_format_contract: dict[str, Any] = Field(default_factory=dict)
    required_checks_before_answer: list[str] = Field(default_factory=list)
    knowledge_table: dict[str, Any] = Field(default_factory=dict)
    inventory_contract: dict[str, Any] = Field(default_factory=dict)
    relationship_context: dict[str, Any] = Field(default_factory=dict)
    story_context: dict[str, Any] = Field(default_factory=dict)
    prompt_preview: str = ""
    prompt_preview_usage: str = "Load required files chunks, then render scene only."
    usage_note: str = "Do not stop at this contract. Call getRequiredFilesManifest and all getRequiredFilesChunk chunks."


def _small_output_contract() -> dict[str, Any]:
    return {
        "format": "1206_visual_novel_header",
        "scene_header_required": True,
        "bottom_blocks": ["✦ Что можно сделать", "✦ Что Акира могла бы сказать", "✦ Мысли Акиры"],
        "rules": [
            "Final gameplay answer must be the scene only, not API/status/debug summary.",
            "For the first start_scene, output initial exact text verbatim if processTurn returns scene_text.",
            "Use 1206 scene header and hidden voice labels exactly as provided.",
            "Do not reveal Emma/Irey names in Akira POV before in-scene reveal.",
            "Player controls only Akira; do not invent Akira speech unless written outside parentheses.",
        ],
    }


def _small_prompt_preview(chars: list[str], required_files: list[str]) -> str:
    return (
        "PLAY MODE 1206 SIZE-GUARD BRIEF\n"
        "- Load getRequiredFilesManifest, then all getRequiredFilesChunk chunks before rendering.\n"
        "- If this is the first start scene, use processTurn('начнем') or initial_scene.exact_text verbatim.\n"
        f"- Focus characters: {', '.join(chars)}.\n"
        f"- Required files count: {len(required_files)}.\n"
        "- Final answer must be visible scene only, no API/status/debug.\n"
    )


_remove_routes(CONTEXT_PATH, {"GET"}, "getSessionContext")
_remove_routes(TURN_CONTRACT_PATH, {"GET"}, "getSessionTurnContract")


@app.get(CONTEXT_PATH, response_model=SizeGuardContextResponse, operation_id="getSessionContext")
def get_session_context_size_guard(session_id: str) -> SizeGuardContextResponse:
    sid = _ensure_session(session_id)
    current = _safe_read_json("state/current_state.json", sid, {})
    future = _safe_read_json("state/future_locks_progress.json", sid, {})
    files = _required_files(current, future)
    chars = _scene_chars(current, future)
    return SizeGuardContextResponse(
        session_id=sid,
        current_state=_current_state_slice(current),
        active_character_ids=_unique(current.get("active_characters", []) or current.get("active_character_ids", []) or []),
        nearby_character_ids=_unique(current.get("nearby_characters", []) or current.get("nearby_character_ids", []) or []),
        required_files=files,
    )


@app.get(TURN_CONTRACT_PATH, response_model=TurnContractWithPromptPreview, operation_id="getSessionTurnContract")
def get_session_turn_contract_size_guard(session_id: str) -> TurnContractWithPromptPreview:
    sid = _ensure_session(session_id)
    current = _safe_read_json("state/current_state.json", sid, {})
    future = _safe_read_json("state/future_locks_progress.json", sid, {})
    knowledge = _safe_read_json("state/knowledge_state.json", sid, {})
    inventory = _safe_read_json("state/inventory_state.json", sid, {})
    relationships = _safe_read_json("state/relationships.json", sid, {})
    story_lines = _safe_read_json("state/story_lines.json", sid, {})
    chars = _scene_chars(current, future)
    files = _required_files(current, future)
    return TurnContractWithPromptPreview(
        session_id=sid,
        active_character_ids=_unique(current.get("active_characters", []) or current.get("active_character_ids", []) or []),
        nearby_character_ids=_unique(current.get("nearby_characters", []) or current.get("nearby_character_ids", []) or []),
        required_files=files,
        output_format_contract=_small_output_contract(),
        required_checks_before_answer=[
            "Call getRequiredFilesManifest next.",
            "Then call getRequiredFilesChunk starting at chunk_index=0 until has_more=false.",
            "Do not render gameplay from this compact contract alone.",
            "For first start: processTurn with player_input='начнем' may return exact scene_text.",
            "Final gameplay answer must be scene only, no status summary.",
        ],
        knowledge_table={cid: _compact(knowledge.get(cid), 1200) for cid in chars if isinstance(knowledge, dict) and cid in knowledge},
        inventory_contract={
            "visible_inventory": _compact(current.get("visible_inventory", []), 900),
            "nearby_items": _compact(current.get("nearby_items", []), 900),
            "akira_inventory_state": _compact((inventory.get("akira") or {}) if isinstance(inventory, dict) else {}, 900),
        },
        relationship_context=_compact(relationships, 1200),
        story_context=_compact(story_lines, 1600),
        prompt_preview=_small_prompt_preview(chars, files),
    )


app.version = "0.3.70-1206-size-guard-v1"
