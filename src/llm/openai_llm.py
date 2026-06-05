"""OpenAI-compatible LLM provider — thin shim around the official
`langchain_openai.ChatOpenAI`.

This module deliberately keeps the shim as small as possible (the
official langchain docs example is the gold standard). The two extras
we layer on top are:

1. A `_before_send` / `_after_send` / `_on_error` log block that prints
   the request messages, the response, and any error to stdout (and to
   the `logs/app.log` file) — because the official shim has zero
   observability and you cannot debug "model not found on this proxy"
   without seeing the wire-level result.

2. An httpx response event hook that raises *before* langchain sees a
   non-JSON body. This is the fix for the
   `'str' object has no attribute 'model_dump'` error that fires when
   a proxy (e.g. dmxapi) returns an HTML error page with status 2xx —
   the openai SDK silently forwards the raw body to langchain which
   then tries to call `.model_dump()` on it.
"""
from __future__ import annotations

import httpx

from src.llm._logging import _print_error, _print_request, _print_response
from src.llm.base import BaseLLM, LLMMessage, LLMResponse


# --------------------------------------------------------------------- #
# httpx event hook: reject HTML / non-JSON bodies up front.
# --------------------------------------------------------------------- #

def _httpx_reject_non_json(response: httpx.Response) -> httpx.Response:
    """Fire on every HTTP response. If the body is HTML / XML (which
    means we hit a CDN / gateway / WAF error page rather than a real
    OpenAI-compatible API), raise with a clear message *before* the
    openai SDK tries to parse it. Without this, langchain-openai
    chokes on the string with `AttributeError: 'str' object has no
    attribute 'model_dump'`."""
    # `response.text` in a hook would raise ResponseNotRead because
    # the body hasn't been consumed yet — call `read()` first.
    try:
        response.read()
    except Exception:
        pass
    ct = (response.headers.get("content-type") or "").lower()
    if "html" in ct or "xml" in ct:
        body_preview = (response.text or "")[:300]
        raise RuntimeError(
            f"Server returned non-JSON response "
            f"(status={response.status_code}, content-type={ct!r}). "
            f"This almost always means the base URL is wrong, or the "
            f"model doesn't exist on it. URL: {response.url}\n"
            f"Body[:300]: {body_preview!r}"
        )
    return response


# --------------------------------------------------------------------- #
# Message normalisation — same shape as the official langchain example.
# --------------------------------------------------------------------- #

def _to_tuples(messages) -> str | list:
    """Map our `LLMMessage` objects onto the (role, content) tuple form
    that the official docs use. Strings and langchain messages are
    forwarded as-is."""
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


# --------------------------------------------------------------------- #
# OpenAILLM
# --------------------------------------------------------------------- #

class OpenAILLM(BaseLLM):
    name = "openai"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key: str = kwargs.get("api_key", "")
        self.base_url: str = kwargs.get("base_url", "")
        self.model: str = kwargs.get("model", "mimo-v2.5")
        self.temperature: float = float(kwargs.get("temperature", 0.2))
        self.max_tokens: int = int(kwargs.get("max_tokens", 8192))
        self.timeout: int = int(kwargs.get("timeout", 60))

    def chat(self, messages) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured. Open Settings.")

        from langchain_openai import ChatOpenAI

        lc_messages = _to_tuples(messages)
        _print_request(self.name, self.model, self.base_url, self.api_key, lc_messages)

        # Per-request httpx client with the HTML-reject hook. The hook
        # intercepts non-JSON responses before the openai SDK parses
        # them, which is what was causing the
        # `AttributeError: 'str' object has no attribute 'model_dump'`
        # failure on dmxapi / other OpenAI-compatible proxies.
        http_client = httpx.Client(event_hooks={"response": [_httpx_reject_non_json]})
        try:
            model = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
                http_client=http_client,
            )
            response = model.invoke(lc_messages)
        except Exception as exc:
            _print_error(self.name, self.model, self.base_url, exc)
            raise
        finally:
            http_client.close()

        content = str(getattr(response, "content", "") or "")
        _print_response(self.name, self.model, self.base_url, content)
        return LLMResponse(content=content, model=self.model)


__all__ = ["OpenAILLM"]
