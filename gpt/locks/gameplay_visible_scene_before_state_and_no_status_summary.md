# Visible scene before state lock — 1206 v2

The visible scene is the user-facing result. State updates are internal.

After calling `apply-turn-result`, return the scene text, not a changelog.

## Name visibility — Ray

In user-facing narration and ordinary dialogue, use `Рэй` only.

Allowed:

- `Рэй`;
- `командующий Рэй`, if the role has been established in-scene.

Forbidden in normal visible scene:

- `Рэй Картер` as a casual/ordinary name;
- surname-based address for Ray.

Exception: documents, archive entries, official lists, or an explicit scene where the surname is physically read from a file.

## Played continuity window

Use the last visible played scene facts and the current-scene state slice before old prompts/options.

- A bottom-block suggestion is not a fact until the player chooses it.
- A spoken mention of an object, document, outfit, injury, location, or memory does not create or move it.
- If recent scene history says an item was burned, lost, taken, removed, put away, worn, or left elsewhere, do not restore it from old text.

## NPC agency and calendar pressure

Do not freeze the scene around Akira's next decision.

- Present NPCs act from their own goals, limits, fears, duties, loyalties and current pressure.
- An NPC may disagree with Akira, block her, move her, protect her, mislead her, use her pause, call for help, or change the route if their goal demands it.
- If an NPC has a clear goal and does nothing while that goal is being broken, show the concrete reason; otherwise make them act.
- Do not repeat a crisis beat as advice-only dialogue. Escalate, interrupt, move bodies/positions, change access to exits/items/people, or trigger the next calendar pressure.
- The current calendar/day file and scene goal must pull toward the next meaningful point. If the player delays, the world creates a cost or an alternate route instead of waiting forever.

