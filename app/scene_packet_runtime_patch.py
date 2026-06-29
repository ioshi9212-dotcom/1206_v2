"""Variant A scene-packet shim for 1206_v2.

Corrected for 1206 runtime: character loading is discovered from the actual
characters/ folder at runtime instead of hardcoded Academy character ids.

Load order:
1) existing runtime chain: context_transport_header_hotfix
2) this patch: dynamic character discovery + getScenePacket action
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import app.context_transport_header_hotfix as header_hotfix
from app.context_transport_header_hotfix import app
from app import compact as base

try:
    import app.compact_context_patch as ccp
except Exception:  # pragma: no cover
    ccp = None  # type: ignore[assignment]

try:
    import app.context_transport_runtime_patch as rt
except Exception:  # pragma: no cover
    rt = None  # type: ignore[assignment]

# Make sure Railway /data receives the non-old runtime folders too.
# compact.py already has characters/gpt/templates/state; these are the newer
# 1206/lore/runtime folders that must not disappear on volume seed.
for _name in [
    "canon_lore",
    "calendar",
    "runtime",
    "world",
    "relationships",
    "story",
    "lore",
    "locations",
]:
    try:
        if _name not in base.SYNC_FROM_REPO:
            base.SYNC_FROM_REPO.append(_name)
    except Exception:
        pass

app.version = "0.3.61-1206v2-dynamic-scene-packet"

_CHARACTER_IGNORE_DIRS = {
    "locks",
    "lock",
    "npc_templates",
    "templates",
    "__pycache__",
}

_GROUP_IDS = {
    "students",
    "student",
    "staff",
    "crowd",
    "academy_staff",
    "new_students",
    "new_students_block_b",
    "block_b_dorm_staff",
    "background_students",
    "npc",
    "npcs",
}

ROSTER_FIELDS = [
    "pov_character_id",
    "pov_character",
    "active_character_ids",
    "active_characters",
    "nearby_character_ids",
    "nearby_characters",
    "speaking_character_ids",
    "speaking_characters",
    "observing_character_ids",
    "observing_characters",
    "addressed_character_ids",
    "addressed_characters",
    "looked_at_character_ids",
    "looked_at_characters",
    "mentioned_character_ids",
    "mentioned_characters",
    "scheduled_character_ids",
    "scheduled_characters",
    "delayed_character_ids",
    "delayed_characters",
    "scene_character_ids",
    "present_character_ids",
    "characters_in_scene",
]


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_to_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    return value


def _cut_text(text: Any, limit: int) -> str:
    raw = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    raw = raw or ""
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + "\n...[truncated]"


def _compact(value: Any, limit: int = 6000) -> str:
    if isinstance(value, str):
        return _cut_text(value, limit)
    return _cut_text(json.dumps(value, ensure_ascii=False, default=str, indent=2), limit)


def _safe_alias(value: Any) -> str:
    text = str(value or "").strip().strip('"\'')
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^0-9A-Za-zА-Яа-яЁё_]+", "", text)
    return text.lower()


def _read_optional(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception:
        return ""
    return ""


def _character_roots() -> list[Path]:
    roots: list[Path] = []
    for root in [getattr(base, "DATA", None), getattr(base, "ROOT", None)]:
        try:
            if root:
                chars = Path(root) / "characters"
                if chars.exists() and chars.is_dir() and chars not in roots:
                    roots.append(chars)
        except Exception:
            continue
    return roots


def _extract_aliases_from_text(text: str) -> set[str]:
    aliases: set[str] = set()
    if not text:
        return aliases

    for key in ("id", "character_id", "canonical_id", "slug"):
        match = re.search(rf"^\s*{key}\s*:\s*[\"']?([^\"'\n#]+)", text, flags=re.MULTILINE)
        if match:
            aliases.add(match.group(1).strip())

    # aliases: ["ray", "ray_carter"]
    for match in re.finditer(r"^\s*aliases\s*:\s*\[(.*?)\]\s*$", text, flags=re.MULTILINE | re.DOTALL):
        chunk = match.group(1)
        for raw in chunk.split(","):
            item = raw.strip().strip('"\'')
            if item:
                aliases.add(item)

    # aliases:\n  - ray\n  - Рэй
    block = re.search(r"^\s*aliases\s*:\s*\n((?:\s*-\s*[^\n]+\n?)+)", text, flags=re.MULTILINE)
    if block:
        for line in block.group(1).splitlines():
            item = re.sub(r"^\s*-\s*", "", line).strip().strip('"\'')
            if item:
                aliases.add(item)

    # Common yaml fields that often contain usable ids/names.
    for key in ("first_name", "last_name", "short_name", "close_name", "name", "full_name"):
        match = re.search(rf"^\s*{key}\s*:\s*[\"']?([^\"'\n#]+)", text, flags=re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if value and len(value) <= 80:
                aliases.add(value)

    return aliases


def _folder_aliases(folder_name: str) -> set[str]:
    aliases = {folder_name, f"char_{folder_name}"}
    parts = [p for p in folder_name.split("_") if p]
    if parts:
        aliases.add(parts[0])
        aliases.add(f"char_{parts[0]}")
    if len(parts) >= 2:
        aliases.add("_".join(parts[:2]))
    return aliases


def discover_character_sources() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return alias->canonical_id and canonical_id->file paths.

    Canonical id is normally the folder name under characters/.
    This intentionally does not hardcode Academy characters. It scans whatever
    exists in 1206_v2/characters at runtime.
    """
    alias_to_id: dict[str, str] = {}
    id_to_files: dict[str, list[str]] = {}

    for chars_root in _character_roots():
        # New folder layout: characters/<id>/{character.yaml,main.yaml,past.yaml}
        try:
            children = sorted([p for p in chars_root.iterdir() if p.is_dir()], key=lambda p: p.name)
        except Exception:
            children = []

        for folder in children:
            raw_name = folder.name
            if raw_name.startswith(".") or raw_name in _CHARACTER_IGNORE_DIRS:
                continue

            candidates = [
                folder / "character.yaml",
                folder / "character.yml",
                folder / "main.yaml",
                folder / "main.yml",
                folder / "profile.yaml",
                folder / "profile.yml",
                folder / "past.yaml",
                folder / "past.yml",
                folder / "memory.yaml",
                folder / "voice.md",
                folder / "behavior.md",
            ]
            existing = [p for p in candidates if p.exists() and p.is_file()]
            if not existing:
                continue

            canonical = _safe_alias(raw_name)
            if not canonical:
                continue

            rel_files: list[str] = []
            # Keep order: core/profile first, past after.
            for p in candidates:
                if p.exists() and p.is_file():
                    rel_files.append(str(p.relative_to(chars_root.parent)).replace("\\", "/"))
            id_to_files.setdefault(canonical, [])
            for rel in rel_files:
                if rel not in id_to_files[canonical]:
                    id_to_files[canonical].append(rel)

            aliases = set(_folder_aliases(canonical))
            for p in existing:
                aliases |= _extract_aliases_from_text(_read_optional(p))
            for alias in aliases:
                key = _safe_alias(alias)
                if key and key not in _GROUP_IDS:
                    alias_to_id[key] = canonical

        # Legacy flat layout: characters/main/name.md or characters/npc/name.md
        for sub in ["main", "npc"]:
            legacy_root = chars_root / sub
            if not legacy_root.exists() or not legacy_root.is_dir():
                continue
            for file in sorted(legacy_root.glob("*.md")):
                canonical = _safe_alias(file.stem)
                if not canonical:
                    continue
                rel = str(file.relative_to(chars_root.parent)).replace("\\", "/")
                id_to_files.setdefault(canonical, [])
                if rel not in id_to_files[canonical]:
                    id_to_files[canonical].append(rel)
                aliases = set(_folder_aliases(canonical)) | _extract_aliases_from_text(_read_optional(file))
                for alias in aliases:
                    key = _safe_alias(alias)
                    if key and key not in _GROUP_IDS:
                        alias_to_id[key] = canonical

    return alias_to_id, id_to_files


