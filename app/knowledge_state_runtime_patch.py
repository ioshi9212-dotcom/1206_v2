from __future__ import annotations

from datetime import datetime
from typing import Any
import json

import app.state_persistence_runtime_patch as state_persistence
import app.compact_1206_base_guard_runtime_patch as compact_1206_guard  # noqa: F401
import app.repair_roster_1206_runtime_patch as repair_roster_1206  # noqa: F401
from app import compact as base

LEGACY_KNOWLEDGE_INDEX_FILE = "state/knowledge_state.json"
CHARACTER_KNOWLEDGE_DIR = "state/character_knowledge"
_ORIGINAL_APPLY_JSON_SECTION_ROBUST = state_persistence.apply_json_section_robust

NAME_TO_ID = {
    "Акира": "akira", "akira": "akira",
    "Джун": "jun", "jun": "jun", "jun_carter": "jun",
    "Ирэй": "irey", "irey": "irey",
    "Эмма": "emma", "emma": "emma",
    "Райден": "raiden", "raiden": "raiden", "raiden_sterling": "raiden", "парень с пирсингом": "raiden",
    "Рэй": "ray", "ray": "ray", "char_ray": "ray",
    "Юна": "yuna", "yuna": "yuna",
    "Мики": "miki", "miki": "miki",
}

