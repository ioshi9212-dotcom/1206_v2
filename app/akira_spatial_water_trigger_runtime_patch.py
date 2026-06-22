"""Akira spatial water metaphor trigger patch.

Adds a conditional file that loads only when water/storm/wave/flow/depth
language appears. This prevents the model from treating Akira as a water user.
"""
from __future__ import annotations

import app.lean_context_loading_runtime_patch as lean
from app.start_scene_runtime_patch import app

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


def _patch_topic_trigger() -> None:
    triggers = getattr(lean, "TOPIC_TRIGGERS", None)
    if not isinstance(triggers, dict):
        return

    cfg = triggers.setdefault("akira_spatial_water_metaphor", {"needles": [], "files": []})
    needles = cfg.setdefault("needles", [])
    files = cfg.setdefault("files", [])

    for item in WATER_SPACE_NEEDLES:
        if item not in needles:
            needles.append(item)

    if AKIRA_SPATIAL_WATER_RULES_FILE not in files:
        files.append(AKIRA_SPATIAL_WATER_RULES_FILE)


_patch_topic_trigger()

try:
    app.version = "0.3.104-1206-akira-spatial-water-trigger"
except Exception:
    pass
