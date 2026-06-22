"""Assemble the Pipecat cascading pipeline for one call.

Wires: Twilio websocket transport -> STT -> LLM -> TTS -> back to transport,
with a context aggregator (conversation memory) and a transcript processor that
collects the full conversation for write-back to the sheet.

Cascading order (one direction): transport.input -> STT -> context.user ->
LLM -> TTS -> transport.output -> context.assistant. The transcript processor
taps user (post-STT) and assistant (post-TTS) text.
"""

from fastapi import WebSocket

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)

import config
from stt import make_stt
from llm import make_llm
from tts import make_tts
from prompt import build_system_prompt, build_greeting


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
            # VAD drives barge-in: fast local speech-onset detection emits the
            # UserStartedSpeakingFrame that interrupts TTS. AssemblyAI still
            # owns end-of-turn endpointing (see stt.py).
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            serializer=serializer,
        ),
    )

    stt = make_stt()
    llm = make_llm()
    tts = make_tts()

    # Seed the fixed opener as an assistant turn so the LLM knows it has already
    # introduced itself and asked permission. The line itself is spoken directly
    # via TTS on connect (below), skipping the LLM for the first utterance.
    greeting = build_greeting(lead_name)
    context = LLMContext(
        messages=[
            {"role": "system", "content": build_system_prompt(lead_name)},
            {"role": "assistant", "content": greeting},
        ],
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
        params=PipelineParams(allow_interruptions=True, enable_metrics=True),
    )

    # Kick off the conversation: speak the fixed opener directly via TTS once
    # connected. No LLM round-trip for the first line -- the lead hears audio as
    # soon as TTS yields its first chunk. The LLM only runs once they reply.
    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):
        await task.queue_frames([TTSSpeakFrame(greeting)])

    # When Twilio hangs up it closes the websocket; cancel the task so run_task()
    # returns and the transcript gets written back. Without this the pipeline
    # keeps running (services try to reconnect) and the write-back never fires.
    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client):
        await task.cancel()

    return task, session


async def run_task(task: PipelineTask) -> None:
    """Run a built task to completion."""
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
