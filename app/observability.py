from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

try:
    from langfuse import get_client, propagate_attributes
except Exception:  # optional dependency; app still runs without tracing
    get_client = None  # type: ignore[assignment]
    propagate_attributes = None  # type: ignore[assignment]


_LANGFUSE_INITIALIZED = False


def langfuse_configured() -> bool:
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        and os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip()
    )


def initialize_langfuse() -> bool:
    """Initialize the Langfuse v4 client and return whether it is configured."""
    global _LANGFUSE_INITIALIZED
    if not langfuse_configured() or get_client is None:
        return False
    if not _LANGFUSE_INITIALIZED:
        get_client()
        _LANGFUSE_INITIALIZED = True
    return True


def instrument_google_genai() -> bool:
    """Enable the official OpenInference Google GenAI instrumentation once."""
    if not initialize_langfuse():
        return False
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

        # The instrumentor is idempotent for normal application startup.
        GoogleGenAIInstrumentor().instrument()
        return True
    except Exception:
        return False


@contextmanager
def trace_triage(message: dict[str, Any]) -> Iterator[Any]:
    """Create one meaningful root span per triage request.

    Only low-cardinality identifiers and routing metadata are attached to the
    root span. Customer text is redacted before the Gemini provider sees it.
    """
    if not initialize_langfuse():
        yield None
        return

    client = get_client()
    msg_id = str(message.get("id") or "unknown")
    brand = str(message.get("brand") or "unknown")
    channel = str(message.get("channel") or "unknown")

    with client.start_as_current_observation(
        as_type="span",
        name="customer-message-triage",
        input={"message_id": msg_id, "brand": brand, "channel": channel},
        metadata={"message_id": msg_id, "brand": brand, "channel": channel},
    ) as span:
        if propagate_attributes is not None:
            with propagate_attributes(
                session_id=f"triage-{msg_id}",
                metadata={"brand": brand, "channel": channel},
                tags=["customer-message-triage"],
            ):
                try:
                    yield span
                except Exception as exc:
                    span.update(output={"status": "error", "error": str(exc)[:500]})
                    raise
        else:
            try:
                yield span
            except Exception as exc:
                span.update(output={"status": "error", "error": str(exc)[:500]})
                raise


def update_triage_span(observation: Any, *, output: dict[str, Any], model: str | None = None) -> None:
    if observation is None:
        return
    safe_output = {
        "intent": output.get("intent"),
        "handler": output.get("handler"),
        "priority": output.get("priority"),
        "confidence": output.get("confidence"),
        "human_review": output.get("human_review"),
    }
    metadata = {"llm_model": model} if model else None
    observation.update(output=safe_output, metadata=metadata)


def flush_langfuse() -> None:
    if get_client is None or not langfuse_configured():
        return
    try:
        get_client().flush()
    except Exception:
        pass


def test_langfuse_connection() -> tuple[bool, str]:
    """Verify configuration/client initialization without sending customer data."""
    if not langfuse_configured():
        return False, "LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_BASE_URL are not configured."
    if get_client is None:
        return False, "langfuse package is not installed."
    try:
        client = get_client()
        with client.start_as_current_observation(
            as_type="span",
            name="langfuse-connection-test",
            input={"test": True},
            output={"status": "ok"},
            metadata={"purpose": "connection-test"},
        ):
            pass
        client.flush()
        return True, "Langfuse test observation sent successfully."
    except Exception as exc:
        return False, f"Langfuse connection failed: {exc}"
