# Gemini setup

This build uses Gemini Flash-Lite as the recommended fast cloud LLM. Ollama remains optional.

## 1. Create a Gemini API key

Open Google AI Studio and create an API key. Keep the key private and do not commit it to GitHub.

## 2. Windows PowerShell

From the project folder:

```powershell
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
$env:GEMINI_MODEL="gemini-3.5-flash-lite"
python -m streamlit run app/ui.py
```

You can also use the `.env.example` as a reference. The app currently reads environment variables directly, so PowerShell commands are the simplest local setup.

## 3. In the UI

Sign in with the demo account, then leave **Use Gemini (recommended)** enabled.

The app redacts PII before sending customer text to the model and keeps health, payment, prompt-injection, identity, and active travel-disruption cases human-controlled.

## 4. Ollama

Ollama is still available as an optional provider. Select **Use local Ollama** instead if it is working on your machine.
