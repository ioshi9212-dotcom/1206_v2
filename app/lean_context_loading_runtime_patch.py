"""Lean context loading patch for 1206.

Goal: prevent ResponseTooLargeError by never returning full file contents in
turn-contract/processTurn. Files are listed in the manifest and loaded by chunks.

Rules:
- Always load only small global/current-scene context.
- Akira is always loaded.
- Other character cards are loaded only when active/nearby/speaking/triggered.
- Hidden/past files are loaded only by topic triggers or when the character is
  truly active and the scene needs that hidden layer.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from fastapi import Body

import app.start_scene_runtime_patch as start_runtime
from app.start_scene_runtime_patch import app

try:
    import app.character_registry_runtime_patch as character_registry
except Exception:  # pragma: no cover
    character_registry = None  # type: ignore

base = start_runtime.base

MAX_CHARS_PER_FILE = 4500
DEFAULT_CHUNK_MAX_CHARS = 18000
DEFAULT_CHUNK_MAX_ITEMS = 4

ALWAYS_SMALL_FILES = [
    "state/context_loading_rules_1206.json",
    "state/east_sector_1206_context.json",
    "calendar/east_sector_1206_calendar.yaml",
]

CURRENT_SCENE_FILES = {
    "start_scene": [
        "calendar/days/1206-08-31.yaml",
        "scenes/start_scene_logic.md",
    ],
}

CHARACTER_ALIASES = {
    "akira": "akira",
    "char_akira": "akira",

    "jun": "jun",
    "jun_carter": "jun",
    "char_jun": "jun",

    "ray": "ray",
    "ray_carter": "ray",
    "char_ray": "ray",

    "raiden": "raiden",
    "raiden_sterling": "raiden",
    "char_raiden": "raiden",

    "irey": "irey",
    "char_irey": "irey",

    "emma": "emma",
    "char_emma": "emma",

    "yuna": "yuna",
    "yuna_gray": "yuna",
    "char_yuna": "yuna",

    "miki": "miki",
    "miki_larsen": "miki",
    "char_miki": "miki",
}

CHARACTER_FILES = {
    cid: [
        f"characters/{cid}/main.yaml",
        f"characters/{cid}/character.yaml",
    ]
    for cid in ["akira", "jun", "ray", "raiden", "irey", "emma", "yuna", "miki"]
}

PAST_FILES = {
    cid: f"characters/{cid}/past.yaml"
    for cid in ["akira", "jun", "ray", "raiden", "irey", "emma", "yuna", "miki"]
}

TOPIC_TRIGGERS = {
    "samuel": {
        "needles": ["самуэл", "самуэль", "samuel", "северн", "лаборатор", "эксперимент", "полит"],
        "files": ["state/east_sector_1206_context.json"],
    },
    "raiden": {
        "needles": ["райден", "рейден", "кольц", "ar", "сигарет", "холод", "хвоя", "пирсинг", "белые волосы"],
        "files": ["characters/raiden/main.yaml", "characters/raiden/character.yaml", "characters/raiden/past.yaml"],
    },
    "ray": {
        "needles": ["рэй", "рей картер", "восточный сектор", "картер", "старший командир"],
        "files": ["characters/ray/main.yaml", "characters/ray/character.yaml"],
    },
    "yuna": {
        "needles": ["юна", "медик", "медблок", "рана", "ранение", "кровь", "осмотр", "потеря сознания"],
        "files": ["characters/yuna/main.yaml", "characters/yuna/character.yaml"],
    },
    "miki": {
        "needles": ["мики", "еда", "одежд", "свет", "подруга", "алекс"],
        "files": ["characters/miki/main.yaml", "characters/miki/character.yaml"],
    },
    "akira_hidden": {
        "needles": ["память", "шрам", "кольцо", "пирсинг", "кот", "животн", "пространств", "ребён", "беремен"],
        "files": ["characters/akira/past.yaml"],
    },
}


def _remove_route(path: str, method: str | None = None) -> None:
    method_upper = method.upper() if method else None
    for route in list(app.router.routes):
        if getattr(route, "path", None) != path:
            continue
        methods = set(getattr(route, "methods", set()) or set())
        if method_upper is None or method_upper in methods:
            app.router.routes.remove(route)


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        s = str(item or "").strip().replace("\\", "/").lstrip("/")
        if s and s not in out:
            out.append(s)
    return out


def _cid(raw: Any) -> str:
    return CHARACTER_ALIASES.get(str(raw or "").strip(), str(raw or "").strip())


def _safe_state(session_id: str) -> dict[str, Any]:
    try:
        return start_runtime._ensure_start_state(session_id)
    except Exception:
        try:
            return base.read_json("state/current_state.json", session_id, default={}) or {}
        except Exception:
            return {}


def _read_text(path: str, session_id: str | None = None) -> str:
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


def _exists(path: str, session_id: str | None = None) -> bool:
    return bool(_read_text(path, session_id))


def _text_has(text: str, needles: list[str]) -> bool:
    low = str(text or "").lower().replace("ё", "е")
    return any(n.lower().replace("ё", "е") in low for n in needles)


def _scene_id(state: dict[str, Any]) -> str:
    return str(state.get("current_scene_id") or state.get("scene_id") or "start_scene")


def _active_ids(state: dict[str, Any]) -> list[str]:
    raw = []
    for key in ["active_character_ids", "active_characters", "nearby_character_ids", "nearby_characters", "speaking_character_ids", "observing_character_ids"]:
        value = state.get(key)
        if isinstance(value, list):
            raw.extend(value)
    # Akira is always POV.
    raw.insert(0, "akira")
    return _unique([_cid(x) for x in raw])


def _required_files(session_id: str, user_input: str = "") -> list[str]:
    state = _safe_state(session_id)
    files: list[str] = []

    files.extend(ALWAYS_SMALL_FILES)
    files.extend(CURRENT_SCENE_FILES.get(_scene_id(state), []))

    # Akira always.
    files.extend(CHARACTER_FILES["akira"])

    # Only active/nearby/speaking/observing characters.
    for cid in _active_ids(state):
        if cid == "akira":
            continue
        files.extend(CHARACTER_FILES.get(cid, []))

    # Trigger-based deeper / inactive loads.
    trigger_text = " ".join([
        str(user_input or ""),
        str(state.get("current_scene_goal") or ""),
        str(state.get("last_player_action") or ""),
        str(state.get("current_location_text") or state.get("location") or ""),
    ])
    for cfg in TOPIC_TRIGGERS.values():
        if _text_has(trigger_text, cfg["needles"]):
            files.extend(cfg["files"])

    # Medical condition auto-load.
    akira_state = state.get("akira_state") if isinstance(state.get("akira_state"), dict) else {}
    state_text = " ".join(str(v) for v in akira_state.values()) if isinstance(akira_state, dict) else ""
    if _text_has(state_text, ["кров", "рана", "травм", "потеря сознания", "медблок"]):
        files.extend(CHARACTER_FILES["yuna"])

    return [p for p in _unique(files) if _exists(p, session_id)]


def _file_meta(path: str, session_id: str) -> dict[str, Any]:
    text = _read_text(path, session_id)
    return {
        "path": path,
        "chars": len(text),
        "loaded_by": "lean_context_v9",
        "content_in_contract": False,
    }


def _trim(text: str, limit: int = MAX_CHARS_PER_FILE) -> dict[str, Any]:
    if len(text) <= limit:
        return {"content": text, "truncated": False, "chars": len(text)}
    return {"content": text[:limit], "truncated": True, "chars": len(text)}


@app.get("/api/v1/sessions/{session_id}/required-files-manifest")
def getRequiredFilesManifest(session_id: str) -> dict[str, Any]:
    files = _required_files(session_id)
    metas = [_file_meta(p, session_id) for p in files]
    chunks_total = max(1, math.ceil(len(files) / DEFAULT_CHUNK_MAX_ITEMS))
    return {
        "session_id": session_id,
        "required_files": files,
        "files": metas,
        "missing_files": [],
        "chunks_total": chunks_total,
        "loaded_count": len(files),
        "missing_count": 0,
        "usage_note": "Call required-files-chunk. Turn-contract intentionally contains no file contents.",
    }


@app.get("/api/v1/sessions/{session_id}/required-files-chunk")
def getRequiredFilesChunk(
    session_id: str,
    chunk_index: int = 0,
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    max_items: int = DEFAULT_CHUNK_MAX_ITEMS,
) -> dict[str, Any]:
    files = _required_files(session_id)
    max_items = max(1, min(int(max_items or DEFAULT_CHUNK_MAX_ITEMS), 6))
    max_chars = max(1000, min(int(max_chars or DEFAULT_CHUNK_MAX_CHARS), 24000))
    start = max(0, int(chunk_index)) * max_items
    batch = files[start:start + max_items]

    loaded = []
    used = 0
    per_file_limit = max(1000, max_chars // max(1, len(batch) or 1))
    for path in batch:
        raw = _read_text(path, session_id)
        item = {"path": path, **_trim(raw, per_file_limit)}
        used += len(item["content"])
        loaded.append(item)

    chunks_total = max(1, math.ceil(len(files) / max_items))
    has_more = (start + max_items) < len(files)
    return {
        "session_id": session_id,
        "required_files": files,
        "chunk_index": int(chunk_index),
        "chunks_total": chunks_total,
        "has_more": has_more,
        "next_chunk_index": int(chunk_index) + 1 if has_more else None,
        "loaded_files": loaded,
        "missing_files": [],
        "loaded_count": len(loaded),
        "missing_count": 0,
        "total_loaded_parts": used,
    }


def _thin_contract(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    state = _safe_state(session_id)
    files = _required_files(session_id, user_input=user_input)
    return {
        "success": True,
        "session_id": session_id,
        "mode": mode,
        "current_scene_anchor": {
            "date": state.get("current_date") or state.get("date"),
            "time": state.get("current_time") or state.get("time"),
            "scene_id": _scene_id(state),
            "location": state.get("current_location_id") or state.get("location_id") or state.get("location"),
            "active_characters": _active_ids(state),
            "conditional_characters": state.get("conditional_character_ids") or state.get("conditional_characters") or [],
        },
        "active_character_ids": _active_ids(state),
        "nearby_character_ids": state.get("nearby_character_ids") or state.get("nearby_characters") or [],
        "required_files": files,
        "required_file_contents": {},
        "output_format_contract": {
            "scene_only_for_play": True,
            "no_technical_comment_before_scene": True,
            "player_controls_only_akira": True,
        },
        "required_checks_before_answer": [
            "Do not generate from memory if API/contract failed.",
            "Use manifest and chunks for file contents.",
            "Load Akira plus only present/triggered characters.",
            "Do not load inactive future characters.",
        ],
        "knowledge_table": {},
        "inventory_contract": {},
        "relationship_context": {},
        "story_context": {
            "context_loading": "lean_v9",
            "samuel_rule": "Name Samuel may appear as public figure, but do not reveal he seeks/needs Akira or caused her collapse.",
        },
        "prompt_preview": "Lean v9 contract. No file contents in this response. Use required-files-manifest/chunk.",
        "usage_note": "ResponseTooLarge guard active: contract lists files only.",
    }


# Replace bloated turn-contract routes if previous modules registered them.
_remove_route("/api/v1/sessions/{session_id}/turn-contract", "GET")
_remove_route("/api/v1/sessions/{session_id}/turn-contract", "POST")


@app.get("/api/v1/sessions/{session_id}/turn-contract")
def getSessionTurnContract(session_id: str, user_input: str = "", mode: str = "play") -> dict[str, Any]:
    return _thin_contract(session_id, user_input=user_input, mode=mode)


@app.post("/api/v1/sessions/{session_id}/turn-contract")
def postSessionTurnContract(session_id: str, payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    return _thin_contract(
        session_id,
        user_input=str(payload.get("user_input") or payload.get("player_input") or ""),
        mode=str(payload.get("mode") or "play"),
    )


try:
    app.version = "0.3.90-1206-lean-context-v9"
except Exception:
    pass
