# Test checklist

1. После деплоя проверить `/health` или `/openapi-actions.json`.
   Ожидаемая версия:
   `0.3.142-essential-character-context-v1`

2. В сцене с active / nearby NPC вызвать `getFastRenderContext`.

3. Проверить, что для каждого говорящего или наблюдающего активного персонажа в `loaded_files` есть:
   - `characters/<id>/main.yaml`
   - `characters/<id>/character.yaml`
   - `characters/<id>/knowledge.yaml`

4. Проверить, что эти файлы не уходят в `skipped_files` при обычном бюджете fast context.

5. Проверить, что старые diagnostic chunk endpoints не используются в gameplay.
