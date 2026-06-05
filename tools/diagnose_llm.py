"""LLM connection diagnostic.

Run this script to see exactly what the app's LLM layer sees when it
talks to your provider. It will print the resolved base URL, model,
API-key prefix, and the raw response (or error) of a tiny request.

Usage:
    d:\tareSpace\Query-Weaver\.venv\Scripts\python.exe tools\diagnose_llm.py

The script honours the same resolution order as the app:
    1. environment variable  (OPENAI_API_KEY, OPENAI_BASE_URL)
    2. project-root .env
    3. local SQLite setting
"""
from __future__ import annotations

import json
import sys
import textwrap
import traceback
from pathlib import Path

# Make project importable when running this script directly.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from src.core import env_config
from src.core.config import get_secret, get_value
from src.llm.openai_llm import OpenAILLM
from src.llm.base import LLMMessage


def _mask(key: str) -> str:
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


def main() -> int:
    api_key = env_config.resolve("OPENAI_API_KEY") or get_secret("llm.api_key")
    base_url = (
        env_config.resolve("OPENAI_BASE_URL")
        or get_value("llm.base_url", "")
        or "https://api.openai.com/v1"
    )
    model = get_value("llm.model", "gpt-4o-mini")
    timeout = 30

    print("=" * 70)
    print("Query-Weaver LLM diagnostic")
    print("=" * 70)
    print(f"  base_url    : {base_url}")
    print(f"  model       : {model!r}")
    print(f"  api_key src : {env_config.source_of('OPENAI_API_KEY') or 'sqlite'}")
    print(f"  api_key     : {_mask(api_key)}")
    print(f"  base_url src: {env_config.source_of('OPENAI_BASE_URL') or 'default'}")
    print(f"  timeout     : {timeout}s")
    print("-" * 70)

    if not api_key:
        print("FATAL: API key is empty. Set OPENAI_API_KEY or fill in Settings.")
        return 1

    llm = OpenAILLM(
        api_key=api_key, base_url=base_url, model=model, timeout=timeout
    )

    # -------- 0) base URL health probe (catch "proxy returns HTML" early)
    print("[0/2] Base URL health probe (GET {base}/models)...")
    try:
        import httpx
        url = base_url.rstrip("/") + "/models"
        r = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=5.0,
            follow_redirects=True,
        )
        ct = r.headers.get("content-type", "")
        body_preview = r.text[:120]
        print(f"  GET {url} → {r.status_code}, content-type={ct!r}")
        print(f"  body[:120] = {body_preview!r}")
        if "<!DOCTYPE html" in r.text or "<html" in r.text[:200].lower():
            print("  ✗ The base URL is returning HTML — it is NOT an OpenAI-")
            print("    compatible API endpoint. Most likely causes:")
            print("      • the URL is wrong (e.g. you're hitting a marketing site)")
            print("      • the path is wrong (most providers need /v1/models)")
            print("      • a CDN/WAF is intercepting the request")
            print("    Fix the URL in Settings before trying again.")
            print("-" * 70)
            # Don't bail — the chat call might still hit a different path
            # — but at least the user sees the warning above.
        elif "json" not in ct.lower() and r.text:
            print("  ✗ Response is not JSON — base URL is wrong.")
            print("-" * 70)
        elif r.status_code == 401:
            print("  ✗ 401 unauthorized — your API key is invalid for this base URL.")
            print("-" * 70)
        elif r.status_code == 404:
            print("  ✗ 404 not found — base URL path is wrong (try /v1/models?).")
            print("-" * 70)
        elif r.status_code >= 500:
            print("  ✗ 5xx from server — provider is down. Try again later.")
            print("-" * 70)
        else:
            print("  ✓ base URL reachable and looks like an OpenAI-compatible API.")
            print("-" * 70)
    except Exception as exc:
        print(f"  ✗ probe failed: {exc}")
        print("    (the chat call below will probably fail the same way)")
        print("-" * 70)

    # -------- 1) blocking test (the only mode the app uses now) -----
    print("[1/1] Blocking test (single invoke(), what the chat panel uses)...")
    try:
        resp = llm.chat(
            [LLMMessage("user", "Reply with the single word: pong")],
        )
        content = (resp.content or "").strip()
        print(f"  OK, model={resp.model!r}, content={content!r}")
        if not content:
            print("  WARN: empty content despite success — this should not")
            print("        happen any more (raise added in openai_llm.py).")
        print("-" * 70)
        print("Done. If content is non-empty above, the chat panel will work.")
        return 0
    except Exception as exc:
        print("  Call FAILED:")
        print(textwrap.indent(str(exc), "    "))
        # Surface the SDK raw exception type for clarity
        print("  exception type:", type(exc).__name__)
        if hasattr(exc, "status_code"):
            print("  status_code   :", getattr(exc, "status_code"))
        if hasattr(exc, "body"):
            print("  body          :", getattr(exc, "body"))
        if hasattr(exc, "request"):
            try:
                req = exc.request
                print("  request.url   :", req.url)
            except Exception:
                pass
        print("=" * 70)
        return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)





