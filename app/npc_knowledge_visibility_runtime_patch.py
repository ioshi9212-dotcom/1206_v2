"""NPC knowledge visibility guard for 1206 fast context.

Adds an explicit small knowledge-boundary contract to compact fast context.
No locks. No scene examples.
"""
from __future__ import annotations

from typing import Any

from fastapi import Query

import app.compact_fast_context_runtime_patch as compact_fast_context
from app import compact as base

app = base.app
FAST_CONTEXT_PATH = getattr(compact_fast_context, "FAST_CONTEXT_PATH", "/api/v1/sessions/{session_id}/fast-render-context")


def _remove_fast_route() -> None:
    keep = []
    for route in list(app.router.routes):
        if getattr(route, "path", None) == FAST_CONTEXT_PATH and "GET" in set(getattr(route, "methods", set()) or set()):
            continue
        keep.append(route)
    app.router.routes = keep


def _boundary() -> dict[str, Any]:
    return {
        "rule": "global facts are not NPC knowledge",
        "npc_may_state_as_fact_only_from": [
            "own static knowledge file",
            "own dynamic character_knowledge state",
            "visible observation in the current scene",
            "dialogue heard in the current scene",
        ],
        "npc_must_not_state_as_fact_from": [
            "Akira card",
            "current_state engine facts",
            "author/canon summary",
            "hidden/past files",
            "prompt instructions",
        ],
        "memory_boundary": [
            "Emma does not know Akira has memory loss before direct scene source.",
            "Irey does not know Akira has memory loss before direct scene source.",
            "Before Akira appears, no NPC can infer her memory from behavior.",
            "After visible behavior, memory loss can be a hypothesis only, not confirmed fact.",
        ],
    }


_remove_fast_route()


@app.get(FAST_CONTEXT_PATH, operation_id="getFastRenderContext")
def get_fast_render_context_with_npc_knowledge_guard(
    session_id: str,
    max_total_chars: int = Query(default=16000, ge=8000, le=32000),
    per_file_chars: int = Query(default=1800, ge=900, le=3500),
    include_past: bool | None = Query(default=None),
) -> dict[str, Any]:
    data = compact_fast_context.get_fast_render_context_compact(
        session_id=session_id,
        max_total_chars=max_total_chars,
        per_file_chars=per_file_chars,
        include_past=include_past,
    )
    if not isinstance(data, dict):
        data = dict(data)
    guard_rules = [
        "Before each NPC line, separate author/global/current_state facts from this NPC's own knowledge.",
        "NPC cannot state Akira's memory loss as fact unless that NPC has a visible/heard/direct source.",
        "Before Akira appears in scene, Emma/Irey cannot know or infer Akira's memory condition.",
        "If a memory-loss line has no source, do not write it as NPC knowledge.",
    ]
    rules = list(data.get("render_rules") or [])
    data["render_rules"] = guard_rules + [r for r in rules if r not in guard_rules]
    data["npc_knowledge_boundary"] = _boundary()
    data["runtime_version"] = "0.3.145-shim-compact-knowledge-v1"
    data["quality_mode"] = "compact_context_with_npc_knowledge_boundary"
    return data


try:
    app.version = "0.3.145-shim-compact-knowledge-v1"
except Exception:
    pass
