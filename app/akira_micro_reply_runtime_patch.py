"""Akira low-stakes micro-reply rule.

Allows tiny Akira-style replies only when the answer is purely local and has no
route/relationship/knowledge/safety/trust consequences. This prevents NPCs from
having to talk to themselves during routine check-ins while preserving player
control over meaningful Akira choices.
"""
from __future__ import annotations

from typing import Any

from app import compact as base
import app.response_size_guard_runtime_patch as size_guard

_ORIGINAL_SMALL_OUTPUT_CONTRACT = getattr(size_guard, "_small_output_contract", None)
_ORIGINAL_SMALL_PROMPT_PREVIEW = getattr(size_guard, "_small_prompt_preview", None)

OLD_BROAD_RULE = "Low-stakes service, medical or domestic micro-answers may be brief in Akira voice if they change no route, truth, trust, conflict, safety, access or relationship state."

MICRO_REPLY_RULES = [
    "Akira player-control boundary: consequential Akira speech is written only by the player.",
    "Allowed exception: the renderer may give Akira a very short in-character micro-reply only when the reply is a local factual answer and changes no route, knowledge, trust, relationship, conflict, safety, access, promise, consent, reveal, or plan.",
    "Allowed micro-replies must match the current scene tone and Akira's voice: short, dry, level, cold, poisonous, sarcastic or blunt as appropriate.",
    "If the answer would create a new choice, disclose a fact, soften/harden a relationship, accept/refuse a meaningful offer, change route, invite contact, reveal emotion, or affect safety, do not answer for Akira; stop at the response point or offer it in possible lines.",
    "Do not use micro-replies to make Akira confess, explain herself, ask new questions, forgive, trust, attack, agree, leave, disclose memories, or change stance.",
]


def _unique(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in out:
            out.append(item)
    return out


def _small_output_contract_with_akira_micro_reply() -> dict[str, Any]:
    if callable(_ORIGINAL_SMALL_OUTPUT_CONTRACT):
        try:
            contract = dict(_ORIGINAL_SMALL_OUTPUT_CONTRACT() or {})
        except Exception:
            contract = {}
    else:
        contract = {}
    rules = [r for r in list(contract.get("rules") or []) if str(r).strip() != OLD_BROAD_RULE]
    rules.extend(MICRO_REPLY_RULES)
    contract["rules"] = _unique(rules)
    contract["akira_micro_reply_policy"] = {
        "allowed": "only local non-consequential factual micro-replies",
        "voice": "short, dry, level, cold, poisonous/sarcastic/blunt if scene tone supports it",
        "forbidden_if_changes": [
            "route", "knowledge", "trust", "relationship", "conflict", "safety", "access",
            "promise", "consent", "reveal", "plan", "stance", "memory", "emotion disclosure",
        ],
    }
    return contract


def _small_prompt_preview_with_akira_micro_reply(chars: list[str], required_files: list[str]) -> str:
    if callable(_ORIGINAL_SMALL_PROMPT_PREVIEW):
        try:
            text = str(_ORIGINAL_SMALL_PROMPT_PREVIEW(chars, required_files) or "")
        except Exception:
            text = ""
    else:
        text = ""
    return text + (
        "\nAKIRA MICRO-REPLY LOCK\n"
        "- Consequential Akira speech belongs to the player.\n"
        "- You may give only a tiny Akira-style local factual reply when it changes no route/knowledge/trust/relationship/conflict/safety/access/plan/reveal.\n"
        "- If the reply has weight, stop at the response point or put it in possible Akira lines.\n"
    )


size_guard._small_output_contract = _small_output_contract_with_akira_micro_reply  # type: ignore[attr-defined]
size_guard._small_prompt_preview = _small_prompt_preview_with_akira_micro_reply  # type: ignore[attr-defined]
base.output_format_contract = _small_output_contract_with_akira_micro_reply

try:
    size_guard.app.version = "0.3.137-akira-micro-reply-v1"
except Exception:
    pass
