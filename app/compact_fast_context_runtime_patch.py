"""Compact fast-render-context response patch for 1206_v2.

Purpose:
- keep essential active/speaking/nearby character cards in the context first;
- make /fast-render-context small enough for ChatGPT Actions;
- avoid old diagnostic chunk/file-loader gameplay loops.

This patch does not add locks and does not contain scene examples.
Import after fast_context_runtime_patch and after optional character-priority patches.
"""
from __future__ import annotations

from typing import Any

from fastapi import Query

import app.fast_context_runtime_patch as fast_context
from app import compact as base

try:
    import app.roster_identity_context_guard_runtime_patch as roster_guard
except Exception:  # pragma: no cover - optional runtime patch
    roster_guard = None  # type: ignore[assignment]

app = base.app

FAST_CONTEXT_PATH = getattr(fast_context, "FAST_CONTEXT_PATH", "/api/v1/sessions/{session_id}/fast-render-context")

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
    "expected_speakers",
    "last_speaker_ids",
    "last_speakers",
)

BASE_FIRST_FILES = (
    "runtime/scene_context_digest.md",
    "state/current_state.json",
    "characters/character_id_index.md",
    "state/scene_continuity_state.json",
)

SOFT_SUPPORT_FILES = (
    "gpt/scene_format.md",
    "gpt/locks/runtime_scene_rules_digest.md",
    "canon/character_depth_and_rotation.md",
    "gpt/locks/roster_identity_and_style_guard.md",
    "gpt/locks/past_visibility_guard.md",
)

MAX_SKIPPED_RETURNED = 24


def _safe_session_id(session_id: str) -> str:
    try:
        return fast_context._safe_session_id(session_id)  # type: ignore[attr-defined]
    except Exception:
        return base.safe_session_id(session_id)


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(x) for x in value if str(x or "").strip()]
    return []


def _canonical_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if roster_guard is not None:
        try:
            return str(roster_guard.canonical_id(raw))  # type: ignore[attr-defined]
        except Exception:
            pass
    return raw.removeprefix("char_").strip().lower()


def _known_character(cid: str) -> bool:
    if not cid:
        return False
    if roster_guard is not None:
        try:
            return bool(roster_guard._known_character(cid))  # type: ignore[attr-defined]
        except Exception:
            pass
    return base.repo_file_exists(f"characters/{cid}/main.yaml") or base.repo_file_exists(f"characters/{cid}/character.yaml")


def _character_folder(cid: str) -> str:
    if roster_guard is not None:
        try:
            folder = roster_guard._character_folder(cid)  # type: ignore[attr-defined]
            if folder:
                return str(folder)
        except Exception:
            pass
    return cid


def _repo_or_state_exists(path: str) -> bool:
    if path.startswith("state/") or path == "runtime/scene_context_digest.md":
        return True
    try:
        return bool(base.repo_file_exists(path))
    except Exception:
        return False


def _character_core_files(cid: str) -> list[str]:
    cid = _canonical_id(cid)
    if not _known_character(cid):
        return []
    folder = _character_folder(cid)
    candidates = [
        f"characters/{folder}/main.yaml",
        f"characters/{folder}/character.yaml",
        f"characters/{folder}/knowledge.yaml",
    ]
    return [path for path in candidates if _repo_or_state_exists(path)]


def _ids_from_current(current: dict[str, Any], future: dict[str, Any] | None = None) -> list[str]:
    ids: list[str] = []

    # Prefer the roster guard inference when it is available: it can infer
    # characters from visible scene text, aliases and stale current_state.
    if roster_guard is not None:
        try:
            ids.extend(str(x) for x in roster_guard._recommended_scene_ids_from_current(current, future or {}))  # type: ignore[attr-defined]
        except Exception:
            pass

    for field in CHARACTER_FIELDS:
        ids.extend(_as_list(current.get(field)))

    for thread in current.get("open_threads", []) or []:
        if isinstance(thread, dict) and thread.get("status") in {"due", "active", "triggered"}:
            ids.extend(_as_list(thread.get("participants")))

    if isinstance(future, dict):
        for lock in (future.get("locks") or {}).values():
            if isinstance(lock, dict) and lock.get("status") in {"due", "active", "triggered"}:
                ids.extend(_as_list(lock.get("participants")))

    return [cid for cid in _unique([_canonical_id(x) for x in ids]) if _known_character(cid)]


