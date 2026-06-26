from __future__ import annotations

from typing import Any

import app.start_scene_runtime_patch as start_runtime
from app.start_scene_runtime_patch import app
import app.character_registry_runtime_patch as character_registry  # noqa: F401
import app.response_size_guard_runtime_patch as size_guard  # noqa: F401
import app.pov_switch_runtime_patch as pov_switch  # noqa: F401
import app.state_persistence_runtime_patch as state_persistence  # noqa: F401
import app.physical_continuity_runtime_patch as physical_continuity  # noqa: F401
import app.character_entry_runtime_patch as character_entry  # noqa: F401

try:
    import app.knowledge_state_runtime_patch as knowledge_state_runtime  # noqa: F401
except Exception:
    knowledge_state_runtime = None  # type: ignore[assignment]

app.version = "0.3.120-character-entry-v1"


def _object_schema(properties: dict | None = None, *, required: list[str] | None = None) -> dict:
    schema = {"type": "object", "properties": properties or {}, "additionalProperties": True}
    if required:
        schema["required"] = required
    return schema


def _array_string() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def _components() -> dict:
    return {
        "HealthResponse": _object_schema({"status": {"type": "string"}, "app": {"type": "string"}, "version": {"type": "string"}, "public_base_url": {"type": "string"}}),
        "SessionResponse": _object_schema({"session_id": {"type": "string"}, "title": {"type": "string"}, "created_at": {"type": "string"}, "updated_at": {"type": "string"}, "start_scene": _object_schema()}, required=["session_id"]),
        "SizeGuardContextResponse": _object_schema({"session_id": {"type": "string"}, "mode": {"type": "string"}, "current_state": _object_schema(), "active_character_ids": _array_string(), "nearby_character_ids": _array_string(), "required_files": _array_string(), "usage_note": {"type": "string"}}, required=["session_id"]),
        "TurnContractWithPromptPreview": _object_schema({"session_id": {"type": "string"}, "mode": {"type": "string"}, "active_character_ids": _array_string(), "nearby_character_ids": _array_string(), "required_files": _array_string(), "output_format_contract": _object_schema(), "required_checks_before_answer": _array_string(), "knowledge_table": _object_schema(), "inventory_contract": _object_schema(), "relationship_context": _object_schema(), "story_context": _object_schema(), "prompt_preview": {"type": "string"}, "usage_note": {"type": "string"}}, required=["session_id", "required_files", "prompt_preview"]),
        "RequiredFilesManifestResponse": _object_schema({"session_id": {"type": "string"}, "required_files": _array_string(), "files": {"type": "array", "items": _object_schema()}, "missing_files": _array_string(), "chunks_total": {"type": "integer"}, "loaded_count": {"type": "integer"}, "missing_count": {"type": "integer"}}),
        "RequiredFilesChunkResponse": _object_schema({"session_id": {"type": "string"}, "required_files": _array_string(), "chunk_index": {"type": "integer"}, "chunks_total": {"type": "integer"}, "has_more": {"type": "boolean"}, "next_chunk_index": {"type": "integer"}, "loaded_files": {"type": "array", "items": _object_schema()}, "missing_files": _array_string(), "loaded_count": {"type": "integer"}, "missing_count": {"type": "integer"}, "total_loaded_parts": {"type": "integer"}}),
        "ProcessTurnResponse": _object_schema({"success": {"type": "boolean"}, "session_id": {"type": "string"}, "player_input": {"type": "string"}, "current_scene_id": {"type": "string"}, "status": {"type": "string"}, "scene_text": {"type": "string"}, "scene_packet": _object_schema()}),
        "ApplyTurnResultResponse": _object_schema({"status": {"type": "string"}, "session_id": {"type": "string"}, "changed_files": _array_string(), "visible_scene_text": {"type": "string"}, "final_scene_text": {"type": "string"}}),
        "PhysicalContinuityRepairResponse": _object_schema({"status": {"type": "string"}, "session_id": {"type": "string"}, "changed_files": _array_string(), "reason": {"type": "string"}, "physical_continuity_state": _object_schema()}),
        "CharacterEntryRepairResponse": _object_schema({"status": {"type": "string"}, "session_id": {"type": "string"}, "changed_files": _array_string(), "reason": {"type": "string"}, "pending": _object_schema(), "current_state_pending_character_ids": _array_string()}),
    }


def _ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def _response(description: str, name: str) -> dict:
    return {"description": description, "content": {"application/json": {"schema": _ref(name)}}}


def _session_path_param() -> dict:
    return {"name": "session_id", "in": "path", "required": True, "schema": {"type": "string"}}


def _chunk_params() -> list[dict]:
    return [
        {"name": "chunk_index", "in": "query", "required": False, "schema": {"type": "integer", "default": 0}},
        {"name": "max_chars", "in": "query", "required": False, "schema": {"type": "integer", "default": 30000}},
        {"name": "max_items", "in": "query", "required": False, "schema": {"type": "integer", "default": 3}},
    ]


