"""Smoke test: feed a real QueryResult into the result viewer and verify
zebra-stripe tags + scrollbar style are applied without exceptions."""
import sys
sys.path.insert(0, '.')

from src.ui.main_window import MainWindow
from src.database.adapters.base import QueryResult

app = MainWindow()
app.update_idletasks()
app.update()

# Fake a 6-row result and render it.
res = QueryResult(
    columns=["id", "name", "email"],
    rows=[
        (1, "Alice", "alice@example.com"),
        (2, "Bob",   "bob@example.com"),
        (3, "Carol", "carol@example.com"),
        (4, "Dave",  "dave@example.com"),
        (5, "Eve",   "eve@example.com"),
        (6, "Frank", "frank@example.com"),
    ],
    row_count=6,
    duration_ms=12,
    is_dml=False,
    affected_rows=0,
    message="",
)
app.chat_panel.result_viewer.show(res, sql="SELECT id, name, email FROM users WHERE active = 1")
app.update_idletasks()
app.update()
# Make sure the tree actually got the rows + tags.
items = app.chat_panel.result_viewer.tree.get_children()
assert len(items) == 6, f"expected 6 rows, got {len(items)}"
tags = {tuple(app.chat_panel.result_viewer.tree.item(i, "tags")) for i in items}
assert ("odd",) in tags and ("even",) in tags, f"missing zebra tags: {tags}"
print(f"OK: 6 rows rendered with tags {tags}")

# Toggle theme to make sure the rerender doesn't crash.
app._toggle_theme()  # -> light
app.update_idletasks()
app._toggle_theme()  # -> dark
app.update_idletasks()
print("OK: theme toggle re-renders result viewer without exception")

app.destroy()
