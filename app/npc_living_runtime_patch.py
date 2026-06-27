"""Living NPC runtime patch v2.

Adds social-life NPC rules and session-level memory for invented NPCs.
This does not force random NPCs into every turn. It keeps East Sector NPCs alive,
varied and persistent when they become meaningful.
"""
from __future__ import annotations

import json
from typing import Any

import app.context_transport_runtime_patch as rt
from app.context_transport_runtime_patch import app
from app import compact as base
import app.compact_context_patch as ccp

try:
    import app.response_size_guard_runtime_patch as size_guard
except Exception:  # pragma: no cover
    size_guard = None  # type: ignore[assignment]

try:
    import app.fast_context_runtime_patch as fast_context
except Exception:  # pragma: no cover
    fast_context = None  # type: ignore[assignment]

NPC_RULES_FILE = "gpt/locks/npc_living_scene_rules.md"
SESSION_NPCS_FILE = "state/session_npcs.json"

_ORIGINAL_RECOMMENDED = getattr(rt, "lean_recommended_files_for_context", base.recommended_files_for_context)
_ORIGINAL_BUILD_DIGEST = rt.build_scene_context_digest
_ORIGINAL_READ_REQUIRED_FILE = getattr(rt, "read_required_file_for_bundle", None)

DEFAULT_SESSION_NPCS = {
    "schema": "session_npcs_v2_east_sector_social",
    "state_id": "session_npcs",
    "purpose": "Session memory for invented NPCs who are not yet full character files.",
    "policy": {
        "background_npcs": "Disposable background NPCs may speak, move, react, argue, joke, eat, train or interrupt, but are not saved unless they become meaningful.",
        "important_npcs": "Save invented NPCs with name, repeated appearance, personal attitude, role, conflict, rumor value, relationship effect, witness value or future hook.",
        "promotion_rule": "If an NPC becomes major enough for long-term canon, promote them later into characters/<id>/ files. Until then keep them here.",
        "variation_rule": "Do not make all NPCs react the same way to Akira, Raiden, Ray, Miki or authority.",
    },
    "mini_profile_template": {
        "id": "",
        "name": "",
        "role": "",
        "age_range": "",
        "first_seen_location": "",
        "attitude_to_akira": "",
        "attitude_to_raiden": "",
        "relationships_or_group": [],
        "voice": "",
        "habit_or_visible_detail": "",
        "goal_or_current_need": "",
        "knows": [],
        "does_not_know": [],
        "rumors_heard": [],
        "future_hook": "",
    },
    "important_npcs": {},
    "open_npc_threads": [],
    "recent_background_notes": [],
}


def _normalize_session_npcs(state: dict[str, Any]) -> dict[str, Any]:
    """Keep old state/session_npcs.json compatible with v2 structure."""
    if not isinstance(state, dict):
        return dict(DEFAULT_SESSION_NPCS)

    old_npcs = state.get("npcs")
    important = state.get("important_npcs")
    if not isinstance(important, dict):
        important = old_npcs if isinstance(old_npcs, dict) else {}

    normalized = dict(DEFAULT_SESSION_NPCS)
    normalized.update({k: v for k, v in state.items() if k not in {"npcs"}})
    normalized["schema"] = state.get("schema") or DEFAULT_SESSION_NPCS["schema"]
    normalized["state_id"] = "session_npcs"
    normalized["important_npcs"] = important
    normalized["open_npc_threads"] = state.get("open_npc_threads") if isinstance(state.get("open_npc_threads"), list) else []
    normalized["recent_background_notes"] = state.get("recent_background_notes") if isinstance(state.get("recent_background_notes"), list) else []
    normalized["policy"] = {**DEFAULT_SESSION_NPCS["policy"], **(state.get("policy") if isinstance(state.get("policy"), dict) else {})}
    normalized["mini_profile_template"] = DEFAULT_SESSION_NPCS["mini_profile_template"]
    return normalized


def _ensure_session_npcs(session_id: str) -> dict[str, Any]:
    state = base.read_json(SESSION_NPCS_FILE, session_id, default=None)
    normalized = _normalize_session_npcs(state if isinstance(state, dict) else {})
    if state != normalized:
        base.write_json(SESSION_NPCS_FILE, normalized, session_id)
    return normalized


