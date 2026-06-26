ТЕХНИЧЕСКИЙ РЕЖИМ. Не запускай сцену и не пиши художественный текст.

Проверь fast context после обновления 1206 v2:

1. Вызови health.
2. Создай/открой session_id="main-1206-v2", reset=false.
3. Вызови getSessionTurnContract.
4. Проверь, есть ли в ответе:
   - fast_context_available=true
   - preferred_next_action=getFastRenderContext
   - prompt_preview без требования грузить все chunks каждый обычный ход.
5. Вызови getFastRenderContext с max_total_chars=45000, per_file_chars=8000.
6. Выведи технический отчёт:
   - loaded_count
   - skipped_count
   - truncated
   - needs_full_context
   - past_context_loaded
   - какие character files попали в loaded_files
   - есть ли runtime/scene_context_digest.md
   - нужно ли для обычного хода грузить getRequiredFilesChunk.

Не пиши сцену. Только отчёт.
