# Key Characters 1206 Loading Policy

## Core-load

Если персонаж реально присутствует, говорит, действует, наблюдает сцену или является прямым фокусом, загружать только его основные файлы:

- `characters/<id>/main.yaml`
- `characters/<id>/character.yaml`
- `characters/<id>/knowledge.yaml`

Для Райдена это строго:

- `characters/raiden/main.yaml`
- `characters/raiden/character.yaml`
- `characters/raiden/knowledge.yaml`

## Conditional past-load

`characters/<id>/past.yaml` грузить только если текущая сцена прямо касается прошлого, памяти, Самуэля, связи Акиры и Райдена, ребёнка, кольца, шрама, лаборатории, Эхо, кайросов, пространства между, срыва или самоблокировки.

Если сцена обычная, бытовая, медицинская, служебная, дорога, коридор, ожидание, конфликт без скрытого лора — `past.yaml` не нужен.

## Запрет старых файлов

Не использовать как активные источники старые разрозненные файлы:

- `*_main_profile.yaml`
- `*_hidden_past.yaml`
- `*_knowledge_connections.yaml`

Если такие файлы физически остались в папке, они считаются архивом/мусором и не должны входить в required files.

## Knowledge split

Постоянные знания персонажа лежат в `characters/<id>/knowledge.yaml`.

Динамические знания, полученные в игре, лежат в `state/character_knowledge/<id>.json`.

Знания одного персонажа не становятся знаниями другого без сцены, документа, разговора, наблюдения или runtime/state update.

## Приоритет текущего канона

Если старые репозитории или старые loading policy противоречат текущим правкам пользователя, использовать текущие файлы `main.yaml`, `character.yaml`, `knowledge.yaml` и условный `past.yaml`.
