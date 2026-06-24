"""POV switch runtime patch for 1206 v2.

Activated only by explicit `POV:` / `пов:` in latest input.
Default gameplay POV is Akira; `пов: Акира` is ignored.
Adds POV rules file + target character files only for supported non-Akira POV targets.
"""
from __future__ import annotations

import re
from typing import Any

import app.response_size_guard_runtime_patch as rt
from app.response_size_guard_runtime_patch import app
from app import compact as base

POV_SWITCH_MODE_FILE = "gpt/pov_switch_mode.md"

POV_ALIASES = {
    "акира": "akira", "akira": "akira",
    "райден": "raiden", "рейден": "raiden", "raiden": "raiden",
    "рэй": "ray", "рей": "ray", "ray": "ray",
    "ирэй": "irey", "irey": "irey",
    "хару": "haru", "haru": "haru",
}

SUPPORTED_NON_AKIRA = {"raiden", "ray", "irey", "haru"}

_ORIGINAL_SCENE_CHARS = rt._scene_chars
_ORIGINAL_REQUIRED_FILES = rt._required_files
_ORIGINAL_OUTPUT_CONTRACT = rt._small_output_contract
_ORIGINAL_PROMPT_PREVIEW = rt._small_prompt_preview


def _input_text(current: dict[str, Any] | None = None) -> str:
    current = current or {}
    return "\n".join([
        str(current.get("last_player_input") or ""),
        str(current.get("current_scene_goal") or ""),
    ]).strip()


def pov_mode_info(current: dict[str, Any] | None = None) -> dict[str, Any]:
    text = _input_text(current)
    low = text.lower().replace("ё", "е")
    if not re.search(r"\b(pov|пов)\s*[:：]", low):
        return {"active": False}

    m = re.search(r"(?:pov|пов)\s*[:：]\s*([А-Яа-яA-Za-z_\-]+)", text, re.IGNORECASE)
    raw = m.group(1).strip() if m else ""
    key = raw.lower().replace("ё", "е")
    target = POV_ALIASES.get(key)

    if target == "akira":
        return {
            "active": False,
            "ignored": True,
            "target_raw": raw,
            "target_character_id": "akira",
            "reason": "akira_is_default_pov",
        }

    if not target or target not in SUPPORTED_NON_AKIRA:
        return {
            "active": True,
            "target_raw": raw,
            "target_character_id": None,
            "error": "unknown_or_unsupported_pov_target",
        }

    return {
        "active": True,
        "target_raw": raw,
        "target_character_id": target,
        "mode": "explicit_non_akira_pov_switch",
        "duration_rule": "one scene unless the next player command explicitly keeps or changes POV",
        "speech_rule": "text outside parentheses is exact speech of the POV character",
        "action_rule": "text inside parentheses is action/body-state/intention of the POV character",
        "thought_rule": "bottom thoughts and suggested lines belong to the POV character",
        "knowledge_rule": "Akira does not gain knowledge without an in-scene source",
        "state_rule": "relationships/story/knowledge/calendar update normally",
    }


def _scene_chars_with_pov(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    chars = list(_ORIGINAL_SCENE_CHARS(current, future) or [])
    pov = pov_mode_info(current)
    target = pov.get("target_character_id")
    if pov.get("active") and target and target not in chars:
        chars.append(target)
    return chars


def _required_files_with_pov(current: dict[str, Any], future: dict[str, Any]) -> list[str]:
    files = list(_ORIGINAL_REQUIRED_FILES(current, future) or [])
    pov = pov_mode_info(current)
    target = pov.get("target_character_id")
    if pov.get("active"):
        if POV_SWITCH_MODE_FILE not in files:
            files.append(POV_SWITCH_MODE_FILE)
        if target:
            for path in rt.CHARACTER_FILE_MAP.get(target, []):
                if path not in files:
                    files.append(path)
    result: list[str] = []
    for path in files:
        if not path or path in result:
            continue
        if path.startswith("state/") or path == "runtime/scene_context_digest.md":
            result.append(path)
            continue
        try:
            if base.repo_file_exists(path):
                result.append(path)
        except Exception:
            pass
    return result


def _small_output_contract_with_pov() -> dict[str, Any]:
    contract = _ORIGINAL_OUTPUT_CONTRACT()
    rules = list(contract.get("rules") or [])
    rules.extend([
        "POV switch mode activates only with explicit 'пов:' / 'POV:' in latest input.",
        "Akira is the default POV; 'пов: Акира' does not activate special mode.",
        "Supported non-Akira POV targets for 1206 are: raiden, ray, irey, haru.",
        "When non-Akira POV is active, load gpt/pov_switch_mode.md and follow its speech/action/thought boundaries.",
        "Non-Akira POV does not grant Akira knowledge unless she has an in-scene source.",
    ])
    contract["rules"] = rules
    return contract


def _small_prompt_preview_with_pov(chars: list[str], required_files: list[str]) -> str:
    base_preview = _ORIGINAL_PROMPT_PREVIEW(chars, required_files)
    return base_preview + (
        "- POV switch: only explicit 'пов:' / 'POV:' activates non-Akira POV.\n"
        "- Supported non-Akira POV targets in 1206: raiden, ray, irey, haru.\n"
        "- If non-Akira POV is active, load gpt/pov_switch_mode.md and use POV speech/action/thought rules.\n"
        "- Non-Akira POV must not leak knowledge to Akira without an in-scene source.\n"
    )


rt.pov_mode_info = pov_mode_info
rt._scene_chars = _scene_chars_with_pov
rt._required_files = _required_files_with_pov
rt._small_output_contract = _small_output_contract_with_pov
rt._small_prompt_preview = _small_prompt_preview_with_pov

app.version = "0.3.73-1206-pov-switch-timefix-ready"
