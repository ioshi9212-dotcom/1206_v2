from __future__ import annotations

from math import ceil
from typing import Any
from pydantic import BaseModel, Field

import app.calendar_scene_runtime_patch as calendar_runtime  # noqa: F401
from app.calendar_scene_runtime_patch import app
from app import compact as base

try:
    import app.context_transport_runtime_patch as context_transport
except Exception:  # pragma: no cover
    context_transport = None  # type: ignore[assignment]

CONTEXT_PATH = "/api/v1/sessions/{session_id}/context"
TURN_CONTRACT_PATH = "/api/v1/sessions/{session_id}/turn-contract"
MANIFEST_PATH = "/api/v1/sessions/{session_id}/required-files-manifest"
CHUNK_PATH = "/api/v1/sessions/{session_id}/required-files-chunk"
BUNDLE_PATH = "/api/v1/sessions/{session_id}/required-files-bundle"

BASE_RULE_FILES = [
    "runtime/scene_context_digest.md",
    "gpt/locks/runtime_scene_rules_digest.md",
    "gpt/scene_format.md",
]

LIGHT_STATE_FILES = [
    "state/current_state.json",
    "state/calendar_runtime.json",
    "state/relationships.json",
    "state/inventory_state.json",
    "state/scene_continuity_state.json",
    "state/power_state.json",
    "state/future_locks_progress.json",
    "state/session_npcs.json",
]

ACTIVE_CHARACTER_FIELDS = [
    "active_characters",
    "active_character_ids",
    "nearby_characters",
    "nearby_character_ids",
    "speaking_character_ids",
    "observing_character_ids",
    "addressed_character_ids",
    "looked_at_character_ids",
    "scheduled_character_ids",
]

PAST_TRIGGER_WORDS = [
    "прошл", "памят", "вспом", "забы", "кольц", "шрам", "ребен", "ребён",
    "берем", "саму", "лаборатор", "эксперимент", "кайрос", "поток",
    "сон", "кошмар", "пространство между", "самоблок", "срыв", "эхо",
]

CHARACTER_FOLDERS = {
    "akira": "akira", "char_akira": "akira",
    "jun": "jun", "jun_carter": "jun", "char_jun": "jun",
    "ray": "ray", "ray_carter": "ray", "char_ray": "ray", "командующий": "ray", "командующий_рэй": "ray", "командующий_восточного_сектора": "ray", "старший_командир_базы": "ray",
    "raiden": "raiden", "raiden_sterling": "raiden", "char_raiden": "raiden", "парень с пирсингом": "raiden", "парень_с_пирсингом": "raiden", "высокий_парень_у_мотоцикла": "raiden",
    "irey": "irey", "char_irey": "irey",
    "emma": "emma", "char_emma": "emma",
    "yuna": "yuna", "yuna_gray": "yuna", "char_yuna": "yuna", "юна": "yuna", "медик": "yuna", "женщина_медик": "yuna", "девушка_в_халате": "yuna", "медик_восточной_базы": "yuna",
    "miki": "miki", "miki_larsen": "miki", "char_miki": "miki", "мики": "miki", "светловолосая_девушка_из_7_го_отряда": "miki",
    "haru": "haru", "haru_foster": "haru",
    "samuel": "samuel", "samuel_sterling": "samuel",
    "alex": "alex",
}

TOPIC_EXTRA_FILES = {
    "akira_spatial_water": {
        "needles": [
            "вода", "водн", "водя", "море", "океан", "шторм", "буря", "цунами",
            "волна", "поток", "течение", "прилив", "отлив", "глубина", "дно",
            "бездн", "граница", "искаж", "давлен", "вязк",
        ],
        "files": ["characters/akira/spatial_water_metaphor_rules.yaml"],
    },
}


def _remove_routes(path: str, methods: set[str] | None = None, operation_id: str | None = None) -> None:
    keep = []
    for route in app.router.routes:
        route_path = getattr(route, "path", None)
        route_methods = set(getattr(route, "methods", set()) or set())
        route_operation_id = getattr(route, "operation_id", None)
        if route_path == path and (methods is None or bool(route_methods & methods)) and (operation_id is None or route_operation_id == operation_id):
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


def _canonical_id(value: Any) -> str:
    item = str(value or "").strip()
    return CHARACTER_FOLDERS.get(item, item)


def _exists(path: str) -> bool:
    if path == "runtime/scene_context_digest.md":
        return True
    if path.startswith("state/"):
        return True
    try:
        return bool(base.repo_file_exists(path))
    except Exception:
        return False


