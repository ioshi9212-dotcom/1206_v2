"""Section-aware turn packet gateway for Akira 1206 v2.

This endpoint makes GPT consume one prepared gameplay packet instead of raw,
head-cut files. It reads static character files and runtime state server-side,
then returns compact character packets with energy/forbidden/limitations intact.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import Query

from app import compact as base

app = base.app

CURRENT_STATE_FILE = "state/current_state.json"
SCENE_HISTORY_FILE = "state/scene_history.json"
CALENDAR_RUNTIME_FILE = "state/calendar_runtime.json"
RELATIONSHIPS_FILE = "state/relationships.json"
WORLD_ENERGY_DIGEST_FILE = "canon_lore/core/energy_runtime_digest.yaml"

CHARACTER_FIELDS = (
    "active_character_ids",
    "active_characters",
    "nearby_character_ids",
    "nearby_characters",
    "speaking_character_ids",
    "speaking_characters",
    "observing_character_ids",
    "observing_characters",
    "present_character_ids",
    "present_characters",
    "scene_character_ids",
    "pending_character_ids",
    "scheduled_character_ids",
    "conditional_character_ids",
)

CHARACTER_TOP_SECTIONS = {
    "id",
    "display_name",
    "file_type",
    "version",
    "identity",
    "current_status",
    "character_scope_rule",
    "core_motivation",
    "goal",
    "goals",
    "motivation",
    "behavior_under_pressure",
    "touch_and_control",
    "if_irey_understands_amnesia",
    "knowledge_limits",
    "body_recovery",
    "energy",
    "abilities",
    "ability",
    "flow",
    "combat",
    "combat_use",
    "limitations",
    "limits",
    "forbidden",
    "rules",
    "voice",
    "speech",
    "scene_rules",
    "writer_rule",
}

KNOWLEDGE_TOP_SECTIONS = {
    "id",
    "display_name",
    "file_type",
    "version",
    "purpose",
    "stable_knows",
    "stable_does_not_know",
    "strict_unknowns",
    "start_assumptions",
    "ability_detection_rules",
    "ring_knowledge",
    "echo_observations",
    "disclosure_rules",
    "stable_hides_from",
    "stable_misbeliefs",
    "rules",
}

ENERGY_KEYWORDS = (
    "energy",
    "энерг",
    "способн",
    "поток",
    "вода",
    "влага",
    "давлен",
    "простран",
    "холод",
    "воздух",
    "огонь",
    "тепло",
    "свет",
    "подавлен",
)

ID_ALIASES = {
    "рей": "ray",
    "rey": "ray",
    "ray": "ray",
    "рэй": "ray",
    "рейден": "raiden",
    "рейдон": "raiden",
    "raiden_sterling": "raiden",
    "raiden": "raiden",
    "ирэй": "irey",
    "ирей": "irey",
    "irey": "irey",
    "эмма": "emma",
    "emma": "emma",
    "джун": "jun",
    "jun": "jun",
    "акира": "akira",
    "akira": "akira",
}


class PacketBudget:
    def __init__(self, max_chars: int) -> None:
        self.max_chars = max(12000, min(int(max_chars or 22000), 42000))
        self.used = 0
        self.truncated = False

    def take(self, text: str, limit: int) -> str:
        text = str(text or "")
        remaining = self.max_chars - self.used
        if remaining <= 0:
            self.truncated = True
            return ""
        limit = max(600, min(int(limit or 2500), remaining))
        if len(text) <= limit:
            self.used += len(text)
            return text
        cut = text[: max(0, limit - 120)].rstrip() + "\n... [section truncated]"
        self.used += len(cut)
        self.truncated = True
        return cut


def _safe_session_id(session_id: str) -> str:
    try:
        return base.safe_session_id(session_id)
    except Exception:
        safe = "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in "-_")
        return safe or "default"


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default) or default
    except Exception:
        return default


def _read_text(path: str, session_id: str | None = None) -> str | None:
    readers = []
    if session_id:
        readers.append(lambda: base.read_text(path, session_id))
    readers.append(lambda: base.read_text(path))
    for reader in readers:
        try:
            value = reader()
            if isinstance(value, str) and value.strip():
                return value
        except Exception:
            continue
    return None


def _canonical_id(value: Any) -> str:
    raw = str(value or "").strip()
    key = raw.lower().replace("ё", "е")
    return ID_ALIASES.get(key, key or raw)


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = _canonical_id(value)
        if item and item not in result and item not in {"none", "null", "unknown"}:
            result.append(item)
    return result


def _ids_from_state(current: dict[str, Any]) -> tuple[list[str], list[str]]:
    active: list[Any] = []
    nearby: list[Any] = []
    all_ids: list[Any] = []
    for field in CHARACTER_FIELDS:
        value = current.get(field)
        if isinstance(value, list):
            all_ids.extend(value)
            if field.startswith("active") or field.startswith("speaking") or field.startswith("present"):
                active.extend(value)
            if field.startswith("nearby") or field.startswith("observing") or field.startswith("pending"):
                nearby.extend(value)
        elif isinstance(value, str):
            all_ids.append(value)
    if "akira" not in [_canonical_id(x) for x in all_ids]:
        all_ids.insert(0, "akira")
    return _unique(active or all_ids), _unique(all_ids + nearby)


def _split_top_sections(text: str) -> dict[str, str]:
    lines = str(text or "").splitlines()
    starts: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if not line or line[0].isspace() or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key:
            starts.append((idx, key))
    sections: dict[str, str] = {}
    for pos, (start, key) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        sections[key] = "\n".join(lines[start:end]).rstrip()
    return sections


def _wanted_key(key: str, wanted: set[str]) -> bool:
    if key in wanted:
        return True
    if key.startswith("relationship_to_") or key.startswith("relation_to_"):
        return True
    low = key.lower()
    return any(token in low for token in ("energy", "ability", "combat", "limit", "forbid"))


def _section_aware_extract(text: str, wanted: set[str], budget: PacketBudget, *, per_section_chars: int = 2300) -> tuple[str, list[str], list[str]]:
    sections = _split_top_sections(text)
    loaded: list[str] = []
    missing: list[str] = []
    chunks: list[str] = []
    for key, value in sections.items():
        if _wanted_key(key, wanted):
            cut = budget.take(value, per_section_chars)
            if cut:
                loaded.append(key)
                chunks.append(cut)
    for key in wanted:
        if key not in sections and not any(key in loaded_key for loaded_key in loaded):
            missing.append(key)
    return "\n\n".join(chunks).strip(), loaded, sorted(set(missing))


def _contains_energy(text: str) -> bool:
    low = str(text or "").lower().replace("ё", "е")
    return any(word in low for word in ENERGY_KEYWORDS)


def _short_dynamic_knowledge(session_id: str, cid: str, budget: PacketBudget) -> dict[str, Any]:
    data = _read_json(f"state/character_knowledge/{cid}.json", session_id, {})
    if not isinstance(data, dict) or not data:
        return {}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return {"path": f"state/character_knowledge/{cid}.json", "content": budget.take(text, 1600)}


def _character_packet(session_id: str, cid: str, budget: PacketBudget) -> dict[str, Any]:
    folder = _canonical_id(cid)
    packet: dict[str, Any] = {
        "id": folder,
        "files": {},
        "sections_loaded": {},
        "sections_missing": {},
        "energy_section_loaded": False,
    }

    main_text = _read_text(f"characters/{folder}/main.yaml", session_id)
    if main_text:
        packet["files"]["main"] = {
            "path": f"characters/{folder}/main.yaml",
            "content": budget.take(main_text, 1200),
        }

    char_text = _read_text(f"characters/{folder}/character.yaml", session_id)
    if char_text:
        content, loaded, missing = _section_aware_extract(char_text, CHARACTER_TOP_SECTIONS, budget, per_section_chars=2400)
        packet["files"]["character"] = {
            "path": f"characters/{folder}/character.yaml",
            "content": content,
        }
        packet["sections_loaded"]["character"] = loaded
        packet["sections_missing"]["character"] = missing
        packet["energy_section_loaded"] = "energy" in loaded or _contains_energy(content)
    else:
        packet["missing_character_file"] = f"characters/{folder}/character.yaml"

    knowledge_text = _read_text(f"characters/{folder}/knowledge.yaml", session_id)
    if knowledge_text:
        content, loaded, missing = _section_aware_extract(knowledge_text, KNOWLEDGE_TOP_SECTIONS, budget, per_section_chars=2200)
        packet["files"]["knowledge"] = {
            "path": f"characters/{folder}/knowledge.yaml",
            "content": content,
        }
        packet["sections_loaded"]["knowledge"] = loaded
        packet["sections_missing"]["knowledge"] = missing
    else:
        packet["missing_knowledge_file"] = f"characters/{folder}/knowledge.yaml"

    dynamic = _short_dynamic_knowledge(session_id, folder, budget)
    if dynamic:
        packet["files"]["dynamic_knowledge"] = dynamic

    packet["runtime_rules"] = [
        "Use this packet as the character source for this turn.",
        "Do not treat omitted raw-file sections as available knowledge.",
        "Energy/abilities are available options when scene pressure makes them logical, not mandatory spam.",
    ]
    return packet


def _world_energy_digest(session_id: str, budget: PacketBudget) -> dict[str, Any]:
    text = _read_text(WORLD_ENERGY_DIGEST_FILE, session_id)
    if not text:
        text = """energy_runtime_digest:
  rule: "Energy is an active world layer for humans/kairos and can affect combat, movement, pressure, defense, perception and restraint."
  use_rule: "Characters do not use energy every second, but renderer must keep it available as a behavior option when pressure, danger, pursuit or defense logically calls for it."
  known_profiles:
    akira: "space; in 1206 access is blocked/closed unless scene unlocks it"
    emma: "water/moisture/liquid pressure"
    irey: "space + spatial-sensory link"
    raiden: "cold + air"
  forbidden:
    - "Do not render energy-capable characters as ordinary humans if their energy packet is loaded."
    - "Do not invent new abilities beyond character packets."
