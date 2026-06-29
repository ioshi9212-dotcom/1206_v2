# Проверка compact fast context

1. Проверить `/health`.
   Ожидаемая версия: `0.3.143-compact-fast-context-v1`.

2. В игровой сессии вызвать `getSessionTurnContract`.
   Контракт должен по-прежнему предлагать `getFastRenderContext`.

3. Вызвать `getFastRenderContext` с малыми лимитами:
   - `max_total_chars=12000`
   - `per_file_chars=1200`

4. Ожидаемый результат:
   - нет `ResponseTooLargeError`;
   - `mode = fast_render_context_compact_v1`;
   - `loaded_files` содержит компактные записи `path/content`;
   - `essential_character_files_missing` пустой или явно показывает, каких карточек не хватает;
   - `skipped_files_truncated` может быть `true`, это нормально.

5. Если `essential_character_files_missing` не пустой, сцену не продолжать: сначала чинить roster/identity/loading для указанных персонажей.
