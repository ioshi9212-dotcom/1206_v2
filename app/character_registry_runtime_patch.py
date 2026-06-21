"""1206 clean character registry patch.

Keeps the Academy-style structure:
characters/<id>/main.yaml
characters/<id>/character.yaml
characters/<id>/past.yaml

This patch does not replace compact_context_patch. It updates its registry and
start-scene character file refs after the normal runtime is imported.
"""
from __future__ import annotations

from typing import Any

import app.compact_context_patch as context_patch
import app.start_scene_runtime_patch as start_runtime

base = start_runtime.base

CHARACTER_FOLDER_ALIASES: dict[str, str] = {
    "akira": "akira",
    "char_akira": "akira",

    "jun": "jun",
    "jun_carter": "jun",
    "char_jun": "jun",

    "ray": "ray",
    "ray_carter": "ray",
    "char_ray": "ray",

    "raiden": "raiden",
    "raiden_sterling": "raiden",
    "char_raiden": "raiden",

    "irey": "irey",
    "char_irey": "irey",

    "emma": "emma",
    "char_emma": "emma",

    "yuna": "yuna",
    "yuna_gray": "yuna",
    "char_yuna": "yuna",

    "miki": "miki",
    "miki_larsen": "miki",
    "char_miki": "miki",
}


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value).strip() if value else ""
        if item and item not in result:
            result.append(item)
    return result


def _character_files(cid: str) -> list[str]:
    folder = CHARACTER_FOLDER_ALIASES.get(str(cid).strip())
    if not folder:
        return []
    return [
        f"characters/{folder}/main.yaml",
        f"characters/{folder}/character.yaml",
        f"characters/{folder}/past.yaml",
    ]


# 1) Patch compact_context_patch registry. Its character_files_for reads this dict dynamically.
context_patch.NEW_CHARACTER_FOLDERS.update(CHARACTER_FOLDER_ALIASES)

# 2) Patch start-scene forced file refs.
start_runtime.START_CHARACTER_IDS = ["akira", "jun", "irey", "emma"]
start_runtime.CONDITIONAL_CHARACTER_IDS = ["raiden", "ray"]

start_runtime.START_CHARACTER_FILES = {
    "akira": _character_files("akira"),
    "jun": _character_files("jun"),
    "irey": _character_files("irey"),
    "emma": _character_files("emma"),
    "raiden": _character_files("raiden"),
    "ray": _character_files("ray"),
    "yuna": _character_files("yuna"),
    "miki": _character_files("miki"),
}

start_runtime.START_SCENE_GOALS.update(
    {
        "akira": "Проснуться, оценить угрозу, сохранить себя, решить что делать с запиской/документами и найти Рэя / Восточный сектор.",
        "jun": "Выиграть время, не отдать Акиру Ирэю и Эмме, направить её к Рэю / Восточному сектору.",
        "irey": "Найти Акиру первым, увидеть её живой, не отдать Самуэлю, скрыть истинный мотив от Эммы.",
        "emma": "Давить, быстро забрать/вернуть Акиру в линию Самуэля, не быть мягкой союзницей.",
        "raiden": "Появиться около 03:02 из-за дня рождения/морского маршрута и следа Эммы; не помнить Акиру.",
        "ray": "При прибытии Акиры в Восточный сектор перехватить контроль, скрыть правду и ограничить доступ к ней.",
    }
)

_original_ensure_start_state = start_runtime._ensure_start_state


def _ensure_start_state_patched(session_id: str) -> dict[str, Any]:
    current = _original_ensure_start_state(session_id)

    scene_id = current.get("current_scene_id") or current.get("scene_id") or start_runtime.START_SCENE_ID
    completed = bool(current.get("start_scene_completed"))

    if scene_id == start_runtime.START_SCENE_ID and not completed:
        current["active_characters"] = list(start_runtime.START_CHARACTER_IDS)
        current["active_character_ids"] = list(start_runtime.START_CHARACTER_IDS)
        current["conditional_character_ids"] = list(start_runtime.CONDITIONAL_CHARACTER_IDS)
        current["allowed_main_characters"] = _unique(
            list(current.get("allowed_main_characters") or [])
            + list(start_runtime.START_CHARACTER_IDS)
            + list(start_runtime.CONDITIONAL_CHARACTER_IDS)
        )
        current["current_time"] = "02:40"
        current["time"] = "02:40"
        current["current_location_id"] = "jun_house_akira_room"
        current["location_id"] = "jun_house_akira_room"
        current["current_location_text"] = "дом Джуна Картера, комната Акиры"
        current["current_outfit"] = "серая пижама — футболка и шорты; босиком"
        current["visible_inventory"] = []
        current["nearby_items"] = ["дверь", "окно", "стол", "записка Рэй / Восточный сектор", "документы Акира Агатсуми / 12 апреля"]
        current["current_scene_goal"] = (
            "Стартовая сцена: Акира просыпается в 02:40, слышит голоса Эммы и Ирэя внизу, "
            "Джун тянет время, в комнате есть записка Рэй / Восточный сектор и документы Акира Агатсуми."
        )
        current["start_scene_file"] = start_runtime.START_SCENE_PATH
        current["start_scene_logic_file"] = start_runtime.START_SCENE_LOGIC_PATH

        akira_state = current.setdefault("akira_state", {})
        if isinstance(akira_state, dict):
            akira_state.update(
                {
                    "visible_state": "резко проснулась; внешне спокойна и собрана",
                    "internal_state": "эмоции заблокированы; память держит только последние два года",
                    "body_state": "тело собрано и реагирует раньше памяти",
                    "hair_state": "длинные белые волосы без чёлки",
                    "eye_state": "карие почти чёрные; на свету янтарно-красноватые",
                    "flow_state": "поток заблокирован",
                    "emotion_access": "0/100",
                    "memory_recovery": "0/100",
                }
            )

        start_runtime._write_state(session_id, "state/current_state.json", current)

    return current


start_runtime._ensure_start_state = _ensure_start_state_patched

try:
    start_runtime.app.version = "0.3.90-1206-clean-character-registry-miki"
except Exception:
    pass
