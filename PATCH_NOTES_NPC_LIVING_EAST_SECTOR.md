# NPC Living East Sector Patch

## Что входит

Этот ZIP только про NPC и живой Восточный сектор.

Файлы:

- `app/production_runtime_patch.py`
  - подключает `app.npc_living_runtime_patch`;
  - версия: `0.3.122-living-npc-east-social-v1`.

- `app/npc_living_runtime_patch.py`
  - обновляет NPC runtime до v2;
  - создаёт/нормализует `state/session_npcs.json`;
  - подключает `gpt/locks/npc_living_scene_rules.md`;
  - добавляет NPC-файлы в required context, size guard и fast context.

- `gpt/locks/npc_living_scene_rules.md`
  - правила живых NPC;
  - реакции NPC должны быть разными;
  - персонажи появляются по отношениям, целям, привычным маршрутам и локации;
  - важные NPC получают мини-анкету и сохраняются.

- `state/session_npcs.json`
  - новая структура памяти для важных сессионных NPC.

- `canon_lore/east_sector/east_sector_base.yaml`
  - усилена социальная модель Восточного сектора:
    - сплетни;
    - группы;
    - дружба;
    - ревность;
    - отношения;
    - соперничество;
    - разные реакции на Акиру/Райдена/Рэя;
    - взрослые молодые люди, не Академия.

## Что НЕ входит

- Не трогает карточки Рэя.
- Не трогает карточку Райдена.
- Не трогает Юну.
- Не трогает правила скобок/POV.
- Не трогает календарь 31 августа.
- Не трогает загрузку локаций Восточного сектора.
- Не добавляет новые логи.

## Проверка после деплоя

1. `/health` должен показать:
   `0.3.122-living-npc-east-social-v1`

2. В `getFastRenderContext` должны появляться:
   - `gpt/locks/npc_living_scene_rules.md`
   - `state/session_npcs.json`

3. В сценах Восточного сектора:
   - NPC не одинаковые;
   - база не пустая;
   - NPC могут говорить между собой;
   - NPC могут отвлечь Мики/Райдена/других;
   - если NPC становится важным, он получает имя и мини-анкету в `state/session_npcs.json`.
