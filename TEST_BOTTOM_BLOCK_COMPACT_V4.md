# Test checklist — Bottom Block Compact v4

Use after deploy.

## Must keep stats

Expected:

```text
Память: 8% · эмоции: блок · поток: закрыт
Сила: 34 · выносливость: 38 · ловкость: 46 · усталость: 12
Бой: 55/85 · энергия: 0/1 · риск: высокий
```

Fail if state block has:

- `новые факты:`
- protocol recap
- long medical explanation
- offscreen report
- clothing/inventory dump without immediate choice relevance

## Relationship format

Expected:

```text
Райден: +14 · осторожное доверие
Эмма: -18 · угроза
Ирэй: 0 · риск/интерес
```

Fail if relationship block has:

- `+14/-1`
- `+14 / -1`
- event explanation after the score
- offscreen location report
- hidden lore

## Actions and thoughts

Fail if action options are long protocol summaries.
Fail if thoughts retell everything that happened in the previous scene.