def _character_maps() -> tuple[dict[str, str], dict[str, list[str]]]:
    alias_to_id, id_to_files = discover_character_sources()

    # Preserve existing maps as fallbacks, but do not make them the source of truth.
    if ccp is not None and hasattr(ccp, "NEW_CHARACTER_FOLDERS"):
        try:
            for alias, folder in dict(ccp.NEW_CHARACTER_FOLDERS).items():
                key = _safe_alias(alias)
                canonical = _safe_alias(folder)
                if key and canonical and canonical not in id_to_files:
                    # Only map old Academy fallback if the actual folder exists in repo/data.
                    probe_files = [
                        f"characters/{canonical}/character.yaml",
                        f"characters/{canonical}/main.yaml",
                        f"characters/{canonical}/past.yaml",
                    ]
                    existing = [p for p in probe_files if base.repo_file_exists(p)]
                    if existing:
                        id_to_files.setdefault(canonical, existing)
                if key and canonical in id_to_files:
                    alias_to_id.setdefault(key, canonical)
        except Exception:
            pass

    return alias_to_id, id_to_files


def canonical_character_id(value: Any) -> str:
    key = _safe_alias(value)
    if not key or key in _GROUP_IDS:
        return ""
    alias_to_id, id_to_files = _character_maps()
    if key in alias_to_id:
        return alias_to_id[key]
    if key in id_to_files:
        return key
    # char_ray -> ray fallback
    if key.startswith("char_") and key[5:] in id_to_files:
        return key[5:]
    return key if key in id_to_files else ""


