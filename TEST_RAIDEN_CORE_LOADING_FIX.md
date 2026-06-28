# Test — Raiden/Core Character Loading Fix

## Проверка Райдена

В обычной сцене с Райденом required files должны содержать:

- `characters/raiden/main.yaml`
- `characters/raiden/character.yaml`
- `characters/raiden/knowledge.yaml`

И не должны содержать:

- `characters/raiden/raiden_main_profile.yaml`
- `characters/raiden/raiden_hidden_past.yaml`
- `characters/raiden/raiden_knowledge_connections.yaml`

## Проверка past

`characters/raiden/past.yaml` появляется только если сцена касается прошлого, памяти, Самуэля, кольца, скрытой связи Акиры/Райдена, Эхо/кайросов или другого скрытого лора.

## Проверка календаря

Новые календарные дни должны ссылаться на:

- `main.yaml`
- `character.yaml`
- `knowledge.yaml`
- `past.yaml` только как conditional.
