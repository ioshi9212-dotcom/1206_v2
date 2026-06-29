from __future__ import annotations

"""Fast context/runtime cache patch for 1206_v2.

Goal:
- keep scene quality and character fidelity;
- stop forcing GPT to reload every required file chunk on every ordinary turn;
- keep old manifest/chunk endpoints compatible, but cache their heavy bundle;
- add getFastRenderContext for normal gameplay turns.

Import this patch after response_size_guard_runtime_patch and character_entry_runtime_patch
in app/production_runtime_patch.py.
"""

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Query

import app.response_size_guard_runtime_patch as size_guard
from app import compact as base

app = base.app

TURN_CONTRACT_PATH = "/api/v1/sessions/{session_id}/turn-contract"
MANIFEST_PATH = "/api/v1/sessions/{session_id}/required-files-manifest"
CHUNK_PATH = "/api/v1/sessions/{session_id}/required-files-chunk"
BUNDLE_PATH = "/api/v1/sessions/{session_id}/required-files-bundle"
FAST_CONTEXT_PATH = "/api/v1/sessions/{session_id}/fast-render-context"

CACHE_TTL_SECONDS = 15 * 60
CACHE_MAX_ENTRIES = 64
DEFAULT_CHUNK_CHARS = 30000
DEFAULT_CHUNK_ITEMS = 3
DEFAULT_FILE_PART_CHARS = 11000

PAST_TRIGGER_WORDS = {
    "прошл", "памят", "вспом", "забы", "кольц", "шрам", "ребен", "ребён",
    "берем", "саму", "лаборатор", "эксперимент", "кайрос", "поток", "сон",
    "кошмар", "пространство между", "самоблок", "срыв", "эхо", "наблюдател",
}

FAST_ALWAYS_FILES = {
    "runtime/scene_context_digest.md",
    "gpt/locks/runtime_scene_rules_digest.md",
    "gpt/scene_format.md",
    "state/current_state.json",
    "state/calendar_runtime.json",
}

FAST_STATE_SLICES = {
    "state/relationships.json",
    "state/knowledge_state.json",
    "state/story_lines.json",
    "state/inventory_state.json",
    "state/future_locks_progress.json",
}


@dataclass
class CachedBundle:
    created_at: float
    key: str
    required_files: list[str]
    loaded_parts: list[dict[str, Any]]
    manifest: list[dict[str, Any]]
    missing_files: list[str]


_REQUIRED_BUNDLE_CACHE: dict[str, CachedBundle] = {}
_ORIGINAL_TURN_CONTRACT = getattr(size_guard, "get_session_turn_contract_size_guard", None)


def _remove_routes(path: str, methods: set[str] | None = None, operation_id: str | None = None) -> None:
    keep = []
    for route in app.router.routes:
        route_path = getattr(route, "path", None)
        route_methods = set(getattr(route, "methods", set()) or set())
        route_operation_id = getattr(route, "operation_id", None)
        match_path = route_path == path
        match_methods = methods is None or bool(route_methods & methods)
        match_operation = operation_id is None or route_operation_id == operation_id
        if match_path and match_methods and match_operation:
            continue
        keep.append(route)
    app.router.routes = keep


def _safe_session_id(session_id: str) -> str:
    return base.safe_session_id(session_id)


def _read_json(path: str, session_id: str, default: Any) -> Any:
    try:
        return base.read_json(path, session_id, default=default) or default
    except Exception:
        return default