def known_character_folder_dynamic(cid: str) -> str | None:
    canonical = canonical_character_id(cid)
    return canonical or None


def is_known_character_id_dynamic(cid: str) -> bool:
    return bool(known_character_folder_dynamic(cid))


def character_files_for_context_dynamic(cid: str, *, include_past: bool = True) -> list[str]:
    canonical = canonical_character_id(cid)
    if not canonical:
        return []
    _alias_to_id, id_to_files = _character_maps()
    files = list(id_to_files.get(canonical, []))
    if not include_past:
        files = [p for p in files if not p.endswith("/past.yaml") and not p.endswith("/past.yml") and not p.endswith("/past.md")]
    return [p for p in files if base.repo_file_exists(p)]


def character_file_dynamic(cid: str) -> str:
    files = character_files_for_context_dynamic(cid, include_past=True)
    if files:
        return files[0]
    return f"characters/{_safe_alias(cid)}/character.yaml"


def _field_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return []


def scene_character_ids_dynamic(current: dict[str, Any] | None = None, future: dict[str, Any] | None = None) -> list[str]:
    current = current or {}
    future = future or {}
    raw_values: list[Any] = []

    # Include Akira only if she exists in this 1206 character set. Usually yes.
    raw_values.append("akira")

    for field in ROSTER_FIELDS:
        raw_values.extend(_field_values(current.get(field)))

    for thread in current.get("open_threads", []) or []:
        if isinstance(thread, dict) and str(thread.get("status", "")).lower() in {"due", "active", "triggered", "ready"}:
            raw_values.extend(_field_values(thread.get("participants")))
            raw_values.extend(_field_values(thread.get("character_ids")))

    locks = future.get("locks", {}) if isinstance(future, dict) else {}
    if isinstance(locks, dict):
        for lock in locks.values():
            if isinstance(lock, dict) and str(lock.get("status", "")).lower() in {"due", "active", "triggered", "ready"}:
                raw_values.extend(_field_values(lock.get("participants")))
                raw_values.extend(_field_values(lock.get("character_ids")))

    result: list[str] = []
    for value in raw_values:
        cid = canonical_character_id(value)
        if cid and cid not in result:
            result.append(cid)
    return result


