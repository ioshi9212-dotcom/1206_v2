from __future__ import annotations

from typing import Any
import json
import re

from fastapi import HTTPException

import app.scene_packet_runtime_patch as previous_runtime
from app.scene_packet_runtime_patch import app

base = previous_runtime.base

# Make these folders persistent in Railway volume seeding.
for _name in ["calendar", "engine", "canon", "characters", "gpt"]:
    try:
        if _name not in base.SYNC_FROM_REPO:
            base.SYNC_FROM_REPO.append(_name)
    except Exception:
        pass

app.version = "0.3.131-calendar-clean-story-rules-v1"


def _remove_route(path: str) -> None:
    for route in list(app.router.routes):
        if getattr(route, "path", None) == path:
            app.router.routes.remove(route)


def _safe_session_id(session_id: str) -> str:
    try:
        return base.safe_session_id(session_id)
    except Exception:
        safe = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
        return safe or "main-1206-v2"


def _read_state(session_id: str, path: str, default: Any = None) -> Any:
    try:
        return previous_runtime._read_json_state(session_id, path, default)
    except Exception:
        try:
            return base.read_json(path, session_id, default=default)
        except Exception:
            return default


def _repo_exists(path: str) -> bool:
    try:
        return bool(base.repo_file_exists(path))
    except Exception:
        return False


def _read_text(path: str, session_id: str | None = None) -> str:
    try:
        if str(path).startswith("state/"):
            return base.read_text(path, session_id)
        return base.read_text(path, None)
    except TypeError:
        try:
            return base.read_text(path)
        except Exception:
            return ""
    except Exception:
        return ""


def _cut(text: str, limit: int = 20000) -> str:
    try:
        return previous_runtime._cut_text(text, limit)
    except Exception:
        text = text or ""
        return text if len(text) <= limit else text[:limit].rstrip() + "\n...[truncated]"


def _current_date_from_state(current: dict[str, Any]) -> str:
    value = (
        current.get("date")
        or current.get("current_date")
        or current.get("scene_date")
        or "1206-08-31"
    )
    return str(value)


def _current_time_from_state(current: dict[str, Any]) -> str:
    value = (
        current.get("time")
        or current.get("current_time")
        or current.get("scene_time")
        or "02:40"
    )
    return str(value)


def _calendar_day_path(date: str) -> str:
    return f"calendar/days/{date}.yaml"


def _extra_runtime_paths_for_scene(session_id: str) -> list[str]:
    current = _read_state(session_id, "state/current_state.json", {}) or {}
    date = _current_date_from_state(current)

    candidates = [
        _calendar_day_path(date),
        "engine/calendar_day_runtime_rules.md",
        "engine/time_progression_runtime_rules.md",
    ]

    result: list[str] = []
    for path in candidates:
        if _repo_exists(path) and path not in result:
            result.append(path)
    return result


def _append_loaded_file(packet: dict[str, Any], path: str, content: str, limit: int = 22000) -> None:
    if not content:
        return

    required = packet.setdefault("required_files", [])
    if path not in required:
        required.append(path)

    manifest = packet.setdefault("required_file_manifest", [])
    if not any(isinstance(item, dict) and item.get("path") == path for item in manifest):
        manifest.append({
            "path": path,
            "exists": True,
            "source": "project",
            "size_chars": len(content),
            "parts_total": 1,
            "runtime_patch": "calendar_day_template_time_flow",
        })

    loaded = packet.setdefault("loaded_files", [])
    if not any(isinstance(item, dict) and item.get("path") == path for item in loaded):
        cut = _cut(content, limit)
        loaded.append({
            "path": path,
            "part_index": 0,
            "parts_total": 1,
            "content_chars_original": len(content),
            "content_chars_in_packet": len(cut),
            "truncated_in_packet": len(cut) < len(content),
            "content": cut,
        })


def _estimate_hint_block(current: dict[str, Any]) -> dict[str, Any]:
    return {
        "current_date": _current_date_from_state(current),
        "current_time": _current_time_from_state(current),
        "rule": "Время сцены = смысловая длительность действий, а не количество сообщений.",
        "must_before_header": [
            "Оценить, сколько минут реально заняли действия игрока + NPC + диалог + паузы + перемещение.",
            "Если несколько реплик, взглядов, пауз и действий — это уже несколько минут, не одна.",
            "Шапка следующей сцены должна брать новое время из этой оценки.",
        ],
        "typical_delta_minutes": {
            "instant_reaction": "0-1",
            "short_exchange_1_2_replicas": "1-2",
            "normal_dialogue_with_pauses": "3-7",
            "tense_argument_or_interrogation": "5-15",
            "walk_inside_house_or_small_base_area": "2-8",
            "walk_between_base_zones": "5-15",
            "eat_or_coffee": "10-25",
            "change_clothes_or_collect_items": "10-25",
            "medical_check": "10-40",
            "training_block": "20-90",
            "sleep_or_timeskip": "use explicit player request or next meaningful calendar beat",
        },
        "apply_turn_result_requirement": {
            "must_patch_current_state_time": True,
            "patch_fields": [
                "current_state_patch.time",
                "current_state_patch.last_time_advance_min",
                "current_state_patch.last_time_advance_reason",
            ],
            "do_not_count_technical_turns": True,
        },
    }


