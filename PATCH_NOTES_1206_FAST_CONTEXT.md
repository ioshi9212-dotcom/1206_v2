# 1206 v2 — Fast Context Cache Update

## Что делает обновление

Обновление не режет качество сцены и не удаляет карточки персонажей.
Оно меняет способ загрузки контекста:

1. Добавляет новый endpoint `getFastRenderContext` для обычных игровых ходов.
2. Оставляет старые `getRequiredFilesManifest` / `getRequiredFilesChunk`, но делает их легче и добавляет кэш.
3. Перестраивает `getSessionTurnContract`, чтобы GPT не заставлял себя каждый ход грузить все чанки.
4. Подключает новый runtime patch в `app/production_runtime_patch.py`.
5. Обновляет GPT-инструкцию: обычный ход = fast context, полный chunk protocol = только для важных/технических случаев.

## Какие файлы заменить / добавить

Добавить:

- `app/fast_context_runtime_patch.py`

Заменить:

- `app/production_runtime_patch.py`
- `gpt/CUSTOM_GPT_INSTRUCTIONS_1206_V2.md`
- `gpt/schema_usage_1206_v2.md`

## Что должно ускориться

До обновления обычная сцена могла идти так:

1. getTurnContract
2. getRequiredFilesManifest
3. getRequiredFilesChunk 0
4. getRequiredFilesChunk 1
5. getRequiredFilesChunk 2
6. ...
7. сцена
8. applyTurnResult

После обновления обычная сцена должна идти так:

1. getTurnContract
2. getFastRenderContext
3. сцена
4. applyTurnResult

Полный manifest/chunk режим остаётся, но только для диагностики, раскрытий прошлого, hidden lore, новых важных персонажей, боя или противоречий.

## Почему качество не должно сломаться

`getFastRenderContext` всё ещё отдаёт:

- runtime scene context digest;
- текущий state;
- правила формата;
- активные character files;
- календарные/engine-файлы, если они нужны;
- past.yaml только по триггеру или `include_past=true`.

Персонажи не пишутся “из головы”: GPT всё равно получает рабочий контекст, но без полного перечитывания всех чанков на каждый обычный ход.

## Проверка после деплоя

1. Открыть:

`/health`

Ожидаем версию:

`0.3.121-fast-context-cache-v1`

2. Открыть:

`/openapi-actions.json`

Проверить, что есть путь:

`/api/v1/sessions/{session_id}/fast-render-context`

и operationId:

`getFastRenderContext`

3. В тестовом чате попросить технически проверить:

- `getSessionTurnContract`
- `getFastRenderContext`

Обычный ход не должен требовать загрузку всех chunks.

## Откат

Если что-то пойдёт не так:

1. Убрать импорт `app.fast_context_runtime_patch` из `app/production_runtime_patch.py`.
2. Вернуть старые `gpt/CUSTOM_GPT_INSTRUCTIONS_1206_V2.md` и `gpt/schema_usage_1206_v2.md`.
3. Перезапустить деплой.

Файл `app/fast_context_runtime_patch.py` можно оставить в репе: без импорта он не активен.
