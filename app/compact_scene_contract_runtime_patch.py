"""Academy-style compact scene contract for Akira 1206 v2.

Purpose:
- Replace bulky turn-packet gameplay flow with one small scene_contract.
- Keep character energy/knowledge/forbidden rules visible without loading full files.
- Make /api/v2/.../turn-packet a compact compatibility alias, not a fat packet.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import Query

from app import compact as base

app = base.app

RUNTIME_VERSION = "0.3.149-academy-style-scene-contract-v1"
WORLD_ENERGY_DIGEST_FILE = "canon_lore/core/energy_runtime_digest.yaml"
CURRENT_STATE_FILE = "state/current_state.json"
CALENDAR_RUNTIME_FILE = "state/calendar_runtime.json"
RELATIONSHIPS_FILE = "state/relationships.json"
KNOWLEDGE_STATE_FILE = "state/knowledge_state.json"
SCENE_HISTORY_FILE = "state/scene_history.json"

# Make runtime summaries available through DATA after base.seed().
for _name in ["runtime", "scenes", "data", "canon_lore", "characters", "gpt"]:
    try:
        if _name not in base.SYNC_FROM_REPO:
            base.SYNC_FROM_REPO.append(_name)
    except Exception:
        pass

CHARACTER_FIELDS = (
    "active_character_ids", "active_characters",
    "nearby_character_ids", "nearby_characters",
    "speaking_character_ids", "speaking_characters",
    "observing_character_ids", "observing_characters",
    "present_character_ids", "present_characters",
    "scene_character_ids", "addressed_character_ids", "looked_at_character_ids",
    "pending_character_ids",
)

ID_ALIASES = {
    "акира": "akira", "akira": "akira",
    "джун": "jun", "jun": "jun",
    "эмма": "emma", "emma": "emma",
    "ирэй": "irey", "ирей": "irey", "irey": "irey",
    "рейден": "raiden", "рейдон": "raiden", "raiden": "raiden", "raiden_sterling": "raiden",
    "рэй": "ray", "рей": "ray", "ray": "ray",
    "хару": "haru", "haru": "haru",
}

SECTION_PRIORITY = [
    "id", "display_name", "purpose", "identity", "current_status", "scope",
    "character_core", "core_character", "core_motivation", "goal", "goals", "character_goal",
    "behavior_under_pressure", "behavior", "speech", "voice", "care_style", "command_style",
    "knowledge_limits", "stable_knows", "stable_does_not_know", "strict_unknowns", "inference_rules",
    "energy", "energy_behavior", "energy_and_combat", "energy_and_barrier", "abilities", "flow", "combat", "combat_behavior",
    "limitations", "limits", "forbidden", "scene_behavior_rules",
    "relationship_to_akira", "relationship_to_raiden", "relationship_to_emma", "relation_to_irey",
    "withholds_from_akira", "arrival_reaction_rule", "akira_distance_rule",
]

ENERGY_KEYS = ("energy", "энерг", "поток", "простран", "вода", "влага", "давлен", "холод", "воздух", "огонь", "тепло", "свет", "барьер")


def _remove_route(path: str, method: str | None = None) -> None:
    method_upper = method.upper() if method else None
    for route in list(app.router.routes):
        if getattr(route, "path", None) != path:
            continue
        methods = set(getattr(route, "methods", set()) or set())
        if method_upper is None or method_upper in methods:
            app.router.routes.remove(route)


def _safe_session_id(session_id: str) -> str:
    try:
        return base.safe_session_id(session_id)
    except Exception:
        cleaned = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
        return cleaned or "default"


def _trim(text: Any, limit: int = 600) -> str:
    value = str(text or "")
    value = value.replace("\r\n", "\n").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 17)].rstrip() + "\n... [truncated]"


def _compact_json(value: Any, *, max_chars: int = 650, max_items: int = 6, depth: int = 2) -> Any:
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
        return [_compact_json(item, max_chars=max_chars, max_items=max_items, depth=depth - 1) for item in value[:max_items]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        preferred = [
            "id", "status", "summary", "text", "current_date", "current_day_phase", "time_of_day",
            "current_location_id", "current_location_text", "current_scene_id", "scene_id",
            "active_characters", "active_character_ids", "nearby_characters", "nearby_character_ids",
            "known", "knows", "does_not_know", "strict_unknowns", "beliefs", "wrong_beliefs",
            "visible_state", "internal_state", "body_state", "hair_state", "current_outfit",
            "priority", "participants", "characters", "known_by", "source", "certainty",
        ]
        keys = [k for k in preferred if k in value] + [k for k in value.keys() if k not in preferred]
        for key in keys[:max_items]:
            result[str(key)] = _compact_json(value[key], max_chars=max_chars, max_items=max_items, depth=depth - 1)
        return result
    return _trim(str(value), max_chars)


def _read_text(path: str, session_id: str | None = None) -> str:
    # Prefer session override; fallback to project/DATA.
    if session_id:
        try:
            text = base.read_text(path, session_id=session_id)
            if isinstance(text, str) and text.strip():
                return text
        except Exception:
            pass
    try:
        text = base.read_text(path)
        return text if isinstance(text, str) else ""
    except Exception:
        return ""


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        value = base.read_json(path, session_id=session_id, default=default)
        return value if value is not None else default
    except Exception:
        return default


def _canonical_id(value: Any) -> str:
    raw = str(value or "").strip()
    key = raw.lower().replace("ё", "е")
    return ID_ALIASES.get(key, key)


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        cid = _canonical_id(value)
        if cid and cid not in result and cid not in {"none", "null", "unknown", "off"}:
            result.append(cid)
    return result


def _collect_ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return _unique(value)
    if isinstance(value, dict):
        raw: list[Any] = []
        for key, item in value.items():
            if isinstance(item, dict):
                raw.append(item.get("id") or item.get("character_id") or key)
            else:
                raw.append(key)
        return _unique(raw)
    if isinstance(value, str):
        return _unique([value])
    return []


def _scene_ids_from_state(current: dict[str, Any]) -> tuple[list[str], list[str]]:
    raw: list[str] = []
    active_raw: list[str] = []
    for field in CHARACTER_FIELDS:
        ids = _collect_ids(current.get(field))
        if not ids:
            continue
        raw.extend(ids)
        if field.startswith(("active", "present", "speaking")):
            active_raw.extend(ids)
    if not raw:
        raw = ["akira"]
    scene_ids = _unique(raw)
    if "akira" not in scene_ids:
        scene_ids.insert(0, "akira")
    # hard cap like Academy: full scene characters only, not all scheduled future ids.
    scene_ids = scene_ids[:6]
    active_ids = [cid for cid in _unique(active_raw or scene_ids) if cid in scene_ids]
    if "akira" not in active_ids:
        active_ids.insert(0, "akira")
    return active_ids, scene_ids


def _split_top_sections(text: str) -> dict[str, str]:
    lines = str(text or "").splitlines()
    starts: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if not line or line[0].isspace() or line.startswith("#") or ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key:
            starts.append((idx, key))
    result: dict[str, str] = {}
    for pos, (start, key) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        result[key] = "\n".join(lines[start:end]).strip()
    return result


def _section_excerpt(text: str, keys: list[str], *, limit: int = 900, max_sections: int = 5) -> str:
    sections = _split_top_sections(text)
    chunks: list[str] = []
    for key in keys:
        if key not in sections:
            continue
        lines = [ln.rstrip() for ln in sections[key].splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
        chunk = "\n".join(lines[:10])
        if chunk:
            chunks.append(chunk)
        if len(chunks) >= max_sections:
            break
    return _trim("\n\n".join(chunks), limit)


def _contains_energy(text: str) -> bool:
    low = str(text or "").lower().replace("ё", "е")
    return any(key in low for key in ENERGY_KEYS)


def _runtime_summary_for(session_id: str, cid: str) -> tuple[str, str]:
    path = f"runtime/characters/{cid}.yaml"
    text = _read_text(path, session_id)
    if text.strip():
        return path, _trim(text, 1050)

    # Fallback for not-yet-created summaries: section-aware compact extract from real card.
    char_path = f"characters/{cid}/character.yaml"
    char_text = _read_text(char_path, session_id)
    if not char_text.strip():
        main_text = _read_text(f"characters/{cid}/main.yaml", session_id)
        if main_text.strip():
            return f"characters/{cid}/main.yaml", _trim(main_text, 850)
        return char_path, ""
    excerpt = _section_excerpt(char_text, SECTION_PRIORITY, limit=1050, max_sections=7)
    return char_path, excerpt


def _static_knowledge_summary(session_id: str, cid: str) -> str:
    text = _read_text(f"characters/{cid}/knowledge.yaml", session_id)
    if not text.strip():
        return ""
    return _section_excerpt(
        text,
        ["stable_knows", "stable_does_not_know", "strict_unknowns", "start_assumptions", "inference_rules", "rules"],
        limit=520,
        max_sections=4,
    )


def _dynamic_knowledge_summary(session_id: str, cid: str) -> Any:
    per_char = _read_json(f"state/character_knowledge/{cid}.json", session_id, {})
    if isinstance(per_char, dict) and per_char:
        return _compact_json(per_char, max_chars=360, max_items=5, depth=2)
    knowledge_state = _read_json(KNOWLEDGE_STATE_FILE, session_id, {})
    if isinstance(knowledge_state, dict):
        for key in (cid, f"char_{cid}"):
            if isinstance(knowledge_state.get(key), dict):
                return _compact_json(knowledge_state[key], max_chars=360, max_items=5, depth=2)
        character_knowledge = knowledge_state.get("character_knowledge")
        if isinstance(character_knowledge, dict):
            value = character_knowledge.get(cid) or character_knowledge.get(f"char_{cid}")
            if isinstance(value, dict):
                return _compact_json(value, max_chars=360, max_items=5, depth=2)
    return {}


def _character_slice(session_id: str, scene_ids: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for cid in scene_ids[:6]:
        source_path, runtime_summary = _runtime_summary_for(session_id, cid)
        static_knowledge = _static_knowledge_summary(session_id, cid)
        char_text = _read_text(f"characters/{cid}/character.yaml", session_id)
        energy_hint = _section_excerpt(
            char_text,
            ["energy", "energy_behavior", "energy_and_combat", "energy_and_barrier", "abilities", "flow"],
            limit=420,
            max_sections=2,
        )
        forbidden_hint = _section_excerpt(char_text, ["forbidden"], limit=260, max_sections=1)
        result[cid] = {
            "id": cid,
            "source": source_path,
            "runtime_summary": runtime_summary,
            "energy_hint": energy_hint,
            "energy_loaded": bool(_contains_energy(runtime_summary) or _contains_energy(energy_hint)),
            "static_knowledge": static_knowledge,
            "dynamic_knowledge": _dynamic_knowledge_summary(session_id, cid),
            "forbidden_hint": forbidden_hint,
            "use_rule": "Use this compact slice as the primary source for this turn; do not load full character files in gameplay.",
        }
    return result


def _current_frame(session_id: str, current: dict[str, Any], active_ids: list[str], scene_ids: list[str]) -> dict[str, Any]:
    return {
        "current_scene_id": current.get("current_scene_id") or current.get("scene_id"),
        "current_date": current.get("current_date") or current.get("date"),
        "current_day_phase": current.get("current_day_phase") or current.get("time_of_day"),
        "current_location_id": current.get("current_location_id") or current.get("location_id"),
        "current_location_text": current.get("current_location_text") or current.get("location_text"),
        "weather": _compact_json(current.get("weather", {}), max_chars=160, max_items=4, depth=2),
        "pov_character_id": current.get("pov_character_id", "akira"),
        "akira_state": _compact_json(current.get("akira_state", {}), max_chars=180, max_items=6, depth=2),
        "current_outfit": _trim(current.get("current_outfit"), 160),
        "visible_inventory": _compact_json(current.get("visible_inventory", []), max_chars=120, max_items=6, depth=1),
        "nearby_items": _compact_json(current.get("nearby_items", []), max_chars=120, max_items=6, depth=1),
        "active_character_ids": active_ids,
        "scene_character_ids": scene_ids,
        "last_player_input": _trim(current.get("last_player_input"), 220),
    }


def _calendar_slice(session_id: str, current: dict[str, Any]) -> dict[str, Any]:
    calendar = _read_json(CALENDAR_RUNTIME_FILE, session_id, {})
    if not isinstance(calendar, dict):
        calendar = {}
    return {
        "current_date": calendar.get("current_date") or current.get("current_date"),
        "current_day_phase": calendar.get("current_day_phase") or current.get("current_day_phase") or current.get("time_of_day"),
        "current_beat_id": calendar.get("current_beat_id") or current.get("current_beat_id"),
        "pending_events": _compact_json(calendar.get("pending_events", []), max_chars=180, max_items=3, depth=2),
        "selection_rule": "Use only current phase/beat unless the player explicitly skips time or asks for diagnostic audit.",
    }


def _relationship_slice(session_id: str, scene_ids: list[str]) -> Any:
    data = _read_json(RELATIONSHIPS_FILE, session_id, {})
    if not isinstance(data, dict):
        return {}
    focused: dict[str, Any] = {}
    focus = set(scene_ids)
    pairs = data.get("pairs") if isinstance(data.get("pairs"), dict) else data
    for key, value in list(pairs.items())[:80] if isinstance(pairs, dict) else []:
        text_key = str(key).lower()
        if any(cid in text_key for cid in focus):
            focused[str(key)] = _compact_json(value, max_chars=220, max_items=5, depth=2)
        if len(focused) >= 5:
            break
    return focused


def _knowledge_slice(session_id: str, scene_ids: list[str]) -> dict[str, Any]:
    return {cid: _dynamic_knowledge_summary(session_id, cid) for cid in scene_ids if _dynamic_knowledge_summary(session_id, cid)}


def _energy_slice(session_id: str, character_slice: dict[str, Any]) -> dict[str, Any]:
    world = _read_text(WORLD_ENERGY_DIGEST_FILE, session_id)
    if not world.strip():
        world = "energy_runtime_digest: energy is active for kairos/humans; use character slices for type/limits; do not invent."
    return {
        "world_digest": _trim(world, 700),
        "active_character_energy": {
            cid: {
                "loaded": bool(data.get("energy_loaded")),
                "hint": _trim(data.get("energy_hint") or data.get("runtime_summary"), 260),
            }
            for cid, data in character_slice.items()
        },
        "use_rules": [
            "Energy is not mandatory every turn, but it must be available under threat, pursuit, restraint, defense or combat.",
            "Describe energy as physical consequence, not decorative magic.",
            "If energy_loaded=false for an active energy-capable character, stop gameplay and run getContextAudit.",
        ],
    }


def _recent_history(session_id: str) -> list[dict[str, Any]]:
    history = _read_json(SCENE_HISTORY_FILE, session_id, [])
    entries = history if isinstance(history, list) else history.get("entries", []) if isinstance(history, dict) else []
    result: list[dict[str, Any]] = []
    for entry in entries[-1:]:
        if not isinstance(entry, dict):
            continue
        result.append({
            "scene_id": entry.get("scene_id"),
            "status": entry.get("status"),
            "player_input": _trim(entry.get("player_input"), 180),
            "scene_text": _trim(entry.get("visible_scene_text") or entry.get("scene_text"), 520),
        })
    return result


def build_scene_contract_response(session_id: str, *, max_total_chars: int = 9000, include_debug: bool = False) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.seed()
    base.ensure_session(sid)
    current = _read_json(CURRENT_STATE_FILE, sid, {})
    if not isinstance(current, dict):
        current = {}
    active_ids, scene_ids = _scene_ids_from_state(current)
    char_slice = _character_slice(sid, scene_ids)
    contract: dict[str, Any] = {
        "version": "scene_contract_1206_academy_style_v1",
        "current_frame": _current_frame(sid, current, active_ids, scene_ids),
        "calendar_slice": _calendar_slice(sid, current),
        "character_slice": char_slice,
        "relationship_slice": _relationship_slice(sid, scene_ids),
        "knowledge_slice": _knowledge_slice(sid, scene_ids),
        "energy_slice": _energy_slice(sid, char_slice),
        "recent_scene_history": _recent_history(sid),
        "npc_knowledge_boundary": {
            "rule": "Packet/global/current_state facts are not NPC knowledge by default.",
            "npc_may_state_as_fact_only_from": ["own static/dynamic knowledge", "visible observation", "heard dialogue"],
            "npc_must_not_state_as_fact_from": ["Akira card", "hidden/past/canon", "engine state", "instructions"],
        },
        "scene_assembly_gate": {
            "must_have": ["current_frame", "character_slice", "knowledge_slice", "energy_slice"],
            "failure_line": "API-контекст не получен: scene_contract недоступен или неполный. Сцену продолжить нельзя.",
        },
        "render_rules": [
            "Write gameplay only from scene_contract.",
            "Do not call getFastRenderContext/getRequiredFilesChunk during gameplay.",
            "NPC reactions must use character_slice + knowledge_slice + relationship_slice + visible observations.",
            "Do not write significant Akira speech unless player wrote it outside parentheses.",
            "After meaningful scene changes, call applyTurnResult.",
        ],
    }
    audit = {
        "scene_character_ids": scene_ids,
        "active_character_ids": active_ids,
        "energy_loaded_by_character": {cid: bool(data.get("energy_loaded")) for cid, data in char_slice.items()},
        "runtime_sources": {cid: data.get("source") for cid, data in char_slice.items()},
        "contract_chars_estimate": len(json.dumps(contract, ensure_ascii=False)),
        "max_total_chars_requested": max_total_chars,
    }
    response = {
        "success": True,
        "session_id": sid,
        "runtime_version": RUNTIME_VERSION,
        "mode": "scene_contract_compact",
        "created_at": datetime.utcnow().isoformat(),
        "active_character_ids": active_ids,
        "scene_character_ids": scene_ids,
        "scene_contract": contract,
        "context_audit": audit if include_debug else {
            "energy_loaded_by_character": audit["energy_loaded_by_character"],
            "contract_chars_estimate": audit["contract_chars_estimate"],
        },
    }
    # Last safety cap: if JSON still grows too large, cut history then per-character summaries.
    estimated = len(json.dumps(response, ensure_ascii=False))
    if estimated > int(max_total_chars or 9000):
        contract["recent_scene_history"] = []
        for data in contract.get("character_slice", {}).values():
            if isinstance(data, dict):
                data["runtime_summary"] = _trim(data.get("runtime_summary"), 620)
                data["static_knowledge"] = _trim(data.get("static_knowledge"), 320)
                data["dynamic_knowledge"] = _compact_json(data.get("dynamic_knowledge"), max_chars=220, max_items=3, depth=1)
                data["forbidden_hint"] = _trim(data.get("forbidden_hint"), 180)
        response["context_audit"]["compacted_after_estimate"] = estimated
    return response


_remove_route("/api/v2/sessions/{session_id}/scene-contract", "GET")
_remove_route("/api/v2/sessions/{session_id}/turn-packet", "GET")
_remove_route("/api/v2/sessions/{session_id}/debug/context-audit", "GET")


@app.get("/api/v2/sessions/{session_id}/scene-contract", operation_id="getSceneContract")
def get_scene_contract(
    session_id: str,
    max_total_chars: int = Query(default=9000, ge=6000, le=14000),
    include_debug: bool = Query(default=False),
) -> dict[str, Any]:
    return build_scene_contract_response(session_id, max_total_chars=max_total_chars, include_debug=include_debug)


@app.get("/api/v2/sessions/{session_id}/turn-packet", operation_id="getTurnPacket")
def get_turn_packet_compat(
    session_id: str,
    max_total_chars: int = Query(default=9000, ge=6000, le=14000),
    include_debug: bool = Query(default=False),
) -> dict[str, Any]:
    # Backward-compatible compact alias. It intentionally returns scene_contract, not a fat character_packets dump.
    response = build_scene_contract_response(session_id, max_total_chars=max_total_chars, include_debug=include_debug)
    response["mode"] = "turn_packet_compat_returns_scene_contract"
    return response


@app.get("/api/v2/sessions/{session_id}/debug/context-audit", operation_id="getContextAudit")
def get_context_audit(
    session_id: str,
    max_total_chars: int = Query(default=12000, ge=7000, le=18000),
) -> dict[str, Any]:
    response = build_scene_contract_response(session_id, max_total_chars=max_total_chars, include_debug=True)
    contract = response.get("scene_contract", {}) if isinstance(response.get("scene_contract"), dict) else {}
    chars = contract.get("character_slice", {}) if isinstance(contract.get("character_slice"), dict) else {}
    return {
        "success": True,
        "session_id": response.get("session_id"),
        "runtime_version": RUNTIME_VERSION,
        "mode": "context_audit_scene_contract_compact",
        "active_character_ids": response.get("active_character_ids"),
        "scene_character_ids": response.get("scene_character_ids"),
        "energy_loaded_by_character": {cid: bool(data.get("energy_loaded")) for cid, data in chars.items() if isinstance(data, dict)},
        "runtime_sources": {cid: data.get("source") for cid, data in chars.items() if isinstance(data, dict)},
        "has_static_knowledge": {cid: bool(data.get("static_knowledge")) for cid, data in chars.items() if isinstance(data, dict)},
        "contract_chars_estimate": response.get("context_audit", {}).get("contract_chars_estimate"),
        "instructions": [
            "Read-only audit. Do not continue scene from this endpoint.",
            "If an active/nearby character has energy_loaded=false, runtime summary or character energy section is missing.",
        ],
    }


try:
    app.version = RUNTIME_VERSION
except Exception:
    pass
