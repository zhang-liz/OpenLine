"""Configuration loaded from environment variables.

All config lives here so the rest of the app never reads os.environ directly.
"""

import os


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


# --- Public host (how Twilio reaches our websocket) ---
# e.g. "my-app.ngrok.io" or "voice.example.com" -- host only, no scheme.
PUBLIC_URL = _require("PUBLIC_URL")

# Shared secret the Apps Script must send in the X-Lead-Secret header.
LEAD_SHARED_SECRET = _require("LEAD_SHARED_SECRET")

# --- Twilio ---
TWILIO_ACCOUNT_SID = _require("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = _require("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = _require("TWILIO_FROM_NUMBER")

# --- Google Sheets ---
GOOGLE_SERVICE_ACCOUNT_JSON = _require("GOOGLE_SERVICE_ACCOUNT_JSON")  # path to key file
SHEET_ID = _require("SHEET_ID")
SHEET_TAB = os.environ.get("SHEET_TAB", "Sheet1")

# --- STT (AssemblyAI) ---
ASSEMBLYAI_API_KEY = _require("ASSEMBLYAI_API_KEY")

# --- LLM (Anthropic) ---
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5")

# --- TTS (Cartesia) ---
CARTESIA_API_KEY = _require("CARTESIA_API_KEY")
CARTESIA_VOICE_ID = _require("CARTESIA_VOICE_ID")
CARTESIA_MODEL = os.environ.get("CARTESIA_MODEL", "sonic-2")

# --- Server ---
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))
