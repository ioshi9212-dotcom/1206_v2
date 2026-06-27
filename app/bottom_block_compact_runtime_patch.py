"""Bottom block compact runtime patch v4.

Keeps numeric state/relationship indicators, but prevents the visible bottom
block from becoming a state dump, protocol report, or hidden-lore summary.
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


if size_guard is not None:
    if hasattr(size_guard, "BASE_RULE_FILES"):
        _append_unique_list(size_guard.BASE_RULE_FILES, BOTTOM_BLOCK_RULES_FILE)

    _original_small_output_contract = getattr(size_guard, "_small_output_contract", None)

    def _small_output_contract_bottom_block_v4():
        if callable(_original_small_output_contract):
            contract = _original_small_output_contract()
        else:
            contract = {"rules": []}
        if not isinstance(contract, dict):
            contract = {"rules": []}
        rules = list(contract.get("rules") or [])
        extra_rules = [
            "Bottom block is a short interface panel, not a state dump, protocol report, recap, or hidden-lore summary.",
            "State block must keep numeric stats when available, but only as 2-3 compact lines: memory/emotions/flow; strength/endurance/agility/fatigue; combat/energy/risk.",
            "State block must not include 'new facts', protocol history, offscreen reports, clothing/inventory lists, long medical explanations, or scene recap.",
            "Relationships block format: Name: single signed number · 2-3 words describing relationship type/status.",
            "Relationships block must never use paired numbers like +12/-1 or +12 / -1.",
            "Relationships block must not explain what happened; it must describe current relation quality only.",
        ]
        for rule in extra_rules:
            if rule not in rules:
                rules.append(rule)
        contract["rules"] = rules
        contract["bottom_block_compact_v4"] = {
            "state_format": [
                "Память: 8% · эмоции: блок · поток: закрыт",
                "Сила: 34 · выносливость: 38 · ловкость: 46 · усталость: 12",
                "Бой: 55/85 · энергия: 0/1 · риск: высокий",
            ],
            "relationship_format": "Имя: +12 · контроль/забота",
            "relationship_number_rule": "single signed number only; no +12/-1 pairs",
            "forbidden_in_bottom_block": [
                "новые факты",
                "protocol recap",
                "offscreen status report",
                "long explanation of what happened",
                "hidden lore",
                "inventory/clothing dump unless immediately relevant",
            ],
        }
        return contract

    size_guard._small_output_contract = _small_output_contract_bottom_block_v4

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
        app.version = "0.3.124-bottom-block-compact-v4"
except Exception:
    pass
