"""1206 v2 repair roster defaults.

Overrides the repair scene-roster endpoint default so calling it without a body
cannot bring Academy-only characters into the active 1206 scene.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

import app.context_transport_runtime_patch as context_transport
from app.context_transport_runtime_patch import app
from app import compact as base


class RepairSceneRoster1206Request(BaseModel):
    active_character_ids: list[str] = Field(default_factory=lambda: ["akira"])
    nearby_character_ids: list[str] = Field(default_factory=list)
    speaking_character_ids: list[str] = Field(default_factory=list)
    observing_character_ids: list[str] = Field(default_factory=list)
    addressed_character_ids: list[str] = Field(default_factory=list)
    looked_at_character_ids: list[str] = Field(default_factory=list)
    mentioned_character_ids: list[str] = Field(default_factory=list)
    scheduled_character_ids: list[str] = Field(default_factory=list)
    delayed_character_ids: list[str] = Field(default_factory=list)


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


def _canon_list(values: list[str]) -> list[str]:
    return context_transport._unique([context_transport.canonical_id(x) for x in values])


_remove_routes("/api/v1/sessions/{session_id}/repair/scene-roster", {"POST"}, "repairSceneRoster")


@app.post("/api/v1/sessions/{session_id}/repair/scene-roster", operation_id="repairSceneRoster")
def repair_scene_roster_1206(session_id: str, request: RepairSceneRoster1206Request = RepairSceneRoster1206Request()):
    sid = base.safe_session_id(session_id)
    base.ensure_session(sid)
    current = base.read_json("state/current_state.json", sid, default={}) or {}
    current["active_characters"] = _canon_list(request.active_character_ids)
    current["active_character_ids"] = list(current["active_characters"])
    current["nearby_characters"] = _canon_list(request.nearby_character_ids)
    current["nearby_character_ids"] = list(current["nearby_characters"])
    current["speaking_character_ids"] = _canon_list(request.speaking_character_ids)
    current["observing_character_ids"] = _canon_list(request.observing_character_ids)
    current["addressed_character_ids"] = _canon_list(request.addressed_character_ids)
    current["looked_at_character_ids"] = _canon_list(request.looked_at_character_ids)
    current["mentioned_character_ids"] = _canon_list(request.mentioned_character_ids)
    current["scheduled_character_ids"] = _canon_list(request.scheduled_character_ids)
    current["delayed_character_ids"] = _canon_list(request.delayed_character_ids)
    base.write_json("state/current_state.json", current, sid)
    return {
        "status": "repaired",
        "session_id": sid,
        "changed_files": ["state/current_state.json"],
        "active_characters": current["active_characters"],
        "nearby_characters": current["nearby_characters"],
        "default_roster_standard": "1206_v2_akira_only",
    }


app.version = f"{getattr(app, 'version', '0.3')}-repair-roster-1206"
