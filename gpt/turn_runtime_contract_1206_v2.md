# Turn Runtime Contract 1206 v2

## Actions sequence

### First scene

User says: `начнем`, `начнём`, `start`, `begin`.

Call:

`processTurn(session_id, player_input, mode="play", include_file_contents=true)`

If response status is `START_SCENE_EXACT_TEXT`, output exactly `scene_text` as scene.

### Normal play turn

Call:

`getTurnContract(session_id, user_input, mode="play", include_file_contents=true)`

Then call:

`getRequiredFilesManifest(session_id, user_input, mode="play")`

Then call:

`getRequiredFilesChunk(session_id, chunk_index=0, max_chars=60000, max_items=6, user_input, mode="play")`

Repeat with `next_chunk_index` until `has_more=false`.

Only after that generate scene.

Then save:

`submitTurnResult(session_id, scene_id, scene_text, technical=false, state_patches={...})`

## Technical mode

If user asks about repo, Railway, volume, schema, prompt, health, files, saves, API:

- use `mode="technical"`;
- do not continue scene;
- save technical note only if needed.

## Required files rule

If a character speaks, their card must be in required files.

If scene includes hidden memory, past, rings, scars, reincarnation, Samуэль, Эхо, кайросы, or Aкира/Rайден emotional bond — corresponding hidden files must be loaded.

## Do not

- Do not generate from chat memory if API failed.
- Do not load the whole repo without required_files.
- Do not reveal hidden lore only because hidden file was loaded.
- Do not overwrite player control of Akira.
