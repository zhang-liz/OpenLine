# Callback Voice Agent

Outbound voice agent that calls leads from a Google Sheet right after they submit
an interest form. Per call it bridges Twilio audio into a Pipecat cascading
pipeline (AssemblyAI STT → Claude → Cartesia TTS), then writes the call status
and transcript back to the sheet row.

## How it works

```
New row in Sheet
   │  (Apps Script onChange → POST /lead)
   ▼
FastAPI /lead ── checks consent ── Twilio outbound call
   │
   ▼  Twilio fetches /twiml → Connect/Stream to wss /ws
Pipecat pipeline:  Twilio MediaStream ⇄ AssemblyAI STT → Claude Haiku → Cartesia TTS
   │
   ▼  call ends
Status + transcript written back to the row
```

- **Trigger:** Apps Script `onChange` POSTs the new row number to `/lead`. Only
  rows with a blank `status` fire, which both detects new leads and stops the
  server's own write-back from re-triggering a call.
- **No separate VAD:** AssemblyAI Universal-3 Pro Streaming does turn detection.
- **Swappable services:** STT, LLM, and TTS each live in their own one-file
  module (`stt.py`, `llm.py`, `tts.py`). Swap a provider by editing
  one file. The Rime TTS slot is a commented stub in `tts.py`.

## Sheet format

One worksheet used as the call queue. Header row (case-insensitive):

| name | phone | email | consent_given | status | transcript |
|------|-------|-------|---------------|--------|------------|

- `phone` in E.164 (e.g. `+15551234567`).
- `consent_given` truthy values: `true`, `yes`, `y`, `1`, `x`, `✓`.
- `status` / `transcript` are written by the server (`completed` / `no-answer` /
  `failed`). Leave them blank for new leads.

## Setup

### 1. Python

Uses [uv](https://docs.astral.sh/uv/). `uv sync` creates the venv and installs
the locked deps.

```bash
uv sync
cp .env.example .env   # then fill it in
```

### 2. Google service account

1. In Google Cloud, create a service account and download its JSON key.
2. Enable the **Google Sheets API** and **Google Drive API** for the project.
3. Share the Sheet with the key's `client_email` as **Editor**.
4. Point `GOOGLE_SERVICE_ACCOUNT_JSON` at the key file (kept out of git).

### 3. Provider keys

Fill `.env` with Twilio, AssemblyAI, Anthropic, and Cartesia credentials and a
Cartesia `voice_id`. See `.env.example` for every variable.

### 4. Public URL

Twilio needs a public `wss` URL. For local dev:

```bash
ngrok http 8080
```

Set `PUBLIC_URL` to the ngrok host (no scheme), e.g. `abc123.ngrok.io`.

### 5. Run

```bash
uv run python main.py
```

### 6. Apps Script trigger

1. Sheet → **Extensions → Apps Script**, paste `apps_script.gs`.
2. Set `SERVICE_URL` to `https://<PUBLIC_URL>/lead` and `SHARED_SECRET` to match
   `LEAD_SHARED_SECRET` in `.env`.
3. **Triggers → Add Trigger →** function `onChange`, event source *From
   spreadsheet*, event type *On change*.

Add a lead row with a phone and blank status → the agent calls them.

## Security notes

- `/lead` is guarded by the `X-Lead-Secret` shared secret. Without it, anyone who
  finds the URL could trigger calls (toll fraud). Keep the secret long and random.
- `consent_given` is checked before any call is placed; no-consent rows are
  skipped and marked `failed`.
- `.env` and `service_account.json` are gitignored. Never commit them.

## Project layout

```
main.py                  entrypoint (loads .env, runs uvicorn)
pyproject.toml           deps (managed by uv)
uv.lock                  pinned lockfile
.env.example
app.py                   FastAPI: /lead, /twiml, /ws, /status
pipeline.py              builds the Pipecat pipeline per call
stt.py                   AssemblyAI  (swappable)
llm.py                   Claude Haiku (swappable)
tts.py                   Cartesia, Rime slot (swappable)
sheet.py                 gspread read/write
twilio_client.py         outbound call + TwiML
prompt.py                agent system prompt
config.py                env vars
apps_script.gs           paste into the Sheet's Apps Script
```
