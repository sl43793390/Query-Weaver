"""Sidebar with the connection list, schema tree, and quick actions."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

import customtkinter as ctk

from src.core.logger import logger
from src.database.connector import (
    ConnectionProfile,
    list_connections,
    get_connection_profile,
    delete_connection,
    test_connection,
)
from src.database.schema_browser import get_schema, invalidate
from src.ui._theme import palette_for
from src.ui.schema_tree import SchemaTree


class Sidebar(ctk.CTkFrame):
    """Left-side panel: connections + schema."""

    def __init__(
        self,
        master,
        *,
        on_connection_changed: Optional[Callable[[Optional[ConnectionProfile]], None]] = None,
        on_new_connection: Optional[Callable[[], None]] = None,
        on_schema_focus: Optional[Callable[[Optional[dict]], None]] = None,
    ):
        super().__init__(master, width=280, corner_radius=0)
        self.on_connection_changed = on_connection_changed
        self.on_new_connection = on_new_connection
        self.on_schema_focus = on_schema_focus
        self._current_profile: Optional[ConnectionProfile] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---- Header ----
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(header, text="Connections", font=("", 14, "bold")).pack(side="left")

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")
        ctk.CTkButton(btn_frame, text="+", width=28, command=self._on_new).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="⟳", width=28, command=self.refresh).pack(side="left", padx=2)

        # ---- Connection list ----
        # Colors come from the palette; `apply_theme()` will re-configure
        # them when the user toggles between light and dark.
        self._current_mode = "dark"
        p = palette_for(self._current_mode)
        self.conn_list = tk.Listbox(
            self, activestyle="dotbox", exportselection=False, bd=0,
            highlightthickness=0, background=p["surface"], foreground=p["fg"],
            selectbackground=p["selection"], selectforeground=p["selection_fg"],
        )
        self.conn_list.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.conn_list.bind("<<ListboxSelect>>", self._on_select)

        # ---- Action buttons ----
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkButton(actions, text="Test", width=80, command=self._on_test).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="Edit", width=80, command=self._on_edit).pack(side="left", padx=2)
        ctk.CTkButton(actions, text="Delete", width=80, command=self._on_delete,
                      fg_color="#a04040", hover_color="#802f2f").pack(side="left", padx=2)

        # ---- Schema tree ----
        ctk.CTkLabel(self, text="Schema", font=("", 13, "bold")).grid(
            row=3, column=0, sticky="w", padx=8, pady=(8, 0)
        )
        self.schema_tree = SchemaTree(
            self, on_select=self._on_schema_node_selected
        )
        self.schema_tree.grid(row=4, column=0, sticky="nsew", padx=8, pady=(4, 8))

        self.grid_rowconfigure(4, weight=1)

        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        self.conn_list.delete(0, "end")
        self._items: list[dict] = list_connections()
        for item in self._items:
            self.conn_list.insert("end", f"  {item['name']}  ({item['db_type']})")
        self.schema_tree.clear()
        self._current_profile = None
        if self.on_connection_changed:
            self.on_connection_changed(None)

    # ------------------------------------------------------------------ #
    def _selected_id(self) -> Optional[int]:
        sel = self.conn_list.curselection()
        if not sel:
            return None
        return self._items[sel[0]]["id"]

    def _on_select(self, _event=None) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        profile = get_connection_profile(cid)
        if profile is None:
            return
        self._current_profile = profile
        # Lazy-load schema
        try:
            info = get_schema(profile)
        except Exception as exc:  # pragma: no cover - depends on driver
            logger.exception("Schema fetch failed")
            messagebox.showerror("Schema", f"Failed to fetch schema:\n{exc}")
            return
        self.schema_tree.populate(info)
        if self.on_connection_changed:
            self.on_connection_changed(profile)

    def _on_new(self) -> None:
        if self.on_new_connection:
            self.on_new_connection()

    def _on_test(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        profile = get_connection_profile(cid)
        if not profile:
            return
        ok, msg = test_connection(profile)
        if ok:
            messagebox.showinfo("Test", f"✓ {msg}")
        else:
            messagebox.showerror("Test", f"✗ {msg}")

    def _on_edit(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        if self.on_new_connection:
            # Reuse the same dialog in edit mode
            self.on_new_connection(edit_id=cid)

    def _on_delete(self) -> None:
        cid = self._selected_id()
        if cid is None:
            return
        if not messagebox.askyesno("Delete", "Delete this connection?"):
            return
        delete_connection(cid)
        invalidate(cid)
        self.refresh()

    # ------------------------------------------------------------------ #
    @property
    def current_profile(self) -> Optional[ConnectionProfile]:
        return self._current_profile

    # ------------------------------------------------------------------ #
    # Theme switching — re-style the tk.Listbox (CTk doesn't manage its
    # colors) and forward to the SchemaTree's ttk.Treeview.
    # ------------------------------------------------------------------ #
    def apply_theme(self, mode: str) -> None:
        self._current_mode = mode
        p = palette_for(mode)
        try:
            self.conn_list.configure(
                background=p["surface"],
                foreground=p["fg"],
                selectbackground=p["selection"],
                selectforeground=p["selection_fg"],
            )
        except tk.TclError:
            pass
        # Forward to nested widgets that own their own ttk.Style.
        self.schema_tree.apply_theme(mode)

    # ------------------------------------------------------------------ #
    # Schema node selection — forward to whoever cares (ChatPanel).
    # `info` is a dict like {"kind": "database"/"table"/"column",
    # "name": "...", "database": "...", "table": "..."} or None if
    # the user clicked away (clearing the focus).
    # ------------------------------------------------------------------ #
    def _on_schema_node_selected(self, info: Optional[dict]) -> None:
        if self.on_schema_focus:
            self.on_schema_focus(info)
