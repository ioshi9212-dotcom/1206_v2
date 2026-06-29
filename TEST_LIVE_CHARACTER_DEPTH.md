# Test — live character depth

После применения патча и деплоя:

1. `/health` или `/openapi-actions.json` должен показать версию:

```text
0.3.141-live-character-depth-v1
```

2. В обычной игровой сцене `getFastRenderContext` должен включать:

```text
canon/character_depth_and_rotation.md
```

3. Если в сцене active/nearby/speaking/observing есть важный персонаж, его файлы должны быть в приоритетной части списка:

```text
characters/<id>/main.yaml
characters/<id>/character.yaml
characters/<id>/knowledge.yaml
```

4. Тестовое сообщение в игровой чат:

```text
Проверь технически, без продолжения сцены: загружен ли canon/character_depth_and_rotation.md, какие active/nearby/speaking/observing персонажи сейчас определены, и попали ли их main/character/knowledge файлы в getFastRenderContext. Ответ только техническим отчётом.
```

5. Сценический тест:

- NPC должен реагировать не как функция сцены, а из своих знаний/целей.
- Если поведение Акиры ломает ожидание NPC, должна появиться видимая реакция или state hook.
- Если NPC видел/слышал важный факт, это должно быть записано в его dynamic knowledge как наблюдение/вывод, а не hidden truth.
