# Connect the real channels

This project is connection-ready, but the provider accounts remain yours to configure. Never commit secrets.

## 1. Run the application

Copy `.env.example` to `.env` and fill the required values. For local development: start PostgreSQL, Redis, Ollama (optional), FastAPI, the worker, and Streamlit.

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.api:app --reload
python -m app.worker
python -m streamlit run app/ui.py
```

For the easiest full local stack:

```bash
docker compose up --build
```

## 2. WhatsApp

Create/configure a Meta WhatsApp Business Cloud API app and set its webhook callback to:

```text
https://YOUR-API-HOST/webhooks/whatsapp
```

Use the GET verification endpoint with the same `WHATSAPP_VERIFY_TOKEN` configured in the app. Meta POST events are checked with `X-Hub-Signature-256` using `WHATSAPP_APP_SECRET`.

Text messages are normalized and placed on Redis. The worker sends them through the triage router and stores the result in PostgreSQL.

## 3. Instagram

Configure Instagram Messaging webhooks on the Meta app and use:

```text
https://YOUR-API-HOST/webhooks/instagram
```

Set `INSTAGRAM_VERIFY_TOKEN` and `INSTAGRAM_APP_SECRET`. Incoming text messages are normalized into the same internal schema as WhatsApp.

## 4. Email

Point your inbound-email provider/webhook at:

```text
https://YOUR-API-HOST/webhooks/email
```

The endpoint accepts JSON or form-encoded payloads with common fields such as `from`, `subject`, `text`, `body`, or `stripped-text`. The project also contains an IMAP polling adapter for mailbox-based setups.

## 5. Local Ollama

Install Ollama separately and run:

```bash
ollama pull qwen3:0.6b
```

Then set:

```text
# Optional override; default is qwen3:0.6b
OLLAMA_MODEL=qwen3:0.6b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

In the Streamlit sidebar, enable **Use local Ollama**. High-risk messages still remain human-controlled.

## 6. PostgreSQL + Redis

Production ingestion should use both:

```text
Provider webhook → FastAPI → PostgreSQL + Redis → worker → Ollama/rules → PostgreSQL
```

`messages.id` is the database idempotency key. Redis decouples webhook response time from AI processing.

## 7. Render

The included `render.yaml` provisions the API, worker, UI, Redis-compatible Key Value, and PostgreSQL. Add the Meta verification tokens/app secrets as Render environment variables. Configure the provider callback URL using the public API service URL.

Keep Ollama as a separate private service if using a hosted self-managed deployment; do not put a large model inside the public web container.

## Security

- Keep `ALLOW_UNSIGNED_WEBHOOKS=false` in production.
- Do not commit `.env` or provider secrets.
- PII is redacted before optional LLM processing.
- Prompt-injection/high-risk messages are routed to human review.
- Provider retries should be safe because message IDs are stored with a unique constraint.
