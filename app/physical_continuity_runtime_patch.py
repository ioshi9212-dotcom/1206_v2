"""Runtime physical continuity patch v1.

Fixes the case where a gameplay scene is written to scene_history, but the model
returned no explicit current_state_changes / inventory_changes. In that case the
next turn-contract used stale current_state, while the visible scene had already
moved on.

This patch is intentionally conservative:
- it always stores a compact state/physical_continuity_state.json from the visible scene;
- it syncs current_state/inventory_state only when explicit state sections are missing
  or when turn-contract detects scene_history is newer than current_state;
- it keeps visible development diagnostics in state/last_apply_result.json, not inside
  the rendered scene body.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

import app.response_size_guard_runtime_patch as size_guard
import app.state_persistence_runtime_patch as persistence
import app.compact_context_patch as ccp
from app import compact as base
from app.start_scene_runtime_patch import app

APPLY_TURN_RESULT_PATH = ccp.APPLY_TURN_RESULT_PATH
TURN_CONTRACT_PATH = size_guard.TURN_CONTRACT_PATH
CONTEXT_PATH = size_guard.CONTEXT_PATH

PHYSICAL_CONTINUITY_STATE_FILE = "state/physical_continuity_state.json"
LAST_APPLY_RESULT_FILE = persistence.LAST_APPLY_RESULT_FILE
SCENE_HISTORY_FILE = persistence.SCENE_HISTORY_FILE
CALENDAR_RUNTIME_FILE = persistence.CALENDAR_RUNTIME_FILE
WORLD_INTEGRITY_STATE_FILE = persistence.WORLD_INTEGRITY_STATE_FILE


class PhysicalContinuityRepairResponse(BaseModel):
    status: str
    session_id: str
    changed_files: list[str] = Field(default_factory=list)
    reason: str = ""
    physical_continuity_state: dict[str, Any] = Field(default_factory=dict)


def _now() -> str:
    return datetime.utcnow().isoformat()


def _remove_route(path: str, method: str) -> None:
    app.router.routes = [
        route for route in app.router.routes
        if not (
            getattr(route, "path", None) == path
            and method in (getattr(route, "methods", set()) or set())
        )
    ]


def _history_entries(history: Any) -> list[dict[str, Any]]:
    if isinstance(history, list):
        return [item for item in history if isinstance(item, dict)]
    if not isinstance(history, dict):
        return []
    for key in ("entries", "scenes", "items", "history"):
        value = history.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    data = history.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _latest_scene_entry(session_id: str) -> tuple[dict[str, Any] | None, int]:
    history = base.read_json(SCENE_HISTORY_FILE, session_id, default=[]) or []
    entries = _history_entries(history)
    if not entries:
        return None, 0
    return entries[-1], len(entries)


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", str(line or "").strip())


def _after_colon_or_marker(line: str, marker: str) -> str:
    text = _clean_line(line)
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    return text.strip(" -—")


def _first_header_block(scene_text: str) -> list[str]:
    lines: list[str] = []
    for raw in str(scene_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("━") and lines:
            break
        lines.append(line)
    return lines


def _location_id_from_text(location: str, fallback: str | None = None) -> str | None:
    text = location.lower().replace("ё", "е")
    if "лестниц" in text:
        return "jun_house_stairs"
    if "комнат" in text:
        return "jun_house_akira_room"
    if "крыльц" in text:
        return "jun_house_porch"
    if "дорог" in text or "трасс" in text:
        return "road_near_jun_house"
    if "лес" in text or "склон" in text:
        return "forest_slope_near_jun_house"
    return fallback


def _extract_time_and_location(line: str) -> tuple[str | None, str | None]:
    text = _clean_line(line)
    if "🕒" not in text:
        return None, None
    after_time = text.split("🕒", 1)[1].strip()
    location = None
    if "📍" in after_time:
        before_loc, after_loc = after_time.split("📍", 1)
        location = after_loc.strip()
    else:
        before_loc = after_time
    # Typical: "поздняя ночь · 📍 дом..."
    time_part = before_loc.split("·", 1)[0].strip(" ·")
    return time_part or None, location or None


def _items_from_raw(raw: str) -> list[str]:
    if not raw:
        return []
    text = raw
    for prefix in ("рядом:", "рядом", "при себе:", "при себе", "на столе"):
        if text.lower().replace("ё", "е").startswith(prefix):
            text = text[len(prefix):].strip(" :—-;,")
    # Keep common compound item names stable before splitting on "и".
    text = text.replace("Рэй / Восточный сектор", "Рэй / Восточный сектор")
    text = re.sub(r"\s+и\s+", ", ", text)
    parts = re.split(r"[;,]\s*", text)
    result: list[str] = []
    for part in parts:
        item = _clean_line(part).strip(" .")
        if not item:
            continue
        if len(item) > 160:
            item = item[:157].rstrip() + "..."
        if item not in result:
            result.append(item)
    return result


def _item_key(item: str) -> str:
    text = item.lower().replace("ё", "е")
    if "записк" in text:
        return "note_ray_east_sector"
    if "документ" in text:
        return "cover_documents_agatsumi"
    if "блокнот" in text:
        return "small_notebook"
    if "ножниц" in text:
        return "scissors"
    if "ботин" in text:
        return "boots"
    digest = hashlib.sha1(item.encode("utf-8")).hexdigest()[:10]
    return f"item_{digest}"


def _merge_unique(existing: Any, items: list[str]) -> list[str]:
    result: list[str] = []
    if isinstance(existing, list):
        result.extend(str(item) for item in existing if str(item).strip())
    for item in items:
        item = str(item or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _scene_text_from_entry(entry: dict[str, Any] | None) -> str:
    if not isinstance(entry, dict):
        return ""
    for key in ("visible_scene_text", "final_scene_text", "scene_text"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _derive_physical(scene_text: str, entry: dict[str, Any] | None = None, entries_total: int | None = None, *, reason: str = "") -> dict[str, Any]:
    entry = entry or {}
    header = _first_header_block(scene_text)
    physical: dict[str, Any] = {
        "schema": "physical_continuity_state_v1",
        "updated_at": _now(),
        "source": "visible_scene_text",
        "source_reason": reason,
        "source_entry_id": entry.get("id") or entry.get("scene_id"),
        "source_created_at": entry.get("created_at") or entry.get("time"),
        "scene_history_entries": entries_total,
        "raw_header_lines": header[:12],
    }

    inventory_raw = ""
    nearby_raw = ""

    for line in header:
        if "🕒" in line:
            time_part, location = _extract_time_and_location(line)
            if time_part:
                physical["time_of_day"] = time_part
                physical["current_day_phase"] = time_part
            if location:
                physical["current_location_text"] = location
                physical["current_location_id"] = _location_id_from_text(location, entry.get("location_id"))
        elif line.startswith("⚙️"):
            physical["active_scene_state"] = _after_colon_or_marker(line, "⚙️")
        elif line.startswith("✦") and "Что можно" not in line:
            physical.setdefault("akira_visible_state", _after_colon_or_marker(line, "✦"))
        elif line.startswith("🧥"):
            physical["current_outfit"] = _after_colon_or_marker(line, "🧥")
        elif line.startswith("◈"):
            marker_text = _after_colon_or_marker(line, "◈")
            marker_lower = marker_text.lower().replace("ё", "е")
            looks_held = any(word in marker_lower for word in ["при себе", "карман", "за пояс", "в руке", "у шеи", "ножниц"])
            looks_nearby = any(word in marker_lower for word in ["рядом", "на столе", "у стены", "окно", "дверь", "лестниц"])
            if looks_held or not looks_nearby:
                inventory_raw = marker_text
            else:
                nearby_raw = marker_text

    if "current_location_text" not in physical and entry.get("location_text"):
        physical["current_location_text"] = entry.get("location_text")
        physical["current_location_id"] = _location_id_from_text(str(entry.get("location_text")), entry.get("location_id"))
    if "time_of_day" not in physical:
        time_value = entry.get("current_time") or entry.get("time")
        if time_value:
            physical["time_of_day"] = str(time_value)

    visible_inventory = _items_from_raw(inventory_raw)
    nearby_items = _items_from_raw(nearby_raw)
    if inventory_raw:
        physical["visible_inventory_raw"] = inventory_raw
    if nearby_raw:
        physical["nearby_items_raw"] = nearby_raw
    if visible_inventory:
        physical["visible_inventory"] = visible_inventory
    if nearby_items:
        physical["nearby_items"] = nearby_items

    for field, target in [
        ("current_date", "current_date"),
        ("current_time", "current_time"),
        ("player_input", "last_player_input"),
        ("active_characters", "active_characters"),
        ("nearby_characters", "nearby_characters"),
    ]:
        value = entry.get(field)
        if value not in (None, "", []):
            physical[target] = value

    return physical


def _write_physical_state(session_id: str, physical: dict[str, Any], dry_run: bool) -> bool:
    old = base.read_json(PHYSICAL_CONTINUITY_STATE_FILE, session_id, default={}) or {}
    if json.dumps(old, ensure_ascii=False, sort_keys=True) == json.dumps(physical, ensure_ascii=False, sort_keys=True):
        return False
    if not dry_run:
        base.write_json(PHYSICAL_CONTINUITY_STATE_FILE, physical, session_id)
    return True


def _sync_current_and_inventory(session_id: str, physical: dict[str, Any], *, dry_run: bool, allow_current_overwrite: bool, reason: str) -> list[str]:
    changed: list[str] = []

    if _write_physical_state(session_id, physical, dry_run):
        changed.append(PHYSICAL_CONTINUITY_STATE_FILE)

    current = base.read_json("state/current_state.json", session_id, default={}) or {}
    current_old = json.dumps(current, ensure_ascii=False, sort_keys=True)

    if allow_current_overwrite:
        if physical.get("current_location_text"):
            current["current_location_text"] = physical["current_location_text"]
        if physical.get("current_location_id"):
            current["current_location_id"] = physical["current_location_id"]
            current["location_id"] = physical["current_location_id"]
        if physical.get("time_of_day"):
            current["time_of_day"] = physical["time_of_day"]
            current["current_day_phase"] = physical.get("current_day_phase") or physical["time_of_day"]
        if physical.get("current_outfit"):
            current["current_outfit"] = physical["current_outfit"]
        if physical.get("visible_inventory"):
            current["visible_inventory"] = _merge_unique(current.get("visible_inventory", []), list(physical["visible_inventory"]))
        if physical.get("nearby_items"):
            current["nearby_items"] = _merge_unique(current.get("nearby_items", []), list(physical["nearby_items"]))
        if physical.get("active_characters") and not current.get("active_characters"):
            current["active_characters"] = physical["active_characters"]
        if physical.get("nearby_characters") and not current.get("nearby_characters"):
            current["nearby_characters"] = physical["nearby_characters"]
        if physical.get("last_player_input"):
            current["last_player_input"] = physical["last_player_input"]
        if physical.get("active_scene_state"):
            current["current_scene_goal"] = physical["active_scene_state"]
        if physical.get("akira_visible_state"):
            akira_state = current.setdefault("akira_state", {})
            if isinstance(akira_state, dict):
                akira_state["visible_state"] = physical["akira_visible_state"]
        entries_total = physical.get("scene_history_entries")
        if isinstance(entries_total, int) and entries_total > 0:
            try:
                current["scene_count"] = max(int(current.get("scene_count") or 0), entries_total)
            except Exception:
                current["scene_count"] = entries_total
        current["last_scene_status"] = "AWAITING_PLAYER_ACTION"
        current["physical_continuity_source"] = "scene_history_visible_scene_text"
        current["physical_continuity_reason"] = reason
        current["physical_continuity_entry_id"] = physical.get("source_entry_id")
        current["updated_at"] = _now()

    if json.dumps(current, ensure_ascii=False, sort_keys=True) != current_old:
        if not dry_run:
            base.write_json("state/current_state.json", current, session_id)
        changed.append("state/current_state.json")

    # Keep inventory_state usable even if the model only wrote current_state.visible_inventory.
    inventory = base.read_json("state/inventory_state.json", session_id, default={}) or {}
    inv_old = json.dumps(inventory, ensure_ascii=False, sort_keys=True)
    inventory.setdefault("schema", "inventory_state_v1")
    inventory.setdefault("project", "akira-main-1206")
    items = inventory.setdefault("items", {})
    if not isinstance(items, dict):
        items = {}
        inventory["items"] = items
    akira_inv = inventory.setdefault("akira", {})
    if not isinstance(akira_inv, dict):
        akira_inv = {}
        inventory["akira"] = akira_inv
    visible_items = list(current.get("visible_inventory") or physical.get("visible_inventory") or [])
    if visible_items:
        akira_inv["visible_inventory"] = _merge_unique(akira_inv.get("visible_inventory", []), [str(x) for x in visible_items])
        akira_inv.setdefault("nearby_items", [])
        akira_inv.setdefault("issued_items", [])
        for item in visible_items:
            name = str(item).strip()
            if not name:
                continue
            items.setdefault(_item_key(name), {"name": name, "holder": "akira", "visible": True})
    inventory.setdefault("notes", [])
    inventory["last_physical_sync"] = {"updated_at": _now(), "reason": reason, "source_entry_id": physical.get("source_entry_id")}

    if json.dumps(inventory, ensure_ascii=False, sort_keys=True) != inv_old:
        if not dry_run:
            base.write_json("state/inventory_state.json", inventory, session_id)
        changed.append("state/inventory_state.json")

    return changed


def _sync_from_scene_text(session_id: str, scene_text: str, *, entry: dict[str, Any] | None = None, entries_total: int | None = None, dry_run: bool = False, allow_current_overwrite: bool = True, reason: str = "manual") -> list[str]:
    if not isinstance(scene_text, str) or not scene_text.strip():
        return []
    physical = _derive_physical(scene_text.strip(), entry=entry, entries_total=entries_total, reason=reason)
    return _sync_current_and_inventory(session_id, physical, dry_run=dry_run, allow_current_overwrite=allow_current_overwrite, reason=reason)


def _repair_from_latest_scene(session_id: str, *, dry_run: bool = False, force: bool = False, reason: str = "repair_latest_scene") -> list[str]:
    latest, count = _latest_scene_entry(session_id)
    if not latest:
        return []
    scene_text = _scene_text_from_entry(latest)
    if not scene_text:
        return []
    current = base.read_json("state/current_state.json", session_id, default={}) or {}
    latest_id = latest.get("id") or latest.get("scene_id")
    already_synced = current.get("physical_continuity_entry_id") == latest_id
    current_count = int(current.get("scene_count") or 0) if str(current.get("scene_count") or "0").isdigit() else 0
    stale = force or not already_synced or current_count < count
    if not stale:
        return []
    return _sync_from_scene_text(session_id, scene_text, entry=latest, entries_total=count, dry_run=dry_run, allow_current_overwrite=True, reason=reason)


def _payload_has_state_sections(payload: dict[str, Any]) -> bool:
    summary = persistence.section_summary(payload)
    return any(summary.get(key) for key in [
        "current_state_changes",
        "inventory_changes",
        "story_lines_changes",
        "calendar_runtime_changes",
        "future_locks_changes",
    ])


_remove_route(APPLY_TURN_RESULT_PATH, "POST")
_remove_route(TURN_CONTRACT_PATH, "GET")


@app.post(APPLY_TURN_RESULT_PATH, response_model=ccp.ApplyTurnResultWithVisibleSceneResponse, operation_id="applyTurnResult")
def apply_turn_result_physical_continuity(session_id: str, request: ccp.ApplyTurnResultWithVisibleSceneRequest = ccp.ApplyTurnResultWithVisibleSceneRequest()):
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    source, payload = persistence._payload_from_request_or_turn_file(sid, request)
    changed: list[str] = []

    if persistence.apply_relationship_changes_robust(sid, payload, request.dry_run):
        changed.append("state/relationships.json")

    for path, names in list(base.STATE_SECTION_MAP) + [(CALENDAR_RUNTIME_FILE, ["calendar_runtime_changes", "calendar_runtime", "calendar_changes"]), (PHYSICAL_CONTINUITY_STATE_FILE, ["physical_continuity_changes", "physical_continuity_state"] )]:
        if persistence.apply_json_section_robust(sid, payload, path, names, request.dry_run):
            if path == "state/knowledge_state.json":
                changed.extend(getattr(base, "LAST_KNOWLEDGE_CHANGED_FILES", []) or [path])
            else:
                changed.append(path)

    scene_text = persistence.extract_scene_text(request, payload)
    explicit_state = _payload_has_state_sections(payload)
    if scene_text:
        physical_changed = _sync_from_scene_text(
            sid,
            scene_text,
            entry=None,
            entries_total=None,
            dry_run=request.dry_run,
            allow_current_overwrite=not explicit_state,
            reason="apply_turn_result_visible_scene_fallback" if not explicit_state else "apply_turn_result_visible_scene_observed",
        )
        changed.extend(physical_changed)

    changed = list(dict.fromkeys(changed))
    if persistence.append_scene_history(sid, payload, scene_text, changed, request.dry_run):
        changed.append(SCENE_HISTORY_FILE)

    # Once the history entry exists, stamp physical_continuity_state with the real scene_history id.
    if scene_text and not request.dry_run:
        changed.extend(_repair_from_latest_scene(sid, dry_run=False, force=True, reason="apply_turn_result_after_history_write"))

    changed = list(dict.fromkeys(changed))
    if not request.dry_run and persistence.write_world_integrity_state(sid, changed):
        changed.append(WORLD_INTEGRITY_STATE_FILE)

    sections = persistence.section_summary(payload)
    last = {
        "status": "applied" if changed else "no_changes_detected",
        "session_id": sid,
        "source": source,
        "dry_run": request.dry_run,
        "changed_files": changed,
        "payload_sections_present": sections,
        "scene_history_written": SCENE_HISTORY_FILE in changed,
        "physical_continuity_written": PHYSICAL_CONTINUITY_STATE_FILE in changed,
        "current_state_written": "state/current_state.json" in changed,
        "inventory_state_written": "state/inventory_state.json" in changed,
        "note": "If no explicit state sections were present, physical continuity was derived from visible_scene_text.",
    }
    if not request.dry_run:
        base.write_json(LAST_APPLY_RESULT_FILE, last, sid)
        if LAST_APPLY_RESULT_FILE not in changed:
            changed.append(LAST_APPLY_RESULT_FILE)

    return ccp.ApplyTurnResultWithVisibleSceneResponse(
        status="applied" if changed else "no_changes_detected",
        session_id=sid,
        source=source,
        dry_run=request.dry_run,
        changed_files=list(dict.fromkeys(changed)),
        visible_scene_text=scene_text or request.visible_scene_text,
        final_scene_text=scene_text or request.visible_scene_text,
        render_packet_received=isinstance(request.render_packet, dict),
    )


@app.get(TURN_CONTRACT_PATH, response_model=size_guard.TurnContractWithPromptPreview, operation_id="getSessionTurnContract")
def get_session_turn_contract_physical_continuity(session_id: str) -> size_guard.TurnContractWithPromptPreview:
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    # Development-friendly self-heal: if scene_history is ahead, make the compact contract match the latest visible frame.
    _repair_from_latest_scene(sid, dry_run=False, force=False, reason="turn_contract_self_heal_from_scene_history")
    return size_guard.get_session_turn_contract_size_guard(sid)


@app.post("/api/v1/sessions/{session_id}/repair/physical-continuity", response_model=PhysicalContinuityRepairResponse, operation_id="repairPhysicalContinuity")
def repair_physical_continuity(session_id: str, dry_run: bool = False, force: bool = True) -> PhysicalContinuityRepairResponse:
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    changed = _repair_from_latest_scene(sid, dry_run=dry_run, force=force, reason="manual_repair_physical_continuity")
    state = base.read_json(PHYSICAL_CONTINUITY_STATE_FILE, sid, default={}) or {}
    return PhysicalContinuityRepairResponse(
        status="repaired" if changed else "no_changes_detected",
        session_id=sid,
        changed_files=changed,
        reason="latest scene_history visible_scene_text -> current_state/inventory_state",
        physical_continuity_state=state,
    )


app.version = "0.3.119-physical-continuity-v1"
