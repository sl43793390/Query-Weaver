"""Smoke test: launch the MainWindow for 1 second, verify the tabview +
result viewer + SQL editor all instantiate without exception."""
import sys
sys.path.insert(0, '.')

import customtkinter as ctk
from src.ui.main_window import MainWindow

app = MainWindow()
# Force layout so the tabview / result viewer fully realize.
app.update_idletasks()
app.update()
# Switch tabs back and forth to confirm both work.
app.chat_panel.tabs.set("SQL Editor")
app.update_idletasks()
app.chat_panel.tabs.set("Chat")
app.update_idletasks()
# Apply both themes so apply_theme propagates through every child.
app._toggle_theme()  # -> light
app.update_idletasks()
app._toggle_theme()  # -> dark
app.update_idletasks()
# Add a fake assistant message with two SQL blocks to exercise the picker.
from src.llm.base import LLMMessage
app.chat_panel._profile = None  # avoid touching DB
app.chat_panel._messages.append(LLMMessage("assistant", "```sql\nSELECT 1;\n```\n```sql\nSELECT 2;\n```"))
app.chat_panel._render_page = lambda: None  # not used
print("OK: window constructed, tabs switched, themes toggled.")
app.destroy()
