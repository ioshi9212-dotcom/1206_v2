# Railway setup для 1206 v2

## 1. Variables

В Railway → проект → Variables добавь:

```txt
PUBLIC_BASE_URL=https://1206v2-production.up.railway.app
DATA_DIR=/data
PROJECT_SLUG=akira-1206v2
```

## 2. Volume

В Railway → Storage / Volumes:

```txt
Mount path: /data
```

Это важно: в `/data` API хранит seed-файлы, сессии и изменённые state-файлы.

## 3. Start command

Уже лежит в `railway.json`:

```txt
uvicorn app.server:app --host 0.0.0.0 --port $PORT
```

## 4. Проверка после deploy

Открыть:

```txt
https://1206v2-production.up.railway.app/health
```

Нормально, если ответ содержит:

```json
{
  "status": "ok",
  "volume_seeded": true,
  "public_base_url": "https://1206v2-production.up.railway.app"
}
```

Если `volume_seeded: false`, значит `/data` не примонтирован или приложение ещё не стартовало нормально.