def _compact_session_npcs(state: dict[str, Any]) -> dict[str, Any]:
    state = _normalize_session_npcs(state)
    important = state.get("important_npcs") if isinstance(state, dict) else {}
    threads = state.get("open_npc_threads") if isinstance(state, dict) else []
    background = state.get("recent_background_notes") if isinstance(state, dict) else []

    if not isinstance(important, dict):
        important = {}
    if not isinstance(threads, list):
        threads = []
    if not isinstance(background, list):
        background = []

    return {
        "schema": state.get("schema", DEFAULT_SESSION_NPCS["schema"]),
        "important_npcs": important,
        "open_npc_threads": threads[-12:],
        "recent_background_notes": background[-10:],
        "rule": "Use saved important_npcs as session-only recurring NPC memory. Background NPCs may be alive and varied without being saved.",
        "mini_profile_rule": "If a background NPC becomes meaningful, save name, role, attitude, voice, goal, known facts, unknown facts and future hook.",
    }


def read_required_file_for_bundle_with_npcs(path: str, session_id: str):
    safe_path = str(path or "").strip()
    if safe_path == SESSION_NPCS_FILE:
        state = _ensure_session_npcs(session_id)
        return json.dumps(state, ensure_ascii=False, indent=2), "session"
    if callable(_ORIGINAL_READ_REQUIRED_FILE):
        return _ORIGINAL_READ_REQUIRED_FILE(path, session_id)
    return None, None


def recommended_files_with_npcs(current=None, future=None):
    try:
        files = list(_ORIGINAL_RECOMMENDED(current, future) or [])
    except TypeError:
        files = list(base.recommended_files_for_context(current or {}, future or {}) or [])

    for path in [NPC_RULES_FILE, SESSION_NPCS_FILE]:
        if path not in files:
            files.append(path)

    return [p for p in files if p == rt.RUNTIME_DIGEST_FILE or p == SESSION_NPCS_FILE or base.repo_file_exists(p)]


def build_scene_context_digest_with_npcs(session_id: str) -> str:
    text = _ORIGINAL_BUILD_DIGEST(session_id)
    session_npcs = _compact_session_npcs(_ensure_session_npcs(session_id))
    return text + "\n\n## Session NPC memory\n```json\n" + json.dumps(session_npcs, ensure_ascii=False, indent=2) + "\n```\n"


state_map = list(getattr(base, "STATE_SECTION_MAP", []) or [])
entry = (
    SESSION_NPCS_FILE,
    ["session_npcs_changes", "session_npcs", "npc_changes", "important_npcs_changes"],
)
if not any(item and item[0] == SESSION_NPCS_FILE for item in state_map):
    state_map.append(entry)
base.STATE_SECTION_MAP = state_map

if NPC_RULES_FILE not in rt.MINIMAL_LOCK_FILES:
    rt.MINIMAL_LOCK_FILES.append(NPC_RULES_FILE)

if size_guard is not None:
    try:
        if NPC_RULES_FILE not in size_guard.BASE_RULE_FILES:
            size_guard.BASE_RULE_FILES.append(NPC_RULES_FILE)
        if SESSION_NPCS_FILE not in size_guard.LIGHT_STATE_FILES:
            size_guard.LIGHT_STATE_FILES.append(SESSION_NPCS_FILE)
    except Exception:
        pass

if fast_context is not None:
    try:
        fast_context.FAST_ALWAYS_FILES.update({NPC_RULES_FILE, SESSION_NPCS_FILE})
    except Exception:
        pass

rt.read_required_file_for_bundle = read_required_file_for_bundle_with_npcs
rt.lean_recommended_files_for_context = recommended_files_with_npcs
rt.build_scene_context_digest = build_scene_context_digest_with_npcs

base.recommended_files_for_context = recommended_files_with_npcs

ccp.recommended_files_for_context = recommended_files_with_npcs
ccp._read_required_file_for_bundle = read_required_file_for_bundle_with_npcs

app.version = "0.3.122-living-npc-east-social-v1"
