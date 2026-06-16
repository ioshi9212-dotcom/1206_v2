# Gameplay response gate — 1206 v2

In gameplay mode, final answer must be the scene only.

Do not show:

- API status;
- contract summaries;
- saving logs;
- explanations of why the scene is written this way;
- state payloads.

If state needs updating, call `apply-turn-result`, then return the visible scene text.
