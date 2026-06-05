"""High-level LLM manager.

Reads provider settings from the local SQLite store (see `src.core.config`)
and builds the right provider on demand. The UI talks to `get_llm()`.

Resolution order for `api_key` / `base_url`:
    1. environment variable  (e.g. `OPENAI_API_KEY`, `OPENAI_BASE_URL`)
    2. project-root `.env` file
    3. SQLite setting (`llm.api_key` / `llm.base_url`)

Set the SQLite value to override per-user; leave it blank to fall through
to the deployment-time env vars / .env.
"""
from __future__ import annotations

from src.core.config import get_secret, get_value
from src.core import env_config
from src.llm.base import BaseLLM, LLMMessage, LLMResponse
from src.llm.openai_llm import OpenAILLM
from src.llm.ollama_llm import OllamaLLM

_PROVIDERS = {
    "openai": OpenAILLM,
    "ollama": OllamaLLM,
}


class LLMManager:
    """Caches the active provider instance and exposes `chat()`."""

    def __init__(self):
        self._instance: BaseLLM | None = None
        self._signature: tuple | None = None

    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        self._instance = None
        self._signature = None

    def current_signature(self) -> tuple | None:
        return self._signature

    # ------------------------------------------------------------------ #
    def get(self) -> BaseLLM:
        if self._instance is not None:
            return self._instance

        provider = (get_value("llm.provider", "openai") or "openai").lower()
        model = get_value("llm.model", "qwen3.5-flash")
        temperature = float(get_value("llm.temperature", "0.2") or 0.2)
        max_tokens = int(get_value("llm.max_tokens", "8192") or 8192)

        # api_key / base_url fall back to env var / .env, then to the
        # locally-saved value, then to the built-in default. The env
        # var takes top priority so ops can rotate keys without
        # touching the local DB.
        if provider == "openai":
            api_key = env_config.resolve("OPENAI_API_KEY") or get_secret("llm.api_key")
            base_url = (
                env_config.resolve("OPENAI_BASE_URL")
                or get_value("llm.base_url", "")
                or "https://api.openai.com/v1"
            )
        else:                       # ollama / others
            api_key = ""
            base_url = (
                env_config.resolve("OLLAMA_HOST")
                or env_config.resolve("OPENAI_BASE_URL")
                or get_value("llm.base_url", "")
                or "http://127.0.0.1:11434"
            )

        cls = _PROVIDERS.get(provider)
        if cls is None:
            raise ValueError(f"Unknown LLM provider: {provider!r}")

        kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if provider == "openai":
            kwargs.update({"api_key": api_key, "base_url": base_url})
        elif provider == "ollama":
            kwargs.update({"base_url": base_url})

        self._instance = cls(**kwargs)
        self._signature = (provider, model, base_url, bool(api_key))
        return self._instance

    # ------------------------------------------------------------------ #
    def chat(self, messages: list[LLMMessage]) -> LLMResponse:
        llm = self.get()
        return llm.chat(messages)


# Global, lazily-instantiated manager.
_manager = LLMManager()


def get_llm() -> BaseLLM:
    return _manager.get()


def get_manager() -> LLMManager:
    return _manager


__all__ = ["LLMManager", "get_llm", "get_manager"]
