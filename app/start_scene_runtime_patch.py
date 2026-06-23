"""Exact start-scene runtime patch for Akira 1206 v2.

Layered after calendar_scene_runtime_patch.
It makes the first command `начнем`/`начнём`/`старт` return the fixed
start scene from scenes/start_scene.md, while scene-packet also loads Jun,
Irey and Emma cards/goals immediately.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Body, HTTPException
from pydantic import BaseModel, Field

import app.calendar_scene_runtime_patch as previous_runtime
from app.calendar_scene_runtime_patch import app
from app import compact as base

_previous_get_scene_packet = previous_runtime.get_scene_packet
_previous_openapi = app.openapi

for _name in ["scenes", "data"]:
    try:
        if _name not in base.SYNC_FROM_REPO:
            base.SYNC_FROM_REPO.append(_name)
    except Exception:
        pass

app.version = "0.3.108-start-scene-day-phase"

START_SCENE_ID = "start_scene"
START_SCENE_PATH = "scenes/start_scene.md"
START_SCENE_LOGIC_PATH = "scenes/start_scene_logic.md"
START_COMMANDS = {"начнем", "начнём", "начинай", "начать", "старт", "start", "begin"}

VOICE_IDENTITY_MAP = {
    "Женский голос снизу": "emma",
    "Незнакомый мужской голос": "irey",
}

START_CHARACTER_IDS = ["akira", "jun", "irey", "emma"]
CONDITIONAL_CHARACTER_IDS = ["raiden", "ray"]

START_CHARACTER_FILES: dict[str, list[str]] = {
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
}

START_SCENE_GOALS = {
    "akira": "Проснуться, понять угрозу, сохранить себя, использовать записку Джуна и найти Рэя / Восточный сектор.",
    "jun": "Выиграть время, скрыть Акиру, не дать Ирэю и Эмме получить контроль, направить Акиру к Рэю / Восточному сектору.",
    "irey": "Найти Акиру, увидеть её живой, оценить состояние, не отдать Самуэлю и скрыть личную цель от Эммы.",
    "emma": "Давить, быстро завершить задачу, действовать в линии Самуэля и не быть мягкой союзницей Акиры.",
}


class StartSessionCreateRequest(BaseModel):
    session_id: str | None = None
    title: str | None = None
    reset: bool = False


class ProcessTurnRequest(BaseModel):
    player_input: str
    mode: str = "play"
    include_file_contents: bool = False
    state_patches: dict[str, Any] = Field(default_factory=dict)


def _remove_route(path: str, method: str | None = None) -> None:
    method_upper = method.upper() if method else None
    for route in list(app.router.routes):
        if getattr(route, "path", None) != path:
            continue
        methods = set(getattr(route, "methods", set()) or set())
        if method_upper is None or method_upper in methods:
            app.router.routes.remove(route)


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _safe_session_id(session_id: str | None) -> str:
    raw = session_id or f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    try:
        return base.safe_session_id(raw)
    except Exception:
        safe = "".join(ch for ch in str(raw) if ch.isalnum() or ch in "-_")
        return safe or "main-1206-v2"


def _normalize_command(text: str) -> str:
    return " ".join(str(text or "").strip().lower().replace("ё", "е").split())


def _is_start_command(text: str) -> bool:
    normalized = _normalize_command(text)
    return normalized in {cmd.replace("ё", "е") for cmd in START_COMMANDS}


def _read_repo_or_data_text(path: str, session_id: str | None = None) -> str:
    safe = str(path).replace("\\", "/").strip().lstrip("/")
    candidates: list[Path] = []
    if session_id and safe.startswith("state/"):
        try:
            candidates.append(base.session_dir(session_id) / safe)
        except Exception:
            pass
    for root in [getattr(base, "DATA", None), getattr(base, "ROOT", None)]:
        if root:
            candidates.append(Path(root) / safe)
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except Exception:
            continue
    return ""


def _extract_first_text_block(markdown: str) -> str:
    marker = "## Текст первого вывода"
    start = markdown.find(marker)
    if start == -1:
        return ""
    next_section = markdown.find("\n## ", start + len(marker))
    section = markdown[start: next_section if next_section != -1 else len(markdown)]
    block_start = section.find("```text")
    if block_start == -1:
        block_start = section.find("```")
    if block_start == -1:
        return ""
    content_start = section.find("\n", block_start)
    block_end = section.find("```", content_start + 1)
    if content_start == -1 or block_end == -1:
        return ""
    return section[content_start + 1:block_end].strip()


def _start_scene_exact_text() -> str:
    return _extract_first_text_block(_read_repo_or_data_text(START_SCENE_PATH))


def _read_state(session_id: str, path: str, default: Any = None) -> Any:
    try:
        return base.read_json(path, session_id, default=default)
    except Exception:
        return default


def _write_state(session_id: str, path: str, data: Any) -> None:
    base.write_json(path, data, session_id)


def _merge_unique(existing: Any, values: list[str]) -> list[str]:
    result = list(existing or []) if isinstance(existing, list) else []
    for item in values:
        if item not in result:
            result.append(item)
    return result


def _ensure_start_state(session_id: str) -> dict[str, Any]:
    current = _read_state(session_id, "state/current_state.json", {}) or {}
    scene_id = current.get("current_scene_id") or current.get("scene_id") or START_SCENE_ID
    completed = bool(current.get("start_scene_completed"))

    if scene_id == START_SCENE_ID and not completed:
        current.update(
            {
                "project_slug": "akira-1206v2",
                "story": "akira_1206v2",
                "current_scene_id": START_SCENE_ID,
                "scene_id": START_SCENE_ID,
                "current_date": "1206-08-31",
                "date": "1206-08-31",
                "current_day_phase": "поздняя ночь",
                "time_of_day": "поздняя ночь",
                "current_location_id": "jun_house_akira_room",
                "location_id": "jun_house_akira_room",
                "current_location_text": "дом Джуна Картера, комната Акиры",
                "current_outfit": "серая пижама — футболка и шорты; босиком",
                "active_characters": list(START_CHARACTER_IDS),
                "active_character_ids": list(START_CHARACTER_IDS),
                "nearby_characters": [],
                "nearby_character_ids": [],
                "conditional_character_ids": list(CONDITIONAL_CHARACTER_IDS),
                "allowed_main_characters": _merge_unique(current.get("allowed_main_characters"), START_CHARACTER_IDS + CONDITIONAL_CHARACTER_IDS),
                "visible_inventory": ["записка: Рэй / Восточный сектор"],
                "nearby_items": ["дверь", "окно", "стол", "записка"],
                "current_scene_goal": "Стартовая сцена: поздняя ночь. Акира просыпается от голосов Эммы и Ирэя внизу; Джун тянет время; записка ведёт к Рэю / Восточному сектору.",
                "voice_identity_map_hidden": dict(VOICE_IDENTITY_MAP),
                "start_scene_file": START_SCENE_PATH,
                "start_scene_logic_file": START_SCENE_LOGIC_PATH,
                "start_scene_exact_text_required": True,
            }
        )
        current["weather"] = {
            "summary": "прохладная поздняя ночь; подробности погоды использовать только если они влияют на действие",
            "temperature_feel": "прохладно",
            "details": [],
        }
        akira_state = current.setdefault("akira_state", {})
        if isinstance(akira_state, dict):
            akira_state.update(
                {
                    "visible_state": "резко проснулась; внешне собрана",
                    "internal_state": "эмоции заблокированы; память держит только последние два года",
                    "body_state": "тело собрано раньше памяти",
                    "hair_state": "сонные растрёпанные волосы",
                }
            )
        _write_state(session_id, "state/current_state.json", current)
    return current


def _seed_session_files(session_id: str, *, reset: bool = False, title: str | None = None) -> Path:
    base.seed()
    sid = _safe_session_id(session_id)
    d = base.session_dir(sid)
    if reset and d.exists():
        shutil.rmtree(d)
    if not d.exists():
        d.mkdir(parents=True, exist_ok=True)
    try:
        base.copy_missing(base.DATA / "state", d / "state")
    except Exception:
        pass
    meta_path = d / "session.json"
    if reset or not meta_path.exists():
        meta = {
            "session_id": sid,
            "title": title or "Akira 1206 v2 Session",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _ensure_start_state(sid)
    return d


def _is_first_scene_not_delivered(current: dict[str, Any]) -> bool:
    if current.get("first_scene_delivered") or current.get("game_started"):
        return False
    try:
        if int(current.get("scene_count", 0) or 0) > 0:
            return False
    except Exception:
        pass
    scene_id = current.get("current_scene_id") or current.get("scene_id") or START_SCENE_ID
    return scene_id == START_SCENE_ID


def _cut(text: str, limit: int = 24000) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "\n...[truncated]"


def _append_loaded_file(packet: dict[str, Any], path: str, content: str, *, limit: int = 24000, runtime_role: str = "start_scene") -> None:
    if not content:
        return
    required = packet.setdefault("required_files", [])
    if path not in required:
        required.append(path)
    manifest = packet.setdefault("required_file_manifest", [])
    if not any(isinstance(item, dict) and item.get("path") == path for item in manifest):
        manifest.append({"path": path, "exists": True, "source": "project", "size_chars": len(content), "parts_total": 1, "runtime_patch": "start_scene_exact_output", "runtime_role": runtime_role})
    loaded = packet.setdefault("loaded_files", [])
    if not any(isinstance(item, dict) and item.get("path") == path for item in loaded):
        cut = _cut(content, limit)
        loaded.append({"path": path, "part_index": 0, "parts_total": 1, "content_chars_original": len(content), "content_chars_in_packet": len(cut), "truncated_in_packet": len(cut) < len(content), "runtime_patch": "start_scene_exact_output", "runtime_role": runtime_role, "content": cut})


def _start_character_file_refs() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for cid, files in START_CHARACTER_FILES.items():
        result[cid] = [path for path in files if base.repo_file_exists(path)]
    return result


def _attach_start_scene_context(packet: dict[str, Any], session_id: str) -> dict[str, Any]:
    current = _ensure_start_state(session_id)
    exact_text = _start_scene_exact_text()
    first_pending = _is_first_scene_not_delivered(current)

    _append_loaded_file(packet, START_SCENE_PATH, _read_repo_or_data_text(START_SCENE_PATH), runtime_role="start_scene_exact_text")
    _append_loaded_file(packet, START_SCENE_LOGIC_PATH, _read_repo_or_data_text(START_SCENE_LOGIC_PATH), runtime_role="start_scene_logic")

    for cid, files in START_CHARACTER_FILES.items():
        for path in files:
            if base.repo_file_exists(path):
                _append_loaded_file(packet, path, _read_repo_or_data_text(path, session_id), limit=18000, runtime_role=f"start_character:{cid}")

    character_loading = packet.setdefault("character_loading", {})
    ids = list(character_loading.get("scene_character_ids") or [])
    for cid in START_CHARACTER_IDS:
        if cid not in ids:
            ids.append(cid)
    character_loading["scene_character_ids"] = ids
    loaded_character_files = list(character_loading.get("loaded_character_files") or [])
    for files in START_CHARACTER_FILES.values():
        for path in files:
            if base.repo_file_exists(path) and path not in loaded_character_files:
                loaded_character_files.append(path)
    character_loading["loaded_character_files"] = loaded_character_files
    character_loading["start_scene_forced_character_ids"] = list(START_CHARACTER_IDS)

    hard_rules = packet.setdefault("hard_rules", [])
    for rule in [
        "If user starts a new game with 'начнем/начнём/старт/start', create a session and output initial_scene.exact_text verbatim.",
        "For the first start_scene output, do not rewrite, shorten, expand or continue the exact text.",
        "Hidden runtime map: 'Женский голос снизу' is emma; 'Незнакомый мужской голос' is irey. Do not reveal those names in Akira POV before in-scene reveal.",
        "For start_scene, load/read Akira, Jun, Irey and Emma character files and goals before NPC reactions.",
    ]:
        if rule not in hard_rules:
            hard_rules.append(rule)

    packet["initial_scene"] = {
        "scene_id": START_SCENE_ID,
        "status": "READY_EXACT_TEXT" if first_pending else "POST_START_OR_ALREADY_DELIVERED",
        "exact_text_required": first_pending,
        "must_output_exact_text_on_start_command": first_pending,
        "text_path": START_SCENE_PATH,
        "logic_path": START_SCENE_LOGIC_PATH,
        "exact_text": exact_text if first_pending else "",
        "voice_identity_map_hidden": dict(VOICE_IDENTITY_MAP),
        "visible_labels_must_remain": ["Женский голос снизу", "Незнакомый мужской голос"],
        "required_character_ids": list(START_CHARACTER_IDS),
        "conditional_character_ids": list(CONDITIONAL_CHARACTER_IDS),
        "character_file_refs": _start_character_file_refs(),
        "scene_goals_by_character": dict(START_SCENE_GOALS),
        "header_source": "gpt/scene_format.md + state/current_state.json current_location_text",
        "do_not_generate_from_memory": True,
    }
    packet["packet_version"] = "1206v2_scene_packet_v4_start_scene_exact"
    packet["runtime_version"] = app.version
    return packet


_remove_route("/api/v1/sessions", "POST")


@app.post("/api/v1/sessions", operation_id="createSession")
def create_session(payload: StartSessionCreateRequest | None = Body(default=None)) -> dict[str, Any]:
    req = payload or StartSessionCreateRequest()
    sid = _safe_session_id(req.session_id)
    d = _seed_session_files(sid, reset=bool(req.reset), title=req.title)
    current = _read_state(sid, "state/current_state.json", {}) or {}
    exact_text = _start_scene_exact_text()
    return {
        "success": True,
        "session_id": sid,
        "title": req.title or "Akira 1206 v2 Session",
        "created_or_loaded": True,
        "reset": bool(req.reset),
        "files": sorted(p.name for p in d.iterdir()) if d.exists() else [],
        "start_scene": {
            "scene_id": START_SCENE_ID,
            "ready": bool(exact_text),
            "exact_text_required": _is_first_scene_not_delivered(current),
            "text_path": START_SCENE_PATH,
            "logic_path": START_SCENE_LOGIC_PATH,
            "voice_identity_map_hidden": dict(VOICE_IDENTITY_MAP),
            "required_character_ids": list(START_CHARACTER_IDS),
            "character_file_refs": _start_character_file_refs(),
            "next_action": "Call processTurn with player_input='начнем' to receive exact scene_text, or call getScenePacket and output initial_scene.exact_text verbatim.",
        },
        "next": {
            "scene_packet": f"/api/v1/sessions/{sid}/scene-packet",
            "turn": f"/api/v1/sessions/{sid}/turn",
            "turn_contract": f"/api/v1/sessions/{sid}/turn-contract",
            "apply_turn_result": f"/api/v1/sessions/{sid}/apply-turn-result",
        },
    }


def _strip_inline_file_contents(packet: dict[str, Any]) -> dict[str, Any]:
    """Keep scene packet metadata but remove large inline file bodies.

    After the exact first scene is delivered, processTurn should not return
    loaded file contents. The gameplay client must use required-files-chunk for
    file contents; otherwise Action responses exceed the platform size limit.
    """
    if not isinstance(packet, dict):
        return {}
    compact = dict(packet)
    if isinstance(compact.get("loaded_files"), list):
        compact["loaded_files"] = [
            {
                "path": item.get("path"),
                "content_chars_original": item.get("content_chars_original") or item.get("content_chars") or item.get("chars"),
                "truncated_in_packet": item.get("truncated_in_packet") or item.get("truncated"),
                "content_omitted": True,
            }
            for item in compact.get("loaded_files", [])
            if isinstance(item, dict)
        ]
    if isinstance(compact.get("required_file_contents"), dict):
        compact["required_file_contents"] = {}
    initial = compact.get("initial_scene")
    if isinstance(initial, dict):
        initial = dict(initial)
        if not initial.get("exact_text_required"):
            initial["exact_text"] = ""
        compact["initial_scene"] = initial
    compact["content_mode"] = "metadata_only_after_first_scene"
    compact["load_instruction"] = "Use required-files-manifest/chunk for file contents. processTurn scene_packet intentionally omits contents after start scene."
    return compact


_remove_route("/api/v1/sessions/{session_id}/scene-packet", "GET")


@app.get("/api/v1/sessions/{session_id}/scene-packet", operation_id="getScenePacket")
def get_scene_packet(
    session_id: str,
    max_total_chars: int = 12000,
    per_file_chars: int = 3000,
    max_files: int = 4,
    include_file_contents: bool = False,
) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    _seed_session_files(sid, reset=False)
    current = _read_state(sid, "state/current_state.json", {}) or {}
    first_pending = _is_first_scene_not_delivered(current)
    packet = _previous_get_scene_packet(
        sid,
        max_total_chars=min(int(max_total_chars or 12000), 12000),
        per_file_chars=min(int(per_file_chars or 3000), 3000),
        max_files=min(int(max_files or 4), 4),
    )
    packet = _attach_start_scene_context(packet, sid)
    if first_pending:
        return packet
    # Never inline large file contents after the first exact scene, even if an old
    # client still sends include_file_contents=true. This prevents ResponseTooLargeError.
    return _strip_inline_file_contents(packet)


@app.post("/api/v1/sessions/{session_id}/turn", operation_id="processTurn")
def process_turn(session_id: str, req: ProcessTurnRequest) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    _seed_session_files(sid, reset=False)
    current = _ensure_start_state(sid)
    mode = _normalize_command(req.mode)
    if mode and mode != "play":
        return {"success": True, "session_id": sid, "status": "TECHNICAL_TURN", "scene_text": "", "current_scene_id": current.get("current_scene_id") or START_SCENE_ID}

    if _is_first_scene_not_delivered(current):
        if not _is_start_command(req.player_input):
            return {"success": True, "session_id": sid, "status": "AWAIT_START_COMMAND", "scene_text": "", "current_scene_id": START_SCENE_ID}
        scene_text = _start_scene_exact_text()
        if not scene_text:
            raise HTTPException(status_code=404, detail=f"Start scene text not found: {START_SCENE_PATH}")
        current["game_started"] = True
        current["first_scene_delivered"] = True
        current["scene_count"] = max(1, int(current.get("scene_count", 0) or 0))
        current["last_player_input"] = req.player_input
        current["last_scene_status"] = "START_SCENE_EXACT_TEXT"
        current["updated_at"] = _utc_now()
        _write_state(sid, "state/current_state.json", current)
        history = _read_state(sid, "state/scene_history.json", [])
        if not isinstance(history, list):
            history = []
        history.append({"scene_id": START_SCENE_ID, "status": "START_SCENE_EXACT_TEXT", "time": _utc_now(), "player_input": req.player_input, "scene_text": scene_text})
        _write_state(sid, "state/scene_history.json", history)
        return {
            "success": True,
            "session_id": sid,
            "player_input": req.player_input,
            "current_scene_id": START_SCENE_ID,
            "status": "START_SCENE_EXACT_TEXT",
            "scene_text": scene_text,
            "voice_identity_map_hidden": dict(VOICE_IDENTITY_MAP),
            "required_character_ids": list(START_CHARACTER_IDS),
            "character_file_refs": _start_character_file_refs(),
        }

    packet = get_scene_packet(sid, include_file_contents=bool(req.include_file_contents))
    return {
        "success": True,
        "session_id": sid,
        "player_input": req.player_input,
        "current_scene_id": current.get("current_scene_id") or current.get("scene_id") or START_SCENE_ID,
        "status": "SCENE_PACKET_RETURNED_COMPACT",
        "scene_text": "",
        "scene_packet": packet,
        "usage_note": "Compact response. If file contents are needed, call required-files-manifest/chunk; do not request full scene_packet contents on normal turns.",
    }


def _process_turn_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["player_input"],
        "properties": {
            "player_input": {"type": "string"},
            "mode": {"type": "string", "default": "play"},
            "include_file_contents": {"type": "boolean", "default": False},
            "state_patches": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": True,
    }


def _openapi_start_scene_patch() -> dict[str, Any]:
    schema = _previous_openapi()
    schema.setdefault("info", {})["version"] = app.version
    paths = schema.setdefault("paths", {})

    session_path = paths.setdefault("/api/v1/sessions", {}).setdefault("post", {})
    session_path["operationId"] = "createSession"
    session_path["summary"] = "Create or initialize a 1206 v2 gameplay session with exact start-scene metadata"
    session_path["description"] = "Use this when the player writes 'начнем/начнём/старт'. Then call processTurn or getScenePacket for the exact first scene text."

    paths["/api/v1/sessions/{session_id}/turn"] = {
        "post": {
            "operationId": "processTurn",
            "summary": "Return exact first start_scene text for start command; after that return scene packet",
            "parameters": [{"name": "session_id", "in": "path", "required": True, "schema": {"type": "string"}}],
            "requestBody": {"required": True, "content": {"application/json": {"schema": _process_turn_schema()}}},
            "responses": {"200": {"description": "Exact start scene text or scene packet", "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}}}},
        }
    }
    return schema


_remove_route("/openapi-actions.json", "GET")


@app.get("/openapi-actions.json", include_in_schema=False)
def openapi_actions() -> dict[str, Any]:
    return _openapi_start_scene_patch()


app.openapi_schema = None
app.openapi = _openapi_start_scene_patch  # type: ignore[method-assign]
