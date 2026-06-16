# State update payload contract — 1206 v2

Use `apply-turn-result` with a structured payload.

Common keys:

```json
{
  "current_state_changes": {},
  "calendar_runtime_changes": {},
  "relationship_changes": [],
  "knowledge_changes": [],
  "story_lines_changes": {},
  "inventory_changes": {},
  "rumor_changes": [],
  "reputation_changes": []
}
```

Only save meaningful changes.
