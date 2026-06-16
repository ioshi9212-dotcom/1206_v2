# Runtime scene rules digest — 1206 v2

- Final gameplay answer is the scene only.
- Scene starts with the selected 1206 visual-novel header.
- Header line: `🌘 Астрейн · {year} г., {day_month}, {weekday}`.
- Second line: `🕒 {time} · 📍 {location}`.
- Location must come from `current_state.current_location_text`.
- Do not hard-code one place after the scene moves.
- Dialogue format: `**Имя/видимый дескриптор** — Реплика. (*короткая ремарка*)`.
- Descriptions are separate italic paragraphs.
- Akira thoughts only in bottom block.
- Bottom blocks: `Что можно сделать`, `Что Акира могла бы сказать`, `Мысли Акиры`.
- Backend does not infer state from prose; use `apply-turn-result` for meaningful changes.
