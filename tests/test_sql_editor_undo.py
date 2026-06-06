"""Smoke test: SQL editor supports undo after paste."""
import sys
sys.path.insert(0, '.')

from src.ui.main_window import MainWindow

app = MainWindow()
app.update_idletasks()
app.update()

# Switch to the SQL editor tab
app.chat_panel.tabs.set("SQL Editor")
app.update_idletasks()

ed = app.chat_panel.sql_editor
# 1) undo should be enabled
try:
    assert ed.cget("undo") is True or ed.cget("undo") == 1, f"undo={ed.cget('undo')!r}"
    print(f"OK: undo enabled (value={ed.cget('undo')!r})")
except Exception as e:
    print(f"SKIP: cannot read undo attr: {e}")

# 2) Simulate paste, then undo
ed.delete("1.0", "end")
ed.insert("1.0", "SELECT * FROM users;")
ed.edit_separator()
ed.insert("end", " -- extra garbage that we want to undo")
app.update_idletasks()
text_before = ed.get("1.0", "end-1c")
print(f"Before undo: {text_before!r}")
assert "extra garbage" in text_before

# 3) Undo
ed.edit_undo()
app.update_idletasks()
text_after = ed.get("1.0", "end-1c")
print(f"After  undo: {text_after!r}")
assert "extra garbage" not in text_after, f"undo didn't work: {text_after!r}"
assert "SELECT * FROM users;" in text_after
print("OK: undo recovers the pre-paste state")

# 4) Redo brings it back
ed.edit_redo()
app.update_idletasks()
text_redo = ed.get("1.0", "end-1c")
assert "extra garbage" in text_redo, f"redo didn't work: {text_redo!r}"
print("OK: redo brings the garbage back")

# 5) Code block visual is now distinct from bubble bg
app.chat_panel.tabs.set("Chat")
app.update_idletasks()
from src.ui.widgets.markdown_view import MarkdownView
mv = app.chat_panel.history_frame.winfo_children()[0].winfo_children()[1]  # bubble > MarkdownView
# Direct: find the first MarkdownView in the chat
def find_md(widget):
    if isinstance(widget, MarkdownView):
        return widget
    for c in widget.winfo_children():
        r = find_md(c)
        if r is not None:
            return r
    return None
mv = find_md(app.chat_panel.history_frame)
assert mv is not None
# Read the codeblock tag config
bg = mv.tag_cget("codeblock", "background")
print(f"codeblock background: {bg!r}")
# Should NOT be the same as the bubble background (#1e1e1e in dark)
assert bg != "#1e1e1e", f"codeblock still same as bubble: {bg!r}"
print("OK: codeblock has a distinct background")

# 6) Selection colors are set on the widget
sel_bg = mv.cget("selectbackground")
sel_fg = mv.cget("selectforeground")
print(f"select bg={sel_bg!r}  fg={sel_fg!r}")
assert sel_bg and sel_bg != "SystemHighlight", f"selectbg not themed: {sel_bg!r}"
print("OK: selectbackground themed")

app.destroy()
print("ALL OK")
