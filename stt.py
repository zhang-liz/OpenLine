"""STT module -- AssemblyAI Universal-3 Pro Streaming.

Swap this file to change speech-to-text. Expose a make_stt() that returns a
Pipecat STT service. Uses AssemblyAI's built-in neural turn detection; do NOT
add a separate VAD upstream.
"""

from pipecat.services.assemblyai import AssemblyAISTTService, AssemblyAIConnectionParams

import config


def make_stt() -> AssemblyAISTTService:
    return AssemblyAISTTService(
        connection_params=AssemblyAIConnectionParams(
            api_key=config.ASSEMBLYAI_API_KEY,
            # Universal-3 Pro realtime streaming model.
            speech_model="u3-rt-pro",
            # Built-in turn detection thresholds (no separate VAD).
            end_of_turn_confidence_threshold=0.7,
            min_end_of_turn_silence_when_confident=300,
            max_turn_silence=1000,
        )
    )
