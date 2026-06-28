"""Story rule/context locks for 1206.

This patch adds rule files to compact/fast context and reinforces the small turn
contract without creating gameplay logs. It is intentionally focused on rules:
truth discovery, private POV parentheses, relationship-based character presence,
31 Aug time flow, named medic usage, and East Sector arrival/base context.
"""
from __future__ import annotations

from typing import Any

from app import compact as base
import app.response_size_guard_runtime_patch as size_guard
from app.response_size_guard_runtime_patch import app

try:
    import app.fast_context_runtime_patch as fast_context
except Exception:  # pragma: no cover
    fast_context = None  # type: ignore[assignment]

RULE_FILES = [
    "state/narrative_director_rules.json",
    "state/player_input_parsing_rules.json",
    "gpt/locks/story_truth_and_private_pov_rules.md",
    "gpt/locks/east_sector_arrival_time_rules.md",
]

# Keep NPC files when the previous NPC ZIP has been applied; harmless if absent.
OPTIONAL_NPC_FILES = [
    "gpt/locks/npc_living_scene_rules.md",
    "state/session_npcs.json",
]

CHARACTER_DYNAMIC_STATE_FILES = [
    "state/character_knowledge/jun.json",
    "state/character_knowledge/ray.json",
    "state/character_knowledge/yuna.json",
]

_ORIGINAL_REQUIRED_FILES = getattr(size_guard, "_required_files", None)
_ORIGINAL_SMALL_OUTPUT_CONTRACT = getattr(size_guard, "_small_output_contract", None)
_ORIGINAL_SMALL_PROMPT_PREVIEW = getattr(size_guard, "_small_prompt_preview", None)


