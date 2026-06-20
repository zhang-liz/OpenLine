"""FastAPI app: lead trigger, TwiML, media-stream websocket, call status.

Endpoints
---------
POST /lead    Apps Script hits this when a new row appears. Validates consent,
              places the outbound Twilio call. Guarded by a shared secret.
GET  /twiml   Twilio fetches TwiML for the call; returns Connect/Stream to /ws.
WS   /ws      Twilio Media Streams connects here; runs the Pipecat pipeline and
              writes the transcript back to the sheet when the call ends.
POST /status  Twilio status callback; writes final status to the sheet.
"""

import json

from fastapi import FastAPI, Request, WebSocket, Header, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

import config
import sheet
import twilio_client
from pipeline import build_pipeline_task, run_task

app = FastAPI()


@app.post("/lead")
async def lead(request: Request, x_lead_secret: str = Header(default="")):
    """Triggered by Apps Script for a new row. Body: {"row": <int>}."""
    if x_lead_secret != config.LEAD_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="bad secret")

    body = await request.json()
    row = body.get("row")
    if not isinstance(row, int):
        raise HTTPException(status_code=400, detail="row (int) required")

    lead_row = sheet.get_lead(row)

    if not sheet.consent_given(lead_row):
        sheet.write_result(row, "failed", "skipped: no consent")
        return JSONResponse({"status": "skipped", "reason": "no consent"})

    phone = str(lead_row.get("phone", "")).strip()
    if not phone:
        sheet.write_result(row, "failed", "skipped: no phone")
        return JSONResponse({"status": "skipped", "reason": "no phone"})

    call_sid = twilio_client.place_call(phone, row)
    return JSONResponse({"status": "calling", "call_sid": call_sid, "row": row})


@app.get("/twiml")
async def twiml(row: int):
    """Twilio fetches this to learn how to handle the call."""
    return PlainTextResponse(
        twilio_client.build_twiml(row), media_type="application/xml"
    )


@app.websocket("/ws")
async def ws(websocket: WebSocket, row: int):
    """Twilio Media Streams websocket. Runs the pipeline for one call."""
    await websocket.accept()

    # Twilio sends two JSON text frames first: "connected", then "start" which
    # carries streamSid and callSid. Read them before building the pipeline.
    stream_sid = None
    call_sid = None
    for _ in range(2):
        message = await websocket.receive_text()
        data = json.loads(message)
        if data.get("event") == "start":
            start = data["start"]
            stream_sid = start["streamSid"]
            call_sid = start["callSid"]
            break

    if not stream_sid:
        await websocket.close()
        return

    lead_row = sheet.get_lead(row)
    task, session = build_pipeline_task(
        websocket, stream_sid, call_sid, lead_row.get("name", "")
    )

    try:
        await run_task(task)
    finally:
        # Status is written by /status; here we persist the transcript.
        # If the call connected and produced dialogue, mark completed.
        transcript = session.transcript()
        if transcript:
            sheet.write_result(row, "completed", transcript)


@app.post("/status")
async def status(request: Request, row: int):
    """Twilio call status callback. Records non-completed outcomes."""
    form = await request.form()
    call_status = form.get("CallStatus", "")

    # Map Twilio statuses to our vocabulary. "completed" with a transcript is
    # handled in /ws; here we catch no-answer / busy / failed.
    mapping = {
        "no-answer": "no-answer",
        "busy": "no-answer",
        "failed": "failed",
        "canceled": "failed",
    }
    if call_status in mapping:
        sheet.write_result(row, mapping[call_status], f"call {call_status}")

    return PlainTextResponse("", status_code=204)
