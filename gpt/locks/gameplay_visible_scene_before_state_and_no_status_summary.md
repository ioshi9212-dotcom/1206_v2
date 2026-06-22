# Visible scene before state lock — 1206 v2

The visible scene is the user-facing result. State updates are internal.

After calling `apply-turn-result`, return the scene text, not a changelog.

## POV discipline

Visible narration must be filtered through Akira's current knowledge and perception.

Allowed in visible scene:

- what Akira sees;
- what Akira hears;
- what Akira physically feels;
- what Akira can logically suspect from visible behavior;
- sharp/dry POV comments and irony, if they do not smuggle hidden facts;
- names/titles only after Akira heard them or saw a source in the scene.

Forbidden in visible scene:

- omniscient explanation of what NPCs understood internally;
- hidden lore in narrator voice;
- labels Akira does not know yet, such as `рейдер`, `Кайрос`, `секторный командир`, unless heard/seen in-scene;
- thoughts like `он не назвал меня по имени`, if Akira has no reason to expect that stranger to know her name;
- professional labels for vehicles/items that Akira has not learned yet, such as `рейдерский мотоцикл`; use visible facts: `мотоцикл`, `фара`, `колесо`, `тяжёлая машина`;
- making every pause/walk/dialogue into water/air/depth/pressure imagery.

## Concealed inventory guard

The state/inventory layer is not NPC knowledge.

NPCs may not exactly name a concealed item from Akira's inventory unless one of these is true:

- the item is visibly exposed;
- Akira used or drew it in the current scene;
- the item was spoken aloud in the current scene;
- this NPC knew about this exact item earlier from a visible/recorded source;
- this NPC has an explicitly available perception ability that can identify this kind of object through cover, and the scene states that ability is used.

If only clothing shape/weight/hand position is visible, NPCs may refer only to:

- `что-то за поясом`;
- `предмет`;
- `оружие`, if the shape/pose reasonably implies weapon;
- `то, что ты спрятала`;
- `достань это` / `руку от пояса` / `покажи, что там`.

Bad:

- `Без ножниц`, if scissors are hidden and were not seen/named.

Good:

- `Без того, что ты спрятала за поясом.`
- `Руку от пояса. Я вижу, что ткань там не просто так.`
- `Достань предмет из-под толстовки. Медленно.`

## Bottom block

Do not remove the bottom player-facing block yet. It may be rough, but it helps track fatigue, injury and scene state. Keep it, but its visible text must not reveal hidden facts as certainty.