def _essential_character_files(current: dict[str, Any], future: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    ids = _ids_from_current(current, future)
    files: list[str] = []
    for cid in ids:
        files.extend(_character_core_files(cid))
    return ids, _unique(files)


def _reordered_required_files(required_files: list[str], current: dict[str, Any], future: dict[str, Any] | None = None) -> tuple[list[str], list[str], list[str]]:
    ids, essential = _essential_character_files(current, future)

    front: list[str] = []
    front.extend([path for path in BASE_FIRST_FILES if _repo_or_state_exists(path)])
    front.extend(essential)
    front.extend([path for path in SOFT_SUPPORT_FILES if _repo_or_state_exists(path)])

    # Keep remaining files available, but after essential character files.
    return _unique(front + list(required_files)), ids, essential


def _is_past_file(path: str) -> bool:
    try:
        return bool(fast_context._is_past_file(path))  # type: ignore[attr-defined]
    except Exception:
        lowered = path.lower()
        return lowered.endswith("/past.yaml") or lowered.endswith("/past.yml") or "hidden_past" in lowered


def _needs_past(current: dict[str, Any], include_past: bool | None) -> bool:
    try:
        return bool(fast_context._needs_past(current, include_past))  # type: ignore[attr-defined]
    except Exception:
        return bool(include_past)


def _is_fast_context_file(path: str, current: dict[str, Any], include_past: bool | None, essential: set[str]) -> bool:
    if path in essential:
        return True
    if path in BASE_FIRST_FILES or path in SOFT_SUPPORT_FILES:
        return True
    try:
        return bool(fast_context._is_fast_context_file(path, current, include_past))  # type: ignore[attr-defined]
    except Exception:
        pass
    if path.startswith("characters/"):
        if _is_past_file(path) and not _needs_past(current, include_past):
            return False
        return path.endswith((".yaml", ".yml", ".md"))
    return False


def _read_required_file(path: str, session_id: str) -> tuple[str | None, str | None]:
    try:
        return fast_context._read_required_file(path, session_id)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if path.startswith("state/"):
            return base.read_text(path, session_id=session_id), "session"
        return base.read_text(path), "project"
    except Exception:
        return None, None


def _cut_text(text: str, limit: int) -> tuple[str, bool]:
    limit = max(400, int(limit or 1200))
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "\n...[truncated]", True


def _budget_for(path: str, *, remaining: int, per_file_chars: int, is_essential: bool) -> int:
    if remaining <= 0:
        return 0

    if path == "runtime/scene_context_digest.md":
        base_limit = min(per_file_chars, 1600)
    elif path == "state/current_state.json":
        base_limit = min(per_file_chars, 1400)
    elif path.endswith("/main.yaml"):
        base_limit = 1200 if is_essential else 800
    elif path.endswith("/character.yaml"):
        base_limit = 1900 if is_essential else 1000
    elif path.endswith("/knowledge.yaml"):
        base_limit = 1900 if is_essential else 1000
    elif path in SOFT_SUPPORT_FILES:
        base_limit = min(per_file_chars, 1000)
    else:
        base_limit = min(per_file_chars, 900)

    return max(300, min(int(base_limit), int(remaining)))


def _build_compact_loaded_files(
    session_id: str,
    required_files: list[str],
    current: dict[str, Any],
    future: dict[str, Any] | None = None,
    *,
    max_total_chars: int,
    per_file_chars: int,
    include_past: bool | None,
) -> tuple[list[dict[str, Any]], list[str], bool, list[str], list[str], list[str]]:
    try:
        max_total_chars = max(8000, min(int(max_total_chars or 16000), 32000))
    except Exception:
        max_total_chars = 16000
    try:
        per_file_chars = max(900, min(int(per_file_chars or 1800), 3500))
    except Exception:
        per_file_chars = 1800

    required_files, essential_ids, essential_files = _reordered_required_files(required_files, current, future)
    essential_set = set(essential_files)

    fast_files = [
        path for path in required_files
        if _is_fast_context_file(path, current, include_past, essential_set)
    ]

    loaded: list[dict[str, Any]] = []
    skipped: list[str] = []
    used = 0
    truncated = False
    missing_essential: list[str] = []

    for path in fast_files:
        content, _source = _read_required_file(path, session_id)
        if content is None:
            skipped.append(path)
            if path in essential_set:
                missing_essential.append(path)
            continue

        remaining = max_total_chars - used
        if remaining <= 0:
            skipped.append(path)
            truncated = True
            continue

        limit = _budget_for(path, remaining=remaining, per_file_chars=per_file_chars, is_essential=path in essential_set)
        cut, was_cut = _cut_text(content, limit)
        loaded.append({"path": path, "content": cut})
        used += len(cut)
        truncated = truncated or was_cut

    for path in required_files:
        if path not in fast_files and path not in skipped:
            skipped.append(path)

    return loaded, _unique(skipped), truncated, essential_ids, essential_files, _unique(missing_essential)


def _remove_fast_route() -> None:
    try:
        fast_context._remove_routes(FAST_CONTEXT_PATH, {"GET"}, "getFastRenderContext")  # type: ignore[attr-defined]
        return
    except Exception:
        pass

    keep = []
    for route in list(app.router.routes):
        if getattr(route, "path", None) == FAST_CONTEXT_PATH and "GET" in set(getattr(route, "methods", set()) or set()):
            continue
        keep.append(route)
    app.router.routes = keep


_remove_fast_route()


@app.get(FAST_CONTEXT_PATH, operation_id="getFastRenderContext")
def get_fast_render_context_compact(
    session_id: str,
    max_total_chars: int = Query(default=16000, ge=8000, le=32000),
    per_file_chars: int = Query(default=1800, ge=900, le=3500),
    include_past: bool | None = Query(default=None),
) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)

    required_files, current, future = fast_context._required_files_for_session(sid)  # type: ignore[attr-defined]
    loaded_files, skipped_files, truncated, essential_ids, essential_files, missing_essential = _build_compact_loaded_files(
        sid,
        required_files,
        current,
        future,
        max_total_chars=max_total_chars,
        per_file_chars=per_file_chars,
        include_past=include_past,
    )

    skipped_count = len(skipped_files)
    skipped_sample = skipped_files[:MAX_SKIPPED_RETURNED]

    return {
        "success": True,
        "session_id": sid,
        "mode": "fast_render_context_compact_v1",
        "runtime_version": "0.3.143-compact-fast-context-v1",
        "quality_mode": "compact_response_essential_character_cards_first",
        "active_character_ids": current.get("active_character_ids") or current.get("active_characters") or [],
        "nearby_character_ids": current.get("nearby_character_ids") or current.get("nearby_characters") or [],
        "essential_character_ids": essential_ids,
        "essential_character_files_expected": essential_files,
        "essential_character_files_missing": missing_essential,
        "context_files_total": len(required_files),
        "loaded_files": loaded_files,
        "loaded_count": len(loaded_files),
        "skipped_files": skipped_sample,
        "skipped_count": skipped_count,
        "skipped_files_truncated": skipped_count > len(skipped_sample),
        "truncated": truncated,
        "needs_full_context": bool(missing_essential),
        "past_context_loaded": _needs_past(current, include_past),
        "render_rules": [
            "Render only from loaded files, visible state, and character knowledge present in this response.",
            "If essential_character_files_missing is not empty, stop gameplay and report missing character context.",
            "After meaningful scene changes, call applyTurnResult.",
        ],
    }


try:
    app.version = "0.3.143-compact-fast-context-v1"
except Exception:
    pass
