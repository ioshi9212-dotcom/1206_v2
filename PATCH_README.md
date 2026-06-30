# 1206 v2 — Academy-style compact scene contract patch

Version: `0.3.149-academy-style-scene-contract-v1`

## Why

The previous `/turn-packet` route still returned a bulky packet with nested `character_packets`, `world_energy_digest`, history and audit. It could exceed GPT Actions response limits on the first normal turn.

Academy prequel avoids this by returning one compact `scene_contract` built from runtime summaries and small slices.

## What changed

- Adds `app/compact_scene_contract_runtime_patch.py`.
- Updates `app/production_runtime_patch.py` OpenAPI to expose `getSceneContract` as the gameplay context endpoint.
- Keeps `/turn-packet` as a compact compatibility alias, but it is not exposed in the clean OpenAPI schema.
- Adds `runtime/characters/*.yaml` summaries for Akira, Jun, Emma, Irey, Raiden, Ray.
- Keeps `getContextAudit` for technical checks only.

## Gameplay route

First start:

```text
createSession -> processTurn -> output exact scene_text
```

Normal turn:

```text
getSceneContract -> write scene -> applyTurnResult
```

## Check after deploy

1. `health.version` should be `0.3.149-academy-style-scene-contract-v1`.
2. Actions schema should expose `getSceneContract`, not `getFastRenderContext`.
3. Run `getContextAudit` and check `energy_loaded_by_character` for active characters.
