"""Diagnose: can mouse selection land on the 'codeblock' tag region of
a MarkdownView?  We simulate the user's click-and-drag and inspect
what the widget reports as selected."""
import sys
sys.path.insert(0, '.')

import tkinter as tk
from src.ui.widgets.markdown_view import MarkdownView

root = tk.Tk()
root.geometry("800x400")
mv = MarkdownView(root, mode="dark", width=80, height=20)
mv.pack(fill="both", expand=True)
mv.set_markdown(
    "下面是一些中文。\n"
    "以下是 SQL 代码：\n"
    "\n"
    "```sql\n"
    "SELECT u.id, u.name\n"
    "FROM users u\n"
    "WHERE u.name LIKE '%sl%';\n"
    "```\n"
    "\n"
    "希望上面的 SQL 可以被选中并复制。"
)
root.update_idletasks()

# Dump all tags and their ranges
print("Visible text:")
print(mv.get("1.0", "end-1c"))
print()
print("Tag ranges:")
for tag in mv.tag_names():
    if tag == "sel":
        continue
    try:
        ranges = mv.tag_ranges(tag)
    except tk.TclError:
        continue
    if ranges:
        # Pair up start/end indices
        for i in range(0, len(ranges), 2):
            print(f"  {tag}: {ranges[i]} -> {ranges[i+1]}")

# Try to programmatically select across the code block
mv.tag_add("sel", "4.0", "7.0")
sel = mv.tag_ranges("sel")
print()
print(f"Programmatic sel: {sel}")
print(f"Selected text:    {mv.selection_get()!r}" if mv.tag_ranges('sel') else "(nothing)")

# Simulate user drag: mouse press, mouse move, mouse release
# Tk can synthesize events via event_generate
# Click at start of "SELECT" line
mv.update_idletasks()
# Find the bounding box of line 4 character 0
bbox = mv.bbox("4.0")
print(f"bbox of line 4: {bbox}")
if bbox:
    x, y, w, h = bbox
    # Use event_generate to simulate click+drag from (x+2, y+2) to (x+w, y+h)
    rx, ry = mv.winfo_rootx(), mv.winfo_rooty()
    mv.event_generate("<Button-1>", x=2, y=2)
    mv.event_generate("<B1-Motion>", x=200, y=2)
    mv.event_generate("<ButtonRelease-1>", x=200, y=2)
    root.update_idletasks()
    sel = mv.tag_ranges("sel")
    print(f"After drag selection: {sel}")
    if sel:
        try:
            print(f"Selected text: {mv.selection_get()!r}")
        except tk.TclError as e:
            print(f"No selection: {e}")

root.destroy()
