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
