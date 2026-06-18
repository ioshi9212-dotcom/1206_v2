# System Runtime Patch — 1206v2

Этот патч закрывает системный слой, которого не хватало после карточек персонажей и календаря.

## Что добавлено/обновлено

- `app/main.py`  
  Обновлён под `1206v2-production.up.railway.app`, новые character cards, manifest/chunk endpoints, volume/session runtime.

- `docs/gpt_actions_schema.json` и `docs/gpt_actions_schema_1206v2.json`  
  Схема Actions с production URL `https://1206v2-production.up.railway.app`.

- `gpt/CUSTOM_GPT_INSTRUCTIONS_1206_V2.md`  
  Текст для Custom GPT Instructions.

- `gpt/system_prompt_1206_v2.md`  
  Системный промпт как required-file.

- `gpt/turn_runtime_contract_1206_v2.md`  
  Порядок вызовов Actions и сохранений.

- `gpt/schema_usage_1206_v2.md`  
  Как подключать schema и проверять endpoints.

- `railway/VOLUME_AND_VARIABLES_1206V2.md`  
  Что поставить в Railway Variables и как подключить Volume.

- `.env.example`  
  Переменные для Railway.

- `state/*.json`  
  Пустые starter-state файлы, чтобы session volume создавался стабильно.

## После заливки

В Railway Variables поставить:

```env
PUBLIC_BASE_URL=https://1206v2-production.up.railway.app
DATA_DIR=/data
RAILWAY_VOLUME_MOUNT_PATH=/data
DEFAULT_SESSION_ID=main-1206-v2
MAX_FILE_CHARS=12000
PYTHONUNBUFFERED=1
```

В Railway подключить Volume с mount path:

```text
/data
```

Проверить:

```text
https://1206v2-production.up.railway.app/health
https://1206v2-production.up.railway.app/debug/volume
https://1206v2-production.up.railway.app/openapi-actions.json
```

В Custom GPT Actions использовать schema URL:

```text
https://1206v2-production.up.railway.app/openapi-actions.json
```

## Новые operations

- `getRequiredFilesManifest`
- `getRequiredFilesChunk`

Они нужны, чтобы GPT мог читать required files кусками и не тащить весь репозиторий в один ответ.
