"""Diagnose: does row 0 (the toolbar's grid row) grow taller than
34 px when the window is given extra vertical slack?

Symptom reported by user (prompt.txt L85-86):
  '首次启动应用页面头部的名称及dark等三个按钮占用的高度是正常
  且合适的，当我点击主题切换后发现头部和下面的connections栏和
  tabsheet栏中间出现了一段空白的布局占用'
  (The first launch looks fine, but after clicking the theme
   toggle, a blank gap appears between the header and the
   connections bar / tabsheet bar below it.)

Root cause: `self.grid_rowconfigure(0, weight=1)` made row 0
elastic.  On first launch the window height happened to match
toolbar + content + status exactly, so no slack for row 0 to
absorb.  After `ctk.set_appearance_mode(...)` the layout re-passes
and any extra space goes to the highest-weighted row → row 0
grows, pushing a gap below the buttons but above the panels.

This test forces a tall window (so there IS slack to absorb),
then checks row 0's actual height before/after a theme toggle.
"""
import sys
sys.path.insert(0, '.')

import tkinter as tk
import customtkinter as ctk

from src.core import config as _cfg
_cfg.set_value("ui.theme", "dark")

from src.ui.main_window import MainWindow

# MainWindow is a CTk subclass and is the Tk root.  Force a tall
# window so there is *definitely* vertical slack for row 0 to
# absorb (the bug only manifests when the window is taller than
# the sum of all the fixed-height children).
app = MainWindow()
app.geometry("1200x900")
app.update_idletasks()
app.update()

mw = app  # alias
toolbar = mw._toolbar

def measure(label):
    app.update_idletasks()
    app.update()
    # Row 0's height = where row 1 starts minus where the window
    # content begins.  Easier proxy: where the toolbar's bottom
    # edge sits inside `mw` vs the next sibling's top.
    tb_y = toolbar.winfo_y()
    tb_h = toolbar.winfo_height()
    # The next sibling in row 1 is either the chat panel or
    # the sidebar; either one's winfo_y() tells us where row 1
    # begins.
    panel_y = min(
        mw.chat_panel.winfo_y() if mw.chat_panel.winfo_ismapped() else 10**6,
        mw.sidebar.winfo_y()    if mw.sidebar.winfo_ismapped()    else 10**6,
    )
    print(f"{label:>15}: toolbar y={tb_y} h={tb_h}  "
          f"row0_end={tb_y + tb_h}  panel_starts_at={panel_y}  "
          f"gap_below_toolbar={panel_y - (tb_y + tb_h)}")
    return tb_y, tb_h, panel_y

print(f"toolbar widget height: {toolbar.winfo_height()}")
print(f"toolbar reqheight:     {toolbar.winfo_reqheight()}")

tb0, h0, p0 = measure("BEFORE toggle")
assert h0 == 34, f"toolbar should be 34px tall, got {h0}"
# Row 0 is the toolbar's row; row 1 is below it.  If row 0 grew
# beyond 34px, then `panel_starts_at` is > `row0_end` and we'd
# see a gap there.  But here we compare *cell* heights, not
# widget heights: the cell height is `panel_starts_at - tb_y`.
row0_cell = p0 - tb0
print(f"row 0 cell height: {row0_cell}")
assert row0_cell <= 35, (
    f"row 0 cell grew to {row0_cell}px — there's a {row0_cell - 34}px "
    f"blank gap below the toolbar.  The fix is to set "
    f"grid_rowconfigure(0, weight=0) so the toolbar row is fixed."
)

# Now do the theme toggle
mw._toggle_theme()
app.update_idletasks()
app.update()

tb1, h1, p1 = measure("AFTER  toggle")
assert h1 == 34, f"toolbar should still be 34px after toggle, got {h1}"
row1_cell = p1 - tb1
print(f"row 0 cell height: {row1_cell}")
assert row1_cell <= 35, (
    f"row 0 cell GREW to {row1_cell}px after theme toggle — the "
    f"blank-gap bug.  The fix is grid_rowconfigure(0, weight=0)."
)

# Toggle back
mw._toggle_theme()
app.update_idletasks()
app.update()
tb2, h2, p2 = measure("BACK to dark")
assert h2 == 34
row2_cell = p2 - tb2
print(f"row 0 cell height: {row2_cell}")
assert row2_cell <= 35, f"row 0 cell GREW on second toggle: {row2_cell}"

app.destroy()
print("ALL OK: row 0 stays tight (no blank gap) across theme toggles")