def recommended_files_for_context_dynamic(current: dict[str, Any] | None = None, future: dict[str, Any] | None = None) -> list[str]:
    current = current or {}
    future = future or {}
    scene_chars = scene_character_ids_dynamic(current, future)

    files: list[str] = []
    for path in [
        "runtime/scene_context_digest.md",
        "gpt/locks/runtime_scene_rules_digest.md",
        "gpt/locks/lore_usage_lock.md",
        "characters/character_id_index.md",
        "state/current_state.json",
        "state/story_lines.json",
        "state/knowledge_state.json",
        "state/relationships.json",
        "state/inventory_state.json",
        "state/future_locks_progress.json",
        "state/calendar_runtime.json",
    ]:
        if path == "runtime/scene_context_digest.md" or base.repo_file_exists(path):
            files.append(path)

    for cid in scene_chars:
        files.extend(character_files_for_context_dynamic(cid, include_past=True))

    # Let the existing lore module add its selected canon_lore files through the digest.
    # Add the index if present so GPT can see lore routing rules directly too.
    for path in [
        "canon_lore/index.yaml",
        "canon_lore/core/world_background.yaml",
        "canon_lore/academy/academy_background.yaml",
        "canon_lore/hidden/hidden_lore_policy.yaml",
    ]:
        if base.repo_file_exists(path):
            files.append(path)

    result: list[str] = []
    for path in files:
        if path and path not in result:
            result.append(path)
    return result


def _patch_character_runtime() -> None:
    alias_to_id, id_to_files = _character_maps()

    if ccp is not None:
        try:
            ccp.NEW_CHARACTER_FOLDERS = dict(alias_to_id)
        except Exception:
            pass
        for name, fn in [
            ("character_files_for", lambda cid: character_files_for_context_dynamic(cid, include_past=True)),
            ("character_file", character_file_dynamic),
            ("active_scene_characters", scene_character_ids_dynamic),
            ("recommended_files_for_context", recommended_files_for_context_dynamic),
            ("base_recommended_files", lambda: recommended_files_for_context_dynamic({"active_characters": ["akira"]}, {})),
        ]:
            try:
                setattr(ccp, name, fn)
            except Exception:
                pass

    if rt is not None:
        try:
            rt.ID_ALIASES.update(alias_to_id)
        except Exception:
            pass
        for name, fn in [
            ("known_character_folder", known_character_folder_dynamic),
            ("is_known_character_id", is_known_character_id_dynamic),
            ("character_files_for_context", character_files_for_context_dynamic),
            ("scene_character_ids", scene_character_ids_dynamic),
            ("lean_recommended_files_for_context", recommended_files_for_context_dynamic),
        ]:
            try:
                setattr(rt, name, fn)
            except Exception:
                pass

    for name, fn in [
        ("character_file", character_file_dynamic),
        ("character_files_for", lambda cid: character_files_for_context_dynamic(cid, include_past=True)),
        ("active_scene_characters", scene_character_ids_dynamic),
        ("recommended_files_for_context", recommended_files_for_context_dynamic),
        ("base_recommended_files", lambda: recommended_files_for_context_dynamic({"active_characters": ["akira"]}, {})),
    ]:
        try:
            setattr(base, name, fn)
        except Exception:
            pass


_patch_character_runtime()


def _read_json_state(session_id: str, path: str, default: Any = None) -> Any:
    return base.read_json(path, session_id, default=default)


def _required_file_parts(session_id: str) -> tuple[list[str], list[Any], list[Any], list[str]]:
    _patch_character_runtime()
    if ccp is not None and hasattr(ccp, "_required_file_parts"):
        return ccp._required_file_parts(session_id)  # type: ignore[attr-defined]

    current = _read_json_state(session_id, "state/current_state.json", {}) or {}
    future = _read_json_state(session_id, "state/future_locks_progress.json", {}) or {}
    required_files = recommended_files_for_context_dynamic(current, future)

    loaded_parts: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    missing: list[str] = []
    for path in required_files:
        try:
            content = base.read_text(path, session_id if str(path).startswith("state/") else None)
        except Exception:
            if path == "runtime/scene_context_digest.md" and rt is not None and hasattr(rt, "build_scene_context_digest"):
                try:
                    content = rt.build_scene_context_digest(session_id)  # type: ignore[attr-defined]
                except Exception:
                    content = None
            else:
                content = None
        if content is None:
            missing.append(path)
            manifest.append({"path": path, "exists": False, "source": "missing"})
            continue
        source = "session_state" if str(path).startswith("state/") else "project"
        if path == "runtime/scene_context_digest.md":
            source = "runtime"
        manifest.append({"path": path, "exists": True, "source": source, "size_chars": len(content), "parts_total": 1})
        loaded_parts.append({"path": path, "content": content, "part_index": 0, "parts_total": 1, "content_chars": len(content)})
    return required_files, loaded_parts, manifest, missing