DISPLAY = {
    "akira": "Акира", "jun": "Джун", "irey": "Ирэй", "emma": "Эмма", "raiden": "Райден", "ray": "Рэй", "yuna": "Юна", "miki": "Мики"
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(_text(value).lower().replace("ё", "е").split())


def _cid(value: Any) -> str:
    raw = _text(value)
    return NAME_TO_ID.get(raw, NAME_TO_ID.get(raw.lower(), raw.lower()))


def _dedupe(items: Any) -> list[str]:
    result, seen = [], set()
    for item in _as_list(items):
        s = _text(item)
        key = _norm(s)
        if s and key not in seen:
            result.append(s)
            seen.add(key)
    return result


def _state_path(cid: str) -> str:
    return f"{CHARACTER_KNOWLEDGE_DIR}/{cid}.json"


def _ensure_char_state(cid: str, state: Any | None = None) -> dict[str, Any]:
    if not isinstance(state, dict):
        state = {}
    state.setdefault("schema", "character_knowledge_state_v1_ru")
    state.setdefault("character_id", cid)
    state.setdefault("display_name", DISPLAY.get(cid, cid))
    state.setdefault("rules", [
        "Файл хранит только динамические знания и память персонажа по сыгранным сценам.",
        "Постоянные знания персонажа хранятся в characters/<id>/knowledge.yaml.",
        "Этот файл подтягивается runtime только когда персонаж участвует в сцене или находится в фокусе."
    ])
    for field in ["знает", "не знает", "ошибочно считает", "видел", "слышал", "произошло при нём", "важное от Акиры", "важное сказанное Акире", "выводы", "история знаний"]:
        state[field] = _dedupe(state.get(field, [])) if field != "история знаний" else list(state.get(field, []) or [])
    state.setdefault("скрывает от", {})
    if not isinstance(state["скрывает от"], dict):
        state["скрывает от"] = {}
    return state


def _read_char(session_id: str, cid: str) -> dict[str, Any]:
    return _ensure_char_state(cid, base.read_json(_state_path(cid), session_id, default={}) or {})


def _write_char(session_id: str, cid: str, state: dict[str, Any], dry_run: bool) -> None:
    if not dry_run:
        base.write_json(_state_path(cid), state, session_id)


def _append_unique(state: dict[str, Any], field: str, fact: str) -> bool:
    fact = _text(fact)
    if not fact:
        return False
    items = _dedupe(state.get(field, []))
    if _norm(fact) not in {_norm(x) for x in items}:
        items.append(fact)
        state[field] = items
        return True
    state[field] = items
    return False


def _remove_fact(state: dict[str, Any], field: str, fact: str) -> bool:
    n = _norm(fact)
    old = _dedupe(state.get(field, []))
    new = [x for x in old if _norm(x) != n]
    if len(new) == len(old):
        new = [x for x in old if n not in _norm(x) and _norm(x) not in n]
    state[field] = new
    return len(new) != len(old)


def _log(state: dict[str, Any], kind: str, fact: str, source: str | None = None, extra: dict[str, Any] | None = None) -> None:
    entry = {"kind": kind, "fact": fact, "source": source, "recorded_at": datetime.utcnow().isoformat()}
    if extra:
        entry.update(extra)
    state.setdefault("история знаний", [])
    if isinstance(state["история знаний"], list):
        state["история знаний"].append(entry)


def _item_name(item: dict[str, Any]) -> str:
    return _text(item.get("персонаж") or item.get("character_id") or item.get("id") or item.get("имя"))


def _item_fact(item: dict[str, Any]) -> str:
    return _text(item.get("факт") or item.get("знание") or item.get("незнание") or item.get("текст") or item.get("событие") or item.get("реплика"))


def _apply_list_section(session_id: str, section: dict[str, Any], key: str, field: str, dry_run: bool) -> list[str]:
    changed_files: list[str] = []
    for item in _as_list(section.get(key)):
        if not isinstance(item, dict):
            continue
        cid = _cid(_item_name(item)); fact = _item_fact(item)
        if not cid or not fact:
            continue
        state = _read_char(session_id, cid)
        if _append_unique(state, field, fact):
            _log(state, key, fact, _text(item.get("источник")) or None)
            _write_char(session_id, cid, state, dry_run)
            changed_files.append(_state_path(cid))
    return changed_files


def apply_character_knowledge_changes(session_id: str, payload: dict[str, Any], dry_run: bool) -> list[str]:
    section = state_persistence.find_section(payload, ["knowledge_changes", "knowledge_state_changes", "character_knowledge_changes", "memory_changes"])
    if not isinstance(section, dict) or not section:
        return []
    changed_files: list[str] = []

    for item in _as_list(section.get("перенести из незнания в знание")):
        if not isinstance(item, dict):
            continue
        cid = _cid(_item_name(item))
        old = _text(item.get("факт") or item.get("старое незнание"))
        new = _text(item.get("новое знание") or item.get("знание") or old)
        if not cid or not new:
            continue
        state = _read_char(session_id, cid)
        changed = False
        if old:
            changed = _remove_fact(state, "не знает", old) or changed
        changed = _append_unique(state, "знает", new) or changed
        if changed:
            _log(state, "перенести из незнания в знание", new, _text(item.get("источник")) or None, {"было в незнании": old})
            _write_char(session_id, cid, state, dry_run)
            changed_files.append(_state_path(cid))

    for key, field in [
        ("добавить знание", "знает"),
        ("добавить незнание", "не знает"),
        ("добавить ошибочное мнение", "ошибочно считает"),
        ("добавить увиденное", "видел"),
        ("добавить услышанное", "слышал"),
        ("добавить событие при персонаже", "произошло при нём"),
        ("добавить важное от Акиры", "важное от Акиры"),
        ("добавить важное сказанное Акире", "важное сказанное Акире"),
        ("добавить вывод", "выводы"),
    ]:
        changed_files.extend(_apply_list_section(session_id, section, key, field, dry_run))

    for key, field in [("убрать незнание", "не знает"), ("убрать знание", "знает"), ("убрать ошибочное мнение", "ошибочно считает")]:
        for item in _as_list(section.get(key)):
            if not isinstance(item, dict):
                continue
            cid = _cid(_item_name(item)); fact = _item_fact(item)
            if not cid or not fact:
                continue
            state = _read_char(session_id, cid)
            if _remove_fact(state, field, fact):
                _log(state, key, fact, _text(item.get("источник")) or None)
                _write_char(session_id, cid, state, dry_run)
                changed_files.append(_state_path(cid))

    return sorted(set(changed_files))


def apply_json_section_robust_with_character_knowledge(session_id, payload, path, names, dry_run):
    if path == LEGACY_KNOWLEDGE_INDEX_FILE:
        changed = apply_character_knowledge_changes(session_id, payload, dry_run)
        base.LAST_KNOWLEDGE_CHANGED_FILES = changed
        return bool(changed)
    return _ORIGINAL_APPLY_JSON_SECTION_ROBUST(session_id, payload, path, names, dry_run)


state_persistence.apply_json_section_robust = apply_json_section_robust_with_character_knowledge  # type: ignore[assignment]
base.apply_character_knowledge_changes = apply_character_knowledge_changes  # type: ignore[attr-defined]
base.LAST_KNOWLEDGE_CHANGED_FILES = []
