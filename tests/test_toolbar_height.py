"""Diagnose: does the toolbar grow taller when the theme is toggled?
We measure winfo_height() before and after _toggle_theme()."""
import sys
sys.path.insert(0, '.')

import tkinter as tk
from customtkinter import CTkFrame
import customtkinter as ctk

# Pin theme to dark for deterministic bg-colour assertions.  The
# theme is persisted in SQLite (see `src.core.config`), so we
# reset the row directly to avoid relying on whatever the previous
# test run left behind.
from src.core import config as _cfg
_cfg.set_value("ui.theme", "dark")

from src.ui.main_window import MainWindow

app = MainWindow()
app.update_idletasks()
app.update()

# Find the toolbar: it's the first child of the MainWindow that's
# a CTkFrame OR a tk.Frame with columnspan=2.
toolbar = None
for c in app.winfo_children():
    info = c.grid_info()
    if info.get("columnspan") == 2 and isinstance(c, (CTkFrame, tk.Frame)):
        toolbar = c
        break
assert toolbar is not None, "toolbar not found"
print(f"toolbar type: {type(toolbar).__name__}")
print(f"toolbar bg:   {toolbar.cget('bg')!r}")

TARGET = 34

# Measure initial state
app.update_idletasks()
h0 = toolbar.winfo_height()
gp = toolbar.grid_propagate()
pp = toolbar.pack_propagate()
bg0 = toolbar.cget("bg")
print(f"BEFORE toggle:  height={h0}  grid_propagate={gp}  pack_propagate={pp}  bg={bg0}")
# Show the requested height (the height=34 hint)
req = toolbar.winfo_reqheight()
print(f"  winfo_reqheight = {req}")
assert h0 == TARGET, f"toolbar should be {TARGET}px tall before toggle, got {h0}"
assert bg0 == "#1a1a1a", f"toolbar bg should match dark mode (#1a1a1a), got {bg0!r}"

# Toggle to light
app._toggle_theme()
for _ in range(5):
    app.update_idletasks()
    app.update()
h1 = toolbar.winfo_height()
gp1 = toolbar.grid_propagate()
pp1 = toolbar.pack_propagate()
bg1 = toolbar.cget("bg")
print(f"AFTER light:    height={h1}  grid_propagate={gp1}  pack_propagate={pp1}  bg={bg1}  (delta {h1-h0:+})")
req1 = toolbar.winfo_reqheight()
print(f"  winfo_reqheight = {req1}")
assert h1 == TARGET, f"toolbar should still be {TARGET}px tall after light toggle, got {h1}"
assert bg1 == "#e6e6e6", f"toolbar bg should match light mode (#e6e6e6), got {bg1!r}"

# Toggle back to dark
app._toggle_theme()
for _ in range(5):
    app.update_idletasks()
    app.update()
h2 = toolbar.winfo_height()
gp2 = toolbar.grid_propagate()
pp2 = toolbar.pack_propagate()
bg2 = toolbar.cget("bg")
print(f"BACK to dark:   height={h2}  grid_propagate={gp2}  pack_propagate={pp2}  bg={bg2}  (delta {h2-h0:+})")
req2 = toolbar.winfo_reqheight()
print(f"  winfo_reqheight = {req2}")
assert h2 == TARGET, f"toolbar should still be {TARGET}px tall after dark toggle, got {h2}"
assert bg2 == "#1a1a1a", f"toolbar bg should match dark mode (#1a1a1a), got {bg2!r}"

# Show inner button heights.  The toolbar structure is:
#   toolbar (tk.Frame, height=34)
#     ├ title (CTkLabel, side=left)
#     ├ theme (CTkButton, side=right)  ← rightmost
#     ├ execute (CTkButton, side=right)
#     └ settings (CTkButton, side=right)
def _label(c):
    if isinstance(c, (ctk.CTkLabel, ctk.CTkButton)):
        try:
            return c.cget("text")
        except (tk.TclError, AttributeError):
            return "?"
    return type(c).__name__

import io
buf = io.StringIO()
old = sys.stdout
sys.stdout = buf
print("toolbar children:")
for child in toolbar.winfo_children():
    label = _label(child)
    print(f"  {type(child).__name__}  text={label[:30]!r}  "
          f"height={child.winfo_height()!r}  reqheight={child.winfo_reqheight()!r}  "
          f"x={child.winfo_x()!r}  y={child.winfo_y()!r}  "
          f"w={child.winfo_width()!r}")
sys.stdout = old
print(buf.getvalue().encode("ascii", "replace").decode("ascii"))

# Sanity-check the right-bar buttons are actually inside the
# visible area of the toolbar (this is the bug the user reported:
# buttons parked at (0, 0) under the title).
toolbar_w = toolbar.winfo_width()
toolbar_h = toolbar.winfo_height()
assert toolbar_w > 200, f"toolbar unexpectedly narrow: {toolbar_w}"
assert toolbar_h == TARGET

# Find each expected child of the toolbar by type + text.
labels = toolbar.winfo_children()
title = next((c for c in labels if isinstance(c, ctk.CTkLabel)), None)
btns  = [c for c in labels if isinstance(c, ctk.CTkButton)]
assert title is not None, "title (CTkLabel) not found in toolbar"
assert len(btns) == 3, f"expected 3 CTkButtons, got {len(btns)}"
btn_texts = {b.cget("text"): b for b in btns}
assert "Light" in btn_texts or "Dark" in btn_texts, "theme button missing"
assert any("Execute" in t for t in btn_texts), "execute button missing"
assert any("Settings" in t for t in btn_texts), "settings button missing"
print(f"all 3 expected buttons present: {[t.encode('ascii','replace').decode('ascii') for t in sorted(btn_texts.keys())]}")

# Each button must have non-zero width and be within the toolbar.
for text, btn in btn_texts.items():
    bw = btn.winfo_width()
    bh = btn.winfo_height()
    bx = btn.winfo_x()
    by = btn.winfo_y()
    assert bw > 50, f"button {text!r} too narrow: {bw} (the place() bug)"
    assert bh > 20, f"button {text!r} too short: {bh}"
    assert bx >= 0, f"button {text!r} at negative x ({bx})"
    assert bx + bw <= toolbar_w + 1, (
        f"button {text!r} overflows toolbar right edge "
        f"({bx}+{bw} > {toolbar_w})"
    )
    assert by >= 0, f"button {text!r} at negative y ({by})"
    assert by + bh <= toolbar_h + 8, (  # +8 for CTk's overflow tolerance
        f"button {text!r} overflows toolbar bottom "
        f"({by}+{bh} > {toolbar_h})"
    )
print("ALL buttons visible inside toolbar with non-zero size")

app.destroy()
print("ALL OK: toolbar stays at 34px and all 3 buttons are visible")
