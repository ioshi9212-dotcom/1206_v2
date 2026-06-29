# Compact fast context patch

Назначение: убрать `ResponseTooLargeError` на `getFastRenderContext`, не теряя карточки активных/говорящих персонажей.

Состав:
- `app/compact_fast_context_runtime_patch.py`
- `app/production_runtime_patch.py`

Что меняется:
- `getFastRenderContext` переопределяется компактной версией.
- Нижние лимиты уменьшаются: `max_total_chars` от 8000, `per_file_chars` от 900.
- `loaded_files` возвращает только `path` и `content`, без тяжёлой диагностической обвязки.
- `skipped_files` возвращается только коротким sample, полный размер остаётся в `skipped_count`.
- Карточки важных персонажей (`main.yaml`, `character.yaml`, `knowledge.yaml`) ставятся выше supporting-файлов.
- Если обязательная карточка важного персонажа отсутствует, это видно в `essential_character_files_missing`.

Новых lock-файлов нет.
Сценических примеров нет.
