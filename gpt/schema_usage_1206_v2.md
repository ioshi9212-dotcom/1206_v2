# GPT Actions Schema Usage — 1206v2

Production URL:

`https://1206v2-production.up.railway.app`

Actions schema URL:

`https://1206v2-production.up.railway.app/openapi-actions.json`

Health:

`https://1206v2-production.up.railway.app/health`

Volume debug:

`https://1206v2-production.up.railway.app/debug/volume`

## Main operations

- `healthCheck`
- `debugVolume`
- `createSession`
- `processTurn`
- `getTurnContract`
- `getRequiredFilesManifest`
- `getRequiredFilesChunk`
- `submitTurnResult`
- `applyTurnResult`
- `readProjectFile`

## Recommended first test

1. `healthCheck`
2. `debugVolume`
3. `createSession(session_id="main-1206-v2", reset=false)`
4. `processTurn(session_id="main-1206-v2", player_input="начнем")`
5. `getRequiredFilesManifest(session_id="main-1206-v2")`
6. `getRequiredFilesChunk(session_id="main-1206-v2", chunk_index=0, max_chars=60000, max_items=6)`

## Volume expectations

`debugVolume` must show mount `/data` or Railway-provided volume path and persistent session files.
