# Decision Log

## What I chose not to build, and why

I did not make a cloud LLM, Supabase account, Redis/RabbitMQ cluster, Grafana server, or Ollama model a prerequisite. This is a take-home triage service, so the reviewer should be able to run it without credentials or infrastructure provisioning. Instead, the project has clean production integration boundaries: FastAPI, local/Redis queue abstraction, optional Ollama, PII redaction, local authentication, audit/feedback, Docker, CI, and Prometheus-compatible metrics.

I also did not pretend to execute refunds, bookings, payments, CRM changes or airline changes because the fixture provides no real business APIs. The handlers therefore represent the operational owner/workflow rather than claiming an external action was completed.

## Where this breaks

- The zero-credential AI fallback is not a foundation model. Production needs an evaluated LLM such as Ollama/vLLM or a selected hosted provider.
- Very short follow-ups such as “what about the other one” require conversation history, which is not present in the fixture.
- Lightweight entity extraction should become schema-validated extraction backed by domain APIs.
- The local queue is not durable across restarts; production should use Render Key Value/Redis, RabbitMQ or Kafka plus idempotent workers.
- Local SQLite/JSON persistence is not the production source of truth on Render because the default filesystem is ephemeral. Production should use managed Postgres/Key Value or another durable datastore.
- Confidence thresholds must be calibrated using historical labeled data rather than treated as universal constants.
- A production Ollama deployment needs dedicated resources and persistent model storage; it should not be bundled into the public web service.

## What I would do with another day

1. Add a conversation-context store and retrieval layer.
2. Build an offline evaluation set with precision/recall by intent, calibration checks and a confusion matrix.
3. Compare an evaluated Ollama/vLLM model against the deterministic fallback on accuracy, latency and infrastructure cost.
4. Add durable queue workers, retry/dead-letter handling, idempotency keys and circuit breaking.
5. Persist application/audit data in Postgres and feedback in a durable store.
6. Add OpenTelemetry traces and Grafana dashboards/alerts.
7. Add production secrets management and stronger authentication/authorization.

## AI tools used

ChatGPT was used for architecture design, edge-case analysis, implementation assistance, debugging, test design, safety review, documentation and the interactive UI structure. Runtime AI behavior is explicitly labeled; the default application requires no cloud AI API key.


## Langfuse tracing

Added optional Langfuse v4 observability around the existing Gemini path. The official Google GenAI OpenInference instrumentation captures the actual Gemini generation, usage metadata and latency; a manual root triage span adds message-level routing context. Tracing is optional and failures do not break customer-message processing.
