"""Main application window — wires sidebar + chat panel together."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from config.settings import APP_NAME, APP_VERSION, DEFAULT_THEME, WINDOW_DEFAULT_SIZE
from src.core.config import get_value, set_value
from src.database.connector import ConnectionProfile
from src.ui.chat_panel import ChatPanel
from src.ui.settings_dialog import ConnectionDialog, SettingsDialog
from src.ui.sidebar import Sidebar


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        # Centre the window on the primary monitor instead of letting
        # the window manager pick a default position (which on most
        # platforms is just below the taskbar / top-left corner, so
        # the user has to drag the window to use it).  We parse the
        # "WxH" out of WINDOW_DEFAULT_SIZE and compute the top-left
        # coordinates from the screen dimensions.  `update_idletasks`
        # forces winfo_screen{width,height} to be valid before we read
        # them — without it they can return 1×1 on a freshly-created
        # window on some platforms.
        self._center_window(WINDOW_DEFAULT_SIZE)

        theme = get_value("ui.theme", DEFAULT_THEME) or DEFAULT_THEME
        if theme not in ("light", "dark"):
            theme = DEFAULT_THEME
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

        # Layout: sidebar | chat panel
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        # Row 0 (toolbar) is a fixed-height strip — it must NOT
        # have a weight, otherwise any vertical slack in the window
        # gets absorbed by row 0 and the toolbar grows downward,
        # leaving a blank gap between the buttons and the
        # connections panel / tabsheet below.  This bug only showed
        # up after a theme toggle because `ctk.set_appearance_mode`
        # re-runs a full layout pass; on the very first launch the
        # window was already at a height where the 34 px toolbar
        # happened to fill row 0 exactly, so the gap was invisible.
        # Row 1 (the actual content area) keeps the weight=1.
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(2, weight=0)

        # Top toolbar — tight height that just fits the buttons, not
        # the 40+px that CTk's defaults leave.  The previous version
        # wasted ~15 px of vertical space which made the rest of the
        # window feel cramped, especially on 1366x768 laptops, and
        # the height also silently grew back to ~41 px after every
        # theme toggle (CTk re-runs the layout pass and the pack
        # children re-pushed the parent taller).
        #
        # Why a plain `tk.Frame` instead of a `ctk.CTkFrame`:
        # `ctk.CTkFrame` carries an internal `tk.Canvas` for the
        # rounded-corner background.  That canvas has its own
        # requested size (≥ 40 px on this CTk version) and ignores
        # the parent's `height=` hint — and worse, `pack_propagate`
        # and `grid_propagate` only mask the issue at the parent
        # level; the grid manager in MainWindow still asks for the
        # widget's `winfo_reqheight`, which is 43 px.  A plain
        # `tk.Frame` honours the explicit `height=` and stays at
        # exactly the height we ask for, on every theme.
        #
        # Children are added with `.pack(side="left"/"right")` on
        # a *nested* `tk.Frame` (`right_bar`) so they don't push
        # the toolbar taller.  An earlier attempt used `.place()`
        # with pixel x-offsets, but `_layout_right_buttons` ran
        # before the toolbar had a real width and silently
        # short-circuited, leaving the buttons parked at (0, 0)
        # behind the title.  The two-frame approach below is
        # self-sizing: pack figures out the width from the
        # children, and `pack_propagate(False)` on the outer
        # toolbar keeps the height pinned at 34.
        TOOLBAR_HEIGHT = 34
        toolbar = tk.Frame(self, height=TOOLBAR_HEIGHT, bd=0, highlightthickness=0)
        self._toolbar = toolbar
        # `_toolbar_bg` is updated whenever the theme changes (see
        # `_toggle_theme`) so the toolbar blends into the CTk
        # window background.  These are CTk's default window bg
        # colours — matching the value `ctk.CTk().cget("fg_color")`
        # would return in each mode.
        self._toolbar_bg = {
            "dark":  "#1a1a1a",  # matches CTk's dark window bg
            "light": "#e6e6e6",  # matches CTk's light window bg
        }[theme]
        toolbar.configure(bg=self._toolbar_bg)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="new",
                     padx=8, pady=(6, 0))
        toolbar.grid_propagate(False)
        toolbar.pack_propagate(False)
        toolbar.configure(height=TOOLBAR_HEIGHT)

        # Title — left side.  Packed with `side="left"` so it
        # lives on the left half of the toolbar.
        ctk.CTkLabel(toolbar, text=APP_NAME,
                     font=("", 14, "bold"),
                     fg_color="transparent"
                     ).pack(side="left", padx=(12, 4), pady=2)

        # The three right-side buttons are packed DIRECTLY into
        # the toolbar (no inner "right_bar" frame) with
        # `side="right"`.  An earlier attempt funnelled them
        # through a nested `tk.Frame`, but Tk's `pack_propagate`
        # flag is only consulted BEFORE the children are packed —
        # setting it after the buttons are already in a 1×1 frame
        # leaves them parked at (0, 0) with 1 px width, exactly
        # the "invisible buttons" bug the user reported.  Packing
        # the buttons straight into the toolbar sidesteps that
        # whole class of bugs.  The outer toolbar's
        # `pack_propagate(False)` (set above) is what keeps the
        # CTk buttons' 38 px natural height from re-pushing the
        # toolbar to 41 px.
        #
        # Pack order note: when packing multiple `side="right"`
        # children, the FIRST packed child ends up at the
        # rightmost position.  So the code reads "theme, execute,
        # settings" but the visual order is "settings, execute,
        # theme" (left → right), which is what the user expects.
        self._current_theme = theme
        self._theme_button = ctk.CTkButton(
            toolbar, text=self._theme_button_label(),
            width=90, height=TOOLBAR_HEIGHT - 8,
            command=self._toggle_theme,
        )
        btn_execute = ctk.CTkButton(
            toolbar, text="▶ Execute Last SQL",
            width=180, height=TOOLBAR_HEIGHT - 8,
            command=self._execute_last,
        )
        btn_settings = ctk.CTkButton(
            toolbar, text="⚙ Settings",
            width=110, height=TOOLBAR_HEIGHT - 8,
            command=self._open_settings,
        )
        # Pack in this order so the *first* one (`theme`) ends up
        # at the rightmost edge.
        self._theme_button.pack(side="right", padx=4, pady=2)
        btn_execute.pack(side="right", padx=4, pady=2)
        btn_settings.pack(side="right", padx=4, pady=2)

        # Status bar (must exist before the sidebar can call back into it)
        self.status_var = ctk.StringVar(value="Ready")
        status = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w")
        status.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 6))

        # Chat panel (must exist before the sidebar can call back into it)
        self.chat_panel = ChatPanel(self, on_status=self._set_status)
        self.chat_panel.grid(row=1, column=1, sticky="nsew")
        # Prime the chat panel's appearance state.  ChatPanel.__init__
        # hard-codes `_appearance_mode = "dark"`, which then leaks into
        # every `MarkdownView(mode="dark", ...)` it creates — leaving
        # the message content area with dark-on-light or dark-on-dark
        # colours on a light-theme first launch.  `apply_theme` re-tints
        # the sash, the history frame, the result viewer, and (for
        # bubbles added *after* this call) caches the correct mode so
        # subsequent MarkdownView instances pick the right palette.
        self.chat_panel.apply_theme(theme)

        # Sidebar (last, so its on_connection_changed callback is safe)
        self.sidebar = Sidebar(
            self,
            on_connection_changed=self._on_connection_changed,
            on_new_connection=self._open_new_connection,
            on_schema_focus=self._on_schema_focus,
        )
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        # Prime the sidebar's `tk.Listbox` (and the nested SchemaTree)
        # with the *current* theme.  The Sidebar's `__init__` still
        # hard-codes `_current_mode = "dark"` for the initial Listbox
        # config, so without this priming call the connections frame
        # would render with dark-mode colours on a light-theme first
        # launch (and stay that way until the user toggled the theme
        # once).  `apply_theme` is the single source of truth for
        # re-styling tk.Listbox / ttk.Treeview, so we just call it
        # here with the same `theme` value `__init__` used to set
        # `ctk.set_appearance_mode` on the first line.
        self.sidebar.apply_theme(theme)

        self.grid_rowconfigure(1, weight=1)

    # ------------------------------------------------------------------ #
    def _center_window(self, size: str) -> None:
        """Apply `size` ("WxH" or "WxH±X±Y") and centre the window on
        the primary monitor.  Computes the top-left X/Y from
        `winfo_screen{width,height}` so the title bar sits in the
        middle of the visible desktop, not wherever the window
        manager happens to drop it.

        The `max(0, …)` clamp handles the edge case where the
        window is larger than the screen (e.g. user picked a 4K
        resolution but the constant still says 1920×1080 and a
        future bump goes the other way) — we'd rather push the
        window flush to the top-left than request a negative
        coordinate that the WM would silently clamp anyway.
        """
        import re
        m = re.match(r"^(\d+)x(\d+)$", size.strip())
        if not m:
            # Fallback: let Tk pick a position itself.
            self.geometry(size)
            return
        win_w, win_h = int(m.group(1)), int(m.group(2))
        # update_idletasks ensures winfo_screen* are real numbers
        # (they can be 1x1 on a not-yet-mapped toplevel).
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - win_w) // 2)
        y = max(0, (screen_h - win_h) // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")

    # ------------------------------------------------------------------ #
    def _on_connection_changed(self, profile: ConnectionProfile | None) -> None:
        self.chat_panel.set_profile(profile)
        self._set_status(f"Connected: {profile.name}" if profile else "No connection")

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def _on_schema_focus(self, info) -> None:
        """Forward the user's schema-tree click to the chat panel so the
        next LLM call can use it as additional context."""
        self.chat_panel.set_schema_focus(info)

    def _open_new_connection(self, edit_id: int | None = None) -> None:
        """Open the connection dialog and refresh the sidebar after it closes."""
        dlg = ConnectionDialog(self, edit_id=edit_id)
        self.wait_window(dlg)         # blocks until the dialog is destroyed
        self.sidebar.refresh()

    def _open_settings(self) -> None:
        SettingsDialog(self)

    def _execute_last(self) -> None:
        self.chat_panel.execute_last_sql()

    # ------------------------------------------------------------------ #
    # Theme switching
    # ------------------------------------------------------------------ #
    def _theme_button_label(self) -> str:
        # Show the action the user is about to take.
        return "Light" if self._current_theme == "dark" else "Dark"

    def _toggle_theme(self) -> None:
        new = "light" if self._current_theme == "dark" else "dark"
        self._current_theme = new
        ctk.set_appearance_mode(new)
        # Persist so the next launch remembers the user's choice.
        try:
            set_value("ui.theme", new)
        except Exception:
            pass  # don't crash the UI on a settings write failure
        # Re-style the side panels that own their own ttk.Style or
        # raw tk widgets (Sidebar's Listbox + tree, ResultViewer inside
        # the chat panel) and the chat bubbles / markdown text.
        self.sidebar.apply_theme(new)
        self.chat_panel.apply_theme(new)
        self._theme_button.configure(text=self._theme_button_label())
        # The toolbar is a plain `tk.Frame` (not a CTk widget) so
        # `ctk.set_appearance_mode` doesn't re-paint it.  We have to
        # swap its background colour manually to match the new
        # window bg, otherwise it stays the previous theme's colour
        # while everything around it has changed.  See `__init__`
        # for why the toolbar isn't a `ctk.CTkFrame` in the first
        # place (the answer: the CTk one has an internal canvas
        # that ignores our `height=34` hint and would re-grow the
        # toolbar on every theme toggle).
        self._toolbar_bg = {
            "dark":  "#1a1a1a",
            "light": "#e6e6e6",
        }[new]
        try:
            self._toolbar.configure(bg=self._toolbar_bg)
        except (tk.TclError, AttributeError):
            pass
