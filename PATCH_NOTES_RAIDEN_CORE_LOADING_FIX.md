# Patch notes — Raiden/Core Character Loading Fix

Мини-фикс только для загрузки персонажей и политики контекста.

## Что исправлено

- Убраны ссылки на старые `*_main_profile.yaml`, `*_hidden_past.yaml`, `*_knowledge_connections.yaml` из loading policy.
- Core-загрузка персонажа теперь: `main.yaml`, `character.yaml`, `knowledge.yaml`.
- `past.yaml` больше не тянется по умолчанию; только по смысловому триггеру прошлого/памяти/скрытого лора.
- `characters/raiden/*` старые дубли не добавлены в ZIP: пользователь удаляет их вручную.
- Обновлены helper-и, где раньше подтягивался `past.yaml` вместо `knowledge.yaml`.
- Обновлён шаблон календарного дня, чтобы новые даты не создавались со старой структурой.

## Файлы в патче

- `canon/characters/key_characters_1206_loading_policy.md`
- `canon/characters/character_file_loading_policy.md`
- `calendar/days/_day_template.yaml`
- `gpt/locks/runtime_scene_rules_digest.md`
- `app/character_registry_runtime_patch.py`
- `app/context_transport_runtime_patch.py`
- `app/compact_context_patch.py`
- `app/scene_packet_runtime_patch.py`
- `app/start_scene_runtime_patch.py`
