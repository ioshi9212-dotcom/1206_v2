"""Akira clean structure runtime patch.

This existing runtime hook now does two things:
- loads Akira knowledge.yaml with the always-loaded Akira files;
- keeps spatial water metaphor rules conditional by water/storm/wave/flow/depth triggers.

No new locks are created.
"""
from __future__ import annotations

import app.lean_context_loading_runtime_patch as lean
from app.start_scene_runtime_patch import app

AKIRA_KNOWLEDGE_FILE = "characters/akira/knowledge.yaml"
AKIRA_SPATIAL_WATER_RULES_FILE = "characters/akira/spatial_water_metaphor_rules.yaml"

WATER_SPACE_NEEDLES = [
    "вода", "водн", "водя", "море", "океан", "шторм", "буря", "цунами",
    "волна", "волны", "волной", "поток", "потока", "течение", "течени",
    "прилив", "отлив", "глубина", "глубине", "дно", "бездн",
    "граница", "границ", "искаж", "давлен", "вязк",
    "water", "sea", "ocean", "storm", "tsunami", "wave", "flow",
    "stream", "current", "tide", "depth", "bottom", "abyss",
    "boundary", "distortion", "pressure",
    "#akira_water_metaphor", "#space_not_water", "#spatial_pressure",
    "#boundary_depth", "#wave_language", "#storm_tsunami_metaphor",
]


def _append_unique(target: list[str], item: str) -> None:
    if item not in target:
        target.append(item)


def _patch_akira_files() -> None:
    files = getattr(lean, "CHARACTER_FILES", None)
    if isinstance(files, dict):
        akira_files = files.setdefault("akira", ["characters/akira/main.yaml", "characters/akira/character.yaml"])
        if isinstance(akira_files, list):
            _append_unique(akira_files, AKIRA_KNOWLEDGE_FILE)


def _patch_topic_trigger() -> None:
    triggers = getattr(lean, "TOPIC_TRIGGERS", None)
    if not isinstance(triggers, dict):
        return

    cfg = triggers.setdefault("akira_spatial_water_metaphor", {"needles": [], "files": []})
    needles = cfg.setdefault("needles", [])
    files = cfg.setdefault("files", [])

    for item in WATER_SPACE_NEEDLES:
        _append_unique(needles, item)

    _append_unique(files, AKIRA_SPATIAL_WATER_RULES_FILE)

    hidden = triggers.setdefault("akira_hidden", {"needles": [], "files": []})
    hidden_files = hidden.setdefault("files", [])
    _append_unique(hidden_files, "characters/akira/past.yaml")


_patch_akira_files()
_patch_topic_trigger()

try:
    app.version = "0.3.105-1206-akira-clean-structure"
except Exception:
    pass
