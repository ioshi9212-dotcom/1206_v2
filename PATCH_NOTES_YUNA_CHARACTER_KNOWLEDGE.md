# Yuna character + knowledge patch

## Цель

Исправить Юну, чтобы ИИ не писал её холодным приказным медиком.

Юна теперь:
- робкая;
- тихая;
- осторожная;
- с мягким обычным голосом;
- профессиональная, но не ледяная;
- не добренькая/сюсюкающая и не грубая;
- морально серая из-за связи с линией Самуэля.

## Знания

Патч разделяет:

1. постоянные знания Юны;
2. то, чего она не знает на старте;
3. динамические знания в state.

Юна на старте не знает, что Акира жива, и не знает, что её два года скрывал Джун.

## Файлы

- `characters/yuna/character.yaml`
- `characters/yuna/main.yaml`
- `characters/yuna/knowledge.yaml`
- `characters/yuna/past.yaml`
- `state/character_knowledge/yuna.json`
- `engine/yuna_runtime_rules.md`