# Replace previous scene-packet route with enhanced one.
_remove_route("/api/v1/sessions/{session_id}/scene-packet")


@app.get("/api/v1/sessions/{session_id}/scene-packet", operation_id="getScenePacket")
def get_scene_packet(
    session_id: str,
    max_total_chars: int = 70000,
    per_file_chars: int = 14000,
    max_files: int = 24,
) -> dict[str, Any]:
    sid = _safe_session_id(session_id)

    packet = previous_runtime.get_scene_packet(
        sid,
        max_total_chars=max_total_chars,
        per_file_chars=per_file_chars,
        max_files=max_files,
    )

    current = _read_state(sid, "state/current_state.json", {}) or {}
    date = _current_date_from_state(current)
    day_path = _calendar_day_path(date)

    for path in _extra_runtime_paths_for_scene(sid):
        _append_loaded_file(packet, path, _read_text(path, sid))

    packet["calendar_day_runtime"] = {
        "mode": "current_day_file",
        "date": date,
        "path": day_path,
        "exists": _repo_exists(day_path),
        "rule": "Use only current day file for active scene. Future days are for explicit timeskip/calendar audit only.",
        "day_template_path": "calendar/days/_day_template.yaml",
    }

    packet["time_progression_runtime"] = _estimate_hint_block(current)

    hard_rules = packet.setdefault("hard_rules", [])
    for rule in [
        "Load current calendar day file before scene output.",
        "Use day active_characters, file links, goals, scene_general_info, timing_windows and scene_forbidden before NPC actions.",
        "Calendar defines world pressure and NPC timing; it does not write Akira's action for the player.",
        "Conditional arrivals require plausible travel/search time unless current_state already places the character nearby.",
        "Scene time must advance by semantic duration, not by one minute per turn.",
        "If player chooses sleep/rest/timeskip, continue to the next meaningful beat instead of asking what wakes Akira.",
        "After gameplay scene, save current_state.time and last_time_advance_min through applyTurnResult.",
    ]:
        if rule not in hard_rules:
            hard_rules.append(rule)

    packet["packet_version"] = "1206v2_scene_packet_v4_calendar_clean_story_rules"
    packet["runtime_version"] = app.version
    return packet


@app.get("/api/v1/sessions/{session_id}/calendar-day", operation_id="getCalendarDay")
def get_calendar_day(session_id: str, date: str | None = None) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    current = _read_state(sid, "state/current_state.json", {}) or {}
    day = date or _current_date_from_state(current)
    path = _calendar_day_path(str(day))
    content = _read_text(path, sid)
    if not content:
        raise HTTPException(status_code=404, detail=f"Calendar day not found: {path}")
    return {
        "success": True,
        "session_id": sid,
        "date": str(day),
        "path": path,
        "content_chars": len(content),
        "content": content,
    }


@app.get("/api/v1/calendar/day-template", operation_id="getCalendarDayTemplate")
def get_calendar_day_template() -> dict[str, Any]:
    path = "calendar/days/_day_template.yaml"
    content = _read_text(path)
    if not content:
        raise HTTPException(status_code=404, detail=f"Calendar template not found: {path}")
    return {
        "success": True,
        "path": path,
        "content_chars": len(content),
        "content": content,
    }


# Patch OpenAPI/Actions schema after previous runtime shim.
_old_openapi = app.openapi


def _calendar_day_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "success": {"type": "boolean"},
            "session_id": {"type": "string"},
            "date": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
    }


def _session_path_param() -> dict[str, Any]:
    try:
        return previous_runtime.header_hotfix._session_path_param()
    except Exception:
        return {"name": "session_id", "in": "path", "required": True, "schema": {"type": "string"}}


def _openapi_calendar_time_patch() -> dict[str, Any]:
    schema = _old_openapi()
    schema.setdefault("info", {})["version"] = app.version
    paths = schema.setdefault("paths", {})

    paths["/api/v1/sessions/{session_id}/calendar-day"] = {
        "get": {
            "operationId": "getCalendarDay",
            "summary": "Get current or requested calendar day file",
            "parameters": [
                _session_path_param(),
                {
                    "name": "date",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Optional date YYYY-MM-DD. Defaults to current_state date.",
                },
            ],
            "responses": {
                "200": {
                    "description": "Calendar day file",
                    "content": {"application/json": {"schema": _calendar_day_response_schema()}},
                }
            },
        }
    }

    paths["/api/v1/calendar/day-template"] = {
        "get": {
            "operationId": "getCalendarDayTemplate",
            "summary": "Get reusable calendar day YAML template",
            "responses": {
                "200": {
                    "description": "Calendar day template",
                    "content": {"application/json": {"schema": _calendar_day_response_schema()}},
                }
            },
        }
    }

    return schema


_remove_route("/openapi-actions.json")


@app.get("/openapi-actions.json", include_in_schema=False)
def openapi_actions() -> dict[str, Any]:
    return _openapi_calendar_time_patch()


app.openapi_schema = None
app.openapi = _openapi_calendar_time_patch  # type: ignore[method-assign]
