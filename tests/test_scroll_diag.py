"""Diagnose: does _find_canvas return a canvas? Does its scrollregion
update after adding a new bubble? Does yview_moveto actually scroll?"""
import sys
sys.path.insert(0, '.')

from src.ui.main_window import MainWindow

app = MainWindow()
app.update_idletasks()
app.update()

hf = app.chat_panel.history_frame
# 1) Try the private API
pc_priv = getattr(hf, "_parent_canvas", None)
print(f"_parent_canvas private: {pc_priv}")
# 2) Try the walk
pc_walked = app.chat_panel._find_scrollable_canvas(hf)
print(f"_find_scrollable_canvas: {pc_walked}")
canvas = pc_priv or pc_walked
assert canvas is not None

# 3) Measure current scrollregion
app.update_idletasks()
sr_before = canvas.cget("scrollregion")
print(f"scrollregion before:    {sr_before}")

# 4) Add a bubble
from src.llm.base import LLMMessage
app.chat_panel._messages.append(LLMMessage("assistant", "Hello, this is a test message that should be long enough to wrap onto multiple lines."))
bubble = app.chat_panel._add_assistant("Hello, this is a test message that should be long enough to wrap onto multiple lines.")
# _add_assistant already calls _scroll_to_bottom which uses after_idle
# Wait a bit and force updates
for _ in range(10):
    app.update_idletasks()
    app.update()
sr_after = canvas.cget("scrollregion")
print(f"scrollregion after:     {sr_after}")
print(f"yview now: {canvas.yview()}")

# 5) Force scroll to bottom
canvas.yview_moveto(1.0)
app.update_idletasks()
print(f"yview after moveto(1.0): {canvas.yview()}")

# 6) Height of inner content vs visible canvas
print(f"canvas height:    {canvas.winfo_height()}")
# Bbox of all items in canvas
bbox = canvas.bbox("all")
print(f"canvas bbox(all): {bbox}")
# Inner frame size
pf = getattr(hf, "_parent_frame", None)
if pf is not None:
    print(f"inner frame size: {pf.winfo_width()}x{pf.winfo_height()}")

app.destroy()
