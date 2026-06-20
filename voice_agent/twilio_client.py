"""Twilio outbound calling + TwiML for the media stream.

place_call() dials the lead and points the call at our /twiml endpoint, which
returns TwiML that opens a bidirectional Media Stream to /ws.
"""

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

from . import config

_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def place_call(to_number: str, row_number: int) -> str:
    """Dial the lead. The call hits /twiml, which streams audio to /ws.

    row_number is threaded through as a query param so the websocket handler
    knows which sheet row to write back to. Returns the Twilio call SID.
    """
    twiml_url = f"https://{config.PUBLIC_URL}/twiml?row={row_number}"
    call = _client.calls.create(
        to=to_number,
        from_=config.TWILIO_FROM_NUMBER,
        url=twiml_url,
        # Tell us how the call ended (completed / no-answer / busy / failed).
        status_callback=f"https://{config.PUBLIC_URL}/status?row={row_number}",
        status_callback_event=["completed"],
    )
    return call.sid


def build_twiml(row_number: int) -> str:
    """TwiML that connects the call audio to our websocket."""
    response = VoiceResponse()
    connect = Connect()
    stream_url = f"wss://{config.PUBLIC_URL}/ws?row={row_number}"
    connect.stream(url=stream_url)
    response.append(connect)
    return str(response)
