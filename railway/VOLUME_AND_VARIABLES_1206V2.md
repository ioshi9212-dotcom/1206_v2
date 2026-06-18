# Railway Volume + Variables — 1206v2

## Production domain

Use this public URL:

`https://1206v2-production.up.railway.app`

## Railway variables

Set in Railway → Service → Variables:

```env
PUBLIC_BASE_URL=https://1206v2-production.up.railway.app
DATA_DIR=/data
RAILWAY_VOLUME_MOUNT_PATH=/data
DEFAULT_SESSION_ID=main-1206-v2
MAX_FILE_CHARS=12000
PYTHONUNBUFFERED=1
```

`OPENAI_API_KEY` is not required for this FastAPI runtime if GPT Actions call it externally.

## Railway volume

In Railway service settings:

1. Add Volume.
2. Mount path: `/data`.
3. Deploy.
4. Open `/debug/volume`.
5. It should create `volume_test.txt` and session files under `/data/sessions/main-1206-v2/`.

If `/debug/volume` works but saves vanish after deploy/restart, volume is not attached to the same service or mount path is wrong.

## Custom GPT Action schema

Use:

`https://1206v2-production.up.railway.app/openapi-actions.json`

If schema still shows old URL, check `PUBLIC_BASE_URL` variable and redeploy.
