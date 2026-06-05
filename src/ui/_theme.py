"""Color palettes for light / dark themes.

`customtkinter`'s built-in `set_appearance_mode` handles most CTk widgets
automatically, but raw Tk widgets (ttk.Treeview, tk.Listbox, tk.Text
inside MarkdownView) still use whatever hardcoded color we passed at
construction time. This module is the single source of truth for those
colors; widgets call `palette_for(mode)` to get the dict they need,
and `apply_ttk_style(style, mode)` to re-configure their ttk styles
when the user toggles the theme.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Literal

Mode = Literal["light", "dark"]


# --------------------------------------------------------------------- #
# Palettes — keep keys in sync with anything that needs a named color.
# --------------------------------------------------------------------- #
_PALETTES: Dict[str, Dict[str, str]] = {
    "dark": {
        # surfaces
        "surface":      "#2b2b2b",
        "surface_alt":  "#1e1e1e",
        "border":       "#3a3a3a",
        "fg":           "#d4d4d4",
        "fg_strong":    "#ffffff",
        "fg_muted":     "#888888",
        "selection":    "#3a7ebf",
        "selection_fg": "white",
        # code / markdown accents
        "code_bg":      "#2b2b2b",
        "code_fg":      "#ce9178",
        "heading":      "#9cdcfe",
        "link":         "#569cd6",
    },
    "light": {
        "surface":      "#ffffff",
        "surface_alt":  "#f5f5f5",
        "border":       "#d4d4d4",
        "fg":           "#1a1a1a",
        "fg_strong":    "#000000",
        "fg_muted":     "#666666",
        "selection":    "#3a7ebf",
        "selection_fg": "white",
        "code_bg":      "#ececec",
        "code_fg":      "#a31515",
        "heading":      "#0451a5",
        "link":         "#0066cc",
    },
}


def palette_for(mode: str) -> Dict[str, str]:
    """Return the color palette for the given appearance mode.

    Unknown modes silently fall back to dark — that matches the rest of
    the app's defensive default behavior.
    """
    return _PALETTES.get(mode, _PALETTES["dark"])


def current_mode() -> str:
    """Best-effort guess of the active mode by asking customtkinter.

    Wrapped in try/except because in unit tests we sometimes import this
    module before ctk is fully initialized.
    """
    try:
        import customtkinter as ctk
        m = ctk.get_appearance_mode()
        return "light" if m.lower().startswith("light") else "dark"
    except Exception:
        return "dark"


# --------------------------------------------------------------------- #
# ttk.Style helpers — re-style the named style for the new mode.
# --------------------------------------------------------------------- #
def apply_ttk_style(style: ttk.Style, style_name: str, mode: str,
                    *, with_headings: bool = False) -> None:
    """Re-configure a ttk.Treeview style for the given mode.

    `style_name` is the style we previously passed to `ttk.Treeview(...,
    style=...)`, e.g. "Schema.Treeview" or "Result.Treeview".

    `with_headings` is True for the result viewer because the table
    has column headings; we re-style those too so the header row
    doesn't stay dark in light mode.
    """
    p = palette_for(mode)
    try:
        style.configure(
            style_name,
            background=p["surface"],
            fieldbackground=p["surface"],
            foreground=p["fg"],
            bordercolor=p["border"],
            rowheight=22,
            borderwidth=1,
        )
        style.map(
            style_name,
            background=[("selected", p["selection"])],
            foreground=[("selected", p["selection_fg"])],
        )
    except tk.TclError:
        # `style.theme_use("clam")` may not have been called yet.
        pass

    if with_headings:
        try:
            style.configure(
                f"{style_name}.Heading",
                background=p["surface_alt"],
                foreground=p["fg_strong"],
                relief="flat",
            )
        except tk.TclError:
            pass


def apply_scrollbar_style(style: ttk.Style, mode: str) -> None:
    """Re-style ttk.Scrollbar for the given mode.

    ttk's default scrollbar is the chunky Windows-95-ish one; we
    theme it to look more like CustomTkinter's flat slim scrollbar.
    Called by both the chat panel (history scrollbar) and the result
    viewer so they look the same.
    """
    p = palette_for(mode)
    try:
        style.configure(
            "Vertical.TScrollbar",
            background=p["surface_alt"],
            troughcolor=p["surface"],
            bordercolor=p["surface"],
            arrowcolor=p["fg_muted"],
            gripcount=0,
            relief="flat",
            borderwidth=0,
            width=10,
        )
        style.map(
            "Vertical.TScrollbar",
            background=[("active", p["selection"]), ("pressed", p["selection"])],
            arrowcolor=[("active", p["selection_fg"])],
        )
        style.configure(
            "Horizontal.TScrollbar",
            background=p["surface_alt"],
            troughcolor=p["surface"],
            bordercolor=p["surface"],
            arrowcolor=p["fg_muted"],
            gripcount=0,
            relief="flat",
            borderwidth=0,
            height=10,
        )
        style.map(
            "Horizontal.TScrollbar",
            background=[("active", p["selection"]), ("pressed", p["selection"])],
            arrowcolor=[("active", p["selection_fg"])],
        )
    except tk.TclError:
        pass


def row_colors(mode: str) -> tuple[str, str]:
    """Return (odd_row, even_row) bg colors for zebra-striping a Treeview."""
    p = palette_for(mode)
    # Alternating row tints derived from the surface color.
    return p["surface"], p["surface_alt"]


__all__ = ["palette_for", "current_mode", "apply_ttk_style", "apply_scrollbar_style", "row_colors"]
