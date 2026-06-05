"""Misc helper functions used across the app."""
from __future__ import annotations

import re
from typing import Iterable

_SQL_FENCE = re.compile(r"```(?:sql|json|bash)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code_blocks(text: str) -> list[str]:
    """Extract fenced code blocks (```...```) from LLM output."""
    if not text:
        return []
    return [m.group(1).strip() for m in _SQL_FENCE.finditer(text)]


def first_code_block(text: str, default: str = "") -> str:
    blocks = extract_code_blocks(text)
    return blocks[0] if blocks else default


def chunked(seq: Iterable, size: int):
    buf = []
    for item in seq:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def truncate(s: str, n: int = 200) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"
