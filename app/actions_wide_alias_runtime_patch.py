from __future__ import annotations

from typing import Any
from fastapi import Body

import app.actions_compat_runtime_patch as compat
from app.actions_compat_runtime_patch import app
from app import compact as base

app.version = "0.3.65-wide-action-aliases"


def _remove(path: str) -> None:
    for route in list(app.router.routes):
        if getattr(route, "path", None) == path:
            app.router.routes.remove(route)


def _sid(session_id: str | None) -> str:
    return compat._ensure_session_exists(session_id or "main-1206-v2")


def context_any(session_id: str) -> Any:
    return base.context_payload(_sid(session_id))


def context_any_post(session_id: str, body: dict[str, Any] | None = Body(default=None)) -> Any:
    return context_any(session_id)


def contract_any(session_id: str) -> Any:
    sid = _sid(session_id)
    if compat.ccp is not None and hasattr(compat.ccp, "session_turn_contract_with_prompt_preview"):
        return compat.ccp.session_turn_contract_with_prompt_preview(sid)
    if hasattr(base, "session_turn_contract"):
        return base.session_turn_contract(sid)
    return {"session_id": sid, "required_files": [], "output_format_contract": {}, "prompt_preview": ""}


def contract_any_post(session_id: str, body: dict[str, Any] | None = Body(default=None)) -> Any:
    return contract_any(session_id)


def manifest_any(session_id: str) -> Any:
    sid = _sid(session_id)
    if compat.ccp is not None and hasattr(compat.ccp, "get_required_files_manifest"):
        return compat.ccp.get_required_files_manifest(sid)
    return {"session_id": sid, "required_files": [], "files": [], "missing_files": [], "loaded_count": 0, "missing_count": 0, "chunks_total": 0}


def manifest_any_post(session_id: str, body: dict[str, Any] | None = Body(default=None)) -> Any:
    return manifest_any(session_id)


def chunk_any(session_id: str, chunk_index: int = 0, max_chars: int = 12000, max_items: int = 1) -> Any:
    sid = _sid(session_id)
    if compat.ccp is not None and hasattr(compat.ccp, "get_required_files_chunk"):
        return compat.ccp.get_required_files_chunk(sid, chunk_index=chunk_index, max_chars=max_chars, max_items=max_items)
    return {"session_id": sid, "chunk_index": chunk_index, "chunks_total": 0, "has_more": False, "next_chunk_index": None, "loaded_files": [], "missing_files": []}


def chunk_any_post(session_id: str, body: dict[str, Any] | None = Body(default=None)) -> Any:
    body = body or {}
    return chunk_any(session_id, chunk_index=int(body.get("chunk_index", 0) or 0), max_chars=int(body.get("max_chars", 12000) or 12000), max_items=int(body.get("max_items", 1) or 1))


def bundle_any(session_id: str, chunk_index: int = 0, max_chars: int = 12000, max_items: int = 1) -> Any:
    return chunk_any(session_id, chunk_index=chunk_index, max_chars=max_chars, max_items=max_items)


def bundle_any_post(session_id: str, body: dict[str, Any] | None = Body(default=None)) -> Any:
    return chunk_any_post(session_id, body=body)


def _add(paths: list[str], get_fn: Any, post_fn: Any, op: str) -> None:
    for i, path in enumerate(paths):
        _remove(path)
        app.add_api_route(path, get_fn, methods=["GET"], operation_id=op if i == 0 else f"{op}Alias{i}", include_in_schema=(i == 0))
        app.add_api_route(path, post_fn, methods=["POST"], include_in_schema=False)


_add([
    "/api/v1/sessions/{session_id}/context",
    "/api/v1/session/{session_id}/context",
    "/api/v1/sessions/{session_id}/session-context",
    "/api/v1/sessions/{session_id}/get-context",
    "/api/v1/context/{session_id}",
], context_any, context_any_post, "getSessionContext")

_add([
    "/api/v1/sessions/{session_id}/turn-contract",
    "/api/v1/session/{session_id}/turn-contract",
    "/api/v1/sessions/{session_id}/turn_contract",
    "/api/v1/sessions/{session_id}/contract",
    "/api/v1/sessions/{session_id}/get-turn-contract",
], contract_any, contract_any_post, "getSessionTurnContract")

_add([
    "/api/v1/sessions/{session_id}/required-files-manifest",
    "/api/v1/session/{session_id}/required-files-manifest",
    "/api/v1/sessions/{session_id}/required_files_manifest",
    "/api/v1/sessions/{session_id}/required-files/manifest",
    "/api/v1/sessions/{session_id}/manifest",
], manifest_any, manifest_any_post, "getRequiredFilesManifest")

_add([
    "/api/v1/sessions/{session_id}/required-files-chunk",
    "/api/v1/session/{session_id}/required-files-chunk",
    "/api/v1/sessions/{session_id}/required_files_chunk",
    "/api/v1/sessions/{session_id}/required-files/chunk",
    "/api/v1/sessions/{session_id}/files-chunk",
], chunk_any, chunk_any_post, "getRequiredFilesChunk")

_add([
    "/api/v1/sessions/{session_id}/required-files-bundle",
    "/api/v1/session/{session_id}/required-files-bundle",
    "/api/v1/sessions/{session_id}/required_files_bundle",
    "/api/v1/sessions/{session_id}/required-files/bundle",
    "/api/v1/sessions/{session_id}/files-bundle",
], bundle_any, bundle_any_post, "getRequiredFilesBundle")

_old_openapi = app.openapi

def _openapi() -> dict[str, Any]:
    schema = _old_openapi()
    schema.setdefault("info", {})["version"] = app.version
    return schema

_remove("/openapi-actions.json")

@app.get("/openapi-actions.json", include_in_schema=False)
def openapi_actions() -> dict[str, Any]:
    return _openapi()

app.openapi_schema = None
app.openapi = _openapi
