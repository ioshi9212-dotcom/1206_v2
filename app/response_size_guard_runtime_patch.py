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
    "gpt/locks/calendar_usage_lock.md",
    "gpt/locks/npc_living_scene_rules.md",
    "gpt/locks/lore_usage_lock.md",
    "characters/character_id_index.md",
]

PROGRESS_FILES = [
    "state/akira_progress_state.json",
    "state/relationship_score_panel.json",
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
        "canon/relationships/akira_raiden_hidden_bond.yaml",
    ],
    "ray": [
        "characters/ray/ray_main_profile.yaml",
        "characters/ray/ray_knowledge_connections.yaml",
        "characters/ray/ray_hidden_past.yaml",
    ],
    "yuna": [
        "characters/yuna/yuna_main_profile.yaml",
        "characters/yuna/yuna_knowledge_connections.yaml",
        "characters/yuna/yuna_hidden_past.yaml",
    ],
}

VISIBLE_LABELS_DEFAULT = {
    "akira__jun": "Джун",
    "akira__irey": "незнакомый мужской голос / беловолосый мужчина",
    "akira__emma": "женский голос снизу / беловолосая девушка",
    "akira__ray": "имя из записки",
    "akira__raiden": "незнакомый мужчина / рейдер",
    "akira__yuna": "медик",
}

