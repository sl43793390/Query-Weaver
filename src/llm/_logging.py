"""Shared log / print helpers for the LLM provider modules.

These are intentionally lightweight: print the request, the response,
or the error to stdout (with `flush=True` so it shows up immediately
even when the app is GUI-mode) *and* write a one-liner to the
application's structured log file (`logs/app.log`).
"""
from __future__ import annotations

import traceback

from src.core.logger import logger


def _mask(key: str) -> str:
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


def _preview(text: str, limit: int = 300) -> str:
    s = text or ""
    if len(s) <= limit:
        return s
    return s[:limit] + f"...[+{len(s) - limit} chars]"


def _print_request(provider: str, model: str, base_url: str, api_key: str, messages) -> None:
    bar = "=" * 70
    print(bar, flush=True)
    print(
        f"[LLM REQUEST] provider={provider} model={model!r} "
        f"base_url={base_url or '(default)'}",
        flush=True,
    )
    print(f"  api_key = {_mask(api_key)}", flush=True)
    if isinstance(messages, str):
        print(f"  messages: <single string, len={len(messages)}>", flush=True)
        print(f"    [user] {_preview(messages)}", flush=True)
    else:
        print(f"  messages ({len(messages)}):", flush=True)
        for role, content in messages:
            print(f"    [{role}] {_preview(content)}", flush=True)
    print(bar, flush=True)
    logger.info(
        "LLM REQUEST provider={} model={} base_url={} key={} msgs={}",
        provider, model, base_url or "(default)", _mask(api_key),
        len(messages) if isinstance(messages, list) else 1,
    )


def _print_response(provider: str, model: str, base_url: str, content: str) -> None:
    bar = "=" * 70
    print(bar, flush=True)
    print(
        f"[LLM RESPONSE] provider={provider} model={model!r} "
        f"base_url={base_url or '(default)'}",
        flush=True,
    )
    print(f"  content_len = {len(content)}", flush=True)
    print(f"  content[:500] = {_preview(content, 500)!r}", flush=True)
    print(bar, flush=True)
    logger.info(
        "LLM RESPONSE provider={} model={} base_url={} content_len={}",
        provider, model, base_url or "(default)", len(content),
    )


def _print_error(provider: str, model: str, base_url: str, exc: Exception) -> None:
    bar = "=" * 70
    print(bar, flush=True)
    print(
        f"[LLM ERROR] provider={provider} model={model!r} "
        f"base_url={base_url or '(default)'}",
        flush=True,
    )
    print(f"  exception_type = {type(exc).__name__}", flush=True)
    print(f"  message = {exc}", flush=True)
    print("  traceback:", flush=True)
    traceback.print_exc()
    print(bar, flush=True)
    logger.exception(
        "LLM ERROR provider={} model={} base_url={}",
        provider, model, base_url or "(default)",
    )
