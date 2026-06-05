"""Modal dialogs: new/edit connection, LLM settings."""
from __future__ import annotations

from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from config.settings import DB_TYPES, LLM_PROVIDERS
from src.core import env_config
from src.core.config import get_secret, get_value, set_secret, set_value
from src.database.connector import (
    ConnectionProfile,
    get_connection_profile,
    save_connection,
    test_connection,
)
from src.llm.manager import get_manager


# --------------------------------------------------------------------------- #
# New / Edit Connection
# --------------------------------------------------------------------------- #
class ConnectionDialog(ctk.CTkToplevel):
    def __init__(self, master, *, edit_id: Optional[int] = None):
        super().__init__(master)
        self.title("Edit Connection" if edit_id else "New Connection")
        self.geometry("460x520")
        self.transient(master)
        self.grab_set()

        self._edit_id = edit_id
        self._profile: Optional[ConnectionProfile] = None

        self.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(self, text="Name *").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.name_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.name_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="DB Type *").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.type_var = ctk.StringVar(value=DB_TYPES[0])
        ctk.CTkOptionMenu(self, values=list(DB_TYPES), variable=self.type_var).grid(
            row=row, column=1, sticky="ew", padx=12, pady=6
        )
        row += 1

        ctk.CTkLabel(self, text="Host").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.host_var = ctk.StringVar(value="127.0.0.1")
        ctk.CTkEntry(self, textvariable=self.host_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Port").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.port_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.port_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Database").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.db_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.db_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Username").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.user_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.user_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Password").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.pwd_var = ctk.StringVar()
        ctk.CTkEntry(self, textvariable=self.pwd_var, show="*").grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        self.ro_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="Read-only mode (recommended)", variable=self.ro_var).grid(
            row=row, column=1, sticky="w", padx=12, pady=6
        )
        row += 1

        # Buttons
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=row, column=0, columnspan=2, sticky="e", padx=12, pady=12)
        ctk.CTkButton(btns, text="Cancel", command=self.destroy, width=80).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Save", command=self._on_save, width=80).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Test", command=self._on_test, width=80,
                      fg_color="#3a7ebf", hover_color="#2f6ba6").pack(side="right", padx=4)

        if edit_id is not None:
            self._load(edit_id)

    # ------------------------------------------------------------------ #
    def _load(self, conn_id: int) -> None:
        profile = get_connection_profile(conn_id)
        if not profile:
            return
        self._profile = profile
        self.name_var.set(profile.name)
        self.type_var.set(profile.db_type)
        self.host_var.set(profile.host)
        self.port_var.set(str(profile.port) if profile.port else "")
        self.db_var.set(profile.database)
        self.user_var.set(profile.username)
        self.pwd_var.set(profile.password)
        self.ro_var.set(profile.read_only)

    def _collect(self) -> Optional[ConnectionProfile]:
        name = self.name_var.get().strip()
        db_type = self.type_var.get().strip().lower()
        if not name or not db_type:
            messagebox.showwarning("Validation", "Name and DB type are required.")
            return None
        try:
            port = int(self.port_var.get()) if self.port_var.get().strip() else 0
        except ValueError:
            messagebox.showwarning("Validation", "Port must be an integer.")
            return None
        return ConnectionProfile(
            id=self._profile.id if self._profile else None,
            name=name,
            db_type=db_type,
            host=self.host_var.get().strip(),
            port=port,
            database=self.db_var.get().strip(),
            username=self.user_var.get().strip(),
            password=self.pwd_var.get(),
            options={},
            read_only=self.ro_var.get(),
        )

    def _on_test(self) -> None:
        profile = self._collect()
        if not profile:
            return
        ok, msg = test_connection(profile)
        if ok:
            messagebox.showinfo("Test", f"✓ {msg}")
        else:
            messagebox.showerror("Test", f"✗ {msg}")

    def _on_save(self) -> None:
        profile = self._collect()
        if not profile:
            return
        try:
            save_connection(profile)
        except Exception as exc:
            messagebox.showerror("Save", f"Failed to save: {exc}")
            return
        self.destroy()


