"""Simple SQL syntax highlighter for tkinter Text widgets.

We avoid heavy 3rd-party deps (Pygments is listed in requirements for future
use) and implement a small, fast regex-based highlighter that works inside
a `tk.Text` widget. CustomTkinter's `CTkTextbox` wraps `tk.Text`, so we
poke through the underlying widget.
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont

# Token regexes — order matters (longest match first).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("keyword", re.compile(r"\b(SELECT|FROM|WHERE|AND|OR|NOT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|ORDER|BY|LIMIT|OFFSET|FETCH|HAVING|UNION|ALL|AS|IN|LIKE|IS|NULL|TRUE|FALSE|DISTINCT|COUNT|SUM|AVG|MAX|MIN|TABLE|INDEX|VIEW|DATABASE|SCHEMA|EXPLAIN|DESC|DESCRIBE|WITH|CASE|WHEN|THEN|ELSE|END|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|CHECK)\b", re.IGNORECASE)),
    ("string",  re.compile(r"'[^']*'|\"[^\"]*\"")),
    ("number",  re.compile(r"\b\d+(\.\d+)?\b")),
    ("comment", re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)),
]

_COLORS = {
    "keyword": "#569cd6",
    "string":  "#ce9178",
    "number":  "#b5cea8",
    "comment": "#6a9955",
}


class SQLHighlighter:
    """Attach a regex highlighter to a `tk.Text` widget."""

    def __init__(self, text_widget: tk.Text):
        self.text = text_widget
        base_font = tkfont.nametofont("TkFixedFont")
        self.text.configure(font=base_font)
        for tag, color in _COLORS.items():
            self.text.tag_configure(tag, foreground=color)
        self.text.bind("<<Modified>>", self._on_modified)

    def _on_modified(self, _event=None):
        if not self.text.edit_modified():
            return
        self.highlight()
        self.text.edit_modified(False)

    def highlight(self) -> None:
        # Remove existing tags on the visible range.
        self.text.tag_remove("keyword", "1.0", "end")
        self.text.tag_remove("string", "1.0", "end")
        self.text.tag_remove("number", "1.0", "end")
        self.text.tag_remove("comment", "1.0", "end")

        data = self.text.get("1.0", "end-1c")
        for tag, pat in _PATTERNS:
            for m in pat.finditer(data):
                start = f"1.0+{m.start()}c"
                end = f"1.0+{m.end()}c"
                self.text.tag_add(tag, start, end)


__all__ = ["SQLHighlighter"]
