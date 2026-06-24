from __future__ import annotations

"""Runtime override for legacy minute anchors in 1206-08-31 calendar text.

The repository still contains older minute-based labels for compatibility/history.
This patch makes the gameplay context expose day-phase windows instead of hard
clock triggers, so rendering cannot fire Raiden or other events by exact minute.
"""

import app.current_scene_context_filter_runtime_patch as current_scene
import app.lean_context_loading_runtime_patch as lean

try:
    import app.calendar_scene_runtime_patch as calendar_runtime
except Exception:  # pragma: no cover
    calendar_runtime = None  # type: ignore[assignment]

DAY_FILE = "calendar/days/1206-08-31.yaml"


def sanitize_day_phase_calendar(text: str) -> str:
    if not text:
        return text
    replacements = {
        'time_start: "02:40"': 'start_phase: "поздняя ночь"',
        '  - id: start_scene_0240\n    time: "02:40"': '  - id: start_scene_late_night\n    phase: "поздняя ночь"',
        '  - id: raiden_arrival_0302\n    time: "03:02"': '  - id: raiden_arrival_late_night\n    phase: "поздняя ночь"',
        '  - id: samuel_people_window_0323\n    earliest_time: "03:23"': '  - id: samuel_people_predawn_window\n    phase: "предрассвет"',
        '"не держать сцену на 02:40 после нескольких обменов репликами"': '"не держать сцену в стартовой фазе после нескольких обменов репликами"',
        'time: "02:40"\n    note: "это старт, не якорь навсегда"': 'phase: "поздняя ночь"\n    note: "это стартовая фаза, не якорь навсегда"',
        '"сбрасывать время к старту"': '"сбрасывать время к стартовой фазе"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    extra_rule = '    - "не запускать Райдена, людей Самуэля или другой календарный event по точной минуте"\n'
    if extra_rule not in text and '    - "сбрасывать время к стартовой фазе"\n' in text:
        text = text.replace('    - "сбрасывать время к стартовой фазе"\n', '    - "сбрасывать время к стартовой фазе"\n' + extra_rule)

    raiden_condition = (
        '    condition:\n'
        '      - "прошло достаточно сцены после первого вывода; не первые минуты/не первые пару ходов"\n'
        '      - "Эмма или другой кайросский/энергетический след достаточно заметен"\n'
        '      - "Райден логично идёт от морского маршрута/смотровой точки к источнику следа"\n'
    )
    if '  - id: raiden_arrival_late_night\n    phase: "поздняя ночь"\n    type: "conditional_required_window"\n    condition:' not in text:
        text = text.replace(
            '  - id: raiden_arrival_late_night\n    phase: "поздняя ночь"\n    type: "conditional_required_window"\n',
            '  - id: raiden_arrival_late_night\n    phase: "поздняя ночь"\n    type: "conditional_required_window"\n' + raiden_condition,
        )
    if '      - "запускать появление Райдена по точной минуте или таймеру"' not in text:
        text = text.replace(
            '      - "называть Акиру Кирой"\n',
            '      - "называть Акиру Кирой"\n      - "запускать появление Райдена по точной минуте или таймеру"\n',
        )
    if '      - "прошла длительная задержка после ночного старта"' not in text:
        text = text.replace(
            '      - "ветка дома/дороги ещё активна"\n',
            '      - "ветка дома/дороги ещё активна"\n      - "прошла длительная задержка после ночного старта"\n',
        )
    if '      - "не запускать их по точной минуте или через несколько минут после Райдена"' not in text:
        text = text.replace(
            '      - "не вести их в Восточный сектор"\n',
            '      - "не вести их в Восточный сектор"\n      - "не запускать их по точной минуте или через несколько минут после Райдена"\n',
        )
    return text


_ORIGINAL_LEAN_READ_TEXT = lean._read_text
_ORIGINAL_CURRENT_SCENE_READ_TEXT = current_scene.lean._read_text


def _read_text_day_phase(path: str, session_id: str | None = None) -> str:
    text = _ORIGINAL_LEAN_READ_TEXT(path, session_id=session_id)
    if str(path or "").replace("\\", "/").strip().lstrip("/") == DAY_FILE:
        return sanitize_day_phase_calendar(text)
    return text


lean._read_text = _read_text_day_phase  # type: ignore[assignment]
current_scene.lean._read_text = _read_text_day_phase  # type: ignore[assignment]

if calendar_runtime is not None and hasattr(calendar_runtime, "_read_text"):
    _ORIGINAL_CALENDAR_READ_TEXT = calendar_runtime._read_text

    def _calendar_read_text_day_phase(path: str, session_id: str | None = None) -> str:
        text = _ORIGINAL_CALENDAR_READ_TEXT(path, session_id=session_id)
        if str(path or "").replace("\\", "/").strip().lstrip("/") == DAY_FILE:
            return sanitize_day_phase_calendar(text)
        return text

    calendar_runtime._read_text = _calendar_read_text_day_phase  # type: ignore[assignment]
