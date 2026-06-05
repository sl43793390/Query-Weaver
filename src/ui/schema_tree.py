"""Treeview-based schema browser."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk

from src.database.adapters.base import SchemaInfo
from src.ui._theme import apply_ttk_style, current_mode


class SchemaTree(ctk.CTkFrame):
    def __init__(self, master, on_select: Optional[Callable[[Optional[dict]], None]] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        # Maps ttk item id -> {"kind", "name", "database", "table"}
        self._node_meta: dict[str, dict] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        apply_ttk_style(self.style, "Schema.Treeview", current_mode())

        self.tree = ttk.Treeview(
            self, style="Schema.Treeview", show="tree", selectmode="browse"
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        if on_select is not None:
            self.tree.bind("<<TreeviewSelect>>", self._emit_selection)

    # ------------------------------------------------------------------ #
    def apply_theme(self, mode: str) -> None:
        """Re-style the tree for the given appearance mode."""
        apply_ttk_style(self.style, "Schema.Treeview", mode)

    # ------------------------------------------------------------------ #
    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._node_meta.clear()
        if self._on_select is not None:
            # Clearing the tree also clears any current focus.
            self._on_select(None)

    def populate(self, info: SchemaInfo) -> None:
        """Render every database as a top-level node, with its tables
        nested underneath. The configured default database is opened
        by default; the rest are folded."""
        self.clear()
        if not info.databases:
            empty_id = self.tree.insert("", "end", text="(no schema available)", open=True)
            self._node_meta[empty_id] = {"kind": "empty", "name": "(no schema available)"}
            return
        for db in info.databases:
            label = f"📁 {db.name}"
            if db.name and db.name == info.default_database:
                label += "  ★"   # mark the configured default
            db_node = self.tree.insert("", "end", text=label,
                                       open=(db.name == info.default_database))
            self._node_meta[db_node] = {
                "kind": "database", "name": db.name, "database": db.name,
            }
            for t in db.tables:
                tid = self.tree.insert(
                    db_node, "end", text=f"📄 {t.name}", open=False
                )
                self._node_meta[tid] = {
                    "kind": "table",
                    "name": t.name,
                    "database": db.name,
                    "table": t.name,
                }
                for col in t.columns:
                    nullable = "" if col.nullable else " NOT NULL"
                    cid = self.tree.insert(
                        tid, "end",
                        text=f"  {col.name}  {col.data_type}{nullable}",
                    )
                    self._node_meta[cid] = {
                        "kind": "column",
                        "name": col.name,
                        "database": db.name,
                        "table": t.name,
                        "data_type": col.data_type,
                        "nullable": col.nullable,
                    }

    # ------------------------------------------------------------------ #
    # Selection handling — translate the ttk item id into a structured
    # dict and forward to the callback registered in __init__.
    # ------------------------------------------------------------------ #
    def _emit_selection(self, _event=None) -> None:
        if self._on_select is None:
            return
        sel = self.tree.selection()
        if not sel:
            self._on_select(None)
            return
        # The user may have selected multiple items (e.g. after a shift
        # click); we only care about the first.
        info = self._node_meta.get(sel[0])
        self._on_select(info)
