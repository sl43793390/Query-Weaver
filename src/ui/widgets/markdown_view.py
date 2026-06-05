"""Lightweight Markdown-to-Tk renderer.

We don't aim for full CommonMark — just enough for chat messages
(headers, code fences, bold/italic, lists, paragraphs, links). Output
goes into a `tk.Text` widget with style tags.
"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import font as tkfont

_INLINE = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1", "bold"),
    (re.compile(r"\*(.+?)\*"),     r"\1", "italic"),
    (re.compile(r"`([^`]+)`"),      r"\1", "code"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r"\1 (\2)", "link"),
]


class MarkdownView(tk.Text):
    """A read-only `tk.Text` that renders Markdown."""

    # Color schemes — keyed by appearance mode ("dark" / "light").
    _PALETTES = {
        "dark": {
            "fg":          "#d4d4d4",
            "fg_bold":     "#ffffff",
            "bg":          "#1e1e1e",  # matches assistant bubble in dark mode
            "code_bg":     "#2b2b2b",  # inline `code` background
            "codeblock_bg": "#262626",  # ```fenced``` block background —
            # intentionally distinct from `bg` so the block is
            # visually obvious AND clickable as a unit.  The old
            # value (`#1e1e1e`, the same as the bubble) made the
            # SQL blend into the bubble background and the user's
            # mouse-drag selections "missed" because there was no
            # visible region to land on.
            "code_fg":     "#ce9178",
            "heading":     "#9cdcfe",
            "link":        "#569cd6",
            "sel_bg":      "#264f78",  # dark-mode selection
            "sel_fg":      "#ffffff",
        },
        "light": {
            "fg":          "#1a1a1a",
            "fg_bold":     "#000000",
            "bg":          "#f5f5f5",  # matches assistant bubble in light mode
            "code_bg":     "#ececec",
            "codeblock_bg": "#e4e4e4",
            "code_fg":     "#a31515",
            "heading":     "#0451a5",
            "link":        "#0066cc",
            "sel_bg":      "#0078d7",  # light-mode selection
            "sel_fg":      "#ffffff",
        },
    }

    def __init__(self, master=None, mode: str = "dark", **kwargs):
        self._mode = mode if mode in self._PALETTES else "dark"
        p = self._PALETTES[self._mode]
        kwargs.setdefault("foreground", p["fg"])
        kwargs.setdefault("insertbackground", p["fg"])
        kwargs.setdefault("background", p["bg"])
        # Configure selection colors up-front so dragging the mouse
        # over a code block actually shows the user what they
        # highlighted — without these, Tk falls back to the
        # system default, which is nearly invisible against the
        # dark code-block background.
        kwargs.setdefault("selectbackground", p["sel_bg"])
        kwargs.setdefault("selectforeground", p["sel_fg"])
        super().__init__(master, wrap="word", **kwargs)
        self._refresh_tags()

    def _refresh_tags(self) -> None:
        """Re-configure all tags for the current mode."""
        p = self._PALETTES[self._mode]
        base = tkfont.nametofont("TkTextFont")
        bold = base.copy(); bold.configure(weight="bold")
        italic = base.copy(); italic.configure(slant="italic")
        code = tkfont.nametofont("TkFixedFont")
        h1 = base.copy(); h1.configure(size=base.actual("size") + 6, weight="bold")
        h2 = base.copy(); h2.configure(size=base.actual("size") + 4, weight="bold")
        h3 = base.copy(); h2.configure(size=base.actual("size") + 2, weight="bold")
        # Background must follow the palette so it matches the bubble.
        # The selection colors are also re-applied here so they
        # update on theme toggle; otherwise an old selection drawn
        # in light mode would stay in light colors after a switch
        # to dark mode.
        try:
            self.configure(background=p["bg"], foreground=p["fg"],
                           insertbackground=p["fg"],
                           selectbackground=p["sel_bg"],
                           selectforeground=p["sel_fg"])
        except tk.TclError:
            pass
        self.tag_configure("default", foreground=p["fg"])
        self.tag_configure("h1", font=h1, foreground=p["heading"], spacing1=6, spacing3=4)
        self.tag_configure("h2", font=h2, foreground=p["heading"], spacing1=4, spacing3=2)
        self.tag_configure("h3", font=h3, foreground=p["heading"], spacing1=2)
        self.tag_configure("bold", font=bold, foreground=p["fg_bold"])
        self.tag_configure("italic", font=italic, foreground=p["fg"])
        self.tag_configure("code", font=code, background=p["code_bg"], foreground=p["code_fg"])
        # Code block (``` fenced ```) — use a distinct background
        # colour (slightly darker than the bubble in dark mode,
        # slightly lighter in light mode) so the block is both
        # visually obvious and has a clickable rectangular region.
        # lmargin1/2 are kept small (4) so the SQL isn't shifted
        # so far right that it appears to start outside the bubble.
        self.tag_configure("codeblock", font=code,
                           background=p["codeblock_bg"], foreground=p["fg"],
                           lmargin1=4, lmargin2=4,
                           rmargin=4,
                           spacing1=4, spacing3=4)
        self.tag_configure("bullet", lmargin1=16, lmargin2=24, foreground=p["fg"])
        self.tag_configure("link", foreground=p["link"], underline=True)
        # Keep the text widget in `state="normal"` so the user can
        # mouse-select and Ctrl+C to copy rendered messages.  We
        # intercept any <Key> that would mutate the buffer (see
        # `_block_keypress`); the widget is effectively read-only for
        # editing purposes.  The old `state="disabled"` was simpler
        # but it also killed selection, which made the chat
        # essentially un-quotable.
        self.configure(state="normal")
        self.bind("<Key>", self._block_keypress)
        # Block the virtual edit events that don't go through <Key>
        # (e.g. paste from a context menu, cut, delete).
        self.bind("<<Cut>>",    lambda _e: "break")
        self.bind("<<Paste>>",  lambda _e: "break")
        self.bind("<<Clear>>",  lambda _e: "break")
        self.bind("<<Undo>>",   lambda _e: "break")
        self.bind("<<Redo>>",   lambda _e: "break")

    def _block_keypress(self, event) -> str:
        """Allow only non-mutating keys (navigation, copy, select-all).

        Returning "break" from <Key> prevents the default Text
        behaviour (insert, delete).  We still let through:
          * arrows / Home / End / PgUp / PgDn / Tab / Esc
          * Shift / Ctrl / Alt (modifier keys)
          * Ctrl+C / Ctrl+Insert — copy
          * Ctrl+A — select all
        All other printable / delete / backspace events are blocked.
        """
        state = int(getattr(event, "state", 0) or 0)
        ctrl = bool(state & 0x4)  # Tk's ControlMask bit
        sym = (event.keysym or "").lower()
        nav = {
            "left", "right", "up", "down",
            "home", "end", "prior", "next",
            "tab", "escape",
            "shift_l", "shift_r",
            "control_l", "control_r",
            "alt_l", "alt_r", "meta_l", "meta_r",
            "caps_lock", "num_lock", "scroll_lock",
        }
        if sym in nav:
            return None  # let it through
        if ctrl and sym in ("c", "a", "insert"):
            return None  # copy / select-all
        return "break"

    def set_mode(self, mode: str) -> None:
        """Switch the color palette and re-render the current content."""
        if mode not in self._PALETTES or mode == self._mode:
            return
        self._mode = mode
        self._refresh_tags()
        # Force a re-render so the new colors actually show up — the
        # disabled `tk.Text` keeps the old text in storage, so re-insert
        # the latest markdown by re-asking the caller.
        if hasattr(self, "_last_md"):
            self.set_markdown(self._last_md)

    # ------------------------------------------------------------------ #
    def set_markdown(self, text: str) -> None:
        self._last_md = text or ""
        self.configure(state="normal")
        self.delete("1.0", "end")

        in_code = False
        code_buffer: list[str] = []

        for line in (text or "").splitlines():
            if line.strip().startswith("```"):
                if in_code:
                    self.insert("end", "\n".join(code_buffer) + "\n", "codeblock")
                    code_buffer = []
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_buffer.append(line)
                continue

            stripped = line.rstrip()
            if stripped.startswith("### "):
                self._insert_inline(stripped[4:] + "\n", base_tag="h3")
            elif stripped.startswith("## "):
                self._insert_inline(stripped[3:] + "\n", base_tag="h2")
            elif stripped.startswith("# "):
                self._insert_inline(stripped[2:] + "\n", base_tag="h1")
            elif stripped.startswith(("- ", "* ")):
                self.insert("end", "•  ", "bullet")
                self._insert_inline(stripped[2:] + "\n", base_tag="bullet")
            elif stripped == "":
                self.insert("end", "\n")
            else:
                self._insert_inline(stripped + "\n")

        if code_buffer:
            self.insert("end", "\n".join(code_buffer) + "\n", "codeblock")

        # Stay in `state="normal"` so the user can select/copy; the
        # <Key> binding in `_refresh_tags` blocks any edit attempts.
        self.configure(state="normal")

    # ------------------------------------------------------------------ #
    def _insert_inline(self, line: str, base_tag: str = "") -> None:
        # Render inline patterns using tag toggles. We use `search` + spans.
        cursor = 0
        s = line
        events: list[tuple[int, int, str]] = []

        for pat, _, tag in _INLINE:
            for m in pat.finditer(s):
                events.append((m.start(), m.end(), tag))

        events.sort()
        # Filter overlapping events (first one wins).
        pruned: list[tuple[int, int, str]] = []
        last_end = -1
        for start, end, tag in events:
            if start < last_end:
                continue
            pruned.append((start, end, tag))
            last_end = end

        for start, end, tag in pruned:
            if start > cursor:
                self.insert("end", s[cursor:start], base_tag)
            self.insert("end", s[start:end], (base_tag, tag) if base_tag else tag)
            cursor = end
        if cursor < len(s):
            self.insert("end", s[cursor:], base_tag)


__all__ = ["MarkdownView"]
