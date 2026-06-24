from __future__ import annotations

import app.response_size_guard_runtime_patch as size_guard

try:
    import app.prompt_builder as prompt_builder
except Exception:
    prompt_builder = None

LOCK_FILE = "gpt/locks/scene_pacing_transition_lock.md"

PACING_RULES = [
    "Use story-scene pacing, not step-by-step RPG pacing.",
    "When the player gives a chain of actions, movement direction, following, waiting, or a routine transition, complete that declared chain to the nearest meaningful point.",
    "Do not split ordinary movement into choices for every step, turn, glance, pause, meter, or harmless route detail.",
    "Stop only when there is a real response point: direct address to Akira, demanded decision, physical block, new threat, important character entry, consequential route fork, new information requiring reaction, body/energy/control risk, or relationship/safety/control decision.",
    "Do not repeat an already chosen movement/following action as a new bottom-block choice unless a new obstacle or consequence appears.",
    "Bottom-block actions must have stakes for risk, route, knowledge, relationships, body state, control, safety, access, or conflict.",
    "World and NPCs keep acting according to their goals; Akira's silence or waiting does not freeze the scene.",
    "Never mention pacing rules, compression, nodes, mechanics, structure, or directorial handling in visible scene prose.",
]

if LOCK_FILE not in getattr(size_guard, "START_REQUIRED_FILES", []):
    size_guard.START_REQUIRED_FILES.append(LOCK_FILE)

_ORIGINAL_SMALL_OUTPUT_CONTRACT = size_guard._small_output_contract
_ORIGINAL_SMALL_PROMPT_PREVIEW = size_guard._small_prompt_preview


def _small_output_contract_scene_pacing() -> dict:
    contract = _ORIGINAL_SMALL_OUTPUT_CONTRACT()
    rules = contract.setdefault("rules", [])
    for rule in PACING_RULES:
        if rule not in rules:
            rules.append(rule)
    contract["scene_pacing"] = {
        "mode": "story_scene_transition",
        "not_step_by_step_rpg": True,
        "complete_declared_action_chain": True,
        "stop_only_on_meaningful_response_point": True,
        "forbid_micro_choices_without_stakes": True,
        "forbid_visible_rule_commentary": True,
    }
    return contract


def _small_prompt_preview_scene_pacing(chars: list[str], required_files: list[str]) -> str:
    base = _ORIGINAL_SMALL_PROMPT_PREVIEW(chars, required_files).rstrip()
    brief = (
        "\nSCENE PACING:\n"
        "- Use story-scene pacing, not step-by-step RPG pacing.\n"
        "- Complete the player's declared action chain to the nearest meaningful response point.\n"
        "- Do not stop for every step, turn, glance, pause, meter, or harmless route detail.\n"
        "- Stop only for a real response point with stakes.\n"
        "- Bottom-block actions must have stakes. Do not repeat an already chosen movement/following action as a new choice unless something changed.\n"
        "- World and NPCs keep acting; silence/waiting does not freeze the scene.\n"
        "- Never mention pacing rules, compression, nodes, mechanics, structure, or directorial handling in visible prose.\n"
    ).rstrip()
    return f"{base}\n{brief}\n"


size_guard._small_output_contract = _small_output_contract_scene_pacing
size_guard._small_prompt_preview = _small_prompt_preview_scene_pacing


if prompt_builder is not None and hasattr(prompt_builder, "build_prompt_preview"):
    _ORIGINAL_BUILD_PROMPT_PREVIEW = prompt_builder.build_prompt_preview

    def build_prompt_preview_scene_pacing(*args, **kwargs) -> str:
        text = _ORIGINAL_BUILD_PROMPT_PREVIEW(*args, **kwargs).rstrip()
        brief = (
            "\nSCENE PACING:\n"
            "- Complete the player's declared action chain to the nearest meaningful response point.\n"
            "- Do not fragment ordinary movement into step-by-step choices.\n"
            "- Stop only when the scene presents a real response point with stakes.\n"
            "- Do not put rule/mechanic/directorial wording into visible prose.\n"
        ).rstrip()
        return f"{text}\n\n{brief}\n"

    prompt_builder.build_prompt_preview = build_prompt_preview_scene_pacing