DISPLAY_NAMES_DEFAULT = {
    "jun": "Джун",
    "irey": "Ирэй",
    "emma": "Эмма",
    "ray": "Рэй",
    "raiden": "Райден",
    "yuna": "Юна",
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
        return [_compact(item, limit) for item in value[:30]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 40:
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
    for thread in current.get("open_threads", []) or []:
        if isinstance(thread, dict) and str(thread.get("status", "")).lower() in {"due", "active", "triggered", "ready"}:
            values.extend(thread.get("participants", []) or [])
            values.extend(thread.get("character_ids", []) or [])
    for lock in (future.get("locks") or {}).values():
        if isinstance(lock, dict) and str(lock.get("status", "")).lower() in {"due", "active", "triggered", "ready"}:
            values.extend(lock.get("participants", []) or [])
            values.extend(lock.get("character_ids", []) or [])
    return _unique([str(v).strip() for v in values if str(v).strip()])


def _required_files(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files = list(START_REQUIRED_FILES)
    for cid in _scene_chars(current, future):
        files.extend(CHARACTER_FILE_MAP.get(cid, []))
    files.extend([
        "state/current_state.json", "state/story_lines.json", "state/knowledge_state.json", "state/relationships.json",
        "state/inventory_state.json", "state/power_state.json", "state/future_locks_progress.json",
        "state/session_npcs.json", "state/calendar_runtime.json",
    ])
    files.extend(PROGRESS_FILES)
    result: list[str] = []
    for path in files:
        if not path or path in result:
            continue
        if path.startswith("state/"):
            result.append(path)
            continue
        try:
            if base.repo_file_exists(path):
                result.append(path)
        except Exception:
            pass
    return result


def _current_state_slice(current: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "current_date", "date", "current_time", "time", "time_of_day", "current_location_id", "location_id",
        "current_location_text", "current_scene_goal", "akira_state", "current_outfit", "visible_inventory",
        "nearby_items", "active_characters", "nearby_characters", "speaking_character_ids", "observing_character_ids",
        "addressed_character_ids", "looked_at_character_ids", "mentioned_character_ids", "scheduled_character_ids",
        "delayed_character_ids", "open_threads", "voice_identity_map_hidden", "start_scene_file", "start_scene_logic_file",
    ]
    return {key: _compact(current.get(key), 1000) for key in keys if key in current}


def _clamp_score(value: float) -> int:
    return max(-100, min(100, int(round(value))))


def _relationship_score(data: Any) -> int:
    if not isinstance(data, dict):
        return 0
    positive = {
        "affection": 1.2,
        "trust": 1.2,
        "respect": 1.0,
        "interest": 0.8,
        "curiosity": 0.8,
        "warmth": 1.2,
        "attachment": 1.5,
        "protective_pull": 0.8,
        "recognition_pull": 0.8,
    }
    negative = {
        "tension": -0.8,
        "irritation": -0.7,
        "fear": -1.0,
        "resentment": -1.2,
        "suspicion": -1.0,
        "jealousy": -0.4,
        "threat": -1.0,
        "control_pressure": -0.8,
    }
    total = 0.0
    for key, weight in positive.items():
        total += float(data.get(key) or 0) * weight
    for key, weight in negative.items():
        total += float(data.get(key) or 0) * weight
    return _clamp_score(total)


def _label_for_score(score: int, *, default_zero: str = "неясно") -> str:
    if score <= -60:
        return "враждебность"
    if score <= -35:
        return "сильное напряжение"
    if score <= -15:
        return "настороженность"
    if score <= 14:
        return default_zero
    if score <= 34:
        return "интерес"
    if score <= 54:
        return "доверие"
    if score <= 74:
        return "близость"
    return "сильная привязанность"


def _normalize_pair_id(pair_id: str) -> str:
    pair_id = str(pair_id or "").strip()
    aliases = {
        "akira__raiden_sterling": "akira__raiden",
        "akira__ray_carter": "akira__ray",
        "akira__jun_carter": "akira__jun",
    }
    return aliases.get(pair_id, pair_id)


def _display_for_pair(pair_id: str, stored: dict[str, Any] | None = None) -> tuple[str, str]:
    stored = stored or {}
    visible = stored.get("visible_label")
    display = stored.get("display_name")
    if visible and display:
        return str(display), str(visible)
    pair = _normalize_pair_id(pair_id)
    other = pair.replace("akira__", "") if pair.startswith("akira__") else pair
    display_name = display or DISPLAY_NAMES_DEFAULT.get(other, other)
    visible_label = visible or VISIBLE_LABELS_DEFAULT.get(pair, display_name)
    return str(display_name), str(visible_label)


def _computed_relationship_panel(relationships: Any, stored_panel: Any) -> dict[str, Any]:
    pairs = relationships.get("pairs") if isinstance(relationships, dict) else {}
    if not isinstance(pairs, dict):
        pairs = {}
    stored_items = {}
    if isinstance(stored_panel, dict):
        stored_items = stored_panel.get("relationship_score_panel") or {}
        if not isinstance(stored_items, dict):
            stored_items = {}
    wanted = ["akira__jun", "akira__irey", "akira__emma", "akira__ray", "akira__raiden", "akira__yuna"]
    result: dict[str, Any] = {}
    for pair_id in wanted:
        source_pair_id = pair_id
        data = pairs.get(pair_id)
        if data is None:
            for alt in [pair_id.replace("raiden", "raiden_sterling"), pair_id.replace("ray", "ray_carter"), pair_id.replace("jun", "jun_carter")]:
                if alt in pairs:
                    data = pairs.get(alt)
                    source_pair_id = alt
                    break
        stored = stored_items.get(pair_id) or stored_items.get(source_pair_id) or {}
        display_name, visible_label = _display_for_pair(pair_id, stored if isinstance(stored, dict) else {})
        if isinstance(data, dict):
            score = _relationship_score(data)
            label = _label_for_score(score, default_zero=str(stored.get("label") or "неясно") if isinstance(stored, dict) else "неясно")
            result[pair_id] = {
                "display_name": display_name,
                "visible_label": visible_label,
                "score": score,
                "label": label,
                "source": "computed_from_relationships_json",
            }
        elif isinstance(stored, dict) and stored:
            result[pair_id] = {
                "display_name": display_name,
                "visible_label": visible_label,
                "score": int(stored.get("score") or 0),
                "label": str(stored.get("label") or "неясно"),
                "source": str(stored.get("source") or "stored_relationship_score_panel"),
            }
        else:
            result[pair_id] = {
                "display_name": display_name,
                "visible_label": visible_label,
                "score": 0,
                "label": "неясно" if pair_id != "akira__emma" else "угроза неясна",
                "source": "default_no_relationship_pair",
            }
    return result


def _relationship_slice(relationships: Any, chars: list[str]) -> dict[str, Any]:
    if not isinstance(relationships, dict):
        return {}
    pairs = relationships.get("pairs")
    if not isinstance(pairs, dict):
        return {}
    focus = set(chars)
    out: dict[str, Any] = {}
    for pair_id, data in pairs.items():
        parts = {part for part in str(pair_id).split("__") if part}
        if parts and ("akira" in parts or parts <= focus):
            out[pair_id] = _compact(data, 900)
        if len(out) >= 25:
            break
    return {"pairs": out, "_context_filter": "akira_or_focus_pairs_size_guard"}


def _progress_slice(session_id: str, relationships: Any | None = None) -> dict[str, Any]:
    progress = _safe_read_json("state/akira_progress_state.json", session_id, {})
    relationship_panel = _safe_read_json("state/relationship_score_panel.json", session_id, {})
    computed_panel = _computed_relationship_panel(relationships or {}, relationship_panel)
    return {
        "akira_progress_state": _compact(progress, 1400),
        "relationship_score_panel": _compact(relationship_panel, 1400),
        "computed_relationship_score_panel": _compact(computed_panel, 1800),
        "visible_panel_rule": "Show current total state/relationship scores, not only per-scene deltas. Use visible_label when character name is not known in POV.",
    }


def _small_output_contract() -> dict[str, Any]:
    return {
        "format": "1206_visual_novel_header_v2",
        "scene_header_required": True,
        "bottom_blocks": [
            "✦ Что можно сделать",
            "✦ Что Акира могла бы сказать",
            "✦ Мысли Акиры",
            "✦ Состояние",
            "✦ Отношения",
        ],
        "rules": [
            "Final gameplay answer must be the scene only, not API/status/debug summary.",
            "Use 1206 scene header and current state/calendar location/time.",
            "Scene-specific bans and permissions must come from the current day/scenes file, not from global rules.",
            "Calendar day goals are character intentions, not guaranteed outcomes.",
            "Player controls only Akira; do not invent Akira speech unless written outside parentheses.",
            "The last explicit player action is the scene boundary; do not move Akira beyond it without a new player turn.",
            "If an NPC asks/challenges/blocks/addresses Akira, stop at the player choice point.",
            "Do not decide that Akira ignored, answered, attacked, followed, trusted or left unless the player wrote it.",
            "Characters know only what they saw, heard, were told, have in knowledge_state, or can infer from visible signs.",
            "Delayed/absent/off-screen characters cannot know scenes they missed unless told or saved in knowledge_state.",
            "Do not rename invented/unnamed NPCs into fixed canon characters after description.",
            "Use visible_label / pov_name_before_introduction for characters whose names Akira does not know.",
            "Bottom-block options are not facts until player chooses them.",
            "End panel must show current total state/progress/relationship scores, not only per-scene deltas.",
            "Relationship details stay internal; visible panel shows visible label, score and short label.",
        ],
    }


def _small_prompt_preview(chars: list[str], required_files: list[str]) -> str:
    return (
        "PLAY MODE 1206 SIZE-GUARD BRIEF\n"
        "- Load getRequiredFilesManifest, then all getRequiredFilesChunk chunks before rendering.\n"
        "- Render a generated scene from current state/calendar/files; exact first text is optional only if processTurn returns scene_text.\n"
        f"- Focus characters/internal ids: {', '.join(chars)}. Use visible labels when POV does not know names.\n"
        f"- Required files count: {len(required_files)}.\n"
        "- Enforce player action boundary and unanswered hook rule.\n"
        "- Final answer must be visible scene only, no API/status/debug.\n"
        "- Bottom panel must include actions, possible Akira lines, Akira thoughts, state, relationships.\n"
    )


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


_remove_routes(CONTEXT_PATH, {"GET"}, "getSessionContext")
_remove_routes(TURN_CONTRACT_PATH, {"GET"}, "getSessionTurnContract")


@app.get(CONTEXT_PATH, response_model=SizeGuardContextResponse, operation_id="getSessionContext")
def get_session_context_size_guard(session_id: str) -> SizeGuardContextResponse:
    sid = _ensure_session(session_id)
    current = _safe_read_json("state/current_state.json", sid, {})
    future = _safe_read_json("state/future_locks_progress.json", sid, {})
    files = _required_files(current, future)
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
    story_context = _compact(story_lines, 1600)
    if not isinstance(story_context, dict):
        story_context = {"story_lines": story_context}
    story_context["progress_panel"] = _progress_slice(sid, relationships)
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
            "Load current calendar day file and scene/global technical rules before scene output.",
            "Use latest visible scene facts before stale current_state.",
            "Do not grant absent/delayed/off-screen characters knowledge of scenes they missed.",
            "Do not rename invented/session NPCs into fixed canon characters.",
            "Use visible_label/pov descriptor until the POV has a source for the real name.",
            "Stop at a player choice point when Akira is directly challenged, questioned, blocked or addressed.",
            "End panel must show current total progress/relationship scores, not only per-scene deltas.",
            "Final gameplay answer must be scene only, no status summary.",
        ],
        knowledge_table={cid: _compact(knowledge.get(cid), 1200) for cid in chars if isinstance(knowledge, dict) and cid in knowledge},
        inventory_contract={
            "visible_inventory": _compact(current.get("visible_inventory", []), 900),
            "nearby_items": _compact(current.get("nearby_items", []), 900),
            "akira_inventory_state": _compact((inventory.get("akira") or {}) if isinstance(inventory, dict) else {}, 900),
        },
        relationship_context=_relationship_slice(relationships, chars),
        story_context=story_context,
        prompt_preview=_small_prompt_preview(chars, files),
    )


app.version = "0.3.72-1206-scene-rules-panel-v1"