# --------------------------------------------------------------------------- #
# LLM Settings
# --------------------------------------------------------------------------- #
class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Settings — LLM")
        self.geometry("520x420")
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(self, text="Provider").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.provider_var = ctk.StringVar(value=get_value("llm.provider", "openai") or "openai")
        ctk.CTkOptionMenu(
            self,
            values=list(LLM_PROVIDERS.keys()),
            variable=self.provider_var,
            command=lambda _v: self._update_hints(),
        ).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Model").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.model_var = ctk.StringVar(value=get_value("llm.model", "qwen3.5-flash") or "qwen3.5-flash")
        ctk.CTkEntry(self, textvariable=self.model_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Base URL").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        # env var > .env > sqlite setting; this lets operators set the
        # endpoint at deploy time and still override per-user in the UI.
        self.url_var = ctk.StringVar(
            value=(
                env_config.resolve("OPENAI_BASE_URL")
                or env_config.resolve("OLLAMA_HOST")
                or get_value("llm.base_url", "")
                or ""
            )
        )
        ctk.CTkEntry(self, textvariable=self.url_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="API Key").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        # Same resolution order: env > .env > encrypted sqlite value.
        self.api_var = ctk.StringVar(
            value=(env_config.resolve("OPENAI_API_KEY") or get_secret("llm.api_key"))
        )
        ctk.CTkEntry(self, textvariable=self.api_var, show="*").grid(
            row=row, column=1, sticky="ew", padx=12, pady=6
        )
        self._api_hint = ctk.CTkLabel(self, text="", anchor="w", text_color="#888", wraplength=420)
        self._api_hint.grid(row=row + 1, column=1, sticky="ew", padx=12, pady=(0, 6))
        row += 2

        ctk.CTkLabel(self, text="Temperature").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.temp_var = ctk.StringVar(value=get_value("llm.temperature", "0.2") or "0.2")
        ctk.CTkEntry(self, textvariable=self.temp_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        ctk.CTkLabel(self, text="Max tokens").grid(row=row, column=0, sticky="w", padx=12, pady=6)
        self.tokens_var = ctk.StringVar(value=get_value("llm.max_tokens", "2048") or "2048")
        ctk.CTkEntry(self, textvariable=self.tokens_var).grid(row=row, column=1, sticky="ew", padx=12, pady=6)
        row += 1

        self.hint = ctk.CTkLabel(self, text="", anchor="w", text_color="#888")
        self.hint.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 6))
        row += 1

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=12)
        ctk.CTkButton(btns, text="Cancel", command=self.destroy, width=80).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Save", command=self._on_save, width=80).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Test", command=self._on_test, width=80,
                      fg_color="#1f6aa5", hover_color="#0d4a7a").pack(side="left", padx=4)

        self._update_hints()

    def _update_hints(self) -> None:
        p = self.provider_var.get()
        if p == "openai":
            self.hint.configure(text="OpenAI / DeepSeek / Qwen — leave Base URL empty to use api.openai.com")
            self._api_hint.configure(
                text="(blank = use env var OPENAI_API_KEY or .env; clear and save to fall back to env)"
            )
        elif p == "ollama":
            self.hint.configure(text="Local Ollama — Base URL defaults to http://127.0.0.1:11434, no API key required.")
            self._api_hint.configure(text="(blank = use env var OLLAMA_HOST / OPENAI_BASE_URL or .env)")

    def _collect(self) -> dict:
        return {
            "provider": self.provider_var.get(),
            "model": self.model_var.get().strip(),
            "base_url": self.url_var.get().strip(),
            "api_key": self.api_var.get().strip(),
            "temperature": self.temp_var.get().strip() or "0.2",
            "max_tokens": self.tokens_var.get().strip() or "2048",
        }

    def _on_test(self) -> None:
        """Send a tiny ping to the configured LLM and report the result.

        Runs on a background thread so the UI doesn't hang; the result
        is shown via `messagebox` from the main thread."""
        import threading
        from src.llm.base import LLMMessage
        cfg = self._collect()
        provider = cfg["provider"]

        def _run():
            from src.core import env_config
            from src.llm.manager import get_manager
            # Save current values, so `get_manager()` picks them up.
            set_value("llm.provider", cfg["provider"])
            set_value("llm.model", cfg["model"])
            set_value("llm.base_url", cfg["base_url"])
            set_secret("llm.api_key", cfg["api_key"])
            get_manager().reload()
            llm = get_manager().get()
            try:
                resp = llm.chat(
                    [LLMMessage("user", "Reply with the single word: pong")],
                )
                text = (resp.content or "").strip()[:80] or "(empty)"
                msg = (
                    f"OK\n\nbase_url: {getattr(llm, 'base_url', '')}\n"
                    f"model:    {getattr(llm, 'model', '')}\n"
                    f"key src:  {env_config.source_of('OPENAI_API_KEY') or 'sqlite'}\n"
                    f"reply:    {text}"
                )
                self.after(0, lambda: messagebox.showinfo("Test LLM", msg))
            except Exception as exc:
                self.after(0, lambda e=exc: messagebox.showerror("Test LLM", f"Failed:\n\n{e}"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_save(self) -> None:
        set_value("llm.provider", self.provider_var.get())
        set_value("llm.model", self.model_var.get())
        set_value("llm.base_url", self.url_var.get())
        set_secret("llm.api_key", self.api_var.get())
        set_value("llm.temperature", self.temp_var.get() or "0.2")
        set_value("llm.max_tokens", self.tokens_var.get() or "2048")
        get_manager().reload()
        self.destroy()
