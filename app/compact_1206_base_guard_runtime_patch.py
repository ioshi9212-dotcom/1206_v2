"""1206 v2 guard for legacy compact.py fallback.

This patch keeps the repository files untouched, but replaces the old base
fallback character map from app/compact.py during production import.

The production fallback should resolve characters through the 1206 v2 structure:
characters/<id>/main.yaml.
"""
from __future__ import annotations

from typing import Any

from app import compact as base

try:
    import app.compact_context_patch as compact_context_patch  # type: ignore
except Exception:
    compact_context_patch = None  # type: ignore[assignment]

try:
    import app.response_size_guard_runtime_patch as response_size_guard  # type: ignore
except Exception:
    response_size_guard = None  # type: ignore[assignment]

CHARACTER_MAIN_FILES_1206_V2: dict[str, str] = {
    "akira": "characters/akira/main.yaml",
    "char_akira": "characters/akira/main.yaml",
    "jun": "characters/jun/main.yaml",
    "jun_carter": "characters/jun/main.yaml",
    "char_jun": "characters/jun/main.yaml",
    "ray": "characters/ray/main.yaml",
    "char_ray": "characters/ray/main.yaml",
    "raiden": "characters/raiden/main.yaml",
    "raiden_sterling": "characters/raiden/main.yaml",
    "char_raiden": "characters/raiden/main.yaml",
    "irey": "characters/irey/main.yaml",
    "char_irey": "characters/irey/main.yaml",
    "emma": "characters/emma/main.yaml",
    "char_emma": "characters/emma/main.yaml",
    "yuna": "characters/yuna/main.yaml",
    "yuna_gray": "characters/yuna/main.yaml",
    "char_yuna": "characters/yuna/main.yaml",
    "miki": "characters/miki/main.yaml",
    "miki_larsen": "characters/miki/main.yaml",
    "char_miki": "characters/miki/main.yaml",
    "haru": "characters/haru/main.yaml",
    "haru_foster": "characters/haru/main.yaml",
    "samuel": "characters/samuel/main.yaml",
    "samuel_sterling": "characters/samuel/main.yaml",
    "alex": "characters/alex/main.yaml",
    "shiro": "characters/shiro/main.yaml",
    "kai": "characters/kai/main.yaml",
}

base.MAIN_CHARACTER_FILES.clear()
base.MAIN_CHARACTER_FILES.update(CHARACTER_MAIN_FILES_1206_V2)


def character_file_1206_v2(character_id: str) -> str:
    cid = str(character_id or "").strip()
    mapped = base.MAIN_CHARACTER_FILES.get(cid)
    if mapped:
        return mapped
    direct = f"characters/{cid}/main.yaml"
    if cid and base.repo_file_exists(direct):
        return direct
    return f"characters/npc/{cid}.md"


base.character_file = character_file_1206_v2

if compact_context_patch is not None:
    folders = getattr(compact_context_patch, "NEW_CHARACTER_FOLDERS", None)
    if isinstance(folders, dict):
        folders.pop("ray_carter", None)
        folders["ray"] = "ray"
        folders["char_ray"] = "ray"

if response_size_guard is not None:
    folders = getattr(response_size_guard, "CHARACTER_FOLDERS", None)
    if isinstance(folders, dict):
        folders.pop("ray_carter", None)
        folders["ray"] = "ray"
        folders["char_ray"] = "ray"

_ORIGINAL_OUTPUT_FORMAT_CONTRACT = base.output_format_contract


def output_format_contract_1206_v2() -> dict[str, Any]:
    try:
        contract = _ORIGINAL_OUTPUT_FORMAT_CONTRACT()
    except Exception:
        contract = {}
    if not isinstance(contract, dict):
        contract = {}
    rules = list(contract.get("rules", []) or [])
    cleaned = [rule for rule in rules if "Livia" not in str(rule) and "Academy Prequel" not in str(rule)]
    guard_rules = [
        "1206 v2 base fallback: do not load old Academy characters/main/*.md files.",
        "1206 v2 base fallback: character_file() resolves to characters/<id>/main.yaml.",
        "Ray visible name is only 'Рэй' / 'командующий Рэй'; technical aliases are not permission to use a surname.",
    ]
    for rule in reversed(guard_rules):
        if rule not in cleaned:
            cleaned.insert(0, rule)
    contract["rules"] = cleaned
    contract["base_character_fallback"] = "1206_v2_only"
    return contract


base.output_format_contract = output_format_contract_1206_v2
