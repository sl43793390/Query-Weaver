"""LLM provider abstraction.

A `BaseLLM` exposes a blocking `chat(messages)` method. Concrete
implementations live in `openai_llm.py` (any OpenAI-compatible API) and
`ollama_llm.py` (local models). Streaming is intentionally not exposed
— the UI shows a spinner while the call is in flight.
"""
from src.llm.base import BaseLLM, LLMMessage, LLMResponse
from src.llm.manager import LLMManager, get_llm

__all__ = ["BaseLLM", "LLMMessage", "LLMResponse", "LLMManager", "get_llm"]
