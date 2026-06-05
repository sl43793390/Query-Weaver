"""LLM abstractions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMMessage:
    role: str            # 'system' | 'user' | 'assistant'
    content: str


@dataclass
class LLMResponse:
    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    raw: object = None


class BaseLLM(ABC):
    """Common interface for LLM providers.

    We deliberately use *blocking* `chat()` only — no streaming. The UI
    shows a spinner / status text while the call is in flight, and the
    full response replaces the placeholder once it's available. This
    keeps the call sites trivial and dodges all the proxy quirks that
    show up in streaming (empty SSE bodies, half-decoded chunks, etc).
    """

    name: str = "base"

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @abstractmethod
    def chat(self, messages: list[LLMMessage]) -> LLMResponse: ...


__all__ = ["BaseLLM", "LLMMessage", "LLMResponse"]
