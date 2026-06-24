"""
Scene output format runtime patch v16.

Restores the selected selected visual-novel output format after speed mode.
"""

from __future__ import annotations

from typing import Any

import app.context_transport_runtime_patch as rt
from app.context_transport_runtime_patch import app
from app import compact as base
import app.compact_context_patch as ccp

SCENE_FORMAT_FILE = "gpt/scene_format.md"
RUNTIME_DIGEST_FILE = "runtime/scene_context_digest.md"
RUNTIME_RULES_FILE = "gpt/locks/runtime_scene_rules_digest.md"

_ORIG_RT_LEAN = getattr(rt, "lean_recommended_files_for_context", None)
_ORIG_BASE_RECOMMENDED = getattr(base, "recommended_files_for_context", None)
_ORIG_BUILD_DIGEST = getattr(rt, "build_scene_context_digest", None)


def _unique(paths: list[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        item = str(path or "").strip()
        if item and item not in result:
            result.append(item)
    return result


def _add_scene_format(paths: list[str]) -> list[str]:
    result: list[str] = []
    for path in paths:
        result.append(path)
        if path == RUNTIME_RULES_FILE and base.repo_file_exists(SCENE_FORMAT_FILE):
            result.append(SCENE_FORMAT_FILE)
    if SCENE_FORMAT_FILE not in result and base.repo_file_exists(SCENE_FORMAT_FILE):
        if RUNTIME_DIGEST_FILE in result:
            result.insert(result.index(RUNTIME_DIGEST_FILE) + 1, SCENE_FORMAT_FILE)
        else:
            result.insert(0, SCENE_FORMAT_FILE)
    return _unique(result)


def recommended_files_with_scene_format(current: dict[str, Any] | None = None, future: dict[str, Any] | None = None) -> list[str]:
    if callable(_ORIG_RT_LEAN):
        files = _ORIG_RT_LEAN(current, future)
    elif callable(_ORIG_BASE_RECOMMENDED):
        files = _ORIG_BASE_RECOMMENDED(current, future)
    else:
        files = []
    return _add_scene_format(list(files or []))


def build_scene_context_digest_with_style(session_id: str) -> str:
    base_digest = _ORIG_BUILD_DIGEST(session_id) if callable(_ORIG_BUILD_DIGEST) else ""
    strict = """
## Strict visible output format reminder

Use the selected 1206 scene style, not loose emoji-card style.

Required header:

🌘 Астрейн · 1206 г., 31 августа, день уточнить
🕒 02:40 · 📍 Дом Джуна
🌦️ Погода: ...
⚙️ Активное состояние сцены: учитывать в тексте, действиях и предметах

✦ ...
🧥 ...
◈ ...

━━━━━━━━━━━━━━━━━━━━

Dialogue:
**Имя/видимый дескриптор** — Реплика. (*короткая ремарка*)

Bottom blocks:
━━━━━━━━━━━━━━━━━━━━

✦ Что можно сделать
Варианты ниже не считаются действием, пока игрок не выбрал.

◈ ...

✦ Что Акира могла бы сказать

— “...”

✦ Мысли Акиры

— ...

Akira suggestion tone:
poisonous, dry, sharp, socially dangerous, not cute-friendly, not generic helper jokes.
"""
    return str(base_digest).rstrip() + "\n\n" + strict.strip() + "\n"


def strict_output_format_contract() -> dict[str, Any]:
    return {
        "priority": "highest_for_scene_output",
        "selected_style": "academy_old_visual_novel_header_v2",
        "header_template": [
            "🌘 Астрейн · 1206 г., 31 августа, день уточнить",
            "🕒 02:40 · 📍 Дом Джуна",
            "🌦️ Погода: ...",
            "⚙️ Активное состояние сцены: учитывать в тексте, действиях и предметах",
            "",
            "✦ видимое состояние Акиры",
            "🧥 одежда/форма только из current_state",
            "◈ предметы при себе / рядом только из current_state",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
        ],
        "forbidden_header_style": [
            "Do not use loose card header: 🗓️ date / 📍 location / 👤 Akira / 🎒 nearby.",
            "Do not omit separators.",
            "Do not turn the header into a generic status list.",
        ],
        "dialogue_format": "**Имя или видимый дескриптор** — Реплика. (*короткая ремарка*)",
        "description_format": "*Описание действия, окружения или атмосферы отдельной строкой курсивом.*",
        "bottom_blocks": [
            "━━━━━━━━━━━━━━━━━━━━",
            "✦ Что можно сделать",
            "Варианты ниже не считаются действием, пока игрок не выбрал.",
            "◈ ...",
            "✦ Что Акира могла бы сказать",
            "— “...”",
            "✦ Мысли Акиры",
            "— ...",
        ],
        "akira_suggestion_tone": [
            "Possible Akira lines must be poisonous, dry, sharp and socially dangerous.",
            "Do not make suggested Akira lines generic, friendly, cute, soft, helpful or neutral.",
            "Use Akira's current behavior profile and loaded character card.",
        ],
        "rules": [
            "Final gameplay answer is the scene only.",
            "Every spoken line starts with bold speaker name or visible descriptor.",
            "Do not use names Akira has not heard or read yet.",
            "After speaker name use long dash.",
            "Dialogue text is plain.",
            "Optional stage note must be short and italic in parentheses.",
            "Descriptions are separate italic paragraphs.",
            "No direct Akira thoughts inside the scene.",
            "Akira thoughts only in bottom block: Мысли Акиры.",
            "No invented Akira speech in the scene body unless the player wrote it outside parentheses.",
            "If output format or Akira suggestion tone is wrong, rewrite before sending.",
        ],
    }


rt.lean_recommended_files_for_context = recommended_files_with_scene_format
rt.build_scene_context_digest = build_scene_context_digest_with_style

base.recommended_files_for_context = recommended_files_with_scene_format
base.output_format_contract = strict_output_format_contract

ccp.recommended_files_for_context = recommended_files_with_scene_format

app.version = "0.3.36-scene-output-format-v16"
