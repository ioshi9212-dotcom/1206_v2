# Gameplay response gate — 1206 v2

In gameplay mode, final answer must be the scene only.

Do not show:

- API status;
- contract summaries;
- saving logs;
- explanations of why the scene is written this way;
- state payloads;
- author notes;
- technical notes;
- debug comments;
- visible labels like `Комментарий:`, `Технически:`, `Пояснение:`, `Примечание:`;
- descriptions of what files/context were loaded;
- phrases like "я проверил", "я загрузил", "я сохранил", "сработал контракт" inside gameplay output.

Gameplay output may include only:

- scene header;
- scene body;
- NPC/world reaction;
- scene hook/consequence/time movement;
- bottom player-facing action/thought options, if the current format requires them.

If state needs updating, call `apply-turn-result`, then return the visible scene text.