def _unique(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _exists(path: str) -> bool:
    if path.startswith("state/"):
        return True
    try:
        return bool(base.repo_file_exists(path))
    except Exception:
        return False


def _scene_text(current: dict[str, Any]) -> str:
    parts = [
        current.get("current_location_id"),
        current.get("current_location_text"),
        current.get("current_scene_goal"),
        current.get("last_player_input"),
        current.get("time_of_day"),
        current.get("current_day_phase"),
    ]
    return "\n".join(str(p or "") for p in parts).lower().replace("ё", "е")


def _is_east_sector_context(current: dict[str, Any]) -> bool:
    text = _scene_text(current)
    needles = [
        "east_sector", "восточный сектор", "восточную баз", "восточной баз",
        "база", "ворота", "территория базы", "общежит", "столов", "медпункт",
        "кабинет рэя", "комната акиры", "трениров", "крыша", "корт",
    ]
    return any(n in text for n in needles)


def _scene_chars(current: dict[str, Any]) -> set[str]:
    fields = [
        "active_characters", "active_character_ids", "nearby_characters", "nearby_character_ids",
        "speaking_character_ids", "observing_character_ids", "addressed_character_ids",
        "looked_at_character_ids", "scheduled_character_ids",
    ]
    values: set[str] = set()
    for field in fields:
        raw = current.get(field) or []
        if isinstance(raw, list):
            values.update(str(v).strip() for v in raw if str(v).strip())
    return values


def _extra_required_files(current: dict[str, Any]) -> list[str]:
    files: list[str] = []
    files.extend(RULE_FILES)

    if _is_east_sector_context(current):
        files.extend([
            "canon_lore/east_sector/east_sector_base.yaml",
            "locations/east_sector_locations.yaml",
            "state/east_sector_1206_context.json",
            "calendar/east_sector_1206_calendar.yaml",
        ])

    chars = _scene_chars(current)
    for cid in ["jun", "ray", "yuna"]:
        if cid in chars or (cid == "ray" and _is_east_sector_context(current)):
            files.append(f"state/character_knowledge/{cid}.json")

    for path in OPTIONAL_NPC_FILES:
        if _exists(path):
            files.append(path)

    return [path for path in _unique(files) if _exists(path)]


def _required_files_with_story_rules(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files: list[str] = []
    if callable(_ORIGINAL_REQUIRED_FILES):
        try:
            files.extend(_ORIGINAL_REQUIRED_FILES(current, future) or [])
        except Exception:
            pass
    files.extend(_extra_required_files(current or {}))
    return _unique(files)


def _small_output_contract_with_story_rules() -> dict[str, Any]:
    if callable(_ORIGINAL_SMALL_OUTPUT_CONTRACT):
        try:
            contract = dict(_ORIGINAL_SMALL_OUTPUT_CONTRACT() or {})
        except Exception:
            contract = {}
    else:
        contract = {}
    rules = list(contract.get("rules") or [])
    rules.extend([
        "Text outside parentheses is the exact spoken line of the current POV character.",
        "Text inside parentheses is private POV layer unless it describes visible action: action, thought, intention, pause, body state, observation.",
        "NPCs cannot hear, read, or answer thoughts, private intentions, author notes, or hidden conclusions inside parentheses.",
        "NPCs may react only to visible signs: movement, pause, silence, gaze, posture, breathing, object use, energy manifestation, injury, distance.",
        "NPC inference from visible behavior must be partial, uncertain, character-based, and can be wrong.",
        "Private sensory/energy/empathy/medical ability results are not visible narration facts in Akira POV unless spoken, shown by device, or already revealed.",
        "NPC goals are motives, not instant commands: preserve questions, suspicion, mistakes, hesitation, lies, tactics and character voice before action.",
        "All NPCs have the same knowledge boundary: hidden object content, purpose, route or document meaning is not known from pocket/inventory/state alone.",
        "Akira must discover major truth through action, evidence, documents, contradictions, scenes and consequences; NPCs are not lore-delivery tools.",
        "Character presence follows relationship, goals, habitual routes, current location, calendar pressure and open threads; characters are not glued to Akira but do not disappear from the world.",
        "East Sector is a living base, not Northern/lab protocol speech; everyday NPC language should stay human unless an official/closed context requires formality.",
        "If Akira arrived at East Sector before/during dawn on 31 Aug and sleeps, she wakes later on 31 Aug unless an explicit night timeskip moves the date.",
    ])
    contract["rules"] = _unique(rules)
    return contract


def _small_prompt_preview_with_story_rules(chars: list[str], required_files: list[str]) -> str:
    if callable(_ORIGINAL_SMALL_PROMPT_PREVIEW):
        try:
            text = str(_ORIGINAL_SMALL_PROMPT_PREVIEW(chars, required_files) or "")
        except Exception:
            text = ""
    else:
        text = ""
    extra = (
        "\nSTORY RULE LOCKS\n"
        "- Parentheses are private POV/action layer; NPCs do not read thoughts.\n"
        "- NPC private ability results are not visible facts in Akira POV unless revealed in-scene.\n"
        "- NPC goals are motives, not autopilot; preserve questions, uncertainty and character tactics.\n"
        "- All NPCs know only visible/heard/valid-known facts; concealed content is not readable from inventory/state.\n"
        "- Truth is discovered by Akira through evidence and scenes, not dumped by Jun/Ray/Yuna/others.\n"
        "- Character entry depends on relationship, goals, ordinary routes and social context.\n"
        "- East Sector base context and locations must be used when the scene is at/near the base.\n"
        "- East Sector everyday speech is human, not Northern/lab protocol tone.\n"
        "- 31 Aug sleep after base arrival does not automatically become 1 Sep.\n"
    )
    return text + extra


# Patch size-guard selectors and contracts.
size_guard._required_files = _required_files_with_story_rules  # type: ignore[attr-defined]
size_guard._small_output_contract = _small_output_contract_with_story_rules  # type: ignore[attr-defined]
size_guard._small_prompt_preview = _small_prompt_preview_with_story_rules  # type: ignore[attr-defined]

# Make base and fast-context use the patched recommendation path.
base.recommended_files_for_context = _required_files_with_story_rules
if fast_context is not None:
    try:
        fast_context.FAST_ALWAYS_FILES.update(RULE_FILES)
        fast_context.FAST_ALWAYS_FILES.update(CHARACTER_DYNAMIC_STATE_FILES)
        fast_context.FAST_ALWAYS_FILES.update(OPTIONAL_NPC_FILES)
        fast_context.FAST_ALWAYS_FILES.update([
            "canon_lore/east_sector/east_sector_base.yaml",
            "locations/east_sector_locations.yaml",
            "state/east_sector_1206_context.json",
            "calendar/east_sector_1206_calendar.yaml",
        ])
    except Exception:
        pass

app.version = "0.3.125-pov-npc-goal-east-v1"