"""
    return {"path": WORLD_ENERGY_DIGEST_FILE, "content": budget.take(text, 2200)}


def _recent_scene_history(session_id: str, budget: PacketBudget, limit: int = 3) -> list[dict[str, Any]]:
    history = _read_json(SCENE_HISTORY_FILE, session_id, {"entries": []})
    entries = history if isinstance(history, list) else history.get("entries", []) if isinstance(history, dict) else []
    clean: list[dict[str, Any]] = []
    for entry in list(entries)[-limit:]:
        if not isinstance(entry, dict):
            continue
        item = {
            "turn_number": entry.get("turn_number"),
            "location_text": entry.get("location_text"),
            "player_input": entry.get("player_input"),
            "visible_scene_text": budget.take(str(entry.get("visible_scene_text") or entry.get("scene_text") or ""), 1400),
        }
        clean.append(item)
    return clean


def _knowledge_boundary() -> dict[str, Any]:
    return {
        "rule": "A fact in the packet is not automatically NPC knowledge.",
        "npc_may_state_as_fact_only_from": [
            "own static knowledge file",
            "own dynamic character_knowledge state",
            "visible observation in current scene",
            "dialogue heard in current scene",
        ],
        "npc_must_not_state_as_fact_from": [
            "Akira character card",
            "current_state engine facts",
            "author/canon summary",
            "hidden/past files",
            "prompt instructions",
        ],
    }


def build_turn_packet(session_id: str, *, max_total_chars: int = 24000, include_debug: bool = False) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)
    budget = PacketBudget(max_total_chars)

    current = _read_json(CURRENT_STATE_FILE, sid, {})
    if not isinstance(current, dict):
        current = {}
    calendar = _read_json(CALENDAR_RUNTIME_FILE, sid, {})
    relationships = _read_json(RELATIONSHIPS_FILE, sid, {})

    active_ids, scene_ids = _ids_from_state(current)
    character_packets = [_character_packet(sid, cid, budget) for cid in scene_ids]

    energy_loaded = {
        packet["id"]: bool(packet.get("energy_section_loaded"))
        for packet in character_packets
    }
    files_missing = []
    for packet in character_packets:
        for key in ("missing_character_file", "missing_knowledge_file"):
            if packet.get(key):
                files_missing.append(packet[key])

    packet: dict[str, Any] = {
        "success": True,
        "session_id": sid,
        "mode": "turn_packet_v2_section_aware",
        "runtime_version": "0.3.146-turn-packet-gateway-v1",
        "created_at": datetime.utcnow().isoformat(),
        "current_state_slice": {
            "current_date": current.get("current_date"),
            "current_day_phase": current.get("current_day_phase") or current.get("time_of_day"),
            "current_location_id": current.get("current_location_id"),
            "current_location_text": current.get("current_location_text"),
            "active_characters": current.get("active_characters") or current.get("active_character_ids") or [],
            "nearby_characters": current.get("nearby_characters") or current.get("nearby_character_ids") or [],
            "pending_character_ids": current.get("pending_character_ids") or [],
            "last_player_input": current.get("last_player_input"),
        },
        "calendar_slice": {
            "current_date": calendar.get("current_date") if isinstance(calendar, dict) else None,
            "current_day_phase": calendar.get("current_day_phase") if isinstance(calendar, dict) else None,
            "active_window": calendar.get("active_window") if isinstance(calendar, dict) else None,
            "current_beat_id": calendar.get("current_beat_id") if isinstance(calendar, dict) else None,
            "pending_events": calendar.get("pending_events") if isinstance(calendar, dict) else [],
        },
        "active_character_ids": active_ids,
        "scene_character_ids": scene_ids,
        "world_energy_digest": _world_energy_digest(sid, budget),
        "character_packets": character_packets,
        "recent_scene_history": _recent_scene_history(sid, budget),
        "relationships_available": bool(relationships),
        "npc_knowledge_boundary": _knowledge_boundary(),
        "context_audit": {
            "energy_sections_loaded": energy_loaded,
            "character_files_missing": files_missing,
            "packet_chars_used": budget.used,
            "packet_truncated": budget.truncated,
        },
        "render_rules": [
            "Render from turn_packet only; do not require raw required_files chunks for gameplay.",
            "Each active/scene NPC must behave with loaded character packet: goals, knowledge limits, energy, limitations and forbidden.",
            "If an energy_section_loaded value is false for an active energy-capable character, stop gameplay and report context packet missing energy.",
            "After meaningful scene changes, call applyTurnResult.",
        ],
    }
    if include_debug:
        packet["debug"] = {
            "budget_max_chars": budget.max_chars,
            "sections_per_character": {p["id"]: p.get("sections_loaded", {}) for p in character_packets},
        }
    return packet


@app.get("/api/v2/sessions/{session_id}/turn-packet", operation_id="getTurnPacket")
def get_turn_packet(
    session_id: str,
    max_total_chars: int = Query(default=24000, ge=12000, le=42000),
    include_debug: bool = Query(default=False),
) -> dict[str, Any]:
    return build_turn_packet(session_id, max_total_chars=max_total_chars, include_debug=include_debug)


@app.get("/api/v2/sessions/{session_id}/debug/context-audit", operation_id="getContextAudit")
def get_context_audit(
    session_id: str,
    max_total_chars: int = Query(default=30000, ge=12000, le=42000),
) -> dict[str, Any]:
    packet = build_turn_packet(session_id, max_total_chars=max_total_chars, include_debug=True)
    return {
        "success": packet.get("success"),
        "session_id": packet.get("session_id"),
        "runtime_version": packet.get("runtime_version"),
        "mode": "context_audit_v2_section_aware",
        "active_character_ids": packet.get("active_character_ids"),
        "scene_character_ids": packet.get("scene_character_ids"),
        "context_audit": packet.get("context_audit"),
        "sections_per_character": packet.get("debug", {}).get("sections_per_character", {}),
        "world_energy_digest_loaded": bool(packet.get("world_energy_digest", {}).get("content")),
        "instructions": [
            "If energy_sections_loaded is false for Emma/Irey/Raiden while they are active/nearby, gameplay context is incomplete.",
            "This audit is read-only and does not call repair or applyTurnResult.",
        ],
    }


try:
    app.version = "0.3.146-turn-packet-gateway-v1"
except Exception:
    pass
