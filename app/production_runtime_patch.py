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
import app.fast_context_runtime_patch as fast_context  # noqa: F401

# Optional patch from the previous NPC ZIP. Keep it here so this file does not
# accidentally disable living NPC/session NPC support when applied after it.
try:
    import app.npc_living_runtime_patch as npc_living  # noqa: F401
except Exception:
    npc_living = None  # type: ignore[assignment]

# East Sector location/base context and story rule locks. These are rule/context
# patches, not gameplay logs.
try:
    import app.east_sector_context_runtime_patch as east_sector_context  # noqa: F401
except Exception:
    east_sector_context = None  # type: ignore[assignment]

try:
    import app.story_rules_context_runtime_patch as story_rules_context  # noqa: F401
except Exception:
    story_rules_context = None  # type: ignore[assignment]

try:
    import app.knowledge_state_runtime_patch as knowledge_state_runtime  # noqa: F401
except Exception:
    knowledge_state_runtime = None  # type: ignore[assignment]

# Must be imported after fast_context/state_persistence: it wraps turn-contract,
# fast-render-context and apply-turn-result to prevent stale roster / NPC identity drift.
try:
    import app.roster_identity_context_guard_runtime_patch as roster_identity_context_guard  # noqa: F401
except Exception:
    roster_identity_context_guard = None  # type: ignore[assignment]

app.version = "0.3.138-roster-identity-context-guard-v1"


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
        "SizeGuardContextResponse": _object_schema({"session_id": {"type": "string"}, "mode": {"type": "string"}, "current_state": _object_schema(), "active_character_ids": _array_string(), "nearby_character_ids": _array_string(), "usage_note": {"type": "string"}}, required=["session_id"]),
        "TurnContractWithPromptPreview": _object_schema({"session_id": {"type": "string"}, "mode": {"type": "string"}, "active_character_ids": _array_string(), "nearby_character_ids": _array_string(), "fast_context_file_hints": _array_string(), "context_files_available": {"type": "integer"}, "output_format_contract": _object_schema(), "required_checks_before_answer": _array_string(), "knowledge_table": _object_schema(), "inventory_contract": _object_schema(), "relationship_context": _object_schema(), "story_context": _object_schema(), "prompt_preview": {"type": "string"}, "fast_context_available": {"type": "boolean"}, "preferred_next_action": {"type": "string"}, "usage_note": {"type": "string"}}, required=["session_id", "prompt_preview"]),
        "FastRenderContextResponse": _object_schema({"success": {"type": "boolean"}, "session_id": {"type": "string"}, "mode": {"type": "string"}, "quality_mode": {"type": "string"}, "active_character_ids": _array_string(), "nearby_character_ids": _array_string(), "context_files_total": {"type": "integer"}, "loaded_files": {"type": "array", "items": _object_schema()}, "loaded_count": {"type": "integer"}, "skipped_files": _array_string(), "skipped_count": {"type": "integer"}, "truncated": {"type": "boolean"}, "needs_full_context": {"type": "boolean"}, "past_context_loaded": {"type": "boolean"}, "render_rules": _array_string()}),
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


def _fast_context_params() -> list[dict]:
    return [
        {"name": "max_total_chars", "in": "query", "required": False, "schema": {"type": "integer", "default": 26000, "minimum": 12000, "maximum": 42000}},
        {"name": "per_file_chars", "in": "query", "required": False, "schema": {"type": "integer", "default": 4500, "minimum": 1800, "maximum": 8000}},
        {"name": "include_past", "in": "query", "required": False, "schema": {"type": "boolean", "nullable": True}},
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
            "/api/v1/sessions/{session_id}/turn-contract": {"get": {"operationId": "getSessionTurnContract", "summary": "Get compact turn contract. For normal turns, call getFastRenderContext next.", "parameters": [_session_path_param()], "responses": {"200": _response("Turn contract", "TurnContractWithPromptPreview")}}},
            "/api/v1/sessions/{session_id}/fast-render-context": {"get": {"operationId": "getFastRenderContext", "summary": "Get fast render context for normal gameplay: synced roster, character context and selected state slices", "parameters": [_session_path_param()] + _fast_context_params(), "responses": {"200": _response("Fast render context", "FastRenderContextResponse")}}},
            "/api/v1/sessions/{session_id}/scene-packet": {"get": {"operationId": "getScenePacket", "summary": "Get one compact scene packet", "parameters": [_session_path_param()], "responses": {"200": {"description": "Scene packet", "content": {"application/json": {"schema": _object_schema()}}}}}},
            "/api/v1/sessions/{session_id}/turn": {"post": {"operationId": "processTurn", "summary": "Return gameplay scene or compact scene packet", "parameters": [_session_path_param()], "requestBody": {"required": True, "content": {"application/json": {"schema": _object_schema({"player_input": {"type": "string"}, "mode": {"type": "string", "default": "play"}, "state_patches": _object_schema()}, required=["player_input"])}}}, "responses": {"200": _response("Processed turn", "ProcessTurnResponse")}}},
            "/api/v1/sessions/{session_id}/apply-turn-result": {"post": {"operationId": "applyTurnResult", "summary": "Apply meaningful scene changes and sync roster/location before scene history", "parameters": [_session_path_param()], "requestBody": {"required": False, "content": {"application/json": {"schema": _object_schema({"turn_file": {"type": "string"}, "data": _object_schema(), "dry_run": {"type": "boolean", "default": False}, "visible_scene_text": {"type": "string"}})}}}, "responses": {"200": _response("Apply result", "ApplyTurnResultResponse")}}},
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
app.version = "0.3.138-roster-identity-context-guard-v1"
