# Test — NPC/item continuity

1. If an NPC receives a physical consequence, next scene must remember it in behavior, not as a long bottom-block report.
2. If an item leaves Akira, `current_state.visible_inventory` must no longer show it.
3. NPC-held, hidden, transferred or offscreen objects must stay in hidden state/inventory, not Akira header.
4. No object may appear with NPC without source: prior state, visible action, location, card equipment or explicit scene event.
5. Bottom block remains compact: no object ledger, no NPC injury report, no offscreen logistics.
