# Patch notes — NPC/item continuity

Small fix based on current repo.

## Fixes

- Adds hidden `state/scene_continuity_state.json` for NPC physical state and object continuity.
- Tells runtime to preserve NPC injuries/limitations without bloating the lower block.
- Makes Akira visible inventory a current visible slice, not an append-only list.
- If an object leaves Akira, it must disappear from Akira header and remain only in hidden state/inventory if important.
- Prevents NPC-held/hidden/offscreen objects from being written in Akira header/lower panel.
- Adds scene continuity state to fast context and scene packet state slices.

## Files changed

- app/physical_continuity_runtime_patch.py
- app/state_persistence_runtime_patch.py
- app/response_size_guard_runtime_patch.py
- app/fast_context_runtime_patch.py
- app/scene_packet_runtime_patch.py
- app/bottom_block_compact_runtime_patch.py
- app/production_runtime_patch.py
- app/context_transport_runtime_patch.py
- gpt/scene_format.md
- gpt/locks/runtime_scene_rules_digest.md
- gpt/locks/bottom_block_compact_rules.md
- state/inventory_rules.md
- state/memory_update_rules.md
- state/scene_continuity_state.json
