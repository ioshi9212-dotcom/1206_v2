# Essential character context patch

Цель: не допустить рендер активных NPC без их основных карточек.

Состав:
- `app/essential_character_context_runtime_patch.py`
- `app/production_runtime_patch.py`

Что меняется:
- `main.yaml`, `character.yaml`, `knowledge.yaml` для active / nearby / speaking / observing персонажей поднимаются в начало fast context.
- Если бюджет контекста мал, сначала режутся длинные supporting-файлы, а не карточки персонажей.
- Старый chunk-протокол не возвращается.
- Новые lock-файлы не добавляются.
- Примеры реплик/сцен не добавляются.

Версия после применения:
`0.3.142-essential-character-context-v1`
