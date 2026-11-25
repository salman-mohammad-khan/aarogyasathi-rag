# Deployment Guide (non-WhatsApp / cloud hosting)

The bot is a plain FastAPI app — it can run anywhere Python 3.12 runs.

## Option 1: Local Windows (dev/demo) — current setup

```powershell
$env:PYTHONPATH = "$PWD"; python -m uvicorn app.main:app --port 8000
# open http://127.0.0.1:8000
```

## Option 2: Docker

```bash
docker compose up --build -d
```

## Option 3: Any free-tier cloud (Render / Railway / Fly / Oracle)

1. Push this repo to GitHub (`.env` is gitignored — never commit it).
2. Create the service from the repo. Build command: `pip install -r requirements.txt && python scripts/build_index.py`. Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set environment variables in the dashboard:
   - `AWS_BEARER_TOKEN_BEDROCK` — Amazon Bedrock API key (main model, Gemma 3 27B in `ap-south-1` by default)
4. Health check: `GET /api/health` → `{"llm": {"backend": "bedrock", ...}}` (`null` without a Bedrock key; the bot then uses template answers)

## Notes

- First startup builds the embedding cache (`data/embeddings/*.npy`) — keep that volume
  mounted/persisted, or every cold start re-embeds the corpus (~2-5 min).
- RAM: about 1.5 GB in total (LaBSE fp16 ~1 GB + Python); the answer model runs on Amazon Bedrock.
- The WhatsApp webhook is optional: set `WHATSAPP_ENABLED=true` and the `WHATSAPP_*` values.