def _build_turn_contract(session_id: str) -> dict[str, Any]:
    _patch_character_runtime()
    if ccp is not None and hasattr(ccp, "session_turn_contract_with_prompt_preview"):
        try:
            return _to_plain(ccp.session_turn_contract_with_prompt_preview(session_id))  # type: ignore[attr-defined]
        except Exception as exc:
            return {"error": str(exc), "source": "compact_context_patch.session_turn_contract_with_prompt_preview"}
    return {}


def _pack_loaded_files(loaded_parts: list[Any], *, max_total_chars: int, per_file_chars: int, max_files: int) -> tuple[list[dict[str, Any]], bool]:
    max_total_chars = max(12000, min(int(max_total_chars or 70000), 90000))
    per_file_chars = max(2000, min(int(per_file_chars or 14000), 24000))
    max_files = max(1, min(int(max_files or 16), 48))

    result: list[dict[str, Any]] = []
    used = 0
    truncated = False

    for part in loaded_parts:
        plain = _to_plain(part)
        path = str(plain.get("path", ""))
        content = str(plain.get("content", ""))
        if not path:
            continue
        if len(result) >= max_files or used >= max_total_chars:
            truncated = True
            break
        remaining = max_total_chars - used
        limit = min(per_file_chars, remaining)
        if limit <= 0:
            truncated = True
            break
        cut = _cut_text(content, limit)
        used += len(cut)
        result.append(
            {
                "path": path,
                "part_index": plain.get("part_index", 0),
                "parts_total": plain.get("parts_total", 1),
                "content_chars_original": plain.get("content_chars", len(content)),
                "content_chars_in_packet": len(cut),
                "truncated_in_packet": len(cut) < len(content),
                "content": cut,
            }
        )
        if len(cut) < len(content):
            truncated = True
    return result, truncated


@app.get("/api/v1/sessions/{session_id}/scene-packet", operation_id="getScenePacket")
def get_scene_packet(
    session_id: str,
    max_total_chars: int = 70000,
    per_file_chars: int = 14000,
    max_files: int = 24,
) -> dict[str, Any]:
    """Return one compact scene packet for Variant A Custom GPT flow.

    Character files are selected from the actual 1206_v2 characters/ folder,
    based on current_state roster fields, not from Academy hardcoded IDs.
    """
    _patch_character_runtime()
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)

    current_state = _read_json_state(sid, "state/current_state.json", {}) or {}
    story_lines = _read_json_state(sid, "state/story_lines.json", {}) or {}
    knowledge_state = _read_json_state(sid, "state/knowledge_state.json", {}) or {}
    relationships = _read_json_state(sid, "state/relationships.json", {}) or {}
    inventory_state = _read_json_state(sid, "state/inventory_state.json", {}) or {}
    future_locks = _read_json_state(sid, "state/future_locks_progress.json", {}) or {}
    calendar_runtime = _read_json_state(sid, "state/calendar_runtime.json", {}) or {}

    scene_character_ids = scene_character_ids_dynamic(current_state, future_locks)
    turn_contract = _build_turn_contract(sid)
    required_files, loaded_parts, manifest, missing_files = _required_file_parts(sid)
    loaded_files, packet_truncated = _pack_loaded_files(
        list(loaded_parts),
        max_total_chars=max_total_chars,
        per_file_chars=per_file_chars,
        max_files=max_files,
    )

    scene_digest = ""
    if rt is not None and hasattr(rt, "build_scene_context_digest"):
        try:
            scene_digest = rt.build_scene_context_digest(sid)  # type: ignore[attr-defined]
        except Exception:
            scene_digest = ""

    alias_to_id, id_to_files = _character_maps()
    loaded_character_files = [path for path in required_files if path.startswith("characters/")]

    return {
        "success": True,
        "packet_version": "1206v2_scene_packet_v2_dynamic_characters",
        "session_id": sid,
        "runtime_version": app.version,
        "usage_rule": "Use this packet before rendering. If packet_truncated=true or required lore/character info is missing, call getFastRenderContext before scene output; do not start chunk loops.",
        "character_loading": {
            "mode": "dynamic_from_characters_folder",
            "scene_character_ids": scene_character_ids,
            "loaded_character_files": loaded_character_files,
            "known_character_ids_count": len(id_to_files),
            "known_character_ids_preview": sorted(list(id_to_files.keys()))[:80],
            "alias_count": len(alias_to_id),
            "rule": "Do not use Academy hardcoded roster. Use current_state roster + actual files under characters/.",
        },
        "current_state": _compact(current_state, 9000),
        "turn_contract": _compact(turn_contract, 14000),
        "scene_context_digest": _cut_text(scene_digest, 22000),
        "state_slices": {
            "story_lines": _compact(story_lines, 9000),
            "relationships": _compact(relationships, 9000),
            "knowledge_state": _compact(knowledge_state, 9000),
            "inventory_state": _compact(inventory_state, 5000),
            "future_locks_progress": _compact(future_locks, 6000),
            "calendar_runtime": _compact(calendar_runtime, 5000),
        },
        "required_files": required_files,
        "required_file_manifest": [_to_plain(item) for item in manifest],
        "missing_files": missing_files,
        "loaded_files": loaded_files,
        "packet_truncated": packet_truncated,
        "fallback_actions_if_needed": [
            "getSessionTurnContract",
            "getFastRenderContext",
            
            "getProjectFileByQuery",
        ],
        "hard_rules": [
            "Do not render a play scene if this packet failed.",
            "Do not show API/debug/JSON to the player in gameplay mode.",
            "Use loaded 1206 character files, relationship state, knowledge state, lore slice, calendar/runtime and current_state before NPC reactions.",
            "Hidden lore is not NPC knowledge unless revealed in-scene with source.",
            "After meaningful scene, save explicit state changes through applyTurnResult/applyTurnResultSimple.",
        ],
    }