def _openapi() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Akira 1206 v2 Actions", "version": app.version},
        "servers": [{"url": start_runtime.base.BASE_URL}],
        "components": {"schemas": _components()},
        "paths": {
            "/health": {"get": {"operationId": "health", "summary": "Check API health and runtime version", "responses": {"200": _response("API health status", "HealthResponse")}}},
            "/api/v1/sessions": {"post": {"operationId": "createSession", "summary": "Create a new gameplay session", "requestBody": {"required": False, "content": {"application/json": {"schema": _object_schema({"session_id": {"type": "string"}, "title": {"type": "string"}, "reset": {"type": "boolean"}})}}}, "responses": {"200": _response("Created session", "SessionResponse")}}},
            "/api/v1/sessions/{session_id}/context": {"get": {"operationId": "getSessionContext", "summary": "Get compact session context", "parameters": [_session_path_param()], "responses": {"200": _response("Compact session context", "SizeGuardContextResponse")}}},
            "/api/v1/sessions/{session_id}/turn-contract": {"get": {"operationId": "getSessionTurnContract", "summary": "Get compact turn contract; self-heals stale physical continuity and hidden character-entry continuity when needed", "parameters": [_session_path_param()], "responses": {"200": _response("Turn contract", "TurnContractWithPromptPreview")}}},
            "/api/v1/sessions/{session_id}/required-files-manifest": {"get": {"operationId": "getRequiredFilesManifest", "summary": "Get required files manifest and chunk count", "parameters": [_session_path_param()], "responses": {"200": _response("Required files manifest", "RequiredFilesManifestResponse")}}},
            "/api/v1/sessions/{session_id}/required-files-chunk": {"get": {"operationId": "getRequiredFilesChunk", "summary": "Get one chunk of required file contents", "parameters": [_session_path_param()] + _chunk_params(), "responses": {"200": _response("Required files chunk", "RequiredFilesChunkResponse")}}},
            "/api/v1/sessions/{session_id}/required-files-bundle": {"get": {"operationId": "getRequiredFilesBundle", "summary": "Backward-compatible required files chunk endpoint", "parameters": [_session_path_param()] + _chunk_params(), "responses": {"200": _response("Required files chunk", "RequiredFilesChunkResponse")}}},
            "/api/v1/sessions/{session_id}/scene-packet": {"get": {"operationId": "getScenePacket", "summary": "Get one compact scene packet", "parameters": [_session_path_param()], "responses": {"200": {"description": "Scene packet", "content": {"application/json": {"schema": _object_schema()}}}}}},
            "/api/v1/sessions/{session_id}/turn": {"post": {"operationId": "processTurn", "summary": "Return gameplay scene", "parameters": [_session_path_param()], "requestBody": {"required": True, "content": {"application/json": {"schema": _object_schema({"player_input": {"type": "string"}, "mode": {"type": "string", "default": "play"}, "include_file_contents": {"type": "boolean", "default": True}, "state_patches": _object_schema()}, required=["player_input"])}}}, "responses": {"200": _response("Processed turn", "ProcessTurnResponse")}}},
            "/api/v1/sessions/{session_id}/apply-turn-result": {"post": {"operationId": "applyTurnResult", "summary": "Apply meaningful scene changes and fallback physical continuity from visible_scene_text", "parameters": [_session_path_param()], "requestBody": {"required": False, "content": {"application/json": {"schema": _object_schema({"turn_file": {"type": "string"}, "data": _object_schema(), "dry_run": {"type": "boolean", "default": False}, "visible_scene_text": {"type": "string"}})}}}, "responses": {"200": _response("Apply result", "ApplyTurnResultResponse")}}},
            "/api/v1/sessions/{session_id}/repair/physical-continuity": {"post": {"operationId": "repairPhysicalContinuity", "summary": "Repair current_state/inventory_state from latest scene_history visible scene", "parameters": [_session_path_param(), {"name": "dry_run", "in": "query", "required": False, "schema": {"type": "boolean", "default": False}}, {"name": "force", "in": "query", "required": False, "schema": {"type": "boolean", "default": True}}], "responses": {"200": _response("Physical continuity repair result", "PhysicalContinuityRepairResponse")}}},
            "/api/v1/sessions/{session_id}/repair/character-entry": {"post": {"operationId": "repairCharacterEntry", "summary": "Repair hidden pending character-entry state, especially Raiden's late-night conditional entry", "parameters": [_session_path_param(), {"name": "force", "in": "query", "required": False, "schema": {"type": "boolean", "default": True}}, {"name": "dry_run", "in": "query", "required": False, "schema": {"type": "boolean", "default": False}}], "responses": {"200": _response("Character entry repair result", "CharacterEntryRepairResponse")}}},
        },
    }


def _remove(path: str) -> None:
    for route in list(app.router.routes):
        if getattr(route, "path", None) == path:
            app.router.routes.remove(route)


_remove("/openapi-actions.json")


@app.get("/openapi-actions.json", include_in_schema=False)
def openapi_actions() -> dict[str, Any]:
    return _openapi()


app.openapi_schema = None
app.openapi = _openapi  # type: ignore[method-assign]
app.version = "0.3.120-character-entry-v1"
