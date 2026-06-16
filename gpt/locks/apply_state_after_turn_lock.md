# Apply state after turn lock — 1206 v2

Backend does not infer state from prose.

After a meaningful scene, update through `apply-turn-result` if there are changes to:

- `current_state`
- `calendar_runtime`
- `relationships`
- `knowledge_state`
- `reputation_state`
- `rumors_state`
- `inventory_state`
- `power_state`
- `story_lines`

Roster fields are replacement lists, not append-only lists.
