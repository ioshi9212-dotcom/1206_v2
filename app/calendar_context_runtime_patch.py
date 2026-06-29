"""
Calendar context runtime patch v14.

Loads the current calendar index, current story spine, and the current day file.
The calendar is a world-pressure and consequence map, not a script for Akira.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import app.context_transport_runtime_patch as rt
from app.context_transport_runtime_patch import app
from app import compact as base
import app.compact_context_patch as ccp

app.version = "0.3.131-calendar-clean-story-rules-v1"

CALENDAR_INDEX_FILE = "calendar/calendar_index.yaml"
CALENDAR_RUNTIME_FILE = "state/calendar_runtime.json"
CALENDAR_STORY_SPINE_FILE = "calendar/story_spine_1206.yaml"


def _read_text_optional(path: str, session_id: str | None = None) -> str:
    safe_path = str(path or "").strip()
    if not safe_path:
        return ""
    try:
        return base.read_text(safe_path, session_id=session_id)
    except Exception:
        pass
    for root in [getattr(base, "DATA", None), getattr(base, "ROOT", None)]:
        if not root:
            continue
        try:
            file_path = Path(root) / base.safe(safe_path)
            if file_path.exists() and file_path.is_file():
                return file_path.read_text(encoding="utf-8")
        except Exception:
            continue
    return ""


def _cut_text(text: str, limit: int = 9000) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n...<truncated>"


def build_calendar_slice_v2(current: dict[str, Any], session_id: str) -> dict[str, Any]:
    runtime = base.read_json(CALENDAR_RUNTIME_FILE, session_id, default={}) or {}
    current_date = str(current.get("current_date") or current.get("date") or runtime.get("current_date") or "1206-08-31")
    current_time = str(current.get("current_time") or current.get("time") or runtime.get("current_time") or "")
    day_file = str(runtime.get("current_day_file") or current.get("current_day_file") or (f"calendar/days/{current_date}.yaml" if current_date else ""))
    index_text = _read_text_optional(CALENDAR_INDEX_FILE, session_id=session_id)
    story_spine_text = _read_text_optional(CALENDAR_STORY_SPINE_FILE, session_id=session_id)
    day_text = _read_text_optional(day_file, session_id=session_id) if day_file else ""
    return {
        "calendar_mode": "calendar_module_v2_clean_story_rules",
        "current_date": current_date,
        "current_time": current_time,
        "calendar_source": CALENDAR_INDEX_FILE,
        "calendar_story_spine_file": CALENDAR_STORY_SPINE_FILE,
        "calendar_runtime_file": CALENDAR_RUNTIME_FILE,
        "current_day_file": day_file,
        "current_beat_id": runtime.get("current_beat_id") or current.get("current_beat_id"),
        "completed_beat_ids": runtime.get("completed_beat_ids", []),
        "skipped_beat_ids": runtime.get("skipped_beat_ids", []),
        "introduced_character_ids": runtime.get("introduced_character_ids", []),
        "calendar_check_rule": [
            "Use current_date from state/current_state.json first.",
            "Load calendar/calendar_index.yaml and calendar/story_spine_1206.yaml as overview only.",
            "Load only the current day file for active play.",
            "Future day files are for explicit timeskip/calendar audit only, not normal scene generation.",
            "Calendar defines world pressure, NPC goals, timing windows and consequences; it does not write Akira's action.",
            "Player controls Akira's decisions, speech and intentional actions.",
            "If player hesitates, the world continues: NPCs move, ask, pressure, search, wait, withdraw or escalate according to goals.",
            "Characters and pursuers need plausible in-world time and distance before entering a scene.",
            "Do not introduce a conditional character in the same instant as the first faint trigger unless the day file explicitly says already nearby.",
            "All NPC knowledge is limited to visible/heard/revealed facts and their own files.",
            "Use only loaded project files and current state; do not reference external drafts or material not present in context.",
        ],
        "calendar_index_yaml": _cut_text(index_text, 7000),
        "calendar_story_spine_yaml": _cut_text(story_spine_text, 7000),
        "current_day_yaml": _cut_text(day_text, 12000),
    }


def build_scene_context_digest(session_id: str) -> str:
    current = base.read_json("state/current_state.json", session_id, default={}) or {}
    future = base.read_json("state/future_locks_progress.json", session_id, default={}) or {}
    chars = rt.scene_character_ids(current, future)
    relationships = rt.compact_relationships_scene_pairs_only(base.read_json("state/relationships.json", session_id, default={}) or {}, chars)
    story_lines = rt.compact_story_lines_scene_only(base.read_json("state/story_lines.json", session_id, default={}) or {}, chars)
    knowledge = rt.compact_knowledge_scene_only(base.read_json("state/knowledge_state.json", session_id, default={}) or {}, chars)
    inventory = base.compact_if_large(base.read_json("state/inventory_state.json", session_id, default={}) or {}, 2200)
    calendar_slice = build_calendar_slice_v2(current, session_id)
    rule_digest = {
        "output": [
            "Gameplay only: no API/status/debug summary in final answer.",
            "Scene must start with the current selected visual-novel header.",
            "Dialogue format: **Name/descriptor** — speech. (*short italic remark*)",
            "Descriptions are separate italic paragraphs.",
            "Akira thoughts only in bottom block, not inside the scene body.",
            "No empty scene: add hook/reaction/conflict/consequence or time skip.",
            "Do not answer with technical commentary after a gameplay scene.",
        ],
        "calendar": [
            "Calendar module is source of date hooks and world pressure.",
            "Calendar day YAML is not ready-made prose and not a player action script.",
            "Use only the current day file during normal play.",
            "Free gaps between dated nodes may be played, compressed, or skipped by player routine.",
            "If player says to sleep, next output starts at the next meaningful beat, not with a menu asking why to wake up.",
            "Conditional arrivals require plausible travel/search time unless already placed nearby by current state.",
            "NPCs cannot infer hidden contents, routes, motives, past facts, or unseen items without scene access.",
        ],
        "state_write": [
            "Backend does not infer state from prose.",
            "If relationships/story/knowledge/current_state/calendar_runtime change, send explicit state payload to apply-turn-result.",
            "Roster lists are replacement fields, not append-only fields.",
        ],
    }
    text = "# Runtime scene context digest\n"
    text += "This digest replaces heavy global prompt/canon/state files for normal gameplay. Use exact character files also loaded in required_files.\n"
    text += rt.MEDIUM_STYLE_FORMAT_DIGEST + "\n"
    text += rt.MEDIUM_ENGINE_DIGEST + "\n"
    text += rt.MEDIUM_SOURCE_USAGE_DIGEST + "\n"
    text += rt.MEDIUM_RELATIONSHIP_DIGEST + "\n"
    text += rt._json_block("Rule digest", rule_digest, 4200)
    text += rt._json_block("Scene character ids", chars, 1200)
    text += rt._json_block("Current state", current, 4600)
    text += rt._json_block("Relationship slice", relationships, 5600)
    text += rt._json_block("Story lines slice", story_lines, 7600)
    text += rt._json_block("Knowledge slice", knowledge, 5200)
    text += rt._json_block("Inventory slice", inventory, 2200)
    text += rt._json_block("Calendar slice", calendar_slice, 14000)
    text += "\n## State update reminder\nIf scene changes roster, use current_state_changes with roster fields as full replacement lists. If calendar progress changes, update state/calendar_runtime.json explicitly.\n"
    return text


rt.build_calendar_slice_v2 = build_calendar_slice_v2
rt.build_scene_context_digest = build_scene_context_digest
rt.app.version = app.version
ccp._read_required_file_for_bundle = rt.read_required_file_for_bundle
