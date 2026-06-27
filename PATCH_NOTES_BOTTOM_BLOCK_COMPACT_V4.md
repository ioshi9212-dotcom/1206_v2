# Bottom Block Compact Patch v4

Purpose: keep stats and relationship values, but make the bottom block compact and readable.

## Files to add

- `app/bottom_block_compact_runtime_patch.py`
- `gpt/locks/bottom_block_compact_rules.md`

## Merge snippets

- `merge_snippets/production_runtime_patch_import.md`
- `merge_snippets/gpt_scene_format_replace_bottom_block.md`
- `merge_snippets/response_size_guard_runtime_patch_contract.md` optional only

## Correct visible format

```text
✦ Состояние

Память: 8% · эмоции: блок · поток: закрыт
Сила: 34 · выносливость: 38 · ловкость: 46 · усталость: 12
Бой: 55/85 · энергия: 0/1 · риск: высокий

✦ Отношения

Рэй: +12 · контроль/забота
Райден: +14 · осторожное доверие
Ирэй: 0 · риск/интерес
Джун: +9 · доверие с трещиной
Эмма: -18 · угроза
```

## Forbidden visible format

```text
Рэй: +12/-1 · внёс правку без присвоения решения и удержал людей от комнаты ночью
Память: 8% · новые факты: Акира отредактировала пункт Райдена...
Эмма: -18 · вне сцены; местонахождение неизвестно
```

## Version

`0.3.124-bottom-block-compact-v4`
