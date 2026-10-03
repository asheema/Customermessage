# Langfuse setup

This project uses Langfuse Python SDK v4 with the official OpenInference Google GenAI instrumentation. Langfuse Cloud is optional; Gemini still works when tracing is disabled.

## 1. Create Langfuse Cloud project

Create a Langfuse Cloud project and copy its API keys from Project Settings → API Keys.

## 2. Configure PowerShell

```powershell
$env:LANGFUSE_PUBLIC_KEY="pk-lf-your-key"
$env:LANGFUSE_SECRET_KEY="sk-lf-your-key"
$env:LANGFUSE_BASE_URL="https://cloud.langfuse.com"
$env:LANGFUSE_TRACING_ENVIRONMENT="development"
```

Keep your existing Gemini key:

```powershell
$env:GEMINI_API_KEY="your-gemini-key"
```

## 3. Install dependencies

```powershell
pip install -r requirements.txt
```

## 4. Verify tracing

Start Streamlit:

```powershell
streamlit run app/ui.py
```

After login, use **Test Langfuse connection** in the sidebar. Then run an eligible Gemini message. The application creates one `customer-message-triage` span and the official Google GenAI instrumentation creates the nested Gemini generation.

## What is captured

- model name
- Gemini generation latency
- Gemini usage metadata/token counts when returned by the provider
- redacted prompt content
- model output used for triage
- message ID, brand and channel as metadata
- triage status/errors

Customer PII is redacted before the Gemini request. The root trace uses low-cardinality identifiers and does not store the raw customer message.

## Short-lived runs

The app calls `langfuse.flush()` after Gemini calls so traces are exported reliably from Streamlit/CLI runs.

## Troubleshooting

If no traces appear, set:

```powershell
$env:LANGFUSE_DEBUG="True"
```

Then check the terminal. Verify the three Langfuse environment variables and make sure instrumentation is installed before the Gemini call.
