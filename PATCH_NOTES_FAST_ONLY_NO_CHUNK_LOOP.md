# Patch notes — Fast only / no chunk loop

Purpose: stop the model from spending many minutes loading repository chunks during normal gameplay.

## Fixed

- `getSessionTurnContract` no longer exposes the full `required_files` list as a to-do list.
- Turn contract now points to `getFastRenderContext` as the only normal gameplay context loader.
- Required-files manifest/chunk routes are hidden from `/openapi-actions.json`.
- If old/cached clients still call required-files manifest/chunk endpoints, they now return an empty diagnostic response instead of reading the repo.
- Prompt builder and GPT instruction files no longer tell the model to load every chunk before rendering.
- Scene packet/start scene notes now prefer fast context and forbid chunk loops during gameplay.

## Important

The actual diagnostic endpoints may still exist for backward compatibility, but they are not exposed in the action schema and no longer return heavy content unless a developer explicitly enables diagnostic mode in code.

## Expected result

Normal turn flow:

1. `getSessionTurnContract`
2. `getFastRenderContext`
3. render scene
4. `applyTurnResult`

No 15-minute repository-loading loop.
