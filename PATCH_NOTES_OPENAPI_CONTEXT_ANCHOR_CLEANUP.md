# OpenAPI context anchor cleanup patch

Version: `0.3.136-openapi-context-anchor-cleanup-v1`

## Purpose

Stop the model from treating old file-loading vocabulary as an instruction to keep talking to the repository during gameplay.

This patch removes public OpenAPI anchors and normal-turn response anchors around old `required_files` / chunk-style loading.

## Changed files

```text
app/production_runtime_patch.py
app/fast_context_runtime_patch.py
app/prompt_builder.py
docs/gpt_actions_schema.json
docs/gpt_actions_schema_1206v2.json
```

## Main changes

- Public OpenAPI no longer exposes `RequiredFilesManifestResponse` or `RequiredFilesChunkResponse` schemas.
- `TurnContractWithPromptPreview` no longer has `required_files` as a property or required field.
- `getSessionTurnContract` summary no longer mentions hidden chunks / required-file chunks.
- `getFastRenderContext` public response schema now uses `context_files_total`, not `required_files_total`.
- Fast context defaults are reduced:
  - `max_total_chars`: `24000`
  - `per_file_chars`: `4000`
- Runtime `turn-contract` response now removes old `required_files` and `full_required_files_count` fields before returning.
- Runtime wording now says diagnostic file-loader endpoints must not be used during gameplay, without prompting a repo scan.

## Expected normal flow

```text
getSessionTurnContract
→ getFastRenderContext
→ render scene
→ applyTurnResult
```

No repository scan should happen during a normal scene turn.
