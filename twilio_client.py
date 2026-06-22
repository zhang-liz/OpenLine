"""Twilio outbound calling + TwiML for the media stream.

place_call() dials the lead and points the call at our /twiml endpoint, which
returns TwiML that opens a bidirectional Media Stream to /ws.
"""

from urllib.parse import quote

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

import config

_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def place_call(to_number: str, row_number: int, name: str = "") -> str:
    """Dial the lead. The call hits /twiml, which streams audio to /ws.

    row_number is threaded through as a query param so the websocket handler
    knows which sheet row to write back to. name rides along the same way so the
    websocket can greet the lead without a second sheet read. Returns the call SID.
    """
    twiml_url = f"https://{config.PUBLIC_URL}/twiml?row={row_number}&name={quote(name)}"
    call = _client.calls.create(
        to=to_number,
        from_=config.TWILIO_FROM_NUMBER,
        url=twiml_url,
        # Tell us how the call ended (completed / no-answer / busy / failed).
        status_callback=f"https://{config.PUBLIC_URL}/status?row={row_number}",
        status_callback_event=["completed"],
    )
    return call.sid


def build_twiml(row_number: int, name: str = "") -> str:
    """TwiML that connects the call audio to our websocket.

    Twilio strips the query string from a <Stream> url, so the sheet row and the
    lead name are passed as <Parameter>s; they arrive in the websocket "start"
    event under start.customParameters.
    """
    response = VoiceResponse()
    connect = Connect()
    stream_url = f"wss://{config.PUBLIC_URL}/ws"
    stream = connect.stream(url=stream_url)
    stream.parameter(name="row", value=str(row_number))
    stream.parameter(name="name", value=name)
    response.append(connect)
    return str(response)
