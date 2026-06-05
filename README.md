# Query-Weaver

> A Python desktop client that turns natural language into SQL (or Mongo / Redis commands), executes it, and shows the result — all locally.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-CustomTkinter-1f6feb)](#)
[![LLM](https://img.shields.io/badge/LLM-LangChain%201.x-0aaa60)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

---

## Table of contents

- [Highlights](#highlights)
- [Screenshots & UI walkthrough](#screenshots--ui-walkthrough)
- [Project architecture](#project-architecture)
- [Directory layout](#directory-layout)
- [Quick start](#quick-start)
- [Usage flow](#usage-flow)
- [Configuration reference](#configuration-reference)
- [Security model](#security-model)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Development](#development)
- [License](#license)

---

## Highlights

- 🗄️ **Multi-database** — MySQL, PostgreSQL, Oracle (SQL); MongoDB, Redis (NoSQL)
- 🤖 **Multi-LLM** — any OpenAI-compatible endpoint (incl. DMX, Qwen, DeepSeek…) and local Ollama
- 💬 **Conversational chat** — round-trip memory, Markdown rendering, schema-aware system prompts
- 🎯 **Schema-tree focus** — click a database / table / column in the sidebar and the LLM gets that as context
- 🎨 **Light / dark theme** — live toggle, persisted across launches
- 💬 **Bubble UI** — rounded, role-coloured chat bubbles (user / assistant / system)
- 🛡️ **SQL safety guard** — read-only mode, dangerous-statement detection, confirmation prompts
- 📊 **Result viewer** — paginated tree view, CSV / Excel export
- 🔐 **Encrypted credentials** — Fernet (AES-128) at rest, Fernet key in `config/.key`
- 🪵 **Observable** — every LLM call prints request / response / error to terminal AND `logs/app.log`

---

## Screenshots & UI walkthrough

```
┌─ Query-Weaver ────────────────────────────────────────────────┐
│  Query-Weaver     [☀ Light]  [▶ Execute Last SQL]  [⚙ Settings]│
├──────────────┬────────────────────────────────────────────────┤
│ Connections  │  📁 Database focus: shop.order_items  (will...) │
│  +  ⟳        │ ─────────────────────────────────────────────  │
│ ▸ prod-mysql │  🧑 You                          12:04:32      │
│   staging    │   show me the top 5 customers last month      │
│              │                                                │
│ [T][E][Del]  │  🤖 Assistant                     12:04:35     │
│              │   Sure — here you go:                         │
│ Schema       │   ```sql                                       │
│ 📁 shop ★    │   SELECT c.id, c.name, SUM(oi.qty*oi.price)... │
│   📄 orders  │   ```                                          │
│   📄 users   │                                                │
│   📄 items   │ ─────────────────────────────────────────────  │
│              │  Result  12 rows  (47 ms)                      │
│              │  ┌────┬───────┬───────┐                        │
│              │  │ id │ name  │ total │                        │
│              │  │ 1  │ ACME  │ 12340 │                        │
│              │  └────┴───────┴───────┘                        │
│              │  [⏮ Prev]  Page: 1/1  [Next ⏭] [Export CSV]    │
│              │                                                │
│              │ [📝 type a question…          ] [Send] [🗑Clear]│
└──────────────┴────────────────────────────────────────────────┘
```

Top toolbar (left → right): app title · theme toggle · execute-last-SQL · settings.

Sidebar (left): saved connections list, action buttons (Test / Edit / Delete), and the schema tree. Clicking a node in the tree:
- Highlights it
- Shows a focus badge above the input box
- Injects the node into the next LLM call's system prompt so the model doesn't ask "which table did you mean?"

Chat panel (right): vertical paned window with conversation (top) and result viewer (bottom). Drag the sash to resize. New messages auto-scroll into view. The **🗑 Clear** button drops the current conversation without touching the database connection.

---

## Project architecture

```
┌────────────────────────────────────────────────────────────────┐
│  UI layer  (CustomTkinter)                                     │
│  ──────────────────────────                                    │
│  MainWindow                                                    │
│   ├─ Sidebar ─────► SchemaTree ─► emits focus events           │
│   └─ ChatPanel ──► MarkdownView, ResultViewer                 │
│         │                                                     │
│         │  builds messages + system prompt (with focus)        │
│         ▼                                                     │
│  LLM layer  (LangChain 1.x)                                    │
│  ──────────────────────────                                    │
│  Manager  ──►  OpenAILLM  (ChatOpenAI)                         │
│            └─►  OllamaLLM  (ChatOllama)                        │
│  Shared logging: _logging.py prints every request / response  │
│                  / error to stdout + logs/app.log              │
│         │                                                     │
│         │  prompt is: system (schema + focus) + user history   │
│         ▼                                                     │
│  Security layer                                               │
│  ──────────────                                                │
│  sql_guard.analyze(sql)  — read-only / DML / destructive check │
│         │                                                     │
│         │  pass → execute                                     │
│         ▼                                                     │
│  Database layer                                               │
│  ──────────────                                                │
│  BaseAdapter  ◄──  MySQL / PostgreSQL / Oracle / Mongo / Redis │
│       (connect · fetch_schema · execute · close)               │
└────────────────────────────────────────────────────────────────┘
```

### Key abstractions

| Module | Responsibility |
|---|---|
| `src/ui/main_window.py` | Top-level window, toolbar, theme toggle, dispatches sidebar callbacks. |
| `src/ui/sidebar.py` | Connection list, action buttons, hosts `SchemaTree`. |
| `src/ui/schema_tree.py` | ttk.Treeview of databases / tables / columns; emits `on_select` dicts. |
| `src/ui/chat_panel.py` | Chat history, input box, focus badge, LLM invocation, result hand-off. |
| `src/ui/widgets/markdown_view.py` | Lightweight Markdown → `tk.Text` renderer with light/dark palettes. |
| `src/ui/result_viewer.py` | ttk.Treeview of rows, paginated, with CSV/Excel export. |
| `src/ui/_theme.py` | Single source of truth for raw-Tk colors + ttk style application. |
| `src/llm/manager.py` | Picks the right LLM from env / settings, hands out one `BaseLLM`. |
| `src/llm/openai_llm.py` | `ChatOpenAI` wrapper + httpx hook to reject HTML error pages early. |
| `src/llm/ollama_llm.py` | `ChatOllama` wrapper. |
| `src/llm/_logging.py` | Pretty-prints every request / response / exception. |
| `src/security/sql_guard.py` | Tokenises SQL, classifies statements, blocks / warns. |
| `src/database/connector.py` | Connection profiles CRUD + `execute_on_connection`. |
| `src/database/adapters/*.py` | One per dialect; same interface (`connect/execute/fetch_schema/close`). |
| `src/database/schema_browser.py` | Per-profile schema cache, invalidation on connection delete. |
| `config/prompts.py` | SQL / Mongo / Redis system prompts (dialect-aware). |
| `config/settings.py` | Paths, default theme, version, DB-type allow-list, log rotation. |
| `src/core/config.py` | SQLite-backed key-value settings (`get_value` / `set_value`). |
| `src/core/crypto.py` | Fernet helpers for credentials at rest. |
| `src/core/logger.py` | loguru setup with file rotation. |

---

## Directory layout

```
Query-Weaver/
├── main.py                     # entry point — `python main.py`
├── requirements.txt
├── README.md / README-zh.md    # this file (English) and its Chinese sibling
├── prompt.txt                  # internal feature spec / todo list
│
├── config/
│   ├── settings.py             # paths, defaults, DB-type allow-list
│   ├── prompts.py              # LLM system prompts (dialect-aware)
│   └── .key                    # Fernet key — auto-generated, NEVER commit
│
├── src/
│   ├── core/                   # config / crypto / logger / env vars
│   ├── database/
│   │   ├── connector.py        # profiles CRUD + execute helper
│   │   ├── schema_browser.py   # per-profile schema cache
│   │   ├── local_db.py         # SQLite (settings + connection profiles)
│   │   └── adapters/           # one per database dialect
│   ├── llm/
│   │   ├── manager.py          # picks LLM based on env / settings
│   │   ├── openai_llm.py       # OpenAI-compatible endpoints
│   │   ├── ollama_llm.py       # local Ollama
│   │   ├── _logging.py         # request/response/error pretty-printer
│   │   └── base.py             # BaseLLM / LLMMessage / LLMResponse
│   ├── security/
│   │   └── sql_guard.py        # SQL classify + allow/deny
│   ├── ui/
│   │   ├── main_window.py      # top-level window + toolbar + theme toggle
│   │   ├── sidebar.py          # connection list + schema tree
│   │   ├── schema_tree.py      # ttk.Treeview of schema, emits focus events
│   │   ├── chat_panel.py       # chat + input + result hand-off
│   │   ├── result_viewer.py    # ttk.Treeview of query results
│   │   ├── settings_dialog.py  # connection + LLM settings + test
│   │   ├── _theme.py           # shared color palette
│   │   └── widgets/
│   │       ├── markdown_view.py  # Markdown → tk.Text renderer
│   │       └── sql_highlight.py  # Pygments-based SQL syntax highlighting
│   └── utils/
│       └── helpers.py          # extract_code_blocks, first_code_block, …
│
├── data/
│   └── app.db                  # SQLite (settings, connection profiles)
├── logs/
│   └── app.log                 # loguru-rotated (10 MB × 7 days)
├── resources/                  # icons (currently empty)
├── tests/
│   └── test_smoke.py           # pytest smoke tests
└── tools/
    └── diagnose_llm.py         # stand-alone LLM config / connectivity checker
```

---

## Quick start

### 1. Prerequisites

- **Python 3.10+**
- A working Tk installation (`tkinter` from your OS package manager, or "tcl/tk and IDLE" ticked in the Python installer)
- Database driver prerequisites (only the ones you need):
  - PostgreSQL — `libpq` (`brew install libpq` on macOS, `apt install libpq-dev` on Debian/Ubuntu, the official PostgreSQL installer on Windows)
  - Oracle — none if you stay on the default thin mode (`oracledb` is pure-Python)

### 2. Install

```bash
git clone <repo>
cd Query-Weaver
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure (one of these two paths)

**Path A — In-app (recommended for first run)**

1. `python main.py`
2. Click **⚙ Settings** → fill in provider, base URL, model, API key
3. Click **Test** — you should see a "pong" reply
4. Click **Save**

**Path B — `.env` (good for CI / docker / headless)**

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # or your gateway
OPENAI_MODEL=qwen-flash                    # optional, defaults to settings.py
```

Resolution order (highest priority first):
1. `process environment` (e.g. `OPENAI_API_KEY` exported in your shell)
2. `.env` in the project root
3. SQLite `settings` table populated via the Settings dialog

### 4. Add a database connection

1. Sidebar → **+** → choose DB type → fill in host / port / user / password / database
2. Click **Test** — confirms the adapter can open the connection
3. **Save** — credentials are encrypted with Fernet before being written to `data/app.db`
4. Click the new entry in the list — schema is fetched lazily and shown in the tree

### 5. Start chatting

- Type a question in the bottom input box → **Ctrl + Enter** (or click **Send**)
- Optional: click a database / table / column in the schema tree first — the focus badge appears above the input box and that selection is sent with your next question
- When the LLM replies with a fenced code block (```` ```sql ... ``` ````), click **▶ Execute Last SQL** to run it
- The result appears in the bottom pane of the chat panel, paginated and exportable

---

## Usage flow

### Schema-tree focus (the "AI knows which table you mean" feature)

1. Connect to a database — schema appears in the tree on the left
2. Click `📁 shop` (database), or `📄 users` (table), or a column leaf
3. A blue italic badge appears above the input box:

   ```
   📄 Table focus: shop.users  (will be sent with your next question)
   ```

4. Type a question — the LLM's system prompt now contains:

   ```
   The user has selected this in the schema tree:
   - Table: `shop.users`
   The user's next question is almost certainly about this object.
   Do not ask which table / column they meant.
   ```

5. Click the tree again to clear, or refresh the connection

### Theme switching

- Toolbar → **Light** / **Dark** button. The label always shows the action you're about to take (clicking "Light" while in dark mode switches to light).
- Persisted to the `ui.theme` setting — survives restarts
- All `tk.Listbox`, `ttk.Treeview`, and chat bubbles / MarkdownView re-style in place
- Toggling does not close any open dialogs

### Clear current conversation

- Bottom-right **🗑 Clear** button in the chat input bar
- Drops the in-memory LLM history, destroys all bubbles, resets the result viewer
- Does **not** touch the active database connection or the focus selection
- A "Conversation cleared. Still connected to X." system bubble is shown so you know it was intentional

### Executing queries

- **▶ Execute Last SQL** (toolbar) — extracts the last fenced code block from the last assistant message and runs it
- **SQL guard** intercepts:
  - `DROP` / `TRUNCATE` → blocked
  - `UPDATE` / `DELETE` without `WHERE` → blocked
  - `UPDATE` / `DELETE` with `WHERE` but the connection is read-only → blocked
  - All other DML → confirmation prompt ("This will modify data. Proceed?")
- The result viewer handles non-SELECT statements by showing a single info row (`"3 rows affected (12 ms)"`)
- Use **Export CSV** / **Export Excel** to save the result set

### Spinner vs. streaming

We do **not** stream tokens. While the LLM is working, the assistant bubble shows an animated spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) that updates every 120 ms. When the response arrives, the bubble is replaced with the real content and the conversation auto-scrolls to the bottom.

This is a deliberate trade-off: streaming is great for very fast models but makes it hard to debug failures, and most non-OpenAI providers don't support it cleanly. The full request / response is always printed to the terminal and to `logs/app.log` regardless.

---

## Configuration reference

### `config/settings.py` (code-level constants)

| Constant | Default | Notes |
|---|---|---|
| `APP_NAME` / `APP_VERSION` | `Query-Weaver` / `0.1.0` | shown in title bar |
| `WINDOW_DEFAULT_SIZE` | `1280x800` | Tk geometry string |
| `DEFAULT_THEME` | `dark` | first-run theme if `ui.theme` is unset |
| `DEFAULT_LLM_PROVIDER` | `openai` | `openai` or `ollama` |
| `DEFAULT_LLM_MODEL` | `mimo-v2.5` | the model name passed to the API |
| `MAX_RESULT_ROWS` | `1000` | hard cap on rows returned by any adapter |
| `QUERY_TIMEOUT_SEC` | `30` | per-statement timeout |
| `CHAT_HISTORY_LIMIT` | `50` | max messages kept in `_messages` |
| `LOG_ROTATION` / `LOG_RETENTION` | `10 MB` / `7 days` | loguru file rotation |

### Runtime settings (SQLite, set via Settings dialog)

| Key | Example | Purpose |
|---|---|---|
| `ui.theme` | `dark` / `light` | appearance mode |
| `llm.provider` | `openai` / `ollama` | which adapter to use |
| `llm.model` | `qwen-flash` | model name |
| `llm.base_url` | `https://www.dmxapi.cn/v1` | OpenAI-compatible base URL (or empty for default) |
| `llm.api_key` | (encrypted) | API key — stored Fernet-encrypted in `data/app.db` |
| `llm.temperature` | `0.0` | sampling temperature |
| `llm.max_tokens` | `2048` | max response length |

### Environment variables (override everything)

| Name | Notes |
|---|---|
| `OPENAI_API_KEY` | full key; takes precedence over settings |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL (with or without `/v1` suffix) |
| `OPENAI_MODEL` | default model name |
| `QWEN_API_KEY` | alias used by some providers |

`src/core/env_config.py` resolves the actual value as **env → .env → SQLite**, and prints where each value came from on first lookup (use the `tools/diagnose_llm.py` script to see them).

---

## Security model

- **Credentials at rest** — every password / API key is Fernet-encrypted before being written to `data/app.db`. The Fernet key lives in `config/.key` (auto-generated on first run, 600 permissions on Unix).
- **Read-only by default** — new SQL connections are created with `read_only=True`. A non-read-only connection is opt-in (check "Allow writes" in the connection dialog) and the SQL guard will still require a confirmation prompt before running any DML.
- **SQL guard** — uses `sqlparse` to tokenise the statement and applies these rules in order:
  1. `DROP` / `TRUNCATE` / `ALTER` / `GRANT` / `REVOKE` → **blocked**
  2. `INSERT` / `UPDATE` / `DELETE` without `WHERE`, or affecting all rows → **blocked**
  3. `UPDATE` / `DELETE` on a read-only connection → **blocked** (PermissionError)
  4. Any other DML → **requires confirmation** before execution
  5. `SELECT` / `WITH` / `EXPLAIN` / `SHOW` → **allowed**
- **No SQL injection in prompts** — the LLM is told to only use objects from the provided schema; the system prompt is rebuilt per-request from the actual `SchemaInfo` returned by the adapter.
- **Logs are local** — request / response / error traces are written to `logs/app.log` (rotated 10 MB × 7 days). Nothing is sent anywhere else.

---

## Troubleshooting & FAQ

### 🟡 "⚠️ LLM returned no content."

The model responded with an empty `content` field. The error message now prints which config is active; run `python tools/diagnose_llm.py` to see the raw request / response.

**Common causes:**

- **Wrong model name for the base URL** — the OpenAI-compatible gateway you point at may not have the model. The error message includes the actual model string. Check the gateway's model list and update Settings.
- **Wrong base URL** — some gateways expose their OpenAI-compatible endpoint at `/v1` (most) or `/v1/openai` (a few). The error message includes the URL.
- **HTML / proxy interception** — if the base URL is a CDN or WAF proxy, you may get an HTML error page. Our httpx hook intercepts that and raises `Server returned non-JSON response (status=200, content-type='text/html')`. Update the base URL to point at the real OpenAI-compatible API.
- **Rate limit** — the SDK retries automatically; if you keep seeing this, slow down or upgrade your plan.

### 🟡 `'str' object has no attribute 'model_dump'`

This is the **symptom** of an HTML / XML response that the openai SDK tried to parse as JSON. The fix is the new httpx event hook in `src/llm/openai_llm.py`; if you still see this, your LLM response is genuinely malformed — run `python tools/diagnose_llm.py` to capture the raw bytes.

### 🟡 Sidebar / connection list / schema tree backgrounds stay black in light mode

Fixed in the latest version. All raw-Tk widgets (`tk.Listbox`, `ttk.Treeview`) now use the shared `src/ui/_theme.py` palette and re-style on theme toggle. If you see a stray hardcoded color somewhere, add it to `_theme.py` and use `palette_for(mode)` instead of a literal hex value.

### 🟡 "Failed to fetch schema: …"

The connection works (Test passed) but the adapter's `fetch_schema()` failed. Common reasons:

- The user has no `SHOW DATABASES` / `SELECT * FROM information_schema.tables` privilege
- The connection is read-only AND the schema cache has been invalidated; some databases need write access to introspect

Try: edit the connection, uncheck "Allow writes" only if you actually need it.

### 🟡 MongoDB / Redis answers are not real SQL

That's expected. `config/prompts.py` switches the system prompt to a Mongo / Redis-specific one, and the LLM is told to emit a `json` aggregation pipeline (Mongo) or `bash`-fenced Redis commands. The result viewer displays the first column as the response, and "Export CSV" works on the parsed rows.

### 🟡 My result viewer says "No result" even though I ran a query

The query may have been a DML (`UPDATE` / `DELETE` / `INSERT`). The viewer renders a single-row "N rows affected" line in that case. If you expected a tabular result, check whether the LLM emitted a `SELECT`.

### 🟡 Can I import / export connections?

Not in v0.1. The `data/app.db` file is the source of truth. To move connections between machines, copy the file **and** `config/.key` (otherwise the encrypted credentials cannot be decrypted).

### 🟡 Does it run on macOS / Linux?

Yes. The only platform-specific code is `tkinter`, which is shipped with the official Python.org installers on all three OSes. Some Windows console codepages struggle with Unicode — if you see `UnicodeEncodeError` in the terminal, run `chcp 65001` first or set `PYTHONIOENCODING=utf-8`.

### 🟡 Will it support X?

See `prompt.txt` for the living feature spec. The current roadmap (extracted):

- Tabbed workspaces (one chat per DB)
- Query history & favourites
- SQL autocomplete
- Auto-charting (ECharts)
- Plugin system for new dialects
- i18n

---

## Development

```bash
# Run the app
python main.py

# Diagnose LLM config / connectivity
python tools/diagnose_llm.py

# Run the test suite
python -m pytest tests/
# or
python tests/test_smoke.py

# Watch the live log
tail -f logs/app.log
```

### Coding conventions

- All public methods carry a docstring explaining *why* (not *what* — the type signature is the *what*)
- Long-running work goes to a `threading.Thread(daemon=True)`; Tk widgets are only touched from the main thread via `self.after(0, ...)`
- Every new file that adds a Tk widget should also expose an `apply_theme(mode)` method and be wired into `MainWindow._toggle_theme`
- Anything that talks to the LLM should use `src.llm._logging._print_request` / `_print_response` / `_print_error`

### Adding a new database dialect

1. Create `src/database/adapters/<dialect>_adapter.py` subclassing `BaseAdapter`
2. Implement `connect`, `close`, `test`, `execute`, `fetch_schema`
3. Register it in `src/database/adapters/factory.py::get_adapter`
4. Add the type to `DB_TYPES` in `config/settings.py`
5. Add a row to the connection dialog's DB-type dropdown (already auto-populated from `DB_TYPES`)

---

## License

MIT. See [LICENSE](LICENSE) if present, otherwise the standard MIT terms apply.
