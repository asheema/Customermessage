# Customer Message AI Triage — Render-ready Production-Style Take-Home

A customer-message triage service for WhatsApp, email and Instagram. It decides what the customer wants, extracts useful information, chooses the next action/handler, emits a confidence signal, and applies a human-review rule.

## Architecture

```text
WhatsApp / Email / Instagram
            ↓
       Render Web Service
            ↓
FastAPI → validation → PII redaction → idempotency boundary
            ↓
 Render Key Value / Redis queue
            ↓
      Triage Router
       ├─ deterministic rules → Automatic
       ├─ Ollama / vLLM → AI/LLM lane
       └─ risk/ambiguity → Human review
            ↓
 PostgreSQL / audit store (production)
            ↓
OpenTelemetry / Prometheus → Grafana
            ↓
 Streamlit reviewer dashboard
```

The repository is intentionally **zero-credential by default**. The real local LLM is optional. Without Ollama, the AI lane uses the deterministic zero-credential fallback and labels that behavior honestly.

## What is implemented

- FastAPI backend: `/health`, `/triage`, `/queue`, `/metrics`, `/metrics/prometheus`
- Streamlit reviewer UI with local role-based demo authentication
- Automatic / AI / Human routing
- Confidence and human-review signal on every processed fixture record
- PII redaction before optional LLM processing
- Prompt-injection handling / fail-closed high-risk routing
- Local queue with a production swap to Render Key Value/Redis via `REDIS_URL`
- Optional Ollama integration using `OLLAMA_MODEL` and `OLLAMA_BASE_URL`
- Audit log and reviewer feedback
- Docker + Docker Compose
- Render Blueprint (`render.yaml`)
- GitHub Actions CI
- `output.json`, `decision.json`, and `decisions.json` batch exports
- Prometheus-compatible metrics endpoint

## Run locally — no API key

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app/ui.py
```

Open `http://localhost:8501`.

Demo accounts:
- `admin / admin123`
- `reviewer / reviewer123`
- `agent / agent123`

FastAPI:

```bash
python -m uvicorn app.api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Batch CLI:

```bash
python -m app.main messages.json -o output.json
```

## Ollama — real local LLM, no cloud API key

Install Ollama locally, pull the small Qwen3 model, then set:

```bash
# Optional override; default is qwen3:0.6b
OLLAMA_MODEL=qwen3:0.6b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

The application redacts PII before the Ollama request. The default small-model configuration uses Qwen3 0.6B, disables thinking for this short classification task, limits generated output, and keeps the model warm to reduce latency. High-risk messages are kept out of the LLM lane by the deterministic safety router.

For Docker Compose, Ollama is an optional local service and its model data is kept in a named volume.

### Render + Ollama

Do **not** bundle a large model into the public Streamlit container. On Render, keep Ollama as a separate **private service** with enough CPU/RAM and a persistent disk, then set:

```text
OLLAMA_BASE_URL=http://<ollama-private-service>:11434
OLLAMA_MODEL=<installed-model>  # optional override; default: qwen3:0.6b
```

The public UI/API remains deployable without Ollama. This means the demo does not fail just because a model service is unavailable.

## Deploy to Render

Render supports Docker services and private networking. The included `render.yaml` defines:

1. `customer-message-triage-ui` — public Streamlit web service
2. `customer-message-triage-api` — optional private FastAPI service
3. Optional environment-variable hooks for Render Key Value/Redis and Ollama

### Simplest deployment

1. Push this folder to GitHub.
2. In Render, create a **New Web Service** from the repository.
3. Choose **Docker**.
4. Render will use the Dockerfile; the Blueprint also contains the correct Streamlit `$PORT` command.
5. Deploy.
6. Open the generated `onrender.com` URL.
7. Log in with `admin/admin123`.

For the take-home demo, you do **not** need an OpenAI key, Supabase key, Redis, PostgreSQL or Ollama to get the UI running.

### Production Render setup

Add these services when moving beyond the demo:

- **Render Key Value** — Redis-compatible queue/cache. Set `REDIS_URL` on the UI/API/worker services.
- **Render Postgres** — durable application/audit data instead of local SQLite/files.
- **Ollama private service** — only when a self-hosted model is required; give it appropriate compute and persistent model storage.
- **Background worker** — consume the queue and process messages asynchronously.
- **Prometheus/Grafana/OpenTelemetry** — monitor latency, errors, route distribution, queue depth, LLM usage and human-review rate.
- **Sentry** — optional application error tracking.

Render services in the same region can communicate over the private network. Render's filesystem is ephemeral by default, so production data should use managed Postgres/Key Value or an appropriate persistent disk rather than relying on local JSON/SQLite files.

## Downloadable batch outputs

In **Batch Triage**, upload `messages.json`. The UI creates:

- `output.json` — canonical complete triage output
- `decision.json` — same structured decision export
- `decisions.json` — backward-compatible filename

All three have Streamlit download buttons. The CLI also writes the filename supplied with `-o`.

## 10,000 messages/day

10,000/day is approximately 417/hour, 6.94/minute and 0.116/second averaged over 24 hours. Production should design for bursts rather than only the average. A queue separates ingestion from processing and allows multiple stateless workers.

Recommended production controls:

- message-ID idempotency
- retries with exponential backoff
- dead-letter queue
- circuit breaker around external/model dependencies
- rate limiting
- confidence thresholds and human review
- model/prompt version tracking
- offline evaluation and regression tests
- audit trail
- metrics/alerts

