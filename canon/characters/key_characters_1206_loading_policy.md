# Key Characters 1206 Loading Policy

## Always-load

Если персонаж присутствует в сцене, загружать его `*_main_profile.yaml`.

Для первой проверки сцены важны:

- `characters/akira/akira_main_profile.yaml`
- `characters/raiden/raiden_main_profile.yaml`
- `characters/ray/ray_main_profile.yaml`
- `characters/jun/jun_main_profile.yaml`
- `characters/emma/emma_main_profile.yaml`
- `characters/irey/irey_main_profile.yaml`

## Conditional-load

`*_hidden_past.yaml` грузить только если сцена касается прошлого, памяти, Самуэля, Райдена/Акиры, ребёнка, кольца, шрама, лаборатории, Эхо, кайросов, пространства между, срыва или самоблокировки.

`*_knowledge_connections.yaml` грузить, если в сцене есть несколько важных персонажей и нужен контроль того, кто что знает.

## Без lock-файлов

Старые lock-и и scattered rules не переносить отдельными файлами. Их смысл уже собран в обычные поля YAML: `knows`, `does_not_know`, `forbidden`, `allowed`, `pov_rules`, `rules`.

## Приоритет текущего канона

Если старые репозитории противоречат текущим правкам пользователя, использовать текущие правки:

- Акира сама заблокировала эмоции, поток и память.
- Перегруз и потеря контроля не одно и то же.
- 1198 — Академия, 1206 — спустя восемь лет.
- Акира чистокровный кайрос, но выросла среди людей и не помнит этого на старте.
- Райден после стирания не помнит Акиру/Картер и всё, что с ней связано.
