"""Tabular result viewer with export and pagination."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from tkinter import ttk

from config.settings import MAX_RESULT_ROWS
from src.database.adapters.base import QueryResult
from src.ui._theme import apply_scrollbar_style, apply_ttk_style, current_mode, palette_for, row_colors


class ResultViewer(ctk.CTkFrame):
    """Displays a `QueryResult` in a Treeview with paging and export."""

    def __init__(self, master):
        super().__init__(master)
        self._result: Optional[QueryResult] = None
        self._page = 0
        self._page_size = 100

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header — single line, no wrapping.  wraplength=0 disables
        # word-wrap entirely; combined with `height=1` the label never
        # grows vertically and never steals space from the table below.
        self.header = ctk.CTkLabel(
            self, text="No result", anchor="w",
            font=("", 13, "bold"),
            height=20, width=0,
        )
        self.header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkButton(toolbar, text="⏮ Prev", width=80, command=self._prev).pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="Next ⏭", width=80, command=self._next).pack(side="left", padx=2)
        ctk.CTkLabel(toolbar, text="Page:").pack(side="left", padx=(12, 2))
        self.page_label = ctk.CTkLabel(toolbar, text="0/0", width=80)
        self.page_label.pack(side="left", padx=2)
        ctk.CTkButton(toolbar, text="Export CSV", width=100, command=self._export_csv).pack(side="right", padx=2)
        ctk.CTkButton(toolbar, text="Export Excel", width=100, command=self._export_excel).pack(side="right", padx=2)

        # Treeview — colors come from the palette so we can re-style
        # the result table when the user toggles between light/dark.
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        apply_ttk_style(self.style, "Result.Treeview", current_mode(),
                        with_headings=True)
        # Configure zebra-stripe row tags.  The tags are assigned per-row
        # in `_render_page` so odd rows get the alt-surface color, giving
        # the table a subtle grid-like separation that reads as "grid
        # lines" without resorting to custom drawing.
        odd, even = row_colors(current_mode())
        self.style.configure("Result.Treeview",
                             fieldbackground=odd, background=odd,
                             borderwidth=1, relief="solid")
        self.tree = ttk.Treeview(self, style="Result.Treeview", show="headings")
        self.tree.tag_configure("odd", background=odd)
        self.tree.tag_configure("even", background=even)
        self.tree.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        # Use the themed scrollbars so they match the chat panel's look.
        apply_scrollbar_style(self.style, current_mode())
        vsb = ttk.Scrollbar(self, orient="vertical", style="Vertical.TScrollbar",
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", style="Horizontal.TScrollbar",
                            command=self.tree.xview)
        vsb.grid(row=2, column=1, sticky="ns")
        hsb.grid(row=3, column=0, sticky="ew", padx=8)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    # ------------------------------------------------------------------ #
    def apply_theme(self, mode: str) -> None:
        """Re-style the result table for the new appearance mode."""
        apply_ttk_style(self.style, "Result.Treeview", mode, with_headings=True)
        apply_scrollbar_style(self.style, mode)
        odd, even = row_colors(mode)
        self.style.configure("Result.Treeview", fieldbackground=odd, background=odd)
        try:
            self.tree.tag_configure("odd", background=odd)
            self.tree.tag_configure("even", background=even)
        except tk.TclError:
            pass
        # Re-apply the existing rows so the new tag colors take effect.
        # The result itself doesn't change, only the row backgrounds.
        if self._result is not None:
            self._render_page()

    # ------------------------------------------------------------------ #
    def show(self, result: QueryResult, *, sql: str = "") -> None:
        self._result = result
        self._page = 0
        self._render_header(sql)
        self._render_page()

    def show_message(self, text: str) -> None:
        self._result = None
        self.tree.delete(*self.tree.get_children())
        self.tree.configure(columns=())
        self.header.configure(text=text)
        self.page_label.configure(text="0/0")

    # ------------------------------------------------------------------ #
    def _render_header(self, sql: str) -> None:
        r = self._result
        if r is None:
            self.header.configure(text="No result")
            return
        if r.is_dml:
            self.header.configure(text=f"⚙  {r.message or 'DML executed'}   ({r.duration_ms} ms)")
        else:
            self.header.configure(
                text=f"✓  {r.row_count} row(s)   ({r.duration_ms} ms)"
            )
        if sql:
            # Truncate aggressively — this is a single-line status bar,
            # not a SQL viewer.  50 chars is enough to recognize the
            # statement while leaving room for the row count and timing.
            one_line = " ".join(sql.split())
            preview = one_line[:50] + ("…" if len(one_line) > 50 else "")
            self.header.configure(text=self.header.cget("text") + f"   —  {preview}")

    def _render_page(self) -> None:
        r = self._result
        self.tree.delete(*self.tree.get_children())
        if r is None:
            return
        if r.is_dml:
            # Show a single info row.
            self.tree.configure(columns=("info",))
            self.tree.heading("info", text="Result")
            self.tree.insert("", "end", values=(r.message or f"{r.affected_rows} rows affected",))
            self.page_label.configure(text="1/1")
            return

        self.tree.configure(columns=r.columns or ("result",))
        for c in (r.columns or ["result"]):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=140, anchor="w")

        total_pages = max(1, (r.row_count + self._page_size - 1) // self._page_size)
        start = self._page * self._page_size
        end = min(start + self._page_size, r.row_count)
        for i, row in enumerate(r.rows[start:end]):
            # Alternate odd/even tags so the table has a grid-line feel.
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=row, tags=(tag,))

        self.page_label.configure(text=f"{self._page + 1}/{total_pages}")

    # ------------------------------------------------------------------ #
    def _prev(self) -> None:
        if self._result and self._page > 0:
            self._page -= 1
            self._render_page()

    def _next(self) -> None:
        if not self._result:
            return
        total_pages = max(1, (self._result.row_count + self._page_size - 1) // self._page_size)
        if self._page + 1 < total_pages:
            self._page += 1
            self._render_page()

    # ------------------------------------------------------------------ #
    def _export_csv(self) -> None:
        if not self._result or self._result.is_dml:
            messagebox.showinfo("Export", "No tabular result to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile=f"result-{datetime.now():%Y%m%d-%H%M%S}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            df = self._result.to_dataframe()
            df.to_csv(path, index=False, encoding="utf-8-sig")
            messagebox.showinfo("Export", f"Saved to {path}")
        except Exception as exc:
            messagebox.showerror("Export", f"Failed: {exc}")

    def _export_excel(self) -> None:
        if not self._result or self._result.is_dml:
            messagebox.showinfo("Export", "No tabular result to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"result-{datetime.now():%Y%m%d-%H%M%S}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            df = self._result.to_dataframe()
            df.to_excel(path, index=False, engine="openpyxl")
            messagebox.showinfo("Export", f"Saved to {path}")
        except Exception as exc:
            messagebox.showerror("Export", f"Failed: {exc}")