## Cost per 1,000

Default no-cloud mode has **$0 external model-token cost per 1,000** because it does not call a paid API. Local Ollama also has no vendor API-token charge, but its CPU/GPU/hosting resources still have an infrastructure cost.

For a hosted LLM, calculate:

`LLM cost / 1,000 = LLM calls × input tokens × input price + LLM calls × output tokens × output price + allocated compute`

Illustrative planning assumption: 30% of messages use an external LLM and each such call averages 500 input + 150 output tokens. For 1,000 messages: 300 LLM calls, 150,000 input tokens and 45,000 output tokens. Insert the selected provider's current published prices rather than inventing a vendor price.

## AI tools used

ChatGPT was used for architecture design, edge-case analysis, implementation assistance, debugging, test design, safety review, documentation and the interactive UI structure. Runtime AI behavior is explicitly labeled; the default application requires no cloud AI API key.

## Real channel ingestion (v2)

See `CONNECT_REAL_CHANNELS.md` for the exact provider connection checklist and environment variables.

The project now supports actual inbound channel adapters rather than treating `messages.json` as the only source:

```text
WhatsApp Cloud API ─┐
Instagram Messaging ├─ HTTPS webhook → FastAPI → Redis/Render Key Value → Worker → PostgreSQL
Inbound Email ──────┘                                      ↓
                                                     Triage / LLM
                                                          ↓
                                                  decision + audit
                                                          ↓
                                               Prometheus metrics
```

### WhatsApp
Set `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, and `WHATSAPP_BRAND`. Configure the Meta webhook callback URL:

`https://<your-api-service>.onrender.com/webhooks/whatsapp`

Use the GET endpoint for Meta webhook verification and POST endpoint for signed event delivery. Text messages are normalized into the common message schema and queued.

### Instagram
Set `INSTAGRAM_VERIFY_TOKEN`, `INSTAGRAM_APP_SECRET`, and `INSTAGRAM_BRAND`. Configure the Meta Instagram Messaging webhook callback URL:

`https://<your-api-service>.onrender.com/webhooks/instagram`

The adapter handles Instagram messaging webhook text events and queues them for the worker.

### Email
`POST /webhooks/email` accepts inbound email payloads from an inbound-email provider. It accepts JSON and form-encoded payloads with common fields such as `from`, `subject`, `text`, `body`, or `stripped-text`.

For mailbox polling, the optional `app.email_poller` module supports IMAP using `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_FOLDER`, and `EMAIL_POLL_SECONDS`.

### PostgreSQL
When `DATABASE_URL` is set, the application creates these tables automatically:

- `messages` — inbound message, source channel, sender, raw payload, status
- `decisions` — triage intent, entities, handler, confidence, human-review decision, route, model and latency

### Redis / Render Key Value
When `REDIS_URL` is set, the API uses the Redis-compatible queue. Without it, local mode uses an in-process queue so the demo can still run.

For production on Render, the Blueprint provisions a Render Key Value service and a background worker. Render documents Key Value as Redis-compatible and suitable for job queues, and background workers as services that poll a queue for asynchronous work. See the official Render documentation for [Key Value](https://render.com/docs/key-value) and [Background Workers](https://render.com/docs/background-workers).

### Worker
Run locally:

```bash
python -m app.worker
```

The worker consumes queued messages, performs triage, writes the result to PostgreSQL, and updates metrics.

### Local full stack

```bash
docker compose up --build
```

This starts:

- FastAPI: `http://localhost:8000`
- Streamlit: `http://localhost:8501`
- Redis: `localhost:6379`
- PostgreSQL: `localhost:5432`
- Triage worker

Test an inbound email:

```bash
curl -X POST http://localhost:8000/webhooks/email \
  -H "Content-Type: application/json" \
  -d '{"id":"EMAIL-001","from":"customer@example.com","subject":"Order tracking","text":"Tracking has not moved. Order VW-12345"}'
```

Check queue/API health:

```bash
curl http://localhost:8000/health
```

Check Prometheus metrics:

```bash
curl http://localhost:8000/metrics/prometheus
```

Check stored decisions:

```bash
curl http://localhost:8000/decisions
```

### Render deployment

The updated `render.yaml` defines:

1. FastAPI web service
2. Streamlit web service
3. Background worker
4. Render Key Value queue
5. Render Postgres database

Render Blueprints support background workers, Key Value services, and Postgres databases. The API and worker receive their datastore connection strings from the Blueprint rather than hardcoding credentials.

You must still configure the channel-provider secrets (`WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `INSTAGRAM_VERIFY_TOKEN`, `INSTAGRAM_APP_SECRET`) and configure the corresponding Meta webhooks. For email, configure your inbound email provider to POST to `/webhooks/email`, or configure the IMAP poller with a mailbox credential.

### Important: channel credentials

The software can be deployed without third-party channel credentials, but it cannot receive real WhatsApp/Instagram/email traffic until the relevant provider is connected. `messages.json` remains available as a deterministic test fixture.


## Langfuse observability

This version optionally traces Gemini calls with Langfuse v4 using the official Google GenAI OpenInference instrumentation. See `LANGFUSE_SETUP.md`. Langfuse is disabled unless its credentials are configured. The root triage observation contains only low-cardinality metadata; customer text is PII-redacted before the Gemini request.
