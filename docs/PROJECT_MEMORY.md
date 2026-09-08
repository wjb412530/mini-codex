# mini-codex 项目记忆文档（Project Memory）

> 本文档是 `mini-codex` 项目的完整知识库与迁移手册，包含：项目理解、整体架构、实现流程、完整文件清单、依赖关系、配置说明、**可复现的完整迁移步骤**，以及**近期变更记录**。目标读者：任何需要接手、维护或从零重建本项目的开发者。

---

## 目录

1. [项目概述与理解](#1-项目概述与理解)
2. [整体架构](#2-整体架构)
3. [完整目录与文件清单](#3-完整目录与文件清单)
4. [模块详解](#4-模块详解)
5. [核心实现流程](#5-核心实现流程)
6. [关键类与函数速查表](#6-关键类与函数速查表)
7. [依赖关系](#7-依赖关系)
8. [配置清单](#8-配置清单)
9. [完整迁移指南](#9-完整迁移指南)
10. [已知权衡与注意点](#10-已知权衡与注意点)
11. [变更记录](#11-变更记录)

---

## 1. 项目概述与理解

### 1.1 项目定位

`mini-codex` 是一个**独立开发、轻量级的 AI 结对编程智能体（终端 CLI）**。它由大语言模型（Qwen、DeepSeek、Kimi、GLM、Claude 等）驱动，在终端中提供流畅的结对编程体验：读文件、写文件、执行命令，并通过「思考 → 调用工具 → 观察结果 → 再思考」的自动循环完成任务。

### 1.2 核心价值

- 用**纯 Python + asyncio**实现了一个完整可运行的 AI Agent 最小闭环。
- 通过**策略模式 + 注册表模式**实现 Provider 与 Tool 的可插拔，是学习 Agent 架构的典型范例。
- 内置**三层命令安全防线**（破坏性命令拦截 / 注入拦截 / 白名单沙盒判定）。
- 提供**跨会话记忆**（`.ai_memory`）与 **MCP 插件**扩展能力。
- **默认走 OpenAI 兼容协议接入国内大模型（通义千问 Qwen）**，无需 anthropic。

### 1.3 技术栈

| 类别 | 选型 |
|------|------|
| 语言 / 运行时 | Python >= 3.9（开发环境 3.10），全异步 `asyncio` |
| 参数校验 | `pydantic v2`（工具参数 Schema + JSON Schema 生成） |
| 模型 SDK | `openai`（兼容协议，默认）；`anthropic`（Claude，可选） |
| 终端 UI | `rich`（ANSI 渲染）+ `prompt_toolkit`（交互输入） |
| 配置加载 | `python-dotenv` |
| 打包 / 安装 | `setuptools` + `pyproject.toml`；推荐用 `pipx` 全局安装 |
| 测试 | `pytest`（`asyncio_mode = auto`） |

### 1.4 关键设计决策

1. **策略模式（Provider 层）**：抽象类 `LLMProvider` 定义 `send_message` / `send_tool_results` 两个核心协议，`OpenAIProvider` 与 `AnthropicProvider` 各自实现。`Agent` 只依赖抽象，不依赖具体实现。
2. **注册表模式（Tool 层）**：`ToolRegistry` 全局单例统一管理工具，支持别名派发（如 `Bash` ↔ `BashTool`），Agent 通过名称动态查找工具。
3. **Pydantic 驱动工具 Schema**：每个 `BaseTool` 定义一个 `args_schema`（Pydantic 模型），`to_openai_schema()` 用 `model_json_schema()` 自动生成 LLM 可用的 JSON Schema。
4. **流式 + 思维链（可开关）**：OpenAI Provider 逐 chunk 累积 `reasoning_content`（思维链）与 `content`（正文）并实时回调终端；由 `SHOW_THINKING` 控制是否请求/展示思维链。
5. **文件系统记忆**：不依赖数据库，用 `.ai_memory/global_memory.txt` 持久化，注入 System Prompt，超 5000 字符截断防 Token 爆炸。
6. **anthropic 惰性导入**：`anthropic` 为可选依赖，仅在 `provider=anthropic` 时惰性导入，`import mini_codex` 无需 anthropic。

---

## 2. 整体架构

### 2.1 分层架构图

```
                    ┌─────────────────────────────┐
                    │        CLI 入口 (cli/main)    │
                    │  参数解析 / 斜杠命令 / 主循环   │
                    └──────────────┬──────────────┘
                                   │ 构建 Provider + Agent
                    ┌──────────────▼──────────────┐
                    │       Agent (core/agent)     │
                    │  协调者：核心循环 + 工具派发    │
                    └───────┬──────────────┬───────┘
                            │              │
              ┌─────────────▼─────┐   ┌────▼──────────────────┐
              │ LLMProvider(抽象) │   │  ToolRegistry(注册表)   │
              │  ├ OpenAIProvider │   │  ├ Bash / FileRead     │
              │  └ Anthropic(可选)│   │  ├ FileWrite / AddMem  │
              └─────────┬─────────┘   │  ├ GitStatus / Agent   │
                        │             │  └ MCP(动态)           │
           ┌────────────▼───────────┐ │  ┌────────▼────────┐
           │ 云端大模型 API           │ │  │ security 三层安全 │
           └────────────────────────┘ │  └─────────────────┘
```

### 2.2 模块分层职责

| 层 | 目录 | 职责 |
|----|------|------|
| 表现层 | `cli/` | 命令行参数、斜杠命令、交互式主循环 |
| 编排层 | `core/agent.py` | Agent 循环（思考→工具→观察） |
| 模型层 | `core/providers/` | LLM 抽象与多 Provider 实现 |
| 记忆层 | `core/memory.py` | `.ai_memory` 持久化记忆 + AddMemoryTool |
| 工具层 | `tools/` | 工具基类、注册表、内置工具、安全 |
| 配置层 | `config/` | 三级优先级配置 + 首次运行引导 |
| 基础设施 | `utils/` `buddy/` | 终端输出 / 彩蛋 |

---

## 3. 完整目录与文件清单

> 以下为项目全部「源文件」（不含 `venv/`、`__pycache__/`、`.git/`、运行时产物 `.ai_memory/`）。

```
mini-codex/
├── .env.example                    # 环境变量模板
├── .gitignore                      # Git 忽略规则
├── LICENSE                         # MIT 协议
├── pyproject.toml                  # 打包/依赖/入口/测试配置
├── README.md                       # 项目首页文档
├── mini-codex.md                   # 本文档（项目记忆）
├── docs/
│   └── images/logo.jpg             # 项目 Logo（README 引用）
├── src/
│   └── mini_codex/
│       ├── __init__.py             # 包入口，导出公共 API（不预加载 anthropic）
│       ├── main.py                 # 入口，委托 cli.main.run_cli
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py             # parse_args / handle_command / main_loop / run_cli
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py         # 配置读写 + check_first_run_setup
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py            # Agent 核心循环
│       │   ├── memory.py           # MemoryManager + AddMemoryTool
│       │   └── providers/
│       │       ├── __init__.py     # create_provider 工厂（anthropic 惰性导入）
│       │       ├── base.py         # LLMProvider 抽象基类
│       │       ├── openai_provider.py     # 含 show_thinking 开关
│       │       └── anthropic_provider.py  # 可选
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── base.py             # BaseTool + 旧版 Tool/register_tool
│       │   ├── registry.py         # ToolRegistry 单例
│       │   ├── bash.py             # BashTool
│       │   ├── file_read.py        # FileReadTool
│       │   ├── file_write.py       # FileWriteTool
│       │   ├── git_status_tool.py  # GitStatusTool
│       │   ├── agent_tool.py       # AgentTool（子代理）
│       │   ├── mcp_tool.py         # MCPTool + load_mcp_tools_from_config
│       │   └── security/
│       │       ├── __init__.py
│       │       ├── destructive_warning.py   # is_destructive_command
│       │       ├── bash_security.py         # check_bash_security
│       │       └── should_sandbox.py        # should_use_sandbox / strip_wrappers
│       ├── utils/
│       │   ├── __init__.py
│       │   └── console.py          # rich 主题 + print_welcome
│       └── buddy/
│           ├── __init__.py
│           └── companion.py        # mulberry32 + spawn_buddy
└── tests/
    ├── conftest.py                 # 路径注入
    ├── test_agent.py
    ├── test_bash_tool.py
    ├── test_file_tools.py
    ├── test_memory.py
    └── test_security.py
```

**源文件统计**：36 个 `.py`（含 5 个测试 + conftest），7 个非代码文件（pyproject / README / mini-codex.md / LICENSE / .env.example / .gitignore / logo.jpg）。

---

## 4. 模块详解

### 4.1 `config/settings.py` — 配置管理

- 配置目录：`~/.mini-codex/config.json`（`Path.home() / ".mini-codex"`）。
- `get_config_value(key, default)` 三级优先级：**环境变量(含 .env) > config.json > 默认值**。
- `check_first_run_setup()`：无 API Key 时用 `rich.prompt.Prompt` 交互式引导（选择 openai/anthropic）。
- 模块导入即执行 `load_dotenv()`。

### 4.2 `core/providers/` — LLM Provider 层

| 文件 | 类 | 说明 |
|------|-----|------|
| `base.py` | `LLMProvider(ABC)` | 抽象协议：`send_message` / `send_tool_results` |
| `openai_provider.py` | `OpenAIProvider` | `AsyncOpenAI`，流式 + 思维链（可开关）+ Function Calling |
| `anthropic_provider.py` | `AnthropicProvider` | `AsyncAnthropic`，`messages.stream` + 独立 system 参数（可选依赖，惰性导入） |
| `__init__.py` | `create_provider()` | 工厂：按 `provider_type` 返回实例；读取 `SHOW_THINKING` |

- OpenAI：构造请求 `temperature=0.2, stream=True`；`show_thinking=True` 时才传 `extra_body={"enable_thinking": True}`。工具参数 JSON 解析失败时回退 `_fix_json_string`，仍失败则返回 `{"_parse_error": True}` 交由 Agent 处理。
- Anthropic：`system` 单独传参，工具用 `input_schema`，工具结果包在 `role="user"` 的 `tool_result` 里。
- 两个 Provider 都在 System Prompt 内置「防覆盖」约定（新建文件时 `require_new=true`）。

### 4.3 `core/agent.py` — Agent 核心循环

- 常量 `MAX_AGENT_LOOPS = 30` 防无限循环。
- `Agent(provider)`：协调者，不直接处理 LLM/工具细节。
- `chat(user_input, on_text_response)`：单轮入口，内部 `while response["toolCalls"]` 循环。
- `handle_tool_calls(tool_calls)`：遍历 → 解析错误检查 → `registry.get_tool(name)` → `await tool.execute(**args)` → 收集 `{id, result, isError}`。
- `clear_history()`：只保留首条 system 消息。

### 4.4 `core/memory.py` — 记忆系统

- `MemoryManager(workspace_dir=".")`：管理 `.ai_memory/global_memory.txt`。
- `get_global_memory()`：读到 5000 字符强制截断（保留末尾）；`add_memory()` 追加带时间戳。
- `AddMemoryTool`（name=`AddMemory`）：让模型主动把规则写入记忆，在 `registry` 底部延迟注册。

### 4.5 `tools/` — 工具系统

**基类 `base.py`**：`BaseTool`（新式，Pydantic）提供 `to_openai_schema()`；另有旧版 `Tool` dataclass + `register_tool` 装饰器用于向后兼容。

**注册表 `registry.py`**：全局单例 `registry`，启动时注册：
- `BashTool`（别名 `BashTool`）、`FileReadTool`、`FileWriteTool`
- `AgentTool`（别名 `Agent`、`SubAgent`）、`GitStatusTool`（别名 `Git`、`GitStatusTool`）
- MCP 工具（`load_mcp_tools_from_config()` 动态）
- `AddMemoryTool`（末尾延迟注册，避免循环依赖）

**内置工具一览**：

| 工具 | name | 参数 | 说明 |
|------|------|------|------|
| `BashTool` | `Bash` | `command` | shell 执行，30s 超时，三层安全 |
| `FileReadTool` | `FileRead` | `file_path`, `limit` | 读文件，UTF-8 失败回退 latin-1 |
| `FileWriteTool` | `FileWrite` | `file_path`, `content`, `append`, `require_new` | 写/追加，自动建父目录，防覆盖 |
| `AddMemoryTool` | `AddMemory` | `memory_text` | 写 `.ai_memory` |
| `GitStatusTool` | `GitStatus` | `directory` | 只读查询 `git status --short` |
| `AgentTool` | `AgentTool` | `prompt`, `name`, `isolation`, `run_in_background` | 子代理（模拟执行，支持 worktree 隔离/后台） |
| `MCPTool` | 动态 | `args`(dict) | stdio 转发 JSON-RPC 到 MCP Server |

### 4.6 `tools/security/` — 三层安全防线

| 文件 | 函数 | 职责 |
|------|------|------|
| `destructive_warning.py` | `is_destructive_command(cmd)` | 拦截 `rm -rf /`、`mkfs`、`dd` 写盘、fork 炸弹、覆写 `/etc/*` |
| `bash_security.py` | `check_bash_security(cmd)` | 拦截 `$(...)` / 反引号注入（放行 pwd/dirname/basename）、`zmodload` |
| `should_sandbox.py` | `should_use_sandbox(cmd)` / `strip_wrappers(cmd)` | 白名单判定；剥离 `sudo/timeout/env` 等包装器 |

`BashTool` 执行顺序：`is_destructive_command` → `check_bash_security` → `should_use_sandbox`（命中则追加「建议沙盒」提示）。

### 4.7 `cli/main.py` — CLI 入口

- `parse_args()`：`--provider` / `--model` / `--base-url` / `--verbose`。
- `handle_command()`：处理 `/exit` `/clear` `/help` `/buddy`。
- `main_loop()`：初始化 Provider→Agent→注入全局记忆→交互循环（`prompt_toolkit` 缺失时回退 `input()`）。
- `run_cli()`：`pyproject.toml` 的 `[project.scripts]` 入口。

### 4.8 `utils/console.py` 与 `buddy/companion.py`

- `console.py`：`rich` 自定义主题（info/warning/error/success/ai/user/tool）+ `print_welcome()` 欢迎横幅。
- `companion.py`：`mulberry32` 伪随机 + `spawn_buddy()`，`/buddy` 触发，返回 ASCII 宠物卡片。

---

## 5. 核心实现流程

### 5.1 启动流程

```
mini-codex [args]
  └─ run_cli()
      ├─ parse_args()
      ├─ main_loop(args)
      │   ├─ check_first_run_setup()      # 无 Key → 交互引导
      │   ├─ print_welcome()
      │   ├─ create_provider(type/model/base_url)   # 工厂（内置 show_thinking 读取）
      │   ├─ Agent(provider)
      │   ├─ MemoryManager().get_global_memory()    # 读取 .ai_memory
      │   │     └─ 追加到 provider.messages[0] (system)
      │   └─ while True: 读取输入 → handle_command 或 agent.chat()
```

### 5.2 Agent 循环（ReAct 风格）

```
agent.chat(user_input)
  ├─ provider.send_message(user_input, cb)          # user 消息进上下文
  │     └─ create_message() → 流式返回 {text, toolCalls}
  └─ while toolCalls and loop < 30:
        ├─ handle_tool_calls(toolCalls)
        │     └─ 逐个 registry.get_tool(name) → tool.execute(**args)
        └─ provider.send_tool_results(results, cb)  # tool 结果回传，继续生成
```

### 5.3 OpenAI Provider 流式处理（`create_message`）

1. 从 `registry.get_all_schemas()` 取工具 Schema。
2. `stream=True` 发起请求，遍历 chunk（`show_thinking` 为 True 时处理思维链）：
   - `delta.reasoning_content` → 思维链（前缀「思考过程」分隔线）。
   - `delta.content` → 正文（真值判断，`is_thinking_started` 控制「完整回复」分隔线）。
   - `delta.tool_calls` → 按 `tc.index` 拼接工具名与参数碎片。
3. 解析 arguments JSON（失败先 `_fix_json_string` 重试），组装 `{text, toolCalls}`。

### 5.4 工具分发（Tool Use）

`registry.execute_tool(name, args)` → `get_tool(name)`（支持别名）→ `await tool.execute(**args)`；`TypeError` 与其他异常分别捕获，返回可读错误给模型。

### 5.5 MCP 调用流程（`MCPTool`）

大模型调用 → `MCPTool.execute(**kwargs)` → 构造 JSON-RPC `tools/call` → `asyncio.create_subprocess_shell(server_command)` → `process.communicate(input=req)` → 解析 stdout 中最后一行 JSON → 提取 `result.content[].text` 返回。

### 5.6 记忆注入流程

`MemoryManager.get_global_memory()` → 读 `.ai_memory/global_memory.txt` → 截断（>5000 字符）→ `cli` 中追加到 system prompt → 模型每次响应都能见到全局约定。

---

## 6. 关键类与函数速查表

### 类

| 类 | 模块 | 角色 |
|------|------|------|
| `Agent` | `core/agent.py` | 核心协调器 |
| `LLMProvider` | `core/providers/base.py` | Provider 抽象 |
| `OpenAIProvider` | `core/providers/openai_provider.py` | OpenAI 兼容实现（含 show_thinking） |
| `AnthropicProvider` | `core/providers/anthropic_provider.py` | Claude 实现（可选） |
| `BaseTool` | `tools/base.py` | 工具抽象 |
| `ToolRegistry` | `tools/registry.py` | 工具注册表 |
| `BashTool` / `FileReadTool` / `FileWriteTool` | `tools/*.py` | 基础工具 |
| `GitStatusTool` / `AgentTool` / `MCPTool` | `tools/*.py` | 高级工具 |
| `MemoryManager` / `AddMemoryTool` | `core/memory.py` | 记忆 |

### 函数

| 函数 | 模块 | 说明 |
|------|------|------|
| `create_provider()` | `core/providers/__init__.py` | Provider 工厂（读取 SHOW_THINKING） |
| `run_cli()` / `main_loop()` | `cli/main.py` | 入口 / 主循环 |
| `get_config_value()` / `set_config_value()` | `config/settings.py` | 配置读写 |
| `check_first_run_setup()` | `config/settings.py` | 首次引导 |
| `is_destructive_command()` | `tools/security/destructive_warning.py` | 破坏性拦截 |
| `check_bash_security()` | `tools/security/bash_security.py` | 注入拦截 |
| `should_use_sandbox()` / `strip_wrappers()` | `tools/security/should_sandbox.py` | 沙盒判定 |
| `spawn_buddy()` / `mulberry32()` | `buddy/companion.py` | 彩蛋 |

---

## 7. 依赖关系

### 7.1 外部依赖（`pyproject.toml`）

`[project].dependencies`（必装）：

| 包 | 版本约束 | 用途 |
|----|----------|------|
| `openai` | `>=1.0.0` | OpenAI 及兼容接口（默认） |
| `pydantic` | `>=2.0.0` | 工具参数 Schema |
| `python-dotenv` | `>=1.0.0` | 加载 `.env` |
| `aiofiles` | `>=23.0.0` | 异步文件读写（声明） |
| `colorama` | `>=0.4.6` | Windows 终端颜色（声明） |
| `rich` | `>=13.0.0` | 终端渲染 |
| `prompt_toolkit` | `>=3.0.0` | 交互输入（可降级） |

`[project.optional-dependencies]`（可选）：

| 额外 | 内容 | 用途 |
|------|------|------|
| `anthropic` | `anthropic>=0.30.0` | Claude 官方接口（`pip install -e ".[anthropic]"`） |
| `dev` | `pytest>=8.0.0`、`pytest-asyncio>=0.23.0` | 测试依赖（`pip install -e ".[dev]"` 一步装齐） |

### 7.2 内部依赖图（关键引用）

```
cli/main.py ──► config · core/agent · core/providers · core/memory · utils
core/agent.py ──► tools/registry · core/providers/base
core/providers/openai_provider.py ──► tools/registry · core/providers/base
core/providers/__init__.py ──► openai_provider（eager）· anthropic_provider（惰性）
tools/registry.py ──► tools/{base,bash,file_read,file_write} · agent_tool · git_status_tool · mcp_tool · core/memory(延迟)
tools/bash.py ──► tools/security/*
core/memory.py ──► tools/base
mini_codex/__init__.py ──► core.agent · core.providers.base · core.providers.openai_provider · tools.base · tools.registry
```

### 7.3 循环依赖处理

- `tools/registry.py` 底部对 `core/memory.AddMemoryTool` 采用**延迟导入 + try/except**，避免 `registry ↔ memory` 循环依赖。
- 各 Provider 对 `registry` 的导入放在函数内部（`_get_tool_schemas()`），进一步降低模块加载期的耦合。
- `anthropic_provider` 改为**工厂函数内惰性导入**，使 `import mini_codex` 无需 anthropic。

---

## 8. 配置清单

### 8.1 环境变量（`.env` 或系统环境）

| 键 | 必填 | 说明 |
|----|------|------|
| `PROVIDER` | 否 | `openai` 或 `anthropic`，默认 `openai` |
| `OPENAI_API_KEY` | openai 时 | OpenAI/兼容接口 Key（含通义千问等） |
| `OPENAI_BASE_URL` | 否 | 兼容接口地址 |
| `MODEL_NAME` | 否 | 模型名（默认 `gpt-4o` / `claude-sonnet-4-20250514`） |
| `SHOW_THINKING` | 否 | 是否请求并展示思维链，默认 `true`；`false` 关闭 |
| `ANTHROPIC_API_KEY` | anthropic 时 | Claude Key |
| `MINI_CODEX_MCP_SERVERS` | 否 | JSON 数组，动态注册 MCP 工具 |

### 8.2 配置文件

- 全局配置：`~/.mini-codex/config.json`（含 `PROVIDER` / `OPENAI_BASE_URL` / `MODEL_NAME` / `SHOW_THINKING` 等**非敏感项**；密钥保留在系统环境变量）。
- 缓存/记忆：`.ai_memory/global_memory.txt`（运行时生成，已在 `.gitignore` 排除）。

> 国内大模型接入：`OPENAI_API_KEY` 与 `DASHSCOPE_API_KEY` 为同一密钥时，`OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1` + `MODEL_NAME=qwen-plus` 即可走通义千问。

---

## 9. 完整迁移指南

> 目标是：拿到本仓库后，在任意新机器上可完整复现并运行。

### 9.1 方式 A：pipx 安装（推荐）

pipx 一次安装，全局命令随时可用：

```bash
pip install pipx
pipx ensurepath
pipx install .
mini-codex
```

> 更新代码后：`pipx install --force .`（或 `pipx reinstall mini-codex`）。

### 9.2 方式 B：venv 源码构建（开发用）

```bash
git clone https://github.com/wjb412530/mini-codex.git
cd mini-codex
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

pip install -e .
mini-codex
```

### 9.3 配置 LLM 凭证

```env
# 通义千问（推荐，走 OpenAI 兼容协议）
PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus
SHOW_THINKING=true
```

> 通过 pipx 全局启动时，把 `OPENAI_BASE_URL` / `MODEL_NAME` / `SHOW_THINKING` 写入 `~/.mini-codex/config.json`，密钥保留在环境变量，即可脱离项目目录运行。

### 9.4 运行

```bash
mini-codex                          # 默认配置（openai / Qwen）
mini-codex --provider anthropic     # 切换 Claude（需装 optional 依赖）
python -m mini_codex.main           # 模块方式（主包无 __main__.py）
```

### 9.5 运行测试

```bash
pip install -e ".[dev]"    # 首次需装测试依赖（pytest / pytest-asyncio）
pytest                     # 依赖 pyproject 的 asyncio_mode=auto 与 testpaths=tests
```

### 9.6 打包发布到 PyPI（可选）

```bash
pip install build twine
python -m build
twine upload dist/*
```

### 9.7 迁移自检清单

- [ ] 源文件齐全：`src/mini_codex/**`（36 个 `.py` 源文件 + 目录结构，见 §3）。
- [ ] 配置文件齐全：`pyproject.toml`、`.env.example`、`LICENSE`、`README.md`、`mini-codex.md`、`docs/images/logo.jpg`。
- [ ] 依赖可安装：`pipx install .` 或 `pip install -e .` 成功。
- [ ] 凭证可配：`.env` 或 `~/.mini-codex/config.json` + 环境变量 Key。
- [ ] CLI 可启动：`mini-codex --help` 出帮助。
- [ ] 测试通过：`pytest` 全绿。

---

## 10. 已知权衡与注意点

1. **`AgentTool` 的子代理执行为「模拟实现」**：真实环境可替换为启动新的 Agent 实例或子进程。
2. **`BashTool` 使用 `shell=True`**：虽有三层静态正则拦截，但静态拦截非绝对安全的沙盒方案；生产环境建议配合容器隔离。
3. **`should_use_sandbox` 目前只做「判定 + 提示」**：未真正接入 Docker/容器后端，仅在输出中提示「建议沙盒」。
4. **MCP 工具需显式通过环境变量注册**：未配置 `MINI_CODEX_MCP_SERVERS` 时不会出现 MCP 工具。
5. **`aiofiles` / `colorama` 为声明性依赖**：当前主流程未实际调用，保留用于后续扩展或跨平台兼容。
6. **anthropic 依赖已解耦**：`import mini_codex` 不再预加载 anthropic；仅在 `provider=anthropic` 时才惰性导入，使用前需 `pip install -e ".[anthropic]"`。
7. **交互式 UI 需要真实终端（TTY）**：`prompt_toolkit` 在无控制台环境（如 CI/管道）会抛 `NoConsoleScreenBufferError`；可用 `python -m mini_codex.main` 的 programmatic 方式或真实终端运行。
8. **流式收尾告警**：`openai 3.x` 底层 `httpcore2` 在流被提前关闭时会打印 `RuntimeError: generator didn't stop after athrow()`，属无害告警，不影响结果。

---

## 11. 变更记录

记录相对「初版项目记忆」的后续关键改动，便于追溯演进。

| 日期 | 变更 | 涉及文件 |
|------|------|----------|
| 2026-09-08 | **补声明测试依赖**：新增 `[project.optional-dependencies] dev = ["pytest>=8.0.0","pytest-asyncio>=0.23.0"]`，修复全新环境无法直接跑 `pytest` 的问题 | `pyproject.toml` |
| - | **anthropic 解耦为可选**：改为惰性导入，`pyproject.toml` 移入 `optional-dependencies` | `providers/__init__.py`、`__init__.py`、`pyproject.toml` |
| - | **接入国内大模型**：默认走 OpenAI 兼容协议接通义千问 Qwen；`~/.mini-codex/config.json` 写入非敏感配置 | `config`、配置文件 |
| - | **venv 隔离**：创建 `venv`，安装 `openai 3.8.0` + `pydantic 2.13.5` 等，不含 anthropic | 环境 |
| - | **pipx 迁移**：`pipx install .`，`mini-codex` 变全局命令（推荐启动方式） | 环境 + `README.md` |
| - | **思维链两层修复**：① 空串误判修复（`is not None` → 真值）；② 新增 `SHOW_THINKING` 开关 | `openai_provider.py`、`providers/__init__.py` |
| - | **文档同步**：README 增加 pipx / 启动命令 / SHOW_THINKING；`.env.example` 增加 SHOW_THINKING 与 Qwen 示例 | `README.md`、`.env.example` |

---

> 本文档随代码同步维护。若项目结构或依赖再变更，请一并更新 §3（文件清单）、§7（依赖关系）与 §11（变更记录）。