# Akira 1206 v2 — clean GPT Actions skeleton

Чистый рабочий скелет для интерактивной сюжетной сессии 1206 v2.

Основа взята из рабочего API-движка: FastAPI + Railway + GPT Actions + сессии + required files + явное сохранение state через `apply-turn-result`.

## Старт

- Год: 1206.
- Дата: 31 августа 1206.
- Время: 02:40.
- Стартовая локация: дом Джуна.
- Локация в шапке всегда берётся из `state/current_state.json`, поле `current_location_text`.
- Шапка и нижний блок оставлены в старой visual-novel логике, но без привязки к Академии.

## Railway

Start command уже задан:

```bash
uvicorn app.server:app --host 0.0.0.0 --port $PORT
```

Нужные Variables:

```bash
PUBLIC_BASE_URL=https://1206v2-production.up.railway.app
DATA_DIR=/data
PROJECT_SLUG=akira-1206v2
```

Нужен Railway Volume:

```txt
Mount path: /data
```

Без Volume API будет работать, но память сессий может слетать после redeploy/restart.

## Основные endpoints

- `GET /health`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}/context`
- `GET /api/v1/sessions/{session_id}/turn-contract`
- `GET /api/v1/sessions/{session_id}/required-files-manifest`
- `GET /api/v1/sessions/{session_id}/required-files-chunk`
- `POST /api/v1/sessions/{session_id}/apply-turn-result`

## Что добавлять дальше

### Персонажи

Добавляй нового персонажа так:

```txt
characters/<character_id>/character.yaml
characters/<character_id>/main.yaml
characters/<character_id>/past.yaml
```

И добавь ID в:

```txt
characters/character_id_index.md
app/compact_context_patch.py   # NEW_CHARACTER_FOLDERS
app/context_transport_runtime_patch.py   # ID_ALIASES, если нужны алиасы
```

### Лор

Основные папки:

```txt
canon_lore/core/
canon_lore/world/
canon_lore/hidden/
canon_lore/social/
```

### Календарь

```txt
calendar/calendar_index.yaml
calendar/days/1206-08-31.yaml
state/calendar_runtime.json
```

## Важно

Backend не угадывает изменения из текста сцены. После каждого значимого хода нужно явно отправлять изменения через `apply-turn-result`.
