"""Ollama LLM provider — thin shim around the official
`langchain_ollama.ChatOllama`.

Mirrors the official langchain docs (see prompt.txt):
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model="llama3.1", temperature=0, ...)
    messages = [("system", "..."), ("human", "I love programming.")]
    ai_msg = llm.invoke(messages)

We do not wrap errors or invent custom message classes — the
official inputs above are what we forward. We *do* add a request /
response / error print block (also written to `logs/app.log`) for
the same observability reasons as `openai_llm.py`.
"""
from __future__ import annotations

import traceback

from src.core.logger import logger
from src.llm._logging import _print_error, _print_request, _print_response
from src.llm.base import BaseLLM, LLMMessage, LLMResponse


def _to_tuples(messages) -> str | list:
    if isinstance(messages, str):
        return messages
    if isinstance(messages, LLMMessage):
        return (messages.role, messages.content)
    if isinstance(messages, list):
        out = []
        for m in messages:
            if isinstance(m, LLMMessage):
                out.append((m.role, m.content))
            else:
                out.append(m)
        return out
    return messages


class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url: str = kwargs.get("base_url", "http://127.0.0.1:11434")
        self.model: str = kwargs.get("model", "llama3.1")
        self.temperature: float = float(kwargs.get("temperature", 0.2))
        self.timeout: int = int(kwargs.get("timeout", 120))
        self.num_predict: int = int(kwargs.get("max_tokens", 8192))

    def chat(self, messages) -> LLMResponse:
        from langchain_ollama import ChatOllama

        lc_messages = _to_tuples(messages)
        _print_request(self.name, self.model, self.base_url, api_key="", messages=lc_messages)

        try:
            llm = ChatOllama(
                model=self.model,
                base_url=self.base_url,
                temperature=self.temperature,
                num_predict=self.num_predict,
                timeout=self.timeout,
            )
            response = llm.invoke(lc_messages)
        except Exception as exc:
            _print_error(self.name, self.model, self.base_url, exc)
            raise

        content = str(getattr(response, "content", "") or "")
        _print_response(self.name, self.model, self.base_url, content)
        return LLMResponse(content=content, model=self.model)


__all__ = ["OllamaLLM"]
