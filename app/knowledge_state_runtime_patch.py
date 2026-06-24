from __future__ import annotations

from datetime import datetime
from typing import Any
import json

import app.state_persistence_runtime_patch as state_persistence
from app import compact as base

KNOWLEDGE_FILE = "state/knowledge_state.json"
_ORIGINAL_APPLY_JSON_SECTION_ROBUST = state_persistence.apply_json_section_robust


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(_text(value).lower().replace("ё", "е").split())


def _dedupe(items: Any) -> list[str]:
    result, seen = [], set()
    for item in _as_list(items):
        s = _text(item)
        key = _norm(s)
        if s and key not in seen:
            result.append(s)
            seen.add(key)
    return result


def _ensure_root(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        state = {}
    state.setdefault("схема", "knowledge_state_v2_ru")
    state.setdefault("проект", "akira-main-1206")
    state.setdefault("персонажи", {})
    if not isinstance(state["персонажи"], dict):
        state["персонажи"] = {}
    return state


def _ensure_char(state: dict[str, Any], name: str) -> dict[str, Any]:
    chars = state.setdefault("персонажи", {})
    char = chars.setdefault(name, {})
    if not isinstance(char, dict):
        char = {}; chars[name] = char
    char["знает"] = _dedupe(char.get("знает", []))
    char["не знает"] = _dedupe(char.get("не знает", []))
    char["ошибочно считает"] = _dedupe(char.get("ошибочно считает", []))
    char.setdefault("скрывает от", {})
    if not isinstance(char["скрывает от"], dict):
        char["скрывает от"] = {}
    char.setdefault("история знаний", [])
    if not isinstance(char["история знаний"], list):
        char["история знаний"] = []
    return char


def _append_unique(char: dict[str, Any], field: str, fact: str) -> bool:
    fact = _text(fact)
    if not fact: return False
    items = _dedupe(char.get(field, []))
    if _norm(fact) not in {_norm(x) for x in items}:
        items.append(fact)
        char[field] = items
        return True
    char[field] = items
    return False


def _remove_fact(char: dict[str, Any], field: str, fact: str) -> bool:
    n = _norm(fact)
    old = _dedupe(char.get(field, []))
    new = [x for x in old if _norm(x) != n]
    if len(new) == len(old):
        new = [x for x in old if n not in _norm(x) and _norm(x) not in n]
    char[field] = new
    return len(new) != len(old)


def apply_russian_knowledge_changes(session_id: str, payload: dict[str, Any], dry_run: bool) -> bool:
    section = state_persistence.find_section(payload, ["knowledge_changes", "knowledge_state_changes", "knowledge_state"])
    if not isinstance(section, dict) or not section:
        return False
    state = _ensure_root(base.read_json(KNOWLEDGE_FILE, session_id, default={}) or {})
    before = json.dumps(state, ensure_ascii=False, sort_keys=True)

    for item in _as_list(section.get("перенести из незнания в знание")):
        if not isinstance(item, dict): continue
        name = _text(item.get("персонаж")); old = _text(item.get("факт") or item.get("старое незнание")); new = _text(item.get("новое знание") or item.get("знание") or old)
        if not name or not new: continue
        char = _ensure_char(state, name)
        if old: _remove_fact(char, "не знает", old)
        _append_unique(char, "знает", new)
        char["история знаний"].append({"дата": _text(item.get("дата")) or None, "персонаж": name, "было в незнании": old, "стало знанием": new, "источник": _text(item.get("источник")) or None, "записано": datetime.utcnow().isoformat()})

    for key, field in [("добавить знание", "знает"), ("добавить незнание", "не знает"), ("добавить ошибочное мнение", "ошибочно считает")]:
        for item in _as_list(section.get(key)):
            if not isinstance(item, dict): continue
            name = _text(item.get("персонаж")); fact = _text(item.get("факт") or item.get("знание") or item.get("незнание"))
            if name and fact: _append_unique(_ensure_char(state, name), field, fact)

    for key, field in [("убрать незнание", "не знает"), ("убрать знание", "знает")]:
        for item in _as_list(section.get(key)):
            if not isinstance(item, dict): continue
            name = _text(item.get("персонаж")); fact = _text(item.get("факт") or item.get("знание") or item.get("незнание"))
            if name and fact: _remove_fact(_ensure_char(state, name), field, fact)

    after = json.dumps(state, ensure_ascii=False, sort_keys=True)
    if after != before:
        if not dry_run:
            base.write_json(KNOWLEDGE_FILE, state, session_id)
        return True
    return False


def apply_json_section_robust_with_russian_knowledge(session_id, payload, path, names, dry_run):
    if path == KNOWLEDGE_FILE:
        return apply_russian_knowledge_changes(session_id, payload, dry_run)
    return _ORIGINAL_APPLY_JSON_SECTION_ROBUST(session_id, payload, path, names, dry_run)


state_persistence.apply_json_section_robust = apply_json_section_robust_with_russian_knowledge  # type: ignore[assignment]