def _safe_read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default) or default
    except Exception:
        return default


def _safe_read_text(path: str, session_id: str | None = None) -> str:
    try:
        return base.read_text(path, session_id=session_id) if session_id else base.read_text(path)
    except Exception:
        return ""


def _compact(value: Any, limit: int = 1000) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        return text if len(text) <= limit else text[:limit].rstrip() + "...<truncated>"
    if isinstance(value, list):
        return [_compact(item, limit) for item in value[:24]]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 32:
                out["..."] = "truncated"
                break
            out[str(key)] = _compact(item, limit)
        return out
    return str(value)[:limit]


def _field_ids(current: dict[str, Any], fields: list[str]) -> list[str]:
    values: list[Any] = ["akira"]
    for field in fields:
        field_values = current.get(field, []) or []
        if isinstance(field_values, list):
            values.extend(field_values)
    return _unique([_canonical_id(v) for v in values])


def _scene_chars(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    values = _field_ids(current, ACTIVE_CHARACTER_FIELDS)

    for thread in current.get("open_threads", []) or []:
        if isinstance(thread, dict) and str(thread.get("status", "")).lower() in {"due", "active", "triggered", "ready"}:
            values.extend(thread.get("participants", []) or [])
            values.extend(thread.get("character_ids", []) or [])

    for lock in (future.get("locks") or {}).values():
        if isinstance(lock, dict) and str(lock.get("status", "")).lower() in {"due", "active", "triggered", "ready"}:
            values.extend(lock.get("participants", []) or [])
            values.extend(lock.get("character_ids", []) or [])

    return _unique([_canonical_id(v) for v in values])


def _last_player_text(current: dict[str, Any]) -> str:
    return str(current.get("last_player_input") or "").lower().replace("ё", "е")


def _turn_text(current: dict[str, Any]) -> str:
    parts = [current.get("last_player_input"), current.get("current_scene_goal"), current.get("current_location_text")]
    return "\n".join(str(p or "") for p in parts).lower().replace("ё", "е")


def _has_any(text: str, needles: list[str]) -> bool:
    return any(n.lower().replace("ё", "е") in text for n in needles)


def _should_load_past(current: dict[str, Any]) -> bool:
    requested = current.get("load_sensitive_character_context")
    if requested is True:
        return True
    if isinstance(requested, list) and requested:
        return True
    text = _last_player_text(current)
    return _has_any(text, PAST_TRIGGER_WORDS)


def _character_files(cid: str, current: dict[str, Any]) -> list[str]:
    folder = CHARACTER_FOLDERS.get(str(cid).strip())
    if not folder:
        return []

    files = [
        f"characters/{folder}/main.yaml",
        f"characters/{folder}/character.yaml",
        f"characters/{folder}/knowledge.yaml",
    ]

    if _should_load_past(current):
        files.append(f"characters/{folder}/past.yaml")

    return [path for path in files if _exists(path)]


def _topic_extra_files(current: dict[str, Any]) -> list[str]:
    text = _turn_text(current)
    files: list[str] = []
    for cfg in TOPIC_EXTRA_FILES.values():
        if _has_any(text, list(cfg.get("needles", []))):
            files.extend(cfg.get("files", []))
    return [path for path in _unique(files) if _exists(path)]


def _calendar_files(current: dict[str, Any]) -> list[str]:
    files: list[str] = []
    current_date = str(current.get("current_date") or current.get("date") or "").strip()

    if _exists("state/calendar_runtime.json"):
        files.append("state/calendar_runtime.json")

    if current_date:
        day_file = f"calendar/days/{current_date}.yaml"
        if _exists(day_file):
            files.append(day_file)

    return _unique(files)


def _required_files(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files: list[str] = []
    files.extend(path for path in BASE_RULE_FILES if _exists(path))
    files.extend(path for path in LIGHT_STATE_FILES if _exists(path))
    files.extend(_calendar_files(current))

    for cid in _scene_chars(current, future):
        files.extend(_character_files(cid, current))

    files.extend(_topic_extra_files(current))
    return _unique(files)


def _recommended_files_for_context_size_guard(current: dict[str, Any] | None = None, future: dict[str, Any] | None = None) -> list[str]:
    return _required_files(current or {}, future or {})


def _character_knowledge_state(session_id: str, chars: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for cid in chars:
        folder = CHARACTER_FOLDERS.get(cid, cid)
        state_path = f"state/character_knowledge/{folder}.json"
        state = _safe_read_json(state_path, session_id, {})
        if state:
            result[folder] = _compact(state, 1400)
    return result


def _runtime_digest(session_id: str) -> str:
    current = _safe_read_json("state/current_state.json", session_id, {})
    story = _safe_read_json("state/story_lines.json", session_id, {})
    relationships = _safe_read_json("state/relationships.json", session_id, {})
    calendar = _safe_read_json("state/calendar_runtime.json", session_id, {})
    chars = _scene_chars(current, _safe_read_json("state/future_locks_progress.json", session_id, {}))
    payload = {
        "current_scene": _current_state_slice(current),
        "focus_characters": chars,
        "story_lines_compact": _compact(story, 1400),
        "character_knowledge_state": _character_knowledge_state(session_id, chars),
        "relationships": _compact(_relationship_slice(relationships, chars), 1400),
        "calendar_runtime": _compact(calendar, 900),
        "rule": "Static character knowledge is loaded from characters/<id>/knowledge.yaml. Dynamic memory is per-character state and only loaded for focus characters.",
    }
    import json
    return "# Runtime scene context digest — generated\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n"


def _read_required_file(path: str, session_id: str) -> tuple[str | None, str | None]:
    if path == "runtime/scene_context_digest.md":
        return _runtime_digest(session_id), "runtime"
    try:
        return base.read_text(path, session_id=session_id), "session"
    except Exception:
        pass
    try:
        return base.read_text(path), "project"
    except Exception:
        return None, None


def _split_text(text: str, limit: int) -> list[str]:
    limit = max(7000, min(int(limit or 11000), 16000))
    if not text:
        return [""]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


def _current_state_slice(current: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "current_date", "date", "current_day_phase", "time_of_day", "current_location_id",
        "current_location_text", "current_scene_goal", "akira_state", "current_outfit",
        "visible_inventory", "nearby_items", "active_characters", "nearby_characters",
        "speaking_character_ids", "observing_character_ids", "addressed_character_ids",
        "looked_at_character_ids", "mentioned_character_ids", "scheduled_character_ids",
        "delayed_character_ids", "open_threads", "last_player_input",
    ]
    return {key: _compact(current.get(key), 1000) for key in keys if key in current}


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
        if len(out) >= 24:
            break
    return {"pairs": out, "_context_filter": "akira_or_focus_pairs"}


def _small_output_contract() -> dict[str, Any]:
    return {
        "format": "1206_visual_novel_header_clean",
        "scene_header_required": True,
        "bottom_blocks": [
            "✦ Что можно сделать", "✦ Что Акира могла бы сказать", "✦ Мысли Акиры", "✦ Состояние", "✦ Отношения",
        ],
        "rules": [
            "Final gameplay answer must be the scene only, not API/status/debug summary.",
            "Use story-scene pacing, not step-by-step RPG pacing.",
            "Complete the player's declared action chain to the nearest meaningful response point.",
            "Do not stop for every step, turn, glance, pause, meter, or harmless route detail.",
            "Stop only for a real response point with stakes.",
            "Player controls Akira; do not invent consequential Akira speech unless written outside parentheses.",
            "Low-stakes service, medical or domestic micro-answers may be brief in Akira voice if they change no route, truth, trust, conflict, safety, access or relationship state.",
            "Do not decide Akira's new independent choice: trusted, attacked, revealed, agreed, left for a new goal, changed route, disclosed truth or accepted a consequential risk.",
            "Characters know only what they saw, heard, were told, have in their character knowledge state, or can infer from visible signs.",
            "Use visible_label/descriptor when Akira does not know the name.",
                        "Bottom block hard limits: max 3 actions, max 3 possible Akira lines, max 3 Akira thoughts.",
            "State block hard limit: max 3 compact lines; no new facts, no offscreen reports, no clothing/treatment recap, no long injury explanations, no NPC item ledger.",
            "Track NPC injuries/limitations and object ownership in hidden state/scene_continuity/inventory_state, not in Akira's visible header or lower panel unless Akira currently sees it and it affects this beat.",
            "Akira header inventory is a visible current slice only: do not show items that left Akira's possession, are hidden, or are held by NPCs; preserve those only in hidden state.",
            "Relationship block hard limit: max 4 current-scene entries; one signed number plus 1-3 words only; no event recap or offscreen logistics.",
            "Bottom-block actions must have stakes; no micro-actions without consequence.",
            "Never mention pacing rules, compression, nodes, mechanics, structure, or directorial handling in visible prose.",
        ],
    }


def _small_prompt_preview(chars: list[str], required_files: list[str]) -> str:
    return (
        "PLAY MODE 1206 CLEAN BRIEF\n"
        "- Load getRequiredFilesManifest, then all getRequiredFilesChunk chunks before rendering.\n"
        "- Render visible gameplay scene only; no API/status/debug.\n"
        "- Story-scene pacing: complete declared action chains to the nearest meaningful response point.\n"
        "- Do not fragment ordinary movement into step-by-step choices.\n"
        "- Stop only for a real response point with stakes.\n"
        "- Static knowledge: characters/<id>/knowledge.yaml. Dynamic memory: per-character state only.\n"
        "- Do not mention rules/mechanics/directorial wording in visible prose.\n"
        f"- Focus characters/internal ids: {', '.join(chars)}.\n"
        f"- Required files count: {len(required_files)}.\n"
    )


class SizeGuardContextResponse(BaseModel):
    session_id: str
    mode: str = "1206_clean_context"
    current_state: dict[str, Any] = Field(default_factory=dict)
    active_character_ids: list[str] = Field(default_factory=list)
    nearby_character_ids: list[str] = Field(default_factory=list)
    required_files: list[str] = Field(default_factory=list)
    usage_note: str = "Compact context only. Load manifest/chunks before rendering gameplay."


class TurnContractWithPromptPreview(BaseModel):
    session_id: str
    mode: str = "1206_clean_turn_contract"
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
    usage_note: str = "Do not stop here. Load required file chunks."


class RequiredFilesManifestItem(BaseModel):
    path: str
    exists: bool = True
    source: str = "project"
    size_chars: int = 0
    parts_total: int = 0


class RequiredFilesManifestResponse(BaseModel):
    session_id: str
    required_files: list[str] = Field(default_factory=list)
    files: list[RequiredFilesManifestItem] = Field(default_factory=list)
    missing_files: list[str] = Field(default_factory=list)
    loaded_count: int = 0
    missing_count: int = 0
    chunks_total: int = 0


class RequiredFileBundleItem(BaseModel):
    path: str
    content: str
    part_index: int = 0
    parts_total: int = 1
    content_chars: int = 0


class RequiredFilesChunkResponse(BaseModel):
    session_id: str
    required_files: list[str] = Field(default_factory=list)
    chunk_index: int = 0
    chunks_total: int = 0
    has_more: bool = False
    next_chunk_index: int | None = None
    loaded_files: list[RequiredFileBundleItem] = Field(default_factory=list)
    missing_files: list[str] = Field(default_factory=list)
    loaded_count: int = 0
    missing_count: int = 0
    total_loaded_parts: int = 0


def _required_file_parts(session_id: str, *, file_part_chars: int = 11000):
    current = _safe_read_json("state/current_state.json", session_id, {})
    future = _safe_read_json("state/future_locks_progress.json", session_id, {})
    required_files = _required_files(current, future)
    loaded_parts: list[RequiredFileBundleItem] = []
    manifest: list[RequiredFilesManifestItem] = []
    missing_files: list[str] = []

    for path in required_files:
        content, source = _read_required_file(path, session_id)
        if content is None:
            missing_files.append(path)
            manifest.append(RequiredFilesManifestItem(path=path, exists=False, source="missing"))
            continue
        pieces = _split_text(content, file_part_chars)
        manifest.append(RequiredFilesManifestItem(path=path, exists=True, source=source or "project", size_chars=len(content), parts_total=len(pieces)))
        for index, piece in enumerate(pieces):
            loaded_parts.append(RequiredFileBundleItem(path=path, content=piece, part_index=index, parts_total=len(pieces), content_chars=len(piece)))
    return required_files, loaded_parts, manifest, missing_files


def _chunk_loaded_parts(loaded_parts: list[RequiredFileBundleItem], *, max_chars: int = 30000, max_items: int = 3):
    max_chars = max(16000, min(int(max_chars or 30000), 32000))
    max_items = max(1, min(int(max_items or 3), 3))
    chunks: list[list[RequiredFileBundleItem]] = []
    current: list[RequiredFileBundleItem] = []
    current_chars = 0
    for part in loaded_parts:
        part_chars = len(part.content or "")
        if current and (len(current) >= max_items or current_chars + part_chars > max_chars):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(part)
        current_chars += part_chars
    if current:
        chunks.append(current)
    return chunks


def _required_files_chunk_response(session_id: str, *, chunk_index: int = 0, max_chars: int = 30000, max_items: int = 3):
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    required_files, loaded_parts, _manifest, missing_files = _required_file_parts(sid)
    chunks = _chunk_loaded_parts(loaded_parts, max_chars=max_chars, max_items=max_items)
    chunks_total = len(chunks)
    safe_chunk_index = max(0, min(int(chunk_index or 0), max(chunks_total - 1, 0))) if chunks_total else 0
    selected = chunks[safe_chunk_index] if chunks_total else []
    has_more = bool(chunks_total and safe_chunk_index < chunks_total - 1)
    return RequiredFilesChunkResponse(
        session_id=sid,
        required_files=required_files,
        chunk_index=safe_chunk_index,
        chunks_total=chunks_total,
        has_more=has_more,
        next_chunk_index=safe_chunk_index + 1 if has_more else None,
        loaded_files=selected,
        missing_files=missing_files,
        loaded_count=len({part.path for part in loaded_parts}),
        missing_count=len(missing_files),
        total_loaded_parts=len(loaded_parts),
    )


_remove_routes(CONTEXT_PATH, {"GET"}, "getSessionContext")
_remove_routes(TURN_CONTRACT_PATH, {"GET"}, "getSessionTurnContract")
_remove_routes(MANIFEST_PATH, {"GET"}, "getRequiredFilesManifest")
_remove_routes(CHUNK_PATH, {"GET"}, "getRequiredFilesChunk")
_remove_routes(BUNDLE_PATH, {"GET"}, "getRequiredFilesBundle")


@app.get(CONTEXT_PATH, response_model=SizeGuardContextResponse, operation_id="getSessionContext")
def get_session_context_size_guard(session_id: str) -> SizeGuardContextResponse:
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
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
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    current = _safe_read_json("state/current_state.json", sid, {})
    future = _safe_read_json("state/future_locks_progress.json", sid, {})
    inventory = _safe_read_json("state/inventory_state.json", sid, {})
    scene_continuity = _safe_read_json("state/scene_continuity_state.json", sid, {})
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
            "Then call getRequiredFilesChunk from chunk_index=0 until has_more=false.",
            "Do not render gameplay from compact contract alone.",
        ],
        knowledge_table=_character_knowledge_state(sid, chars),
        inventory_contract={
            "visible_inventory": _compact(current.get("visible_inventory", []), 1000),
            "nearby_items": _compact(current.get("nearby_items", []), 1000),
            "current_outfit": _compact(current.get("current_outfit"), 1000),
            "akira_inventory_state": _compact((inventory.get("akira") or {}) if isinstance(inventory, dict) else {}, 1000),
            "scene_object_and_npc_continuity_hidden": _compact(scene_continuity, 1200),
            "visible_rule": "Header/lower panel shows only Akira-visible current slice. NPC-held, hidden, transferred or offscreen objects stay hidden in state.",
        },
        relationship_context=_relationship_slice(relationships, chars),
        story_context=_compact(story_lines, 1400) if isinstance(story_lines, dict) else {},
        prompt_preview=_small_prompt_preview(chars, files),
    )


@app.get(MANIFEST_PATH, response_model=RequiredFilesManifestResponse, operation_id="getRequiredFilesManifest")
def get_required_files_manifest(session_id: str) -> RequiredFilesManifestResponse:
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    required_files, loaded_parts, manifest, missing_files = _required_file_parts(sid)
    chunks_total = max(1, ceil(len(loaded_parts) / 3)) if loaded_parts else 0
    return RequiredFilesManifestResponse(
        session_id=sid,
        required_files=required_files,
        files=manifest,
        missing_files=missing_files,
        loaded_count=len({part.path for part in loaded_parts}),
        missing_count=len(missing_files),
        chunks_total=chunks_total,
    )


@app.get(CHUNK_PATH, response_model=RequiredFilesChunkResponse, operation_id="getRequiredFilesChunk")
def get_required_files_chunk(session_id: str, chunk_index: int = 0, max_chars: int = 30000, max_items: int = 3) -> RequiredFilesChunkResponse:
    return _required_files_chunk_response(session_id, chunk_index=chunk_index, max_chars=max_chars, max_items=max_items)


@app.get(BUNDLE_PATH, response_model=RequiredFilesChunkResponse, operation_id="getRequiredFilesBundle")
def get_required_files_bundle(session_id: str, chunk_index: int = 0, max_chars: int = 30000, max_items: int = 3) -> RequiredFilesChunkResponse:
    return _required_files_chunk_response(session_id, chunk_index=chunk_index, max_chars=max_chars, max_items=max_items)


base.active_scene_characters = _scene_chars
base.recommended_files_for_context = _recommended_files_for_context_size_guard
app.version = "0.3.134-npc-item-continuity-v1"
