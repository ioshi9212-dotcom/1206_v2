from __future__ import annotations

import app.response_size_guard_runtime_patch as size_guard

_ORIGINAL_SMALL_OUTPUT_CONTRACT = size_guard._small_output_contract
_ORIGINAL_SMALL_PROMPT_PREVIEW = size_guard._small_prompt_preview

STRICT_BOTTOM_PANEL_RULES = [
    "Bottom block is strict: max 3 items in `Что можно сделать`, max 3 items in `Что Акира могла бы сказать`, max 3 items in `Мысли Акиры`; delete extra items before final output.",
    "`Мысли Акиры` must be written only in Akira's first person, short and tied to the current visible frame.",
    "Inventory, clothes and item lists belong only in the scene header when confirmed; never add separate bottom sections like `Инвентарь`, `Предметы`, `Одежда`, `Снаряжение`.",
    "Do not put inventory, clothes, item lists or pocket contents inside `Состояние`.",
]


def _small_output_contract_strict() -> dict:
    contract = _ORIGINAL_SMALL_OUTPUT_CONTRACT()
    rules = contract.setdefault("rules", [])
    for rule in STRICT_BOTTOM_PANEL_RULES:
        if rule not in rules:
            rules.append(rule)
    contract["bottom_block_limits"] = {
        "actions_max": 3,
        "possible_akira_lines_max": 3,
        "akira_thoughts_max": 3,
        "akira_thoughts_pov": "first_person_only",
        "inventory_visible_only_in_header": True,
        "forbidden_bottom_sections": ["Инвентарь", "Предметы", "Одежда", "Снаряжение"],
        "state_block_forbids": ["inventory", "clothes", "item_lists", "pocket_contents"],
    }
    return contract


def _small_prompt_preview_strict(chars: list[str], required_files: list[str]) -> str:
    base = _ORIGINAL_SMALL_PROMPT_PREVIEW(chars, required_files).rstrip()
    strict_brief = """
- Strict bottom panel limits: 1-3 actions, 1-3 possible Akira lines, 1-3 Akira thoughts. If there are 4+ items, delete extras before final output.
- Akira thoughts must be first-person only, short, and tied to the current frame.
- Do not add bottom sections for inventory/items/clothes/gear. Confirmed inventory/items/clothes belong only in the scene header.
- Do not put inventory, clothes, item lists or pocket contents inside `Состояние`.
""".rstrip()
    return f"{base}\n{strict_brief}\n"


size_guard._small_output_contract = _small_output_contract_strict
size_guard._small_prompt_preview = _small_prompt_preview_strict
