"""Runtime guard for roster, identity aliases and readable scene flow.

This patch fixes systemic scene assembly issues, not one specific scene:
- infer current active characters from visible scene/history when current_state is stale;
- bind visible Sterling/cosuh/piercing descriptors to character_id=raiden;
- keep Ray/Raiden cards loaded when they are physically present;
- keep known-name checks temporal, not retroactive;
- discourage one-word vertical prose as default output style.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import Query

import app.context_transport_runtime_patch as context_transport
import app.fast_context_runtime_patch as fast_context
import app.state_persistence_runtime_patch as state_persistence
import app.compact_context_patch as ccp
from app import compact as base

app = base.app

LOCK_FILE = "gpt/locks/roster_identity_and_style_guard.md"
SCENE_CONTINUITY_FILE = "state/scene_continuity_state.json"

ALIASES: dict[str, str] = {
    "raiden_sterling": "raiden",
    "rayden_sterling": "raiden",
    "стерлинг": "raiden",
    "стэрлинг": "raiden",
    "стёрлинг": "raiden",
    "райден стерлинг": "raiden",
    "райден стэрлинг": "raiden",
    "рейден стерлинг": "raiden",
    "рейден стэрлинг": "raiden",
    "парень с пирсингом": "raiden",
    "парень в косухе": "raiden",
    "мотоциклист": "raiden",
    "ray_carter": "ray",
    "рей картер": "ray",
    "рэй картер": "ray",
    "командующий": "ray",
    "командир поста": "ray",
    "ирей": "irey",
    "ирэй": "irey",
    "jun_carter": "jun",
    "джун картер": "jun",
}

CHECKPOINT_WORDS = (
    "главный пост",
    "пост восточного сектора",
    "восточный сектор",
    "шипы",
    "линия поста",
    "ворота",
    "кпп",
    "checkpoint",
)

RAIDEN_WORDS = (
    "стэрлинг",
    "стерлинг",
    "стёрлинг",
    "райден",
    "рейден",
    "косух",
    "пирсинг",
    "мотоцикл",
)


def _norm(text: Any) -> str:
    return str(text or "").lower().replace("ё", "е")


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def canonical_id(value: Any) -> str:
    raw = str(value or "").strip()
    lowered = _norm(raw)
    if lowered in ALIASES:
        return ALIASES[lowered]
    try:
        return context_transport.canonical_id(raw)
    except Exception:
        return raw


def _known_character(cid: str) -> bool:
    try:
        return bool(context_transport.is_known_character_id(cid))
    except Exception:
        try:
            return bool(context_transport.known_character_folder(cid))
        except Exception:
            return cid in {"akira", "jun", "irey", "emma", "raiden", "ray", "yuna", "miki"}


def _history_entries(history: Any) -> list[dict[str, Any]]:
    if isinstance(history, list):
        return [x for x in history if isinstance(x, dict)]
    if isinstance(history, dict):
        entries = history.get("entries")
        if isinstance(entries, list):
            return [x for x in entries if isinstance(x, dict)]
    return []


def _recent_history_text(session_id: str, limit: int = 3) -> str:
    history = base.read_json("state/scene_history.json", session_id, default={}) or {}
    chunks: list[str] = []
    for entry in _history_entries(history)[-limit:]:
        for key in ("location_text", "active_characters", "nearby_characters", "player_input", "visible_scene_text", "scene_text"):
            value = entry.get(key)
            if isinstance(value, list):
                chunks.append(" ".join(str(x) for x in value))
            elif value:
                chunks.append(str(value))
    return "\n".join(chunks)


def _current_text(current: dict[str, Any], extra_text: str = "") -> str:
    keys = [
        "current_scene_id",
        "scene_id",
        "current_location_id",
        "location_id",
        "current_location_text",
        "location_text",
        "current_scene_goal",
        "last_player_input",
        "last_visible_scene_text",
        "visible_scene_text",
    ]
    parts = [str(current.get(k) or "") for k in keys]
    for field in context_transport.CHARACTER_FIELDS:
        value = current.get(field)
        if isinstance(value, list):
            parts.append(" ".join(str(x) for x in value))
    if extra_text:
        parts.append(extra_text)
    return "\n".join(parts)


def _ray_named(text: str) -> bool:
    # Match Ray/Рэй as its own word. Do not let Райден/Рейден count as Ray.
    return bool(re.search(r"(?<![а-яa-z])рэй(?![а-яa-z])", text) or re.search(r"(?<![а-яa-z])рей(?!д[её]н)(?![а-яa-z])", text))


def _infer_ids_from_text(text: str) -> list[str]:
    t = _norm(text)
    ids: list[str] = []
    if "джун" in t:
        ids.append("jun")
    if "ирей" in t or "ирэй" in t:
        ids.append("irey")
    if "эмма" in t:
        ids.append("emma")
    if any(word in t for word in RAIDEN_WORDS):
        ids.append("raiden")
    if _ray_named(t) or "командующ" in t:
        ids.append("ray")
    return _unique(ids)


def infer_scene_character_ids(session_id: str, current: dict[str, Any] | None = None, extra_text: str = "") -> list[str]:
    current = current or {}
    text = _current_text(current, extra_text=extra_text) + "\n" + _recent_history_text(session_id)
    text_norm = _norm(text)
    checkpoint_scene = any(word in text_norm for word in CHECKPOINT_WORDS)

    ids: list[str] = ["akira"]
    for field in context_transport.CHARACTER_FIELDS:
        for value in current.get(field, []) or []:
            cid = canonical_id(value)
            if cid and _known_character(cid):
                ids.append(cid)

    ids.extend(_infer_ids_from_text(text))
    ids = _unique(ids)

    # If the scene has moved to the East checkpoint and Emma is not in the current
    # visible/history text, treat her as offscreen instead of keeping the stale start roster.
    if checkpoint_scene and "эмма" not in text_norm and "emma" in ids:
        ids = [cid for cid in ids if cid != "emma"]

    # At the checkpoint, visible Sterling/cosuh/piercing is not a generic NPC.
    # It is Raiden, so Raiden must be loaded whenever that descriptor is in the scene.
    if checkpoint_scene and any(word in text_norm for word in RAIDEN_WORDS) and "raiden" not in ids:
        ids.append("raiden")

    return [cid for cid in _unique(ids) if _known_character(cid)]


def _sync_current_for_context(session_id: str, current: dict[str, Any], extra_text: str = "") -> dict[str, Any]:
    ids = infer_scene_character_ids(session_id, current, extra_text=extra_text)
    text = _norm(_current_text(current, extra_text=extra_text) + "\n" + _recent_history_text(session_id))
    checkpoint_scene = any(word in text for word in CHECKPOINT_WORDS)

    changed = False
    if ids and (current.get("active_characters") != ids or current.get("active_character_ids") != ids):
        current["active_characters"] = list(ids)
        current["active_character_ids"] = list(ids)
        changed = True

    nearby = [cid for cid in ids if cid != "akira"]
    if current.get("nearby_characters") != nearby or current.get("nearby_character_ids") != nearby:
        current["nearby_characters"] = list(nearby)
        current["nearby_character_ids"] = list(nearby)
        changed = True

    if checkpoint_scene:
        if current.get("current_location_id") in {None, "", "road_near_jun_house", "jun_house", "jun_house_akira_room"}:
            current["current_location_id"] = "east_sector_main_gate_checkpoint"
            current["location_id"] = "east_sector_main_gate_checkpoint"
            changed = True
        if not current.get("current_location_text") or "пост" not in _norm(current.get("current_location_text")):
            current["current_location_text"] = "Восточный сектор, главный пост"
            changed = True

    if changed:
        base.write_json("state/current_state.json", current, session_id)
    return current


def _character_folder(cid: str) -> str | None:
    try:
        return context_transport.known_character_folder(cid)
    except Exception:
        return cid if cid in {"akira", "jun", "irey", "emma", "raiden", "ray", "yuna", "miki"} else None


def _needs_past(current: dict[str, Any], include_past: bool | None = None) -> bool:
    try:
        return bool(fast_context._needs_past(current, include_past))
    except Exception:
        text = _norm(_current_text(current))
        return any(word in text for word in ("прошл", "памят", "саму", "кольц", "эхо", "шрам"))


def character_files_for_context(cid: str, *, include_past: bool = False) -> list[str]:
    folder = _character_folder(canonical_id(cid))
    if not folder:
        return []
    candidates = [
        f"characters/{folder}/main.yaml",
        f"characters/{folder}/character.yaml",
        f"characters/{folder}/knowledge.yaml",
    ]
    if include_past:
        candidates.append(f"characters/{folder}/past.yaml")
    return [path for path in candidates if base.repo_file_exists(path)]


def recommended_files_for_context(current: dict[str, Any] | None = None, future: dict[str, Any] | None = None) -> list[str]:
    current = current or {}
    future = future or {}
    ids: list[str] = ["akira"]
    for field in context_transport.CHARACTER_FIELDS:
        for value in current.get(field, []) or []:
            cid = canonical_id(value)
            if cid and _known_character(cid):
                ids.append(cid)
    ids.extend(_infer_ids_from_text(_current_text(current)))
    for thread in current.get("open_threads", []) or []:
        if isinstance(thread, dict) and thread.get("status") in {"due", "active", "triggered"}:
            ids.extend(canonical_id(x) for x in thread.get("participants", []) or [])
    for lock in (future.get("locks") or {}).values() if isinstance(future, dict) else []:
        if isinstance(lock, dict) and lock.get("status") in {"due", "active", "triggered"}:
            ids.extend(canonical_id(x) for x in lock.get("participants", []) or [])
    ids = [cid for cid in _unique(ids) if _known_character(cid)]

    files: list[str] = [
        "runtime/scene_context_digest.md",
        "state/current_state.json",
        "state/calendar_runtime.json",
        "state/scene_continuity_state.json",
        "gpt/locks/runtime_scene_rules_digest.md",
        LOCK_FILE,
        "gpt/scene_format.md",
        "characters/character_id_index.md",
    ]
    include_past = _needs_past(current, None)
    for cid in ids:
        files.extend(character_files_for_context(cid, include_past=include_past))
    return _unique([path for path in files if base.repo_file_exists(path) or path.startswith("state/") or path == "runtime/scene_context_digest.md"])


def _required_files_for_session_guard(session_id: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    sid = base.safe_session_id(session_id)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    current = _sync_current_for_context(sid, current)
    future = base.read_json("state/future_locks_progress.json", sid, default={}) or {}
    files = recommended_files_for_context(current, future)
    return files, current, future


def _visible_text_from_request(request: Any) -> str:
    values: list[Any] = [getattr(request, "visible_scene_text", None), getattr(request, "final_scene_text", None), getattr(request, "scene_text", None)]
    data = getattr(request, "data", None)
    if isinstance(data, dict):
        values.extend([data.get("visible_scene_text"), data.get("final_scene_text"), data.get("scene_text")])
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


# Patch aliases / selectors used by earlier runtime layers.
context_transport.ID_ALIASES.update(ALIASES)
context_transport.canonical_id = canonical_id  # type: ignore[assignment]
context_transport.character_files_for_context = character_files_for_context  # type: ignore[assignment]
context_transport.lean_recommended_files_for_context = recommended_files_for_context  # type: ignore[assignment]
context_transport.scene_character_ids = lambda current=None, future=None: recommended_scene_ids_from_current(current or {}, future or {})  # type: ignore[assignment]
base.recommended_files_for_context = recommended_files_for_context
base.active_scene_characters = lambda current=None, future=None: recommended_scene_ids_from_current(current or {}, future or {})
ccp.recommended_files_for_context = recommended_files_for_context  # type: ignore[assignment]
ccp.active_scene_characters = lambda current=None, future=None: recommended_scene_ids_from_current(current or {}, future or {})  # type: ignore[assignment]

# Make hidden physical continuity available to fast context; it is compact state,
# not visible header text.
try:
    fast_context.FAST_ALWAYS_FILES.add(SCENE_CONTINUITY_FILE)
    fast_context.FAST_ALWAYS_FILES.add(LOCK_FILE)
except Exception:
    pass
fast_context._required_files_for_session = _required_files_for_session_guard  # type: ignore[assignment]


def recommended_scene_ids_from_current(current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    # Session-independent fallback used by older helpers. It cannot read history,
    # so it relies on current fields only.
    ids: list[str] = ["akira"]
    for field in context_transport.CHARACTER_FIELDS:
        for value in current.get(field, []) or []:
            cid = canonical_id(value)
            if cid and _known_character(cid):
                ids.append(cid)
    ids.extend(_infer_ids_from_text(_current_text(current)))
    return [cid for cid in _unique(ids) if _known_character(cid)]


# Replace applyTurnResult with a wrapper that syncs roster/location from visible text
# before the normal persistence layer writes scene history.
fast_context._remove_routes(ccp.APPLY_TURN_RESULT_PATH, {"POST"}, "applyTurnResult")


@app.post(ccp.APPLY_TURN_RESULT_PATH, response_model=ccp.ApplyTurnResultWithVisibleSceneResponse, operation_id="applyTurnResult")
def apply_turn_result_with_roster_guard(session_id: str, request: ccp.ApplyTurnResultWithVisibleSceneRequest = ccp.ApplyTurnResultWithVisibleSceneRequest()):
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    visible_text = _visible_text_from_request(request)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    _sync_current_for_context(sid, current, extra_text=visible_text)
    return state_persistence.apply_turn_result_persistent(session_id, request)


# Replace turn-contract route so the exposed roster is synced before GPT renders.
fast_context._remove_routes(fast_context.TURN_CONTRACT_PATH, {"GET"}, "getSessionTurnContract")


@app.get(fast_context.TURN_CONTRACT_PATH, operation_id="getSessionTurnContract")
def get_session_turn_contract_roster_guard(session_id: str) -> dict[str, Any]:
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    current = _sync_current_for_context(sid, current)
    data = fast_context.get_session_turn_contract_fast_hint(sid)
    ids = infer_scene_character_ids(sid, current)
    data["active_character_ids"] = ids
    data["nearby_character_ids"] = [cid for cid in ids if cid != "akira"]
    data.setdefault("required_checks_before_answer", [])
    data["required_checks_before_answer"] = _unique(list(data["required_checks_before_answer"]) + [
        "Known names are time-scoped: use a personal name only if the current POV or speaking NPC had that name before the line being rendered.",
        "A later line in scene history cannot retroactively justify an earlier name use.",
        "Visible Sterling/cosuh/piercing descriptors bind to character_id=raiden; do not treat him as a generic NPC.",
        "Default prose uses readable paragraphs; isolated one-line fragments are reserved for dialogue, sharp beats, or hard stops.",
    ])
    contract = data.setdefault("output_format_contract", {})
    if isinstance(contract, dict):
        rules = list(contract.get("rules", []) or [])
        rules.extend([
            "Do not write the scene as a vertical stack of tiny fragments; group connected visible action into readable paragraphs.",
            "A paragraph should normally carry a complete visible beat: movement, reaction, consequence, or pressure shift.",
        ])
        contract["rules"] = _unique(rules)
    return data


# Re-register fast context route so sync also happens when the client calls it directly.
fast_context._remove_routes(fast_context.FAST_CONTEXT_PATH, {"GET"}, "getFastRenderContext")


@app.get(fast_context.FAST_CONTEXT_PATH, operation_id="getFastRenderContext")
def get_fast_render_context_roster_guard(
    session_id: str,
    max_total_chars: int = Query(default=26000, ge=12000, le=42000),
    per_file_chars: int = Query(default=4500, ge=1800, le=8000),
    include_past: bool | None = Query(default=None),
) -> dict[str, Any]:
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    current = _sync_current_for_context(sid, current)
    required_files, current, future = _required_files_for_session_guard(sid)
    loaded_files, skipped_files, truncated = fast_context._build_fast_loaded_files(
        sid,
        required_files,
        current,
        max_total_chars=max_total_chars,
        per_file_chars=per_file_chars,
        include_past=include_past,
    )
    ids = infer_scene_character_ids(sid, current)
    return {
        "success": True,
        "session_id": sid,
        "mode": "fast_render_context_roster_identity_guard_v1",
        "runtime_version": app.version,
        "quality_mode": "sync_roster_then_preserve_character_fidelity",
        "active_character_ids": ids,
        "nearby_character_ids": [cid for cid in ids if cid != "akira"],
        "context_files_total": len(required_files),
        "loaded_files": loaded_files,
        "loaded_count": len(loaded_files),
        "skipped_files": skipped_files,
        "skipped_count": len(skipped_files),
        "truncated": truncated,
        "needs_full_context": False,
        "past_context_loaded": _needs_past(current, include_past),
        "render_rules": [
            "Render from the synced roster and loaded character files, not stale start-scene roster.",
            "Known names are temporal and POV-bound; do not retroactively justify earlier name use from later lines.",
            "Sterling/cosuh/piercing descriptors are Raiden identity anchors for backend loading, not a generic NPC.",
            "Use readable paragraphs; avoid default one-word/one-clause vertical prose.",
            "Do not show API/debug/status in visible gameplay.",
            "After scene, call applyTurnResult with explicit state changes if anything meaningful changed.",
        ],
    }


app.version = "0.3.138-roster-identity-context-guard-v1"
