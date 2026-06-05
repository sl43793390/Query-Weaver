"""Application-wide constants and default settings."""
from __future__ import annotations

from pathlib import Path

# ----- Paths -----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CONFIG_DIR = PROJECT_ROOT / "config"
RESOURCES_DIR = PROJECT_ROOT / "resources"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

LOCAL_DB_PATH = DATA_DIR / "app.db"
KEY_FILE_PATH = CONFIG_DIR / ".key"

# ----- UI Defaults -----
APP_NAME = "Query-Weaver"
APP_VERSION = "0.1.0"
WINDOW_DEFAULT_SIZE = "1280x800"
THEMES = ("light", "dark")
DEFAULT_THEME = "dark"

# ----- LLM Defaults -----
LLM_PROVIDERS = {
    "openai": "OpenAI Compatible",
    "ollama": "Ollama (local)",
}
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_MODEL = "mimo-v2.5"

# ----- Database Types -----
DB_TYPES = ("mysql", "postgresql", "oracle", "mongodb", "redis")
SQL_DB_TYPES = ("mysql", "postgresql", "oracle")
NOSQL_DB_TYPES = ("mongodb", "redis")

# ----- Limits -----
MAX_RESULT_ROWS = 1000
QUERY_TIMEOUT_SEC = 30
CHAT_HISTORY_LIMIT = 50

# ----- Logging -----
LOG_LEVEL = "INFO"
LOG_ROTATION = "10 MB"
LOG_RETENTION = "7 days"
