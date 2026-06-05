"""Right-side chat panel: user / assistant messages, SQL extraction, execution."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

from config.prompts import system_prompt_for
from config.settings import NOSQL_DB_TYPES, SQL_DB_TYPES
from src.core.logger import logger
from src.database.adapters.base import QueryResult
from src.database.connector import (
    ConnectionProfile,
    execute_on_connection,
)
from src.database.schema_browser import get_schema
from src.llm.base import LLMMessage
from src.llm.manager import get_manager
from src.security.sql_guard import analyze
from src.ui.result_viewer import ResultViewer
from src.ui.widgets.markdown_view import MarkdownView
from src.ui.widgets.sql_highlight import SQLHighlighter
from src.utils.helpers import extract_code_blocks


class ChatPanel(ctk.CTkFrame):
    """Chat-style conversation + result viewer + input box."""

    def __init__(
        self,
        master,
        *,
        on_status: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(master, corner_radius=0)
        self.on_status = on_status
        self._profile: Optional[ConnectionProfile] = None
        self._messages: list[LLMMessage] = []
        self._busy = False
        # Schema-tree focus: None = no focus, or a dict from
        # `SchemaTree._emit_selection`. Stored here so we can inject
        # it into the next LLM call's system prompt.
        self._schema_focus: Optional[dict] = None
        # Current appearance mode, used to pick light/dark colors.
        self._appearance_mode: str = "dark"

        self.grid_columnconfigure(0, weight=1)
        # row 0 = sash (tabs on top, result on bottom);
        # row 1 = schema-focus badge below the sash.
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # ---- Vertical sash between tabview and result viewer ----
        # tk.PanedWindow lets the user drag the divider to resize the
        # two panes. The top pane (tabview) gets the bigger share.
        # The initial color comes from the palette for the current
        # appearance mode (dark by default — see config.settings).
        from src.ui._theme import palette_for
        self.sash = tk.PanedWindow(
            self, orient="vertical", sashwidth=6, sashrelief="flat",
            background=palette_for("dark")["surface"],
            bd=0, borderwidth=0, showhandle=False,
        )
        self.sash.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))

        # ---- Tabview (top pane) ----
        # Two tabs:
        #   * "Chat"        — natural-language Q&A, renders assistant
        #                     bubbles; "Execute Last SQL" picks the last
        #                     ```sql block from the conversation.
        #   * "SQL Editor"  — empty textbox for the user to paste or
        #                     hand-write SQL and run it against the
        #                     active connection.  Includes a "Paste
        #                     last" helper that drops in the most
        #                     recent ```sql block from chat.
        self.tabs = ctk.CTkTabview(self.sash)
        self.sash.add(self.tabs, minsize=120, stretch="always")

        # === Chat tab ===
        chat_tab = self.tabs.add("Chat")
        chat_tab.grid_columnconfigure(0, weight=1)
        chat_tab.grid_rowconfigure(0, weight=1)   # history grows
        chat_tab.grid_rowconfigure(1, weight=0)   # input bar fixed
        self.history_frame = ctk.CTkScrollableFrame(
            chat_tab, label_text="Conversation"
        )
        self.history_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._history_widgets: list[ctk.CTkFrame] = []

        input_bar = ctk.CTkFrame(chat_tab, fg_color="transparent")
        input_bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        input_bar.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkTextbox(input_bar, height=80)
        self.input_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.input_box.bind("<Control-Return>", lambda _e: self._on_send())
        ctk.CTkButton(input_bar, text="Send  (Ctrl+Enter)",
                      command=self._on_send).grid(row=0, column=1)
        ctk.CTkButton(input_bar, text="🗑 Clear", width=80,
                      fg_color="#7a3535", hover_color="#9a4545",
                      command=self.clear_conversation).grid(
            row=0, column=2, padx=(8, 0))

        # === SQL Editor tab ===
        editor_tab = self.tabs.add("SQL Editor")
        editor_tab.grid_columnconfigure(0, weight=1)
        editor_tab.grid_rowconfigure(0, weight=1)   # textbox grows
        editor_tab.grid_rowconfigure(1, weight=0)   # exec bar fixed
        # `undo=True` enables an internal undo stack so the user can
        # press Ctrl+Z to recover a paste (or anything else).  Default
        # for CTkTextbox is False, which is a real footgun for an
        # editor: paste something long, then accidentally type, and
        # the whole paste is gone with no way back.
        self.sql_editor = ctk.CTkTextbox(
            editor_tab, font=("Consolas", 11), height=200,
            # Slight inset so the textbox doesn't feel glued to the edge.
            border_width=2,
            undo=True,
            maxundo=-1,  # unlimited
        )
        self.sql_editor.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        # Ctrl+Enter inside the SQL editor runs the query.
        self.sql_editor.bind("<Control-Return>", lambda _e: self._on_editor_run())

        editor_bar = ctk.CTkFrame(editor_tab, fg_color="transparent")
        editor_bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 4))
        editor_bar.grid_columnconfigure(0, weight=1)
        # Left side: paste helpers.
        ctk.CTkButton(editor_bar, text="📋 Paste last", width=130,
                      command=self._on_editor_paste_last).grid(row=0, column=0, sticky="w")
        # Right side: clear + run.
        ctk.CTkButton(editor_bar, text="Clear", width=80, fg_color="#7a3535",
                      hover_color="#9a4545",
                      command=self._on_editor_clear).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(editor_bar, text="▶ Execute  (Ctrl+Enter)", width=200,
                      command=self._on_editor_run).grid(row=0, column=1, sticky="e")

        # ---- Result viewer (bottom pane) ----
        self.result_viewer = ResultViewer(self.sash)
        self.sash.add(self.result_viewer, minsize=80, stretch="never")

        # ---- Schema-focus badge (row 1) ----
        # Shows what the user clicked in the schema tree. Empty by
        # default; populated by `set_schema_focus`. Visible as a thin
        # status line below the sash.
        self._focus_badge = ctk.CTkLabel(
            self, text="", anchor="w",
            font=("", 12, "italic"),
            text_color=("#1a4d80", "#7ab4ff"),
        )
        self._focus_badge.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 0))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def clear_conversation(self) -> None:
        """Drop all in-memory chat history and reset the result viewer.

        The active database connection is NOT touched — the user can
        keep querying, just without seeing the previous LLM thread.
        """
        self._messages = []
        for w in self._history_widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._history_widgets.clear()
        # Re-show a fresh empty-state hint so the user knows the chat
        # was cleared on purpose, not by a bug.
        if self._profile is not None:
            self._add_assistant(
                f"_Conversation cleared. Still connected to **{self._profile.name}**._",
                role="system",
            )
        self.result_viewer.show_message("No result yet")

    # ------------------------------------------------------------------ #
    def set_schema_focus(self, info: Optional[dict]) -> None:
        """Record what the user clicked in the schema tree.

        `info` comes from `SchemaTree._emit_selection`; one of:
            {"kind": "database", "name": "...", "database": "..."}
            {"kind": "table",    "name": "...", "database": "...", "table": "..."}
            {"kind": "column",   "name": "...", "database": "...", "table": "...", ...}
            None  (user clicked away / cleared the tree)

        The next time the LLM is called we append a "Current focus: …"
        line to the system prompt so the model doesn't have to ask
        "which table did you mean?" again.
        """
        self._schema_focus = info
        if info is None:
            self._focus_badge.configure(text="")
            return
        kind = info.get("kind")
        if kind == "database":
            self._focus_badge.configure(
                text=f"📁 Database focus: **{info['name']}**  "
                     f"_(will be sent with your next question)_"
            )
        elif kind == "table":
            self._focus_badge.configure(
                text=f"📄 Table focus: **{info['database']}.{info['name']}**  "
                     f"_(will be sent with your next question)_"
            )
        elif kind == "column":
            dt = info.get("data_type", "")
            nl = "" if info.get("nullable", True) else " NOT NULL"
            self._focus_badge.configure(
                text=f"🔎 Column focus: **{info['database']}.{info['table']}.{info['name']}** "
                     f"({dt}{nl})  "
                     f"_(will be sent with your next question)_"
            )
        else:
            self._focus_badge.configure(text="")

    def apply_theme(self, mode: str) -> None:
        """Re-style every existing bubble + markdown view for the new
        appearance mode. Called by MainWindow when the user toggles
        light/dark theme."""
        if mode not in ("light", "dark"):
            return
        self._appearance_mode = mode
        for bubble in self._history_widgets:
            # `bubble` is a CTkFrame; look up role from a private attr
            # we stashed on it in `_build_message_bubble`.
            role = getattr(bubble, "_role", "assistant")
            try:
                bubble.configure(
                    fg_color=self._BUBBLE_COLORS[role],
                    border_color=self._BUBBLE_BORDER[role],
                )
            except tk.TclError:
                continue
            for child in bubble.winfo_children():
                if isinstance(child, MarkdownView):
                    child.set_mode(mode)
        # The history frame itself needs its background updated too.
        try:
            self.history_frame.configure(
                fg_color=("#f5f5f5", "#1e1e1e")
            )
        except tk.TclError:
            pass
        # PanedWindow (the sash) and the sash's panes were constructed
        # with hardcoded dark colors — re-color them from the palette
        # so the divider doesn't show up as a dark stripe in light mode.
        from src.ui._theme import palette_for
        p = palette_for(mode)
        try:
            self.sash.configure(background=p["surface"], sashpad=0, sashwidth=6)
        except tk.TclError:
            pass
        # The result viewer is a ttk.Treeview with its own ttk.Style;
        # apply_theme cascades through its own widgets.
        try:
            self.result_viewer.apply_theme(mode)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ #
    def set_profile(self, profile: Optional[ConnectionProfile]) -> None:
        """Switch active database and reset conversation."""
        self._profile = profile
        self._messages = []
        for w in self._history_widgets:
            w.destroy()
        self._history_widgets.clear()
        if profile is None:
            self._add_assistant(
                "👈  Select or create a connection in the left panel to start.",
                role="system",
            )
        else:
            self._add_assistant(
                f"Connected to **{profile.name}** ({profile.db_type}). "
                f"Ask me anything in natural language.",
                role="system",
            )
        self.result_viewer.show_message("No result yet")

    # ------------------------------------------------------------------ #
    def _add_assistant(self, text: str, *, role: str = "assistant") -> ctk.CTkFrame:
        w = self._build_message_bubble(text, role=role)
        self._history_widgets.append(w)
        self._scroll_to_bottom()
        return w

    def _add_user(self, text: str) -> ctk.CTkFrame:
        w = self._build_message_bubble(text, role="user")
        self._history_widgets.append(w)
        self._scroll_to_bottom()
        return w

    # ------------------------------------------------------------------ #
    # Color palettes — keys: (light_mode, dark_mode) tuples that
    # CustomTkinter picks from based on `appearance_mode`. We define
    # them up here so `apply_theme()` can re-use them later.
    # ------------------------------------------------------------------ #
    _BUBBLE_COLORS = {
        "user":      ("#dce8f5", "#1f2c3a"),
        "assistant": ("#e8e8e8", "#2b2b2b"),
        "system":    ("#f0f0f0", "#1a1a1a"),
    }
    _BUBBLE_BORDER = {
        "user":      ("#a8c5e0", "#3a5070"),
        "assistant": ("#c8c8c8", "#3a3a3a"),
        "system":    ("#dddddd", "#2a2a2a"),
    }
    _LABEL_COLORS = {
        "user":      ("#1a4d80", "#7ab4ff"),
        "assistant": ("#1a1a1a", "#d4d4d4"),
        "system":    ("#666666", "#888888"),
    }

    def _build_message_bubble(self, text: str, *, role: str) -> ctk.CTkFrame:
        mode = getattr(self, "_appearance_mode", "dark")
        bubble = ctk.CTkFrame(
            self.history_frame,
            fg_color=self._BUBBLE_COLORS[role],
            border_width=1,
            border_color=self._BUBBLE_BORDER[role],
            corner_radius=14,
        )
        bubble._role = role  # stashed so apply_theme() can re-style
        bubble.grid(sticky="ew", padx=4, pady=4)
        bubble.grid_columnconfigure(0, weight=1)
        # Row 0 = label (fixed), row 1 = MarkdownView (grows with content).
        bubble.grid_rowconfigure(0, weight=0)
        bubble.grid_rowconfigure(1, weight=0)

        label = ctk.CTkLabel(
            bubble,
            text=("🧑 You" if role == "user" else "🤖 Assistant" if role == "assistant" else "ℹ System"),
            anchor="w", font=("", 12, "bold"),
            text_color=self._LABEL_COLORS[role],
        )
        label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))

        md = MarkdownView(bubble, mode=mode, bd=0, highlightthickness=0)
        md.grid(row=1, column=0, sticky="nsew", padx=12, pady=(2, 10))
        md.set_markdown(text)
        self._fit_markdown(md)
        return bubble

    def _fit_markdown(self, md: MarkdownView) -> None:
        """Resize a MarkdownView to fit its rendered content.

        The text widget's `height` is the visible-line count; the only
        reliable way to get that after `wrap="word"` is `index('end-1c')`
        once the widget has had a chance to lay out.
        """
        try:
            md.update_idletasks()
            last = md.index("end-1c")
            visual_lines = max(1, int(last.split(".")[0]))
            # +2 for top/bottom padding inside the bubble.
            md.configure(height=min(800, visual_lines + 2))
        except tk.TclError:
            pass

    def _scroll_to_bottom(self) -> None:
        """Scroll the conversation area to the very bottom.

        CustomTkinter's CTkScrollableFrame wraps a Tk Canvas internally;
        we want THAT canvas (the one holding the bubble list), not any
        auxiliary canvas used elsewhere in the tree (e.g. CTkTabview
        keeps an internal canvas for rendering tab labels, which a
        naive walk would mistake for our scroll target).  Schedule
        the actual scroll via `after_idle` so the bubble has time to
        be measured.
        """
        def _do_scroll():
            try:
                self.update_idletasks()
                canvas = self._get_scrollable_canvas(self.history_frame)
                if canvas is not None:
                    # Force the scrollregion to recompute — CTk doesn't
                    # always refresh it after we grid() a new bubble.
                    canvas.configure(scrollregion=canvas.bbox("all"))
                    canvas.yview_moveto(1.0)
            except tk.TclError:
                pass
        # Defer until pending idle tasks (layout, scrolling) complete.
        self.after_idle(_do_scroll)

    def _get_scrollable_canvas(self, widget):
        """Find the tk.Canvas that actually scrolls our conversation.

        CTk's stable internal name is `_parent_canvas` on the
        CTkScrollableFrame, so we prefer that.  As a fallback (e.g.
        for a future CTk version that renames the attribute) we walk
        the descendants but reject canvases that don't have a
        `create_window` item — that filter rules out cosmetic canvases
        like the one CTkTabview uses to paint its tab strip.
        """
        try:
            priv = getattr(widget, "_parent_canvas", None)
            if priv is not None:
                return priv
        except Exception:
            pass
        return self._find_scrollable_canvas(widget)

    def _find_scrollable_canvas(self, widget):
        """Walk descendants of `widget` to find a real scrollable canvas.

        A scrollable CTk canvas always has at least one window item
        (`create_window` is how CTk places the inner frame); cosmetic
        canvases (CTkTabview tab strip, CTkOptionMenu, CTkCheckBox)
        have none, so we use that as the discriminator.
        """
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return None
        for child in children:
            if isinstance(child, tk.Canvas):
                try:
                    if child.find_withtag("inner_frame") or any(
                        child.type(i) == "window" for i in child.find_all()
                    ):
                        return child
                except tk.TclError:
                    pass
            found = self._find_scrollable_canvas(child)
            if found is not None:
                return found
        return None

    # ------------------------------------------------------------------ #
    def _on_send(self) -> None:
        if self._busy:
            return
        text = self.input_box.get("1.0", "end-1c").strip()
        if not text:
            return
        if self._profile is None:
            messagebox.showwarning("No connection", "Please select a database connection first.")
            return

        self.input_box.delete("1.0", "end")
        self._add_user(text)
        self._messages.append(LLMMessage("user", text))
        self._busy = True
        # Tk is not thread-safe, so we must create the placeholder on the
        # main thread BEFORE the background thread starts doing anything.
        self.after(0, self._start_llm_call)

    def _start_llm_call(self) -> None:
        """Create the spinner bubble on the main thread, then hand control
        to a background thread for the blocking LLM call. The spinner
        is animated by `self.after` so it runs on the UI thread."""
        self._placeholder = self._add_assistant(self._spinner_text(0))
        self._spinner_after = self.after(120, self._tick_spinner)
        if self.on_status:
            self.on_status("Contacting LLM…")
        threading.Thread(
            target=self._call_llm, args=(self._placeholder,), daemon=True
        ).start()

    _SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def _spinner_text(self, i: int) -> str:
        return f"_{self._SPINNER_FRAMES[i % len(self._SPINNER_FRAMES)]}  Thinking…_"

    def _tick_spinner(self) -> None:
        """Advance the spinner animation. Stops itself once the LLM call
        has finished (i.e. the placeholder has been replaced with a real
        response)."""
        if not self._busy or not hasattr(self, "_placeholder"):
            return
        # The placeholder is still showing the spinner; advance it.
        if self._placeholder in self._history_widgets:
            i = getattr(self, "_spinner_i", 0)
            self._spinner_i = i + 1
            self._update_last_assistant(self._placeholder, self._spinner_text(i))
            self._spinner_after = self.after(120, self._tick_spinner)

    # ------------------------------------------------------------------ #
    def _build_messages(self) -> list[LLMMessage]:
        if self._profile is None:
            return list(self._messages)
        system = system_prompt_for(self._profile.db_type)
        if self._profile.db_type in SQL_DB_TYPES:
            try:
                schema = get_schema(self._profile)
                system += "\n\nDatabase schema (use only these objects):\n"
                system += schema.to_compact_text()
            except Exception:
                logger.exception("Failed to load schema for prompt")
        # Inject the schema-tree focus (if any) so the model knows
        # exactly which table / column the user is asking about.
        focus = getattr(self, "_schema_focus", None)
        if focus:
            system += "\n\nThe user has selected this in the schema tree:"
            kind = focus.get("kind")
            if kind == "database":
                system += f"\n- Database: `{focus['name']}`"
            elif kind == "table":
                system += f"\n- Table: `{focus['database']}.{focus['name']}`"
            elif kind == "column":
                nl = "NOT NULL" if not focus.get("nullable", True) else "NULL"
                system += (
                    f"\n- Column: `{focus['database']}.{focus['table']}.{focus['name']}` "
                    f"({focus.get('data_type', '')} {nl})"
                )
            system += "\nThe user's next question is almost certainly about this object. Do not ask which table / column they meant."
        return [LLMMessage("system", system), *self._messages]

    def _call_llm(self, placeholder) -> None:
        """Run the LLM call in a background thread.

        Note: this method runs off the Tk main thread. It must NOT call
        any Tk API directly — only via `self.after(0, ...)` to schedule
        work on the main thread. `messagebox.showerror` in particular
        hangs / silently fails when called from a non-Tk thread, so we
        render errors inside the chat bubble instead.

        We do a single blocking call (no streaming). When it returns we
        swap the placeholder bubble's text for the real response and
        stop the spinner animation.
        """
        try:
            manager = get_manager()
            messages = self._build_messages()
            resp = manager.chat(messages)
            content = (resp.content or "").strip()
            if not content:
                # Defensive: BaseLLM implementations are expected to
                # raise on empty content, but be paranoid.
                llm = manager.get()
                from src.core import env_config
                src_key = env_config.source_of("OPENAI_API_KEY") or "sqlite"
                src_url = env_config.source_of("OPENAI_BASE_URL") or "default"
                content = (
                    f"⚠️ _LLM returned no content._\n\n"
                    f"**Currently using:**\n"
                    f"- base URL : `{getattr(llm, 'base_url', '')}` (from {src_url})\n"
                    f"- model    : `{getattr(llm, 'model', '')}`\n"
                    f"- api key  : `{getattr(llm, 'api_key', '')[:6] + '***' if getattr(llm, 'api_key', '') else '(empty)'}` (from {src_key})\n\n"
                    f"**Things to check:**\n"
                    f"- Run `python tools/diagnose_llm.py` to see the raw error\n"
                    f"- The model name must exist on the configured base URL\n"
                    f"- Open Settings → ⚙ and update the model / base URL if needed\n"
                    f"- See `logs/app.log` for the full request / response trace"
                )
            self.after(0, lambda: self._finish_placeholder(placeholder, content))
            self._messages.append(LLMMessage("assistant", content))
        except Exception as exc:
            logger.exception("LLM call failed")
            err = f"❌ LLM call failed:\n\n```\n{exc}\n```"
            self.after(0, lambda: self._finish_placeholder(placeholder, err))
        finally:
            self._busy = False
            if self.on_status:
                self.after(0, lambda: self.on_status("Ready"))

    def _finish_placeholder(self, widget, text: str) -> None:
        """Replace the spinner bubble with the real response and stop
        the spinner animation. Safe to call from the UI thread only."""
        if hasattr(self, "_spinner_after"):
            try:
                self.after_cancel(self._spinner_after)
            except tk.TclError:
                pass
            self._spinner_after = None
        self._spinner_i = 0
        self._update_last_assistant(widget, text)

    def _update_last_assistant(self, widget, text: str) -> None:
        # `widget` may be None (caller forgot to return it) or may have
        # been destroyed (user switched connection mid-stream). Guard
        # against both to avoid crashing the Tk main loop.
        if widget is None:
            return
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            if isinstance(child, MarkdownView):
                try:
                    child.set_markdown(text)
                    self._fit_markdown(child)
                except tk.TclError:
                    return
                # Re-scroll after the bubble's content changes so the
                # user still sees the bottom (most important for the
                # spinner → real-response swap).
                self._scroll_to_bottom()
                return

    # ------------------------------------------------------------------ #
    # SQL extraction & execution helpers
    # ------------------------------------------------------------------ #
    def execute_last_sql(self) -> None:
        """Extract SQL from the conversation and run it.

        If the latest assistant message has a single ```sql block we
        just run it.  If it has multiple, the model is usually
        returning a CREATE / INSERT / SELECT chain or alternative
        candidates — we can't guess which one the user wants, so we
        pop up a chooser and let them pick.
        """
        if self._profile is None:
            messagebox.showinfo("Execute", "No active connection.")
            return
        for msg in reversed(self._messages):
            if msg.role == "assistant":
                sqls = extract_code_blocks(msg.content)
                if not sqls:
                    messagebox.showinfo("Execute", "No SQL found in the latest response.")
                    return
                if len(sqls) == 1:
                    self._run_sql(sqls[0])
                    return
                # Multiple SQLs → picker.
                picked = self._pick_sql(sqls)
                if picked is not None:
                    self._run_sql(picked)
                return
        messagebox.showinfo("Execute", "No assistant response yet.")

    def execute_sql(self, sql: str) -> None:
        self._run_sql(sql)

    # ------------------------------------------------------------------ #
    # SQL Editor tab callbacks
    # ------------------------------------------------------------------ #
    def _on_editor_run(self) -> None:
        """Execute whatever is currently in the SQL editor textbox.

        Splits on `;` so the user can paste several statements and
        run them all.  Stops on the first error so a bad statement
        doesn't leave the rest half-applied.
        """
        if self._profile is None:
            messagebox.showwarning("No connection",
                                   "Please select a database connection first.")
            return
        text = self.sql_editor.get("1.0", "end-1c").strip()
        if not text:
            return
        # Split on `;` but ignore semicolons inside string literals.
        stmts = [s.strip() for s in self._split_sql_statements(text) if s.strip()]
        if not stmts:
            return
        # Auto-switch to the result tab so the user can see output.
        try:
            self.tabs.set("Chat")
        except tk.TclError:
            pass
        for stmt in stmts:
            try:
                self._run_sql(stmt)
            except Exception as exc:
                messagebox.showerror(
                    "Execute",
                    f"Statement failed:\n\n{stmt}\n\n{exc}",
                )
                return

    def _on_editor_clear(self) -> None:
        self.sql_editor.delete("1.0", "end")

    def _on_editor_paste_last(self) -> None:
        """Drop the most recent ```sql block from the chat into the editor.

        If there are multiple, paste the first; the user can switch to
        the chat tab to use the multi-SQL picker.
        """
        for msg in reversed(self._messages):
            if msg.role == "assistant":
                sqls = extract_code_blocks(msg.content)
                if sqls:
                    self.sql_editor.delete("1.0", "end")
                    self.sql_editor.insert("1.0", sqls[0])
                    try:
                        self.tabs.set("SQL Editor")
                    except tk.TclError:
                        pass
                    return
        messagebox.showinfo("Paste last", "No previous SQL found.")

    @staticmethod
    def _split_sql_statements(text: str) -> list[str]:
        """Split SQL text on `;`, respecting string literals and comments.

        Avoids the case where a string containing `;` (e.g. a value
        in an INSERT) is wrongly split into two statements.
        """
        out: list[str] = []
        buf: list[str] = []
        i, n = 0, len(text)
        while i < n:
            c = text[i]
            # Line comment
            if c == "-" and i + 1 < n and text[i + 1] == "-":
                j = text.find("\n", i)
                if j == -1:
                    buf.append(text[i:])
                    i = n
                else:
                    buf.append(text[i:j + 1])
                    i = j + 1
                continue
            # Block comment
            if c == "/" and i + 1 < n and text[i + 1] == "*":
                j = text.find("*/", i + 2)
                if j == -1:
                    buf.append(text[i:])
                    i = n
                else:
                    buf.append(text[i:j + 2])
                    i = j + 2
                continue
            # String literal
            if c in ("'", '"'):
                quote = c
                buf.append(c)
                j = i + 1
                while j < n:
                    if text[j] == "\\" and j + 1 < n:
                        buf.append(text[j:j + 2])
                        j += 2
                        continue
                    if text[j] == quote:
                        if j + 1 < n and text[j + 1] == quote:
                            buf.append(text[j:j + 2])
                            j += 2
                            continue
                        buf.append(text[j])
                        j += 1
                        break
                    buf.append(text[j])
                    j += 1
                i = j
                continue
            # Statement separator
            if c == ";":
                out.append("".join(buf))
                buf = []
                i += 1
                continue
            buf.append(c)
            i += 1
        tail = "".join(buf).strip()
        if tail:
            out.append("".join(buf))
        return out

    def _pick_sql(self, sqls: list[str]) -> Optional[str]:
        """Modal chooser for when the assistant returned multiple SQLs.

        Returns the selected SQL, or None if the user cancelled.
        """
        dlg = ctk.CTkToplevel(self)
        dlg.title("Choose a SQL to execute")
        dlg.geometry("700x320")
        try:
            dlg.transient(self)
            dlg.grab_set()
        except tk.TclError:
            pass
        ctk.CTkLabel(
            dlg,
            text=f"The latest response contains {len(sqls)} SQL blocks. Pick one to execute:",
            font=("", 12, "bold"),
        ).pack(pady=(12, 6), padx=12, anchor="w")

        frame = ctk.CTkFrame(dlg)
        frame.pack(fill="both", expand=True, padx=12, pady=4)
        scroll = ctk.CTkScrollableFrame(frame)
        scroll.pack(fill="both", expand=True)
        var = tk.IntVar(value=0)
        rows: list[tk.IntVar] = []
        for i, sql in enumerate(sqls):
            r = ctk.CTkRadioButton(
                scroll, text="", variable=var, value=i,
                font=("", 11),
            )
            preview = " ".join(sql.split())[:80]
            r.grid(row=i, column=0, sticky="w", padx=8, pady=4)
            lbl = ctk.CTkLabel(
                scroll, text=f"#{i + 1}  {preview}{'…' if len(sql) > 80 else ''}",
                font=("Consolas", 11), anchor="w",
            )
            lbl.grid(row=i, column=1, sticky="ew", padx=(0, 8), pady=4)
            rows.append(var)

        chosen: list[Optional[str]] = [None]

        def on_ok():
            idx = var.get()
            if 0 <= idx < len(sqls):
                chosen[0] = sqls[idx]
            dlg.destroy()

        def on_cancel():
            dlg.destroy()

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btns, text="Cancel", width=100,
                      command=on_cancel).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Execute", width=120,
                      command=on_ok).pack(side="right", padx=4)
        dlg.bind("<Return>", lambda _e: on_ok())
        dlg.bind("<Escape>", lambda _e: on_cancel())
        self.wait_window(dlg)
        return chosen[0]

    def _run_sql(self, sql: str) -> None:
        if self._profile is None:
            return
        # Safety check
        report = analyze(sql, db_type=self._profile.db_type, read_only=self._profile.read_only)
        if not report.allowed:
            messagebox.showwarning("Blocked", f"SQL guard blocked this statement:\n{report.reason}")
            return
        if report.is_dml and not messagebox.askyesno(
            "Confirm",
            f"This will modify data ({report.statement_type}).\n\nProceed?",
        ):
            return

        try:
            result = execute_on_connection(self._profile, sql)
        except PermissionError as exc:
            messagebox.showwarning("Blocked", str(exc))
            return
        except Exception as exc:
            logger.exception("Execution failed")
            messagebox.showerror("Execute", f"Execution failed:\n{exc}")
            self.result_viewer.show_message(f"❌ {exc}")
            return

        self.result_viewer.show(result, sql=sql)
