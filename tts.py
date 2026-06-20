"""TTS module -- Cartesia (Rime slot kept swappable).

Swap this file to change text-to-speech. Expose make_tts() returning a Pipecat
TTS service.

To switch to Rime: install pipecat with the rime extra, then replace make_tts()
with the commented stub at the bottom.
"""

from pipecat.services.cartesia.tts import CartesiaTTSService

import config


def make_tts() -> CartesiaTTSService:
    return CartesiaTTSService(
        api_key=config.CARTESIA_API_KEY,
        voice_id=config.CARTESIA_VOICE_ID,
        model=config.CARTESIA_MODEL,
    )


# --- Rime slot (swap-in) -------------------------------------------------
# from pipecat.services.rime.tts import RimeTTSService
#
# def make_tts() -> RimeTTSService:
#     return RimeTTSService(
#         api_key=config.RIME_API_KEY,
#         voice_id=config.RIME_VOICE_ID,
#         model=config.RIME_MODEL,
#     )
