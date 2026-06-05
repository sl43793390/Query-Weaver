# Query-Weaver

> 基于 Python 的桌面客户端：把自然语言变成 SQL（或 MongoDB / Redis 命令），执行并展示结果 —— 全部本地完成。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-CustomTkinter-1f6feb)](#)
[![LLM](https://img.shields.io/badge/LLM-LangChain%201.x-0aaa60)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)

---

## 目录

- [核心特性](#核心特性)
- [界面一览](#界面一览)
- [项目架构](#项目架构)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [使用流程](#使用流程)
- [配置项](#配置项)
- [安全模型](#安全模型)
- [故障排查 & 常见问题](#故障排查--常见问题)
- [开发指南](#开发指南)
- [许可证](#许可证)

---

## 核心特性

- 🗄️ **多数据库** — MySQL、PostgreSQL、Oracle（SQL）；MongoDB、Redis（NoSQL）
- 🤖 **多 LLM** — 任意兼容 OpenAI 协议的端点（含 DMX、千问、DeepSeek…）以及本地 Ollama
- 💬 **对话式交互** — 多轮上下文、Markdown 渲染、感知 schema 的系统提示
- 🎯 **Schema 树焦点** — 在侧边栏点选一个库 / 表 / 字段，会随下一个问题自动发给 LLM
- 🎨 **明暗主题** — 工具栏一键切换，跨启动持久化
- 💬 **气泡式聊天** — 圆角气泡，按角色着色（用户 / 助手 / 系统）
- 🛡️ **SQL 安全守卫** — 只读模式、危险语句拦截、二次确认
- 📊 **结果查看器** — 分页 Treeview、CSV / Excel 一键导出
- 🔐 **凭据加密** — Fernet（AES-128）静态加密存储
- 🪵 **可观测** — 每次 LLM 调用的请求 / 响应 / 错误都会打印到终端 **和** `logs/app.log`

---

## 界面一览

```
┌─ Query-Weaver ────────────────────────────────────────────────┐
│  Query-Weaver     [☀ Light]  [▶ Execute Last SQL]  [⚙ Settings]│
├──────────────┬────────────────────────────────────────────────┤
│ Connections  │  📁 Database focus: shop.order_items  (will...) │
│  +  ⟳        │ ─────────────────────────────────────────────  │
│ ▸ prod-mysql │  🧑 You                          12:04:32      │
│   staging    │   查上月消费前 5 名的客户                       │
│              │                                                │
│ [Test][Edit] │  🤖 Assistant                     12:04:35     │
│ [ Delete ]   │   好的，SQL 如下：                              │
│              │   ```sql                                       │
│ Schema       │   SELECT c.id, c.name, SUM(oi.qty*oi.price)... │
│ 📁 shop ★    │   ```                                          │
│   📄 orders  │                                                │
│   📄 users   │ ─────────────────────────────────────────────  │
│   📄 items   │  Result  12 rows  (47 ms)                      │
│              │  ┌────┬───────┬───────┐                        │
│              │  │ id │ name  │ total │                        │
│              │  │ 1  │ ACME  │ 12340 │                        │
│              │  └────┴───────┴───────┘                        │
│              │  [⏮ Prev]  Page: 1/1  [Next ⏭] [Export CSV]    │
│              │                                                │
│              │ [📝 输入问题…                  ] [Send] [🗑Clear]│
└──────────────┴────────────────────────────────────────────────┘
```

顶部工具栏（左 → 右）：应用名 · 主题切换 · 执行上一条 SQL · 设置。

左侧栏：保存的连接列表、操作按钮（Test / Edit / Delete）、Schema 树。点击树中的节点会：
- 高亮该节点
- 在输入框上方显示一个 focus 提示徽章
- 把该节点注入下一次 LLM 调用的系统提示里，避免它问"你说的是哪个表？"

右侧聊天面板：上下可拖动分隔的窗格（聊天历史 + 结果查看器）。新消息自动滚到底，**🗑 Clear** 按钮可清空当前对话而不影响数据库连接。

---

## 项目架构

```
┌────────────────────────────────────────────────────────────────┐
│  UI 层  (CustomTkinter)                                        │
│  ──────────────                                                │
│  MainWindow                                                    │
│   ├─ Sidebar ──► SchemaTree ──► 发出 focus 事件                │
│   └─ ChatPanel ──► MarkdownView, ResultViewer                  │
│         │                                                     │
│         │  组装 messages + system prompt（带 focus）            │
│         ▼                                                     │
│  LLM 层  (LangChain 1.x)                                       │
│  ──────────────                                                │
│  Manager  ──►  OpenAILLM  (ChatOpenAI)                         │
│            └─►  OllamaLLM  (ChatOllama)                        │
│  共享日志: _logging.py 打印每次 request / response / error     │
│           到 stdout + logs/app.log                             │
│         │                                                     │
│         │  prompt = system (schema + focus) + 用户历史         │
│         ▼                                                     │
│  安全层                                                        │
│  ──────                                                        │
│  sql_guard.analyze(sql)  — 只读 / DML / 危险语句检测            │
│         │                                                     │
│         │  pass → 执行                                        │
│         ▼                                                     │
│  数据库层                                                      │
│  ──────                                                        │
│  BaseAdapter  ◄──  MySQL / PostgreSQL / Oracle / Mongo / Redis │
│       (connect · fetch_schema · execute · close)               │
└────────────────────────────────────────────────────────────────┘
```

### 关键模块

| 模块 | 职责 |
|---|---|
| `src/ui/main_window.py` | 顶层窗口、工具栏、主题切换、分发侧边栏回调。 |
| `src/ui/sidebar.py` | 连接列表、操作按钮，承载 `SchemaTree`。 |
| `src/ui/schema_tree.py` | 用 ttk.Treeview 渲染库 / 表 / 字段，emit `on_select` 字典。 |
| `src/ui/chat_panel.py` | 聊天历史、输入框、focus 徽章、调用 LLM、把结果交给 ResultViewer。 |
| `src/ui/widgets/markdown_view.py` | 轻量级 Markdown → `tk.Text` 渲染器，支持明暗主题色板。 |
| `src/ui/result_viewer.py` | 用 ttk.Treeview 展示结果行，分页、CSV/Excel 导出。 |
| `src/ui/_theme.py` | raw-Tk 颜色 + ttk 样式的唯一来源。 |
| `src/llm/manager.py` | 根据 env / settings 选 LLM，给上层一个 `BaseLLM`。 |
| `src/llm/openai_llm.py` | `ChatOpenAI` 包装 + httpx hook（提前拦截 HTML 错误页）。 |
| `src/llm/ollama_llm.py` | `ChatOllama` 包装。 |
| `src/llm/_logging.py` | 美化打印每次 request / response / exception。 |
| `src/security/sql_guard.py` | 切词、分类、拦截 / 警告。 |
| `src/database/connector.py` | 连接配置 CRUD + `execute_on_connection`。 |
| `src/database/adapters/*.py` | 一种方言一个实现，统一接口。 |
| `src/database/schema_browser.py` | 每个 profile 的 schema 缓存，连接删除时失效。 |
| `config/prompts.py` | SQL / Mongo / Redis 的方言感知系统提示。 |
| `config/settings.py` | 路径、默认主题、版本、数据库类型白名单、日志切割。 |
| `src/core/config.py` | SQLite 存键值设置（`get_value` / `set_value`）。 |
| `src/core/crypto.py` | Fernet 加密 / 解密工具。 |
| `src/core/logger.py` | loguru 配置 + 文件切割。 |

---

## 目录结构

```
Query-Weaver/
├── main.py                     # 启动入口 — `python main.py`
├── requirements.txt
├── README.md / README-zh.md    # 本文件（中文）及英文版
├── prompt.txt                  # 内部需求 / TODO
│
├── config/
│   ├── settings.py             # 路径、默认值、数据库类型白名单
│   ├── prompts.py              # LLM 系统提示（按方言）
│   └── .key                    # Fernet 密钥 — 自动生成，**绝对不要提交**
│
├── src/
│   ├── core/                   # config / crypto / logger / env
│   ├── database/
│   │   ├── connector.py        # profiles CRUD + execute
│   │   ├── schema_browser.py   # 每个 profile 的 schema 缓存
│   │   ├── local_db.py         # SQLite（设置 + 连接配置）
│   │   └── adapters/           # 每种方言一个 adapter
│   ├── llm/
│   │   ├── manager.py          # 根据 env / settings 选 LLM
│   │   ├── openai_llm.py       # 兼容 OpenAI 的端点
│   │   ├── ollama_llm.py       # 本地 Ollama
│   │   ├── _logging.py         # request/response/error 打印器
│   │   └── base.py             # BaseLLM / LLMMessage / LLMResponse
│   ├── security/
│   │   └── sql_guard.py        # SQL 分类 + 允许 / 拒绝
│   ├── ui/
│   │   ├── main_window.py      # 顶层窗口 + 工具栏 + 主题切换
│   │   ├── sidebar.py          # 连接列表 + schema 树
│   │   ├── schema_tree.py      # ttk.Treeview，emit focus 事件
│   │   ├── chat_panel.py       # 聊天 + 输入 + 提交结果
│   │   ├── result_viewer.py    # ttk.Treeview 结果
│   │   ├── settings_dialog.py  # 连接 + LLM 设置 + 测试
│   │   ├── _theme.py           # 共享色板
│   │   └── widgets/
│   │       ├── markdown_view.py  # Markdown → tk.Text
│   │       └── sql_highlight.py  # Pygments SQL 高亮
│   └── utils/
│       └── helpers.py          # extract_code_blocks 等
│
├── data/
│   └── app.db                  # SQLite（设置、连接配置）
├── logs/
│   └── app.log                 # loguru 切割（10 MB × 7 天）
├── resources/                  # 图标（目前空）
├── tests/
│   └── test_smoke.py           # pytest 冒烟测试
└── tools/
    └── diagnose_llm.py         # 独立 LLM 配置 / 连通性诊断脚本
```

---

## 快速开始

### 1. 环境要求

- **Python 3.10+**
- 正常工作的 Tk（`tkinter`，在 Python 安装器里勾选 "tcl/tk and IDLE"，或从系统包管理器装）
- 数据库驱动的前置依赖（按需安装）：
  - PostgreSQL — `libpq`（macOS: `brew install libpq`、Debian/Ubuntu: `apt install libpq-dev`、Windows 用官方安装包）
  - Oracle — 默认 thin 模式无需 Instant Client

### 2. 安装

```bash
git clone <repo>
cd Query-Weaver
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置（两条路任选其一）

**A. 在应用内配置（首次推荐）**

1. `python main.py`
2. 点 **⚙ Settings** → 填 provider、base URL、model、API key
3. 点 **Test** —— 应该看到 "pong" 之类的回包
4. 点 **Save**

**B. 用 `.env`（适合 CI / Docker / 无头）**

```env
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1   # 或你的中转
OPENAI_MODEL=qwen-flash                    # 可选
```

解析优先级（高 → 低）：
1. 进程环境变量（如 shell 里 `export OPENAI_API_KEY=...`）
2. 项目根目录的 `.env`
3. SQLite `settings` 表（由 Settings 弹窗写入）

### 4. 添加数据库连接

1. 侧边栏 **+** → 选数据库类型 → 填 host / port / user / password / database
2. **Test** —— 确认 adapter 能连上
3. **Save** —— 凭据用 Fernet 加密后写入 `data/app.db`
4. 在列表里点新增的条目 —— 懒加载 schema，渲染到 Schema 树

### 5. 开始聊天

- 在底部输入框打字 → **Ctrl + Enter**（或点 **Send**）
- 可选：先在 Schema 树点选库 / 表 / 字段，focus 徽章会出现在输入框上方，并随你的下一个问题一起发给 LLM
- LLM 在回复里出现 ```` ```sql ... ``` ```` 时，点 **▶ Execute Last SQL** 执行
- 结果出现在聊天面板下半部分，可分页、可导出

---

## 使用流程

### Schema 树焦点（"AI 知道你说的是哪个表" 功能）

1. 选中数据库连接 —— Schema 出现在左侧树里
2. 点击 `📁 shop`（库）、`📄 users`（表）或某一列的叶节点
3. 输入框上方出现一个蓝色斜体徽章：

   ```
   📄 Table focus: shop.users  (will be sent with your next question)
   ```

4. 输入问题 —— LLM 收到的 system prompt 会包含：

   ```
   The user has selected this in the schema tree:
   - Table: `shop.users`
   The user's next question is almost certainly about this object.
   Do not ask which table / column they meant.
   ```

5. 再次点击树节点可清除，或点连接名重置

### 主题切换

- 工具栏 **Light** / **Dark** 按钮。按钮文字永远显示"将要切到什么"（在 dark 模式下显示 Light）。
- 写入 `ui.theme` 设置项，跨启动保留
- `tk.Listbox`、`ttk.Treeview`、所有气泡和 MarkdownView 全部原地换色
- 切换不会关闭任何已打开的对话框

### 清空当前会话

- 聊天输入栏右下角 **🗑 Clear** 按钮
- 清空内存里的 LLM 历史、销毁所有气泡、重置结果查看器
- **不会** 触碰当前数据库连接或焦点选择
- 会插入一个 `_Conversation cleared. Still connected to X._` 的系统气泡，明确告诉你这是有意为之

### 执行查询

- **▶ Execute Last SQL**（工具栏）—— 解析最后一条助手消息中最后一个 fenced 代码块并执行
- **SQL 守卫** 拦截规则：
  - `DROP` / `TRUNCATE` → 拦截
  - 没有 `WHERE` 的 `UPDATE` / `DELETE` → 拦截
  - 有 `WHERE` 但连接是只读 → 拦截
  - 其他 DML → 弹窗二次确认（"This will modify data. Proceed?"）
  - `SELECT` / `WITH` / `EXPLAIN` / `SHOW` → 放行
- 非 `SELECT` 语句在结果查看器里显示为单行信息（`"3 rows affected (12 ms)"`）
- 用 **Export CSV** / **Export Excel** 保存结果

### Spinner vs 流式

我们**不做流式**。LLM 思考期间，助手气泡里是一个动画 spinner（`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`），每 120 ms 切一帧。响应到达后，气泡被替换为真实内容，对话自动滚到底。

这是有意为之：流式对快模型友好，但失败时很难定位，而大多数非 OpenAI 提供方对流式支持都不干净。每次请求 / 响应 / 错误都会完整打印到终端和 `logs/app.log`。

---

## 配置项

### `config/settings.py`（代码级常量）

| 常量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` / `APP_VERSION` | `Query-Weaver` / `0.1.0` | 显示在标题栏 |
| `WINDOW_DEFAULT_SIZE` | `1280x800` | Tk 几何字符串 |
| `DEFAULT_THEME` | `dark` | 首次运行主题（若 `ui.theme` 未设置） |
| `DEFAULT_LLM_PROVIDER` | `openai` | `openai` 或 `ollama` |
| `DEFAULT_LLM_MODEL` | `mimo-v2.5` | 默认 model 名 |
| `MAX_RESULT_ROWS` | `1000` | adapter 返回行数硬上限 |
| `QUERY_TIMEOUT_SEC` | `30` | 单语句超时 |
| `CHAT_HISTORY_LIMIT` | `50` | 内存里保留的最大消息数 |
| `LOG_ROTATION` / `LOG_RETENTION` | `10 MB` / `7 days` | loguru 切割策略 |

### 运行时设置（SQLite，由 Settings 弹窗写入）

| Key | 示例 | 用途 |
|---|---|---|
| `ui.theme` | `dark` / `light` | 主题 |
| `llm.provider` | `openai` / `ollama` | adapter 选择 |
| `llm.model` | `qwen-flash` | 模型名 |
| `llm.base_url` | `https://www.dmxapi.cn/v1` | OpenAI 兼容 base URL（空 = 默认） |
| `llm.api_key` | （加密） | API key，Fernet 加密存于 `data/app.db` |
| `llm.temperature` | `0.0` | 采样温度 |
| `llm.max_tokens` | `2048` | 最大输出 token |

### 环境变量（优先级最高）

| 名 | 说明 |
|---|---|
| `OPENAI_API_KEY` | 完整 key；优先于 settings |
| `OPENAI_BASE_URL` | OpenAI 兼容 base URL（有无 `/v1` 后缀均可） |
| `OPENAI_MODEL` | 默认 model 名 |
| `QWEN_API_KEY` | 一些中转的别名 |

`src/core/env_config.py` 按 **env → .env → SQLite** 顺序解析，并在首次查询时打印来源（用 `python tools/diagnose_llm.py` 可一次性看到全部）。

---

## 安全模型

- **凭据静态加密** —— 所有密码 / API key 写入 `data/app.db` 之前先 Fernet 加密。Fernet 密钥在 `config/.key`（首次运行自动生成，Unix 上权限 600）
- **默认只读** —— 新建 SQL 连接默认 `read_only=True`。要写就勾选 "Allow writes"，但 SQL 守卫依然会要求二次确认
- **SQL 守卫** —— 用 `sqlparse` 切词，按顺序应用规则：
  1. `DROP` / `TRUNCATE` / `ALTER` / `GRANT` / `REVOKE` → **拦截**
  2. 无 `WHERE` 的 `INSERT` / `UPDATE` / `DELETE` → **拦截**
  3. 只读连接上的 `UPDATE` / `DELETE` → **拦截**（PermissionError）
  4. 其他 DML → **要求确认**
  5. `SELECT` / `WITH` / `EXPLAIN` / `SHOW` → **放行**
- **提示词中无 SQL 注入风险** —— LLM 被强制使用"提供的 schema 中存在的对象"；system prompt 每次请求都从 adapter 实际返回的 `SchemaInfo` 重新组装
- **日志全部本地** —— 请求 / 响应 / 错误落到 `logs/app.log`（10 MB × 7 天切割），不会外发

---

## 故障排查 & 常见问题

### 🟡 "⚠️ LLM returned no content."

模型回了空 `content`。报错信息现在会打印当前生效的配置；运行 `python tools/diagnose_llm.py` 看完整 request / response。

**常见原因：**

- **model 名跟 base URL 不匹配** —— 中转商可能没有这个 model。错误信息里能看到 model 字符串，去中转的 model 列表里核对，去 Settings 改
- **base URL 写错** —— 多数中转是 `/v1`，少数是 `/v1/openai`。错误信息里有完整 URL
- **HTML / 代理拦截** —— 如果 base URL 是个 CDN / WAF，会回 HTML 错误页。httpx hook 会拦截并抛 `Server returned non-JSON response (status=200, content-type='text/html')`。把 base URL 改成真正的 OpenAI 兼容端点
- **限流** —— SDK 会自动重试；持续出现就降速或升级套餐

### 🟡 `'str' object has no attribute 'model_dump'`

这是**症状**：openai SDK 试图把 HTML / XML 当 JSON 解析。新加的 httpx event hook 已经能拦下大部分这种情况；如果还出现，说明响应体真的畸形，跑 `python tools/diagnose_llm.py` 抓原始字节

### 🟡 Light 主题下连接列表 / Schema 树 / 结果框还是黑底

最新版本已修复。所有 raw-Tk 控件（`tk.Listbox`、`ttk.Treeview`）都从 `src/ui/_theme.py` 取色，主题切换时原地换色。如果发现还有硬编码颜色，挪到 `_theme.py` 里用 `palette_for(mode)` 取，别直接写 hex

### 🟡 "Failed to fetch schema: …"

连接本身 OK（Test 过了），但 adapter 抓 schema 失败。常见原因：

- 当前用户没有 `SHOW DATABASES` / `information_schema.tables` 的 SELECT 权限
- 连接是只读 + schema 缓存被清空；某些库抓 schema 需要写权限

处理：编辑连接，把 "Allow writes" 勾上（如果确实需要的话）

### 🟡 MongoDB / Redis 的回答不是真 SQL

是预期的。`config/prompts.py` 会把 system prompt 切到 Mongo / Redis 版本，让 LLM 输出 `json` 聚合管道（Mongo）或 `bash` 围栏的 Redis 命令。结果查看器按列展示，且 Export CSV 可以工作

### 🟡 "No result" 但我确实跑了查询

可能是 DML（`UPDATE` / `DELETE` / `INSERT`）。这种语句在结果查看器里渲染为单行 "N rows affected"。如果期待表格结果，看一下 LLM 有没有输出 `SELECT`

### 🟡 能导入 / 导出连接吗？

v0.1 还不支持。`data/app.db` 是单一数据源。要在机器间迁移，把 `data/app.db` **和** `config/.key` 一起复制（不然加密的凭据解不开）

### 🟡 能在 macOS / Linux 上跑吗？

可以。唯一的平台相关代码是 `tkinter`，Python.org 安装器三大系统都自带。Windows 控制台默认 GBK 编码，看到 `UnicodeEncodeError` 就 `chcp 65001` 或者 `set PYTHONIOENCODING=utf-8`

### 🟡 未来会支持 X？

参考 `prompt.txt`。当前路线图（摘自 prompt）：

- 多 Tab 工作区（每个库一个聊天）
- 查询历史 & 收藏
- SQL 自动补全
- 自动出图（ECharts）
- 插件化方言适配器
- 国际化（i18n）

---

## 开发指南

```bash
# 跑应用
python main.py

# 诊断 LLM 配置 / 连通性
python tools/diagnose_llm.py

# 跑测试
python -m pytest tests/
# 或
python tests/test_smoke.py

# 实时盯日志
tail -f logs/app.log
```

### 编码约定

- 所有 public 方法都要带 docstring，重点说 **为什么**（类型签名已经说明 **是什么**）
- 长时间操作放进 `threading.Thread(daemon=True)`；Tk 控件只能在主线程通过 `self.after(0, ...)` 触碰
- 新增 Tk 控件的文件必须暴露 `apply_theme(mode)`，并接入 `MainWindow._toggle_theme`
- 跟 LLM 打交道的代码都用 `src.llm._logging._print_request` / `_print_response` / `_print_error`

### 新增一种数据库方言

1. 新建 `src/database/adapters/<dialect>_adapter.py` 继承 `BaseAdapter`
2. 实现 `connect`、`close`、`test`、`execute`、`fetch_schema`
3. 在 `src/database/adapters/factory.py::get_adapter` 注册
4. 把新类型加到 `config/settings.py` 的 `DB_TYPES`
5. 连接弹窗的 DB-type 下拉框会自动列出新类型

---

## 许可证

MIT
