"""Section-aware turn packet gateway for Akira 1206 v2.

v0.3.148 fixes:
- world_energy_digest is loaded before character budget and never starved by packets;
- scene/pending/scheduled/conditional characters are included in packet collection;
- Raiden is included when scene/pending/calendar hints reference him;
- gameplay packet uses compact per-character budgets so include_debug=false does not normally truncate;
- audit reports packet/energy/section availability without calling repair/applyTurnResult.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import Query

from app import compact as base

app = base.app

RUNTIME_VERSION = "0.3.148-turn-packet-energy-audit-fix-v1"

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
    "scene_characters",
    "pending_character_ids",
    "pending_characters",
    "pending_character_entries",
    "scheduled_character_ids",
    "scheduled_characters",
    "conditional_character_ids",
    "conditional_characters",
    "expected_character_ids",
    "essential_character_ids",
)

ACTIVE_FIELDS = (
    "active_character_ids",
    "active_characters",
    "speaking_character_ids",
    "speaking_characters",
    "present_character_ids",
    "present_characters",
)

SCENE_FIELDS = CHARACTER_FIELDS

CHARACTER_TOP_SECTIONS = {
    "id",
    "display_name",
    "slug",
    "file_type",
    "version",
    "identity",
    "current_status",
    "scene_role",
    "character_scope_rule",
    "core_motivation",
    "goal",
    "goals",
    "motivation",
    "behavior_under_pressure",
    "touch_and_control",
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
    "costs",
    "forbidden",
    "do_not",
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
    "dynamic_knows",
    "dynamic_unknowns",
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
    "якор",
)

ID_ALIASES = {
    "рей": "ray",
    "rey": "ray",
    "ray": "ray",
    "рэй": "ray",
    "рейден": "raiden",
    "рейдон": "raiden",
    "рэйден": "raiden",
    "стерлинг": "raiden",
    "стэрлинг": "raiden",
    "raiden_sterling": "raiden",
    "raiden": "raiden",
    "irey": "irey",
    "ирэй": "irey",
    "ирей": "irey",
    "emma": "emma",
    "эмма": "emma",
    "jun": "jun",
    "джун": "jun",
    "akira": "akira",
    "акира": "akira",
}

CHARACTER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_\-]{1,40}$")


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
    if value is None:
        return ""
    raw = str(value).strip().strip("'\"")
    if not raw:
        return ""
    key = raw.lower().replace("ё", "е").replace(" ", "_")
    key = key.split("/")[-1]
    key = key.replace("characters_", "")
    key = key.replace("character_", "")
    key = key.replace(".yaml", "").replace(".json", "")
    return ID_ALIASES.get(key, key)


def _is_plausible_character_id(value: str) -> bool:
    if not value:
        return False
    if value in {"none", "null", "unknown", "false", "true", "active", "nearby", "pending"}:
        return False
    if value in ID_ALIASES.values():
        return True
    return bool(CHARACTER_ID_PATTERN.match(value)) and len(value) <= 42


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = _canonical_id(value)
        if _is_plausible_character_id(item) and item not in result:
            result.append(item)
    return result


def _extract_ids(value: Any) -> list[str]:
    """Recursively extract ids from strings/lists/dicts produced by current_state/calendar."""
    found: list[Any] = []
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        if raw:
            # Event ids can encode character names, e.g. raiden_delayed_conditional_arrival.
            low = raw.lower().replace("ё", "е")
            for alias, cid in ID_ALIASES.items():
                if alias and alias in low:
                    found.append(cid)
            # Also accept direct id strings.
            found.append(raw)
        return _unique(found)
    if isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_extract_ids(item))
        return _unique(found)
    if isinstance(value, dict):
        for key in ("id", "character_id", "character", "cid", "slug", "name"):
            if key in value:
                found.extend(_extract_ids(value.get(key)))
        for key in (
            "character_ids",
            "characters",
            "active_character_ids",
            "nearby_character_ids",
            "scene_character_ids",
            "pending_character_ids",
            "scheduled_character_ids",
            "conditional_character_ids",
            "participants",
            "attendees",
        ):
            if key in value:
                found.extend(_extract_ids(value.get(key)))
        # Conservative heuristic: event_id/title may include a known character name.
        for key in ("event_id", "beat_id", "calendar_event_id", "title", "name", "description"):
            if key in value and isinstance(value.get(key), str):
                found.extend(_extract_ids(value.get(key)))
        return _unique(found)
    return []


def _ids_from_state_and_calendar(current: dict[str, Any], calendar: Any) -> tuple[list[str], list[str]]:
    active_raw: list[Any] = []
    scene_raw: list[Any] = []

    for field in ACTIVE_FIELDS:
        if field in current:
            active_raw.extend(_extract_ids(current.get(field)))
    for field in SCENE_FIELDS:
        if field in current:
            scene_raw.extend(_extract_ids(current.get(field)))

    if isinstance(calendar, dict):
        for field in (
            "active_character_ids",
            "nearby_character_ids",
            "scene_character_ids",
            "pending_character_ids",
            "scheduled_character_ids",
            "conditional_character_ids",
            "pending_events",
            "active_events",
            "current_event",
            "active_window",
            "current_beat_id",
            "events",
        ):
            if field in calendar:
                scene_raw.extend(_extract_ids(calendar.get(field)))

    active_ids = _unique(active_raw)
    scene_ids = _unique(active_raw + scene_raw)
    if "akira" not in scene_ids:
        scene_ids.insert(0, "akira")
    # Keep active first, then scene/pending/conditional. This prevents late arrivals like Raiden being starved.
    ordered = _unique(active_ids + scene_ids)
    return active_ids or ordered[:], ordered


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
    low = key.lower()
    if low.startswith("relationship_to_") or low.startswith("relation_to_") or low.startswith("if_"):
        return True
    return any(token in low for token in ("energy", "ability", "combat", "limit", "forbid", "knowledge", "pressure"))


def _trim(text: str, limit: int) -> tuple[str, bool]:
    text = str(text or "")
    if len(text) <= limit:
        return text, False
    return text[: max(0, limit - 96)].rstrip() + "\n... [section clipped for packet size]", True


def _section_aware_extract(
    text: str,
    wanted: set[str],
    *,
    per_section_chars: int = 1200,
    max_chars: int = 4200,
) -> tuple[str, list[str], list[str], bool]:
    sections = _split_top_sections(text)
    loaded: list[str] = []
    missing: list[str] = []
    chunks: list[str] = []
    truncated = False

    # Load critical sections first, regardless of card order.
    priority = [
        "id",
        "display_name",
        "identity",
        "current_status",
        "scene_role",
        "goal",
        "goals",
        "core_motivation",
        "knowledge_limits",
        "behavior_under_pressure",
        "energy",
        "abilities",
        "ability_detection_rules",
        "combat_use",
        "limitations",
        "limits",
        "costs",
        "forbidden",
        "do_not",
    ]
    ordered_keys = []
    for key in priority:
        if key in sections:
            ordered_keys.append(key)
    for key in sections:
        if key not in ordered_keys and _wanted_key(key, wanted):
            ordered_keys.append(key)

    used = 0
    for key in ordered_keys:
        value, was_cut = _trim(sections[key], per_section_chars)
        if used + len(value) > max_chars:
            remaining = max_chars - used
            if remaining <= 120:
                truncated = True
                break
            value, _ = _trim(value, remaining)
            truncated = True
        if value.strip():
            chunks.append(value)
            loaded.append(key)
            used += len(value)
        truncated = truncated or was_cut

    for key in wanted:
        if key not in sections and not any(key in loaded_key for loaded_key in loaded):
            missing.append(key)
    return "\n\n".join(chunks).strip(), loaded, sorted(set(missing)), truncated


def _contains_energy(text: str) -> bool:
    low = str(text or "").lower().replace("ё", "е")
    return any(word in low for word in ENERGY_KEYWORDS)


def _short_dynamic_knowledge(session_id: str, cid: str) -> dict[str, Any]:
    data = _read_json(f"state/character_knowledge/{cid}.json", session_id, {})
    if not isinstance(data, dict) or not data:
        return {}
    text = json.dumps(data, ensure_ascii=False, indent=2)
    content, _ = _trim(text, 1200)
    return {"path": f"state/character_knowledge/{cid}.json", "content": content}


def _character_packet(session_id: str, cid: str, *, max_chars: int = 5200) -> dict[str, Any]:
    folder = _canonical_id(cid)
    packet: dict[str, Any] = {
        "id": folder,
        "files": {},
        "sections_loaded": {},
        "sections_missing": {},
        "energy_section_loaded": False,
        "packet_truncated": False,
    }

    used = 0

    def add_text(limit: int, text: str) -> str:
        nonlocal used
        remaining = max(0, max_chars - used)
        if remaining <= 0:
            packet["packet_truncated"] = True
            return ""
        content, cut = _trim(text, min(limit, remaining))
        used += len(content)
        packet["packet_truncated"] = bool(packet["packet_truncated"] or cut)
        return content

    main_text = _read_text(f"characters/{folder}/main.yaml", session_id)
    if main_text:
        packet["files"]["main"] = {
            "path": f"characters/{folder}/main.yaml",
            "content": add_text(850, main_text),
        }

    char_text = _read_text(f"characters/{folder}/character.yaml", session_id)
    if char_text:
        content, loaded, missing, cut = _section_aware_extract(
            char_text,
            CHARACTER_TOP_SECTIONS,
            per_section_chars=1050,
            max_chars=3300,
        )
        packet["files"]["character"] = {
            "path": f"characters/{folder}/character.yaml",
            "content": add_text(3300, content),
        }
        packet["sections_loaded"]["character"] = loaded
        packet["sections_missing"]["character"] = missing
        packet["energy_section_loaded"] = "energy" in loaded or _contains_energy(content)
        packet["packet_truncated"] = bool(packet["packet_truncated"] or cut)
    else:
        packet["missing_character_file"] = f"characters/{folder}/character.yaml"

    knowledge_text = _read_text(f"characters/{folder}/knowledge.yaml", session_id)
    if knowledge_text:
        content, loaded, missing, cut = _section_aware_extract(
            knowledge_text,
            KNOWLEDGE_TOP_SECTIONS,
            per_section_chars=900,
            max_chars=1800,
        )
        packet["files"]["knowledge"] = {
            "path": f"characters/{folder}/knowledge.yaml",
            "content": add_text(1800, content),
        }
        packet["sections_loaded"]["knowledge"] = loaded
        packet["sections_missing"]["knowledge"] = missing
        packet["packet_truncated"] = bool(packet["packet_truncated"] or cut)
    else:
        packet["missing_knowledge_file"] = f"characters/{folder}/knowledge.yaml"

    dynamic = _short_dynamic_knowledge(session_id, folder)
    if dynamic:
        packet["files"]["dynamic_knowledge"] = dynamic

    # Defensive fallback: if the card uses a non-standard key but contains energy words,
    # expose a small energy hint instead of silently losing the energy layer.
    if not packet.get("energy_section_loaded") and char_text and _contains_energy(char_text):
        energy_lines = []
        for line in char_text.splitlines():
            if _contains_energy(line):
                energy_lines.append(line)
            if len("\n".join(energy_lines)) > 700:
                break
        if energy_lines:
            packet["files"]["energy_hint"] = {
                "path": f"characters/{folder}/character.yaml#energy_hint",
                "content": "\n".join(energy_lines),
            }
            packet["energy_section_loaded"] = True

    packet["runtime_rules"] = [
        "Use this packet as the character source for this turn.",
        "Do not treat omitted raw-file sections as available knowledge.",
        "Energy/abilities are available options when scene pressure makes them logical, not mandatory spam.",
    ]
    return packet


def _world_energy_digest(session_id: str) -> dict[str, Any]:
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
    content, cut = _trim(text, 1800)
    return {"path": WORLD_ENERGY_DIGEST_FILE, "content": content, "loaded": bool(content.strip()), "truncated": cut}


def _recent_scene_history(session_id: str, limit: int = 2) -> list[dict[str, Any]]:
    history = _read_json(SCENE_HISTORY_FILE, session_id, {"entries": []})
    entries = history if isinstance(history, list) else history.get("entries", []) if isinstance(history, dict) else []
    clean: list[dict[str, Any]] = []
    for entry in list(entries)[-limit:]:
        if not isinstance(entry, dict):
            continue
        text, _ = _trim(str(entry.get("visible_scene_text") or entry.get("scene_text") or ""), 900)
        clean.append({
            "turn_number": entry.get("turn_number"),
            "location_text": entry.get("location_text"),
            "player_input": entry.get("player_input"),
            "visible_scene_text": text,
        })
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


def _packet_size(packet: dict[str, Any]) -> int:
    try:
        return len(json.dumps(packet, ensure_ascii=False))
    except Exception:
        return 0


def build_turn_packet(session_id: str, *, max_total_chars: int = 24000, include_debug: bool = False) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)

    current = _read_json(CURRENT_STATE_FILE, sid, {})
    if not isinstance(current, dict):
        current = {}
    calendar = _read_json(CALENDAR_RUNTIME_FILE, sid, {})
    relationships = _read_json(RELATIONSHIPS_FILE, sid, {})

    active_ids, scene_ids = _ids_from_state_and_calendar(current, calendar)

    # Ensure known active energy actors are not starved if the scene references them.
    character_packets = [_character_packet(sid, cid, max_chars=5200) for cid in scene_ids]
    energy_loaded = {packet["id"]: bool(packet.get("energy_section_loaded")) for packet in character_packets}

    files_missing: list[str] = []
    for packet_item in character_packets:
        for key in ("missing_character_file", "missing_knowledge_file"):
            if packet_item.get(key):
                files_missing.append(packet_item[key])

    world_digest = _world_energy_digest(sid)
    packet: dict[str, Any] = {
        "success": True,
        "session_id": sid,
        "mode": "turn_packet_v2_section_aware",
        "runtime_version": RUNTIME_VERSION,
        "created_at": datetime.utcnow().isoformat(),
        "current_state_slice": {
            "current_date": current.get("current_date"),
            "current_day_phase": current.get("current_day_phase") or current.get("time_of_day"),
            "current_location_id": current.get("current_location_id"),
            "current_location_text": current.get("current_location_text"),
            "active_characters": current.get("active_characters") or current.get("active_character_ids") or [],
            "nearby_characters": current.get("nearby_characters") or current.get("nearby_character_ids") or [],
            "scene_character_ids": current.get("scene_character_ids") or [],
            "pending_character_ids": current.get("pending_character_ids") or [],
            "scheduled_character_ids": current.get("scheduled_character_ids") or [],
            "conditional_character_ids": current.get("conditional_character_ids") or [],
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
        "world_energy_digest": world_digest,
        "character_packets": character_packets,
        "recent_scene_history": _recent_scene_history(sid),
        "relationships_available": bool(relationships),
        "npc_knowledge_boundary": _knowledge_boundary(),
        "context_audit": {
            "energy_sections_loaded": energy_loaded,
            "character_files_missing": files_missing,
            "packet_chars_used": 0,
            "packet_truncated": False,
            "world_energy_digest_loaded": bool(world_digest.get("loaded") or world_digest.get("content")),
            "character_packet_ids": [p.get("id") for p in character_packets],
            "character_packets_truncated": {p.get("id"): bool(p.get("packet_truncated")) for p in character_packets},
        },
        "render_rules": [
            "Render from turn_packet only; do not require raw required_files chunks for gameplay.",
            "Each active/scene NPC must behave with loaded character packet: goals, knowledge limits, energy, limitations and forbidden.",
            "If an energy_section_loaded value is false for an active/scene energy-capable character, stop gameplay and report context packet missing energy.",
            "After meaningful scene changes, call applyTurnResult.",
        ],
    }

    size = _packet_size(packet)
    packet["context_audit"]["packet_chars_used"] = size
    packet["context_audit"]["packet_truncated"] = size > int(max_total_chars or 24000)

    # If gameplay packet is still too large, compact history first. Do not drop energy digest or character energy sections.
    if not include_debug and packet["context_audit"]["packet_truncated"]:
        packet["recent_scene_history"] = packet["recent_scene_history"][-1:]
        size = _packet_size(packet)
        packet["context_audit"]["packet_chars_used"] = size
        packet["context_audit"]["packet_truncated"] = size > int(max_total_chars or 24000)

    if include_debug:
        packet["debug"] = {
            "max_total_chars": int(max_total_chars or 24000),
            "sections_per_character": {p["id"]: p.get("sections_loaded", {}) for p in character_packets},
            "sections_missing_per_character": {p["id"]: p.get("sections_missing", {}) for p in character_packets},
            "source_fields_checked": list(CHARACTER_FIELDS),
        }
    return packet


# Remove stale copies of these routes if another patch registered them before this module was imported.
def _remove_path(path: str) -> None:
    for route in list(app.router.routes):
        if getattr(route, "path", None) == path:
            app.router.routes.remove(route)


_remove_path("/api/v2/sessions/{session_id}/turn-packet")
_remove_path("/api/v2/sessions/{session_id}/debug/context-audit")


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
        "sections_missing_per_character": packet.get("debug", {}).get("sections_missing_per_character", {}),
        "world_energy_digest_loaded": bool(packet.get("world_energy_digest", {}).get("loaded") or packet.get("world_energy_digest", {}).get("content")),
        "instructions": [
            "If energy_sections_loaded is false for Emma/Irey/Raiden while they are active/nearby/scene/pending, gameplay context is incomplete.",
            "This audit is read-only and does not call repair or applyTurnResult.",
            "getSessionTurnContract/getFastRenderContext must not be used as gameplay route in clean schema.",
        ],
    }


try:
    app.version = RUNTIME_VERSION
except Exception:
    pass
