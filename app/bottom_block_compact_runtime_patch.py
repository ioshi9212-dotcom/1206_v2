"""Bottom block compact runtime patch v5.

Makes the visible lower interface small and prevents state/relationship dumps.
This patch must be imported by app.production_runtime_patch.
"""
from __future__ import annotations

BOTTOM_BLOCK_RULES_FILE = "gpt/locks/bottom_block_compact_rules.md"

try:
    import app.response_size_guard_runtime_patch as size_guard
    from app.response_size_guard_runtime_patch import app
except Exception:  # pragma: no cover
    size_guard = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]


def _append_unique_list(container, value: str) -> None:
    try:
        if value not in container:
            container.append(value)
    except Exception:
        pass


STRICT_BOTTOM_RULES = [
    "Bottom block is a tiny interface panel, not a state dump, recap, protocol report, medical chart, inventory/clothing list, or offscreen tracker.",
    "State block maximum: 3 compact lines total. If a detail does not change the next meaningful choice, compress it into one word or omit it.",
    "Never write 'new facts' / 'новые факты' in the visible State block. Knowledge changes belong to state files, not UI text.",
    "State line format: memory/emotions/flow; body stats/fatigue/injury count; combat/energy/risk. No long injury explanations, clothing notes, treatment history, NPC injuries, object ledgers, or location summaries.",
    "Relationships block maximum: 4 entries and only characters currently present, addressed, or immediately affecting the current beat. No offscreen statuses, inventory notes, or injury logs.",
    "Relationship entry format: Name: single signed number · 1-3 words. Do not explain what happened and do not describe logistics.",
    "Before final output, delete bottom-block clauses after semicolons that recap events, report offscreen movement, explain medical details, or repeat the scene.",
]

if size_guard is not None:
    if hasattr(size_guard, "BASE_RULE_FILES"):
        _append_unique_list(size_guard.BASE_RULE_FILES, BOTTOM_BLOCK_RULES_FILE)

    _original_small_output_contract = getattr(size_guard, "_small_output_contract", None)

    def _small_output_contract_bottom_block_v5():
        if callable(_original_small_output_contract):
            contract = _original_small_output_contract()
        else:
            contract = {"rules": []}
        if not isinstance(contract, dict):
            contract = {"rules": []}
        rules = list(contract.get("rules") or [])
        for rule in STRICT_BOTTOM_RULES:
            if rule not in rules:
                rules.append(rule)
        contract["rules"] = rules
        contract["bottom_block_compact_v5"] = {
            "state_max_lines": 3,
            "state_example": [
                "Память: 8% · эмоции: блок · поток: закрыт",
                "Тело: сила 22 · вын 17 · ловк 37 · усталость 86 · травмы 1",
                "Бой: 47/85 · энергия: 0 · риск: низко-средний",
            ],
            "relationship_max_entries": 4,
            "relationship_format": "Имя: +12 · 1-3 слова",
            "forbidden_visible_bottom_terms": [
                "новые факты", "new facts", "offscreen", "вне текущего контакта",
                "идёт к периметру", "одежда заменена", "обезболивание запрещено",
                "протокол", "подробное медицинское пояснение",
            ],
        }
        return contract

    size_guard._small_output_contract = _small_output_contract_bottom_block_v5

try:
    import app.fast_context_runtime_patch as fast_context
except Exception:  # pragma: no cover
    fast_context = None  # type: ignore[assignment]

if fast_context is not None and hasattr(fast_context, "FAST_ALWAYS_FILES"):
    try:
        fast_context.FAST_ALWAYS_FILES.add(BOTTOM_BLOCK_RULES_FILE)
    except Exception:
        pass

try:
    if app is not None:
        app.version = "0.3.134-npc-item-continuity-v1"
except Exception:
    pass