def _scene_packet_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "success": {"type": "boolean"},
            "packet_version": {"type": "string"},
            "session_id": {"type": "string"},
            "runtime_version": {"type": "string"},
            "character_loading": {"type": "object", "additionalProperties": True},
            "current_state": {"type": "string"},
            "turn_contract": {"type": "string"},
            "scene_context_digest": {"type": "string"},
            "state_slices": {"type": "object", "additionalProperties": True},
            "required_files": {"type": "array", "items": {"type": "string"}},
            "required_file_manifest": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "missing_files": {"type": "array", "items": {"type": "string"}},
            "loaded_files": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "packet_truncated": {"type": "boolean"},
        },
    }


def _scene_packet_path_schema() -> dict[str, Any]:
    return {
        "get": {
            "operationId": "getScenePacket",
            "summary": "Get one compact scene packet for gameplay rendering with dynamic 1206 character loading",
            "parameters": [
                header_hotfix._session_path_param(),
                {"name": "max_total_chars", "in": "query", "required": False, "schema": {"type": "integer", "default": 70000}},
                {"name": "per_file_chars", "in": "query", "required": False, "schema": {"type": "integer", "default": 14000}},
                {"name": "max_files", "in": "query", "required": False, "schema": {"type": "integer", "default": 24}},
            ],
            "responses": {
                "200": {
                    "description": "Scene packet",
                    "content": {"application/json": {"schema": _scene_packet_response_schema()}},
                }
            },
        }
    }


def _openapi_with_scene_packet() -> dict[str, Any]:
    schema = header_hotfix._minimal_gpt_openapi()
    schema.setdefault("info", {})["version"] = app.version
    schema.setdefault("paths", {})["/api/v1/sessions/{session_id}/scene-packet"] = _scene_packet_path_schema()
    return schema


def _remove_route(path: str) -> None:
    for route in list(app.router.routes):
        if getattr(route, "path", None) == path:
            app.router.routes.remove(route)


_remove_route("/openapi-actions.json")


@app.get("/openapi-actions.json", include_in_schema=False)
def openapi_actions() -> dict[str, Any]:
    return _openapi_with_scene_packet()


app.openapi_schema = None
app.openapi = _openapi_with_scene_packet  # type: ignore[method-assign]
