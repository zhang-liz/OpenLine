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

## Prerequisites

- **[uv](https://docs.astral.sh/uv/)** — Python package/venv manager.
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **[ngrok](https://ngrok.com/)** — local-dev only, exposes the server to Twilio.
  Not needed in production (use a real domain).
  ```bash
  brew install ngrok                       # macOS
  ngrok config add-authtoken <YOUR_TOKEN>  # free token from dashboard.ngrok.com
  ```
- Accounts/keys: Twilio, AssemblyAI, Anthropic, Cartesia, and a Google Cloud
  service account (see Setup below).

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

Twilio needs a public `wss` URL. For local dev (ngrok from Prerequisites):

```bash
ngrok http 8080
```

Set `PUBLIC_URL` to the forwarding host ngrok prints — host only, no scheme,
e.g. `abc123.ngrok-free.app`. The free host changes on each restart; update
`PUBLIC_URL` (and the Apps Script `SERVICE_URL`) and restart the server when it does.

### 5. Run

```bash
uv run python main.py
```

### 6. Apps Script trigger

Make the Sheet POST to the server whenever a new lead row appears.

1. **Open the editor.** In the Sheet: **Extensions → Apps Script**. A new
   editor tab opens with an empty `Code.gs`.
2. **Paste the script.** Delete whatever is in `Code.gs`, paste the full
   contents of `apps_script.gs`.
3. **Set the three constants** at the top of the file:
   - `SERVICE_URL` → `https://<PUBLIC_URL>/lead` (your ngrok host + `/lead`,
     **with** `https://`).
   - `SHARED_SECRET` → exact same value as `LEAD_SHARED_SECRET` in `.env`.
   - `SHEET_TAB` → your tab name (default `Sheet1`); must match `SHEET_TAB` in `.env`.
4. **Save.** Click the disk icon (or ⌘S).
5. **Add the trigger.** Left sidebar → **Triggers** (alarm-clock icon) →
   **Add Trigger** (bottom-right), then set:
   - Function to run: **onChange**
   - Deployment: **Head**
   - Event source: **From spreadsheet**
   - Event type: **On change**
   - Save.
6. **Authorize.** First save pops a Google auth dialog → pick your account →
   **Advanced → Go to \<project\> (unsafe)** → **Allow**. (Expected — it's your
   own script needing permission to read the Sheet and make outbound requests.)

**Test it:** server + ngrok running, add a row with a `phone` (E.164) and blank
`status`. The script flips `status` to `calling`, the agent dials, and on
hang-up the server writes `completed`/`no-answer`/`failed` + the transcript.

**Troubleshooting:**
- Nothing happens → check **Apps Script → Executions** for `onChange` runs/errors.
- `401`/no call → `SHARED_SECRET` ≠ `LEAD_SHARED_SECRET`.
- Connection error in logs → `SERVICE_URL` host stale (ngrok restarted) or server down.

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
