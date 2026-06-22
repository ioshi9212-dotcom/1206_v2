"""Clean character extra-file runtime patch.

Existing hook. No new locks.

Adds character knowledge files for always-relevant active character context and keeps
Akira water-metaphor rules conditional by trigger words.
"""
from __future__ import annotations

import app.lean_context_loading_runtime_patch as lean
from app.start_scene_runtime_patch import app

AKIRA_KNOWLEDGE_FILE = "characters/akira/knowledge.yaml"
JUN_KNOWLEDGE_FILE = "characters/jun/knowledge.yaml"
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

JUN_PAST_NEEDLES = [
    "джун", "отец", "опекун", "барьер", "дом", "рэй", "восточный сектор",
    "райден", "кольцо", "память", "забыл", "забыла", "связь", "не вспомнил",
    "самуэль", "акира"
]


def _append_unique(target: list[str], item: str) -> None:
    if item not in target:
        target.append(item)


def _patch_character_files() -> None:
    files = getattr(lean, "CHARACTER_FILES", None)
    if isinstance(files, dict):
        akira_files = files.setdefault("akira", ["characters/akira/main.yaml", "characters/akira/character.yaml"])
        if isinstance(akira_files, list):
            _append_unique(akira_files, AKIRA_KNOWLEDGE_FILE)

        jun_files = files.setdefault("jun", ["characters/jun/main.yaml", "characters/jun/character.yaml"])
        if isinstance(jun_files, list):
            _append_unique(jun_files, JUN_KNOWLEDGE_FILE)


def _patch_topic_triggers() -> None:
    triggers = getattr(lean, "TOPIC_TRIGGERS", None)
    if not isinstance(triggers, dict):
        return

    cfg = triggers.setdefault("akira_spatial_water_metaphor", {"needles": [], "files": []})
    needles = cfg.setdefault("needles", [])
    files = cfg.setdefault("files", [])
    for item in WATER_SPACE_NEEDLES:
        _append_unique(needles, item)
    _append_unique(files, AKIRA_SPATIAL_WATER_RULES_FILE)

    akira_hidden = triggers.setdefault("akira_hidden", {"needles": [], "files": []})
    _append_unique(akira_hidden.setdefault("files", []), "characters/akira/past.yaml")

    jun_hidden = triggers.setdefault("jun_hidden", {"needles": [], "files": []})
    for item in JUN_PAST_NEEDLES:
        _append_unique(jun_hidden.setdefault("needles", []), item)
    _append_unique(jun_hidden.setdefault("files", []), "characters/jun/past.yaml")


_patch_character_files()
_patch_topic_triggers()

try:
    app.version = "0.3.106-1206-clean-jun-and-npc-agency"
except Exception:
    pass
