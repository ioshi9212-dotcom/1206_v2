"""Past/hidden visibility guard for normal gameplay rendering.

This patch prevents full past.yaml/hidden past files from being used as visible
prose material during ordinary gameplay. Past files can still be consulted during
technical/audit checks, but normal scene rendering must rely on current state,
character main/character/knowledge cards, scene continuity and visible POV.

Lightweight memory fragment files are allowed: they are not full past and only
provide short sensory/body triggers plus reaction rules.
"""
from __future__ import annotations

from typing import Any

import app.fast_context_runtime_patch as fast_context
import app.roster_identity_context_guard_runtime_patch as roster_guard
from app import compact as base

app = base.app

MEMORY_FRAGMENT_FILES = [
    "canon/relationships/akira_raiden_memory_fragments.yaml",
]

MEMORY_FRAGMENT_TRIGGER_WORDS = (
    "кольц",
    "ar",
    "гравиров",
    "помолв",
    "предложен",
    "безымян",
    "кира",
    "райден",
    "стэрлинг",
    "стерлинг",
    "стёрлинг",
    "запясть",
    "пальц",
    "косну",
    "контакт",
    "холод",
    "иней",
    "дыхан",
    "море",
    "обрыв",
    "край",
    "окно",
    "баскетбол",
    "корт",
    "мяч",
    "не помню",
    "забыл",
    "прошл",
)

TECHNICAL_AUDIT_WORDS = (
    "техническ",
    "проверь",
    "проверка",
    "аудит",
    "отчет",
    "отчёт",
    "debug",
    "диагност",
    "без продолжения сцены",
    "не продолжай сюжет",
    "не переписывай сцену",
)

GAMEPLAY_WORDS = (
    "пов:",
    "сказать",
    "посмотреть",
    "взять",
    "идти",
    "подойти",
    "ответить",
    "молчать",
    "кивнуть",
    "спросить",
)


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("ё", "е")


def _current_text(current: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "last_player_input",
        "current_scene_goal",
        "current_location_text",
        "current_scene_id",
        "scene_id",
        "last_visible_scene_text",
        "visible_scene_text",
    ):
        value = current.get(key)
        if value:
            parts.append(str(value))
    for field in getattr(roster_guard.context_transport, "CHARACTER_FIELDS", []):
        value = current.get(field)
        if isinstance(value, list):
            parts.append(" ".join(str(x) for x in value))
    return "\n".join(parts)


def is_technical_audit_context(current: dict[str, Any], include_past: bool | None = None) -> bool:
    text = _norm(_current_text(current))
    if any(word in text for word in TECHNICAL_AUDIT_WORDS):
        return True
    # include_past=true alone is not enough: old clients/GPT may set it whenever
    # a ring, memory or scar appears, which turns hidden history into visible prose.
    return False


def should_load_memory_fragments(current: dict[str, Any], ids: list[str]) -> bool:
    if not ({"akira", "raiden"} <= set(ids)):
        return False
    text = _norm(_current_text(current))
    return any(word in text for word in MEMORY_FRAGMENT_TRIGGER_WORDS)


def gameplay_needs_private_past(current: dict[str, Any], include_past: bool | None = None) -> bool:
    return is_technical_audit_context(current, include_past=include_past)


def character_files_for_context(cid: str, *, include_past: bool = False) -> list[str]:
    # For gameplay, keep behavior/knowledge fidelity but do not load past.yaml as
    # source text for narration. Technical/audit paths may opt in through the
    # module-level recommended_files_for_context below.
    folder = roster_guard._character_folder(roster_guard.canonical_id(cid))
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
    ids = roster_guard._recommended_scene_ids_from_current(current, future)
    for thread in current.get("open_threads", []) or []:
        if isinstance(thread, dict) and thread.get("status") in {"due", "active", "triggered"}:
            ids.extend(roster_guard.canonical_id(x) for x in thread.get("participants", []) or [])
    for lock in (future.get("locks") or {}).values() if isinstance(future, dict) else []:
        if isinstance(lock, dict) and lock.get("status") in {"due", "active", "triggered"}:
            ids.extend(roster_guard.canonical_id(x) for x in lock.get("participants", []) or [])
    ids = [cid for cid in roster_guard._unique(ids) if roster_guard._known_character(cid)]

    files: list[str] = [
        "runtime/scene_context_digest.md",
        "state/current_state.json",
        "state/calendar_runtime.json",
        roster_guard.SCENE_CONTINUITY_FILE,
        "gpt/locks/runtime_scene_rules_digest.md",
        roster_guard.LOCK_FILE,
        "gpt/locks/past_visibility_guard.md",
        "gpt/scene_format.md",
        "characters/character_id_index.md",
    ]

    if should_load_memory_fragments(current, ids):
        files.extend(MEMORY_FRAGMENT_FILES)

    include_past = is_technical_audit_context(current)
    for cid in ids:
        files.extend(character_files_for_context(cid, include_past=include_past))
    return roster_guard._unique([
        path for path in files
        if base.repo_file_exists(path) or path.startswith("state/") or path == "runtime/scene_context_digest.md"
    ])


def required_files_for_session_guard(session_id: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    sid = base.safe_session_id(session_id)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    current = roster_guard._sync_current_for_context(sid, current)
    future = base.read_json("state/future_locks_progress.json", sid, default={}) or {}
    return recommended_files_for_context(current, future), current, future


# Monkey-patch all context selectors after roster_guard is imported.
roster_guard._needs_past = gameplay_needs_private_past  # type: ignore[assignment]
roster_guard.character_files_for_context = character_files_for_context  # type: ignore[assignment]
roster_guard.recommended_files_for_context = recommended_files_for_context  # type: ignore[assignment]
roster_guard._required_files_for_session_guard = required_files_for_session_guard  # type: ignore[assignment]
fast_context._required_files_for_session = required_files_for_session_guard  # type: ignore[assignment]
fast_context._needs_past = gameplay_needs_private_past  # type: ignore[assignment]
base.recommended_files_for_context = recommended_files_for_context

app.version = "0.3.140-memory-fragments-v1"
