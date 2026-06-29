# Test — Fast only / no chunk loop

## Checks performed

- Python files compile with `python -m py_compile`.
- Runtime OpenAPI schema has no exposed `getRequiredFilesManifest`, `getRequiredFilesChunk`, or `getRequiredFilesBundle` operations.
- `docs/gpt_actions_schema.json` has no required-files paths.
- `docs/gpt_actions_schema_1206v2.json` has no required-files paths.
- User-facing prompts no longer contain instructions to call manifest/chunks until `has_more=false`.

## Manual test after deploy

1. Open `/openapi-actions.json`.
2. Confirm only `getFastRenderContext` is available for context loading.
3. Start/continue a scene.
4. The model should call `getSessionTurnContract`, then `getFastRenderContext`, then render.
5. It should not call required-files chunks repeatedly.
