"""Smoke test: MarkdownView is selectable + copyable but still blocks edits."""
import sys
sys.path.insert(0, '.')

import tkinter as tk
from src.ui.widgets.markdown_view import MarkdownView

root = tk.Tk()
root.withdraw()
mv = MarkdownView(root, mode="dark")
mv.set_markdown("Hello, **world**! Click and copy me.")
root.update_idletasks()

# 1) State should be "normal" (so selection works)
assert mv.cget("state") == "normal", f"state = {mv.cget('state')!r}"
print("OK: state=normal")

# 2) Insert a character programmatically — should succeed (we control the renderer)
mv.insert("end", " EXTRA")
root.update_idletasks()
text = mv.get("1.0", "end-1c")
assert "EXTRA" in text
print("OK: programmatic insert works")

# 3) Programmatic selection should work
mv.tag_add("sel", "1.0", "end")
sel_range = mv.tag_ranges("sel")
assert sel_range, "selection range empty"
print(f"OK: programmatic selection covers {sel_range}")

# 4) Simulate a keypress — _block_keypress should return "break" for letters
class FakeEvent:
    def __init__(self, keysym, state=0):
        self.keysym = keysym
        self.state = state

# Typing a letter must be blocked
result = mv._block_keypress(FakeEvent("a"))
assert result == "break", f"a key returned {result!r}"
print("OK: 'a' keypress blocked")

# Ctrl+C must be allowed
result = mv._block_keypress(FakeEvent("c", state=0x4))
assert result is None, f"Ctrl+C returned {result!r}"
print("OK: Ctrl+C allowed")

# Ctrl+A must be allowed
result = mv._block_keypress(FakeEvent("a", state=0x4))
assert result is None, f"Ctrl+A returned {result!r}"
print("OK: Ctrl+A allowed")

# Backspace must be blocked
result = mv._block_keypress(FakeEvent("BackSpace"))
assert result == "break", f"BackSpace returned {result!r}"
print("OK: BackSpace blocked")

# Arrow keys must be allowed
result = mv._block_keypress(FakeEvent("Up"))
assert result is None, f"Up returned {result!r}"
print("OK: Up arrow allowed")

# Delete must be blocked
result = mv._block_keypress(FakeEvent("Delete"))
assert result == "break", f"Delete returned {result!r}"
print("OK: Delete blocked")

root.destroy()
print("ALL OK")