def _required_files_for_session(session_id: str) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    current = _read_json("state/current_state.json", session_id, {})
    future = _read_json("state/future_locks_progress.json", session_id, {})
    try:
        files = list(base.recommended_files_for_context(current, future))
    except Exception:
        try:
            files = list(size_guard._required_files(current, future))  # type: ignore[attr-defined]
        except Exception:
            files = []
    return _unique(files), current, future


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _locate_file(path: str, session_id: str | None = None) -> Path | None:
    safe = str(path).strip().lstrip("/")
    candidates: list[Path] = []
    if session_id and safe.startswith("state/"):
        try:
            candidates.append(base.session_dir(session_id) / safe)
        except Exception:
            pass
    for root in [getattr(base, "DATA", None), getattr(base, "ROOT", None)]:
        if root:
            candidates.append(Path(root) / safe)
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def _file_stat_signature(path: str, session_id: str) -> dict[str, Any]:
    # Runtime digest is generated from state slices, so it needs state signatures.
    if path == "runtime/scene_context_digest.md":
        state_paths = [
            "state/current_state.json",
            "state/story_lines.json",
            "state/relationships.json",
            "state/knowledge_state.json",
            "state/inventory_state.json",
            "state/calendar_runtime.json",
            "state/future_locks_progress.json",
        ]
        return {
            "path": path,
            "runtime_sources": [_file_stat_signature(p, session_id) for p in state_paths],
        }

    file = _locate_file(path, session_id)
    if not file:
        return {"path": path, "exists": False}
    try:
        stat = file.stat()
        return {"path": path, "exists": True, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    except Exception:
        return {"path": path, "exists": True, "stat": "unavailable"}


def _cache_key(session_id: str, required_files: list[str]) -> str:
    signature = {
        "session_id": session_id,
        "required_files": required_files,
        "files": [_file_stat_signature(path, session_id) for path in required_files],
    }
    raw = json.dumps(signature, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cleanup_cache() -> None:
    now = time.time()
    expired = [key for key, value in _REQUIRED_BUNDLE_CACHE.items() if now - value.created_at > CACHE_TTL_SECONDS]
    for key in expired:
        _REQUIRED_BUNDLE_CACHE.pop(key, None)
    if len(_REQUIRED_BUNDLE_CACHE) <= CACHE_MAX_ENTRIES:
        return
    oldest = sorted(_REQUIRED_BUNDLE_CACHE.items(), key=lambda item: item[1].created_at)
    for key, _value in oldest[: max(0, len(_REQUIRED_BUNDLE_CACHE) - CACHE_MAX_ENTRIES)]:
        _REQUIRED_BUNDLE_CACHE.pop(key, None)


def _read_required_file(path: str, session_id: str) -> tuple[str | None, str | None]:
    try:
        return size_guard._read_required_file(path, session_id)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if str(path).startswith("state/"):
            return base.read_text(path, session_id=session_id), "session"
        return base.read_text(path), "project"
    except Exception:
        return None, None


def _split_text(content: str, part_chars: int = DEFAULT_FILE_PART_CHARS) -> list[str]:
    try:
        limit = max(7000, min(int(part_chars or DEFAULT_FILE_PART_CHARS), 16000))
    except Exception:
        limit = DEFAULT_FILE_PART_CHARS
    if not content:
        return [""]
    return [content[i:i + limit] for i in range(0, len(content), limit)]


def _build_required_bundle(session_id: str, required_files: list[str]) -> CachedBundle:
    key = _cache_key(session_id, required_files)
    cached = _REQUIRED_BUNDLE_CACHE.get(key)
    if cached and time.time() - cached.created_at <= CACHE_TTL_SECONDS:
        return cached

    loaded_parts: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    missing_files: list[str] = []

    for path in required_files:
        content, source = _read_required_file(path, session_id)
        if content is None:
            missing_files.append(path)
            manifest.append({"path": path, "exists": False, "source": "missing", "size_chars": 0, "parts_total": 0})
            continue
        pieces = _split_text(content)
        manifest.append({
            "path": path,
            "exists": True,
            "source": source or "project",
            "size_chars": len(content),
            "parts_total": len(pieces),
        })
        for index, piece in enumerate(pieces):
            loaded_parts.append({
                "path": path,
                "content": piece,
                "part_index": index,
                "parts_total": len(pieces),
                "content_chars": len(piece),
            })

    bundle = CachedBundle(
        created_at=time.time(),
        key=key,
        required_files=required_files,
        loaded_parts=loaded_parts,
        manifest=manifest,
        missing_files=missing_files,
    )
    _REQUIRED_BUNDLE_CACHE[key] = bundle
    _cleanup_cache()
    return bundle


def _light_manifest_item(path: str, session_id: str) -> dict[str, Any]:
    if path == "runtime/scene_context_digest.md":
        # Dynamic file: do not build it during manifest. It will be generated once in cached chunk/context.
        return {"path": path, "exists": True, "source": "runtime", "size_chars": 0, "parts_total": 1, "lazy": True}
    file = _locate_file(path, session_id)
    if not file:
        return {"path": path, "exists": False, "source": "missing", "size_chars": 0, "parts_total": 0}
    try:
        size = file.stat().st_size
    except Exception:
        size = 0
    # UTF-8 bytes are not exact chars, but enough for a cheap manifest estimate.
    parts = max(1, (int(size) + DEFAULT_FILE_PART_CHARS - 1) // DEFAULT_FILE_PART_CHARS) if size else 1
    source = "session" if str(path).startswith("state/") else "project"
    return {"path": path, "exists": True, "source": source, "size_chars": int(size), "parts_total": int(parts), "lazy": True}


def _chunk_loaded_parts(loaded_parts: list[dict[str, Any]], *, max_chars: int, max_items: int) -> list[list[dict[str, Any]]]:
    max_chars = max(16000, min(int(max_chars or DEFAULT_CHUNK_CHARS), 32000))
    max_items = max(1, min(int(max_items or DEFAULT_CHUNK_ITEMS), 3))
    chunks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for part in loaded_parts:
        part_chars = len(str(part.get("content") or ""))
        if current and (len(current) >= max_items or current_chars + part_chars > max_chars):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(part)
        current_chars += part_chars
    if current:
        chunks.append(current)
    return chunks


def _lower_turn_text(current: dict[str, Any]) -> str:
    parts = [
        current.get("last_player_input"),
        current.get("current_scene_goal"),
        current.get("current_location_text"),
        current.get("akira_state"),
    ]
    return "\n".join(str(p or "") for p in parts).lower().replace("ё", "е")


def _needs_past(current: dict[str, Any], include_past: bool | None) -> bool:
    if include_past is True:
        return True
    if include_past is False:
        return False
    text = _lower_turn_text(current)
    return any(word in text for word in PAST_TRIGGER_WORDS)


def _is_character_file(path: str) -> bool:
    return path.startswith("characters/") and path.endswith(('.yaml', '.yml', '.md'))


def _is_past_file(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith("/past.yaml") or lowered.endswith("/past.yml") or lowered.endswith("/past.md") or "hidden_past" in lowered


def _is_fast_context_file(path: str, current: dict[str, Any], include_past: bool | None) -> bool:
    if path in FAST_ALWAYS_FILES:
        return True
    if path in FAST_STATE_SLICES:
        # These are already summarized inside runtime digest / turn contract for normal turns.
        return False
    if _is_character_file(path):
        if _is_past_file(path) and not _needs_past(current, include_past):
            return False
        return True
    if path.startswith("calendar/days/") or path.startswith("engine/"):
        return True
    if path.startswith("canon_lore/"):
        # Lore index can be useful, but avoid heavy hidden lore by default.
        return path.endswith("index.yaml") or "hidden_lore_policy" in path
    return False


def _cut_text(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "\n...[truncated]", True


def _build_fast_loaded_files(
    session_id: str,
    required_files: list[str],
    current: dict[str, Any],
    *,
    max_total_chars: int,
    per_file_chars: int,
    include_past: bool | None,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    max_total_chars = max(24000, min(int(max_total_chars or 45000), 70000))
    per_file_chars = max(2500, min(int(per_file_chars or 8000), 14000))
    loaded: list[dict[str, Any]] = []
    skipped: list[str] = []
    used = 0
    truncated = False

    fast_files = [path for path in required_files if _is_fast_context_file(path, current, include_past)]
    for path in required_files:
        if path not in fast_files:
            skipped.append(path)

    # Keep runtime digest first, then state/rules, then characters.
    priority = {"runtime/scene_context_digest.md": 0, "state/current_state.json": 1, "gpt/locks/runtime_scene_rules_digest.md": 2, "gpt/scene_format.md": 3}
    fast_files = sorted(fast_files, key=lambda p: (priority.get(p, 20), p))

    for path in fast_files:
        content, source = _read_required_file(path, session_id)
        if content is None:
            skipped.append(path)
            continue
        remaining = max_total_chars - used
        if remaining <= 0:
            skipped.append(path)
            truncated = True
            continue
        limit = min(per_file_chars, remaining)
        cut, was_cut = _cut_text(content, limit)
        loaded.append({
            "path": path,
            "source": source or ("session" if path.startswith("state/") else "project"),
            "content": cut,
            "content_chars_original": len(content),
            "content_chars_in_context": len(cut),
            "truncated_in_context": was_cut,
        })
        used += len(cut)
        truncated = truncated or was_cut

    return loaded, _unique(skipped), truncated


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    return value


_remove_routes(TURN_CONTRACT_PATH, {"GET"}, "getSessionTurnContract")
_remove_routes(MANIFEST_PATH, {"GET"}, "getRequiredFilesManifest")
_remove_routes(CHUNK_PATH, {"GET"}, "getRequiredFilesChunk")
_remove_routes(BUNDLE_PATH, {"GET"}, "getRequiredFilesBundle")
_remove_routes(FAST_CONTEXT_PATH, {"GET"}, "getFastRenderContext")


@app.get(TURN_CONTRACT_PATH, operation_id="getSessionTurnContract")
def get_session_turn_contract_fast_hint(session_id: str) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)
    current = _read_json("state/current_state.json", sid, {})
    future = _read_json("state/future_locks_progress.json", sid, {})
    all_required_files, _current, _future = _required_files_for_session(sid)
    fast_file_hints = [path for path in all_required_files if _is_fast_context_file(path, current, include_past=None)]

    if _ORIGINAL_TURN_CONTRACT is not None:
        try:
            data = _to_plain(_ORIGINAL_TURN_CONTRACT(sid))
        except Exception as exc:
            data = {"session_id": sid, "error": str(exc)}
    else:
        data = {
            "session_id": sid,
            "active_character_ids": current.get("active_characters", []) or current.get("active_character_ids", []),
            "nearby_character_ids": current.get("nearby_characters", []) or current.get("nearby_character_ids", []),
            "future_locks_progress": future,
        }

    # IMPORTANT: do not expose the full required file list as a to-do list.
    # The model was treating it as an instruction to call every chunk and could
    # spend many minutes "talking to the repo". getFastRenderContext is the only
    # normal-turn loader; full chunks are hidden/diagnostic fallback.
    data["required_files"] = []
    data["fast_context_file_hints"] = fast_file_hints[:24]
    data["full_required_files_count"] = len(all_required_files)
    data["fast_context_available"] = True
    data["preferred_next_action"] = "getFastRenderContext"
    data["required_checks_before_answer"] = [
        "Call getFastRenderContext next for normal gameplay and render from it.",
        "Do not call required-files manifest/chunk in normal gameplay.",
        "Use full file chunks only during explicit diagnostics or manual audit, not during scene rendering.",
    ]
    data["prompt_preview"] = (
        "PLAY MODE 1206 FAST ONLY BRIEF\n"
        "- Call getFastRenderContext for this session_id before rendering normal gameplay.\n"
        "- Render from fast context: runtime digest + active character files + compact state slices.\n"
        "- Do not call required-files manifest/chunk for ordinary movement, dialogue, medical checks, or scene continuation.\n"
        "- If context is missing, continue from the fast context and visible state; ask for full audit only outside gameplay.\n"
        "- Preserve character fidelity and output the gameplay scene only.\n"
    )
    data["usage_note"] = "Normal gameplay uses getFastRenderContext only. Full chunks are diagnostic-only and hidden from the action schema."
    return data


@app.get(MANIFEST_PATH, operation_id="getRequiredFilesManifest")
def get_required_files_manifest_light(session_id: str) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)
    # Diagnostic endpoint kept for backward compatibility only. It intentionally
    # does not return a chunk plan, so the model cannot enter a long loading loop.
    return {
        "session_id": sid,
        "mode": "diagnostic_disabled_for_normal_gameplay",
        "cache_enabled": True,
        "required_files": [],
        "files": [],
        "missing_files": [],
        "loaded_count": 0,
        "missing_count": 0,
        "total_parts": 0,
        "chunks_total": 0,
        "usage_note": "Use getFastRenderContext. Full manifest/chunk loading is disabled for normal gameplay.",
    }


def _required_files_chunk_cached_response(
    session_id: str,
    *,
    chunk_index: int = 0,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    max_items: int = DEFAULT_CHUNK_ITEMS,
    force_full_context: bool = False,
) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)
    if not force_full_context:
        return {
            "session_id": sid,
            "mode": "full_chunks_disabled_for_normal_gameplay",
            "cache_enabled": True,
            "cache_hit": False,
            "required_files": [],
            "chunk_index": 0,
            "chunks_total": 0,
            "has_more": False,
            "next_chunk_index": None,
            "loaded_files": [],
            "missing_files": [],
            "loaded_count": 0,
            "missing_count": 0,
            "total_loaded_parts": 0,
            "usage_note": "Use getFastRenderContext. Full chunks require explicit force_full_context=true diagnostic mode.",
        }
    required_files, _current, _future = _required_files_for_session(sid)
    key = _cache_key(sid, required_files)
    cache_hit = key in _REQUIRED_BUNDLE_CACHE and time.time() - _REQUIRED_BUNDLE_CACHE[key].created_at <= CACHE_TTL_SECONDS
    bundle = _build_required_bundle(sid, required_files)
    chunks = _chunk_loaded_parts(bundle.loaded_parts, max_chars=max_chars, max_items=max_items)
    chunks_total = len(chunks)
    safe_index = max(0, min(int(chunk_index or 0), max(chunks_total - 1, 0))) if chunks_total else 0
    selected = chunks[safe_index] if chunks_total else []
    has_more = bool(chunks_total and safe_index < chunks_total - 1)
    return {
        "session_id": sid,
        "mode": "cached_required_files_chunk",
        "cache_enabled": True,
        "cache_hit": cache_hit,
        "cache_key": bundle.key[:16],
        "required_files": required_files,
        "chunk_index": safe_index,
        "chunks_total": chunks_total,
        "has_more": has_more,
        "next_chunk_index": safe_index + 1 if has_more else None,
        "loaded_files": selected,
        "missing_files": bundle.missing_files,
        "loaded_count": len({part.get("path") for part in bundle.loaded_parts}),
        "missing_count": len(bundle.missing_files),
        "total_loaded_parts": len(bundle.loaded_parts),
        "usage_note": "Chunk content is cached while state/files are unchanged. Prefer getFastRenderContext for normal turns.",
    }


@app.get(CHUNK_PATH, operation_id="getRequiredFilesChunk")
def get_required_files_chunk_cached(
    session_id: str,
    chunk_index: int = 0,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    max_items: int = DEFAULT_CHUNK_ITEMS,
    force_full_context: bool = False,
) -> dict[str, Any]:
    return _required_files_chunk_cached_response(session_id, chunk_index=chunk_index, max_chars=max_chars, max_items=max_items, force_full_context=force_full_context)


@app.get(BUNDLE_PATH, operation_id="getRequiredFilesBundle")
def get_required_files_bundle_cached(
    session_id: str,
    chunk_index: int = 0,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    max_items: int = DEFAULT_CHUNK_ITEMS,
    force_full_context: bool = False,
) -> dict[str, Any]:
    return _required_files_chunk_cached_response(session_id, chunk_index=chunk_index, max_chars=max_chars, max_items=max_items, force_full_context=force_full_context)


@app.get(FAST_CONTEXT_PATH, operation_id="getFastRenderContext")
def get_fast_render_context(
    session_id: str,
    max_total_chars: int = Query(default=45000, ge=24000, le=70000),
    per_file_chars: int = Query(default=8000, ge=2500, le=14000),
    include_past: bool | None = Query(default=None),
) -> dict[str, Any]:
    sid = _safe_session_id(session_id)
    base.ensure_session(sid)
    required_files, current, future = _required_files_for_session(sid)
    loaded_files, skipped_files, truncated = _build_fast_loaded_files(
        sid,
        required_files,
        current,
        max_total_chars=max_total_chars,
        per_file_chars=per_file_chars,
        include_past=include_past,
    )
    needs_full_context = bool(truncated and len(loaded_files) < 3)
    return {
        "success": True,
        "session_id": sid,
        "mode": "fast_render_context_v1",
        "runtime_version": app.version,
        "quality_mode": "preserve_character_fidelity_without_full_chunk_reload",
        "required_files_total": len(required_files),
        "loaded_files": loaded_files,
        "loaded_count": len(loaded_files),
        "skipped_files": skipped_files,
        "skipped_count": len(skipped_files),
        "truncated": truncated,
        "needs_full_context": needs_full_context,
        "past_context_loaded": _needs_past(current, include_past),
        "past_context_rule": "past.yaml/hidden past is loaded only when include_past=true or the current turn contains memory/past/lab/Samuel/Kairos/Echo/reveal triggers.",
        "fallback_if_needed": {
            "when": [
                "new important character appears and no character file is loaded",
                "major hidden lore / memory / Samuel / laboratory / Echo reveal",
                "contradiction in character behavior",
                "needs_full_context=true",
            ],
            "action": "stop gameplay and request manual diagnostic outside the scene; do not start required-file chunk loops during gameplay",
        },
        "render_rules": [
            "Use fast context as sufficient for ordinary gameplay turns.",
            "Preserve loaded character voice, knowledge, relationship state and current scene pressure.",
            "Do not show API/debug/status in visible gameplay.",
            "After scene, call applyTurnResult with explicit state changes if anything meaningful changed.",
        ],
    }


try:
    app.version = "0.3.135-fast-only-no-chunk-loop-v1"
except Exception:
    pass
