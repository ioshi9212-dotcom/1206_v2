# Test checklist: OpenAPI context anchor cleanup

After deploy, open `/openapi-actions.json` and check:

```text
RequiredFilesManifestResponse -> absent
RequiredFilesChunkResponse -> absent
required_files -> absent
required-files -> absent
chunks -> absent
required_files_total -> absent
```

`TurnContractWithPromptPreview.required` should be:

```text
session_id
prompt_preview
```

`TurnContractWithPromptPreview.properties` may include:

```text
fast_context_file_hints
context_files_available
```

It should not include:

```text
required_files
```

`getFastRenderContext` should show defaults:

```text
max_total_chars default: 24000
per_file_chars default: 4000
```

Runtime check:

1. Create or use a session.
2. Call `getSessionTurnContract`.
3. The JSON response must not contain:

```text
required_files
required-files
chunks
full_required_files_count
```

4. Call `getFastRenderContext`.
5. The JSON response must contain `context_files_total`, not `required_files_total`.
