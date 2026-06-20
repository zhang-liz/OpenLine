"""LLM module -- Anthropic Claude (Haiku by default).

Swap this file to change the language model. Expose make_llm(). Model id is
config-driven (LLM_MODEL) so swapping to a different Claude tier is an env change.
"""

from pipecat.services.anthropic.llm import AnthropicLLMService

from . import config


def make_llm() -> AnthropicLLMService:
    return AnthropicLLMService(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.LLM_MODEL,
    )
