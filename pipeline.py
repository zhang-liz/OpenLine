"""Assemble the Pipecat cascading pipeline for one call.

Wires: Twilio websocket transport -> STT -> LLM -> TTS -> back to transport,
with a context aggregator (conversation memory) and a transcript processor that
collects the full conversation for write-back to the sheet.

Cascading order (one direction): transport.input -> STT -> context.user ->
LLM -> TTS -> transport.output -> context.assistant. The transcript processor
taps user (post-STT) and assistant (post-TTS) text.
"""

from fastapi import WebSocket

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)

import config
from stt import make_stt
from llm import make_llm
from tts import make_tts
from prompt import build_system_prompt


class CallSession:
    """Holds per-call state: the runner task and the accumulating transcript."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def transcript(self) -> str:
        return "\n".join(self.lines)


def build_pipeline_task(
    websocket: WebSocket,
    stream_sid: str,
    call_sid: str,
    lead_name: str,
) -> tuple[PipelineTask, CallSession]:
    """Build a PipelineTask for a single Twilio call.

    Returns the task plus a CallSession whose .transcript() is populated as the
    conversation proceeds.
    """
    session = CallSession()

    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        account_sid=config.TWILIO_ACCOUNT_SID,
        auth_token=config.TWILIO_AUTH_TOKEN,
    )

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            # AssemblyAI does its own turn detection -- no VAD here.
            serializer=serializer,
        ),
    )

    stt = make_stt()
    llm = make_llm()
    tts = make_tts()

    context = LLMContext(
        messages=[{"role": "system", "content": build_system_prompt(lead_name)}],
    )
    aggregator = LLMContextAggregatorPair(context)

    transcript = TranscriptProcessor()

    @transcript.event_handler("on_transcript_update")
    async def _on_transcript_update(_processor, frame):
        for msg in frame.messages:
            session.lines.append(f"{msg.role}: {msg.content}")

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript.user(),
            aggregator.user(),
            llm,
            tts,
            transport.output(),
            transcript.assistant(),
            aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True),
    )

    # Kick off the conversation: have the agent speak first once connected.
    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):
        await task.queue_frames([aggregator.user().get_context_frame()])

    return task, session


async def run_task(task: PipelineTask) -> None:
    """Run a built task to completion."""
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
