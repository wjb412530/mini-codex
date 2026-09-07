# mini-cc (Python 版) Code Wiki

> 本文档是 `you-want-mini-cc` Python 实现的代码知识库，覆盖整体架构、模块职责、关键类与函数、依赖关系与运行方式。重点聚焦 Python 实现（`python/` 目录），其余语言（TypeScript / Go / Rust）不在本文档范围内。

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [模块详解](#4-模块详解)
   - [4.1 配置模块 `mini_cc/config`](#41-配置模块-mini_ccconfig)
   - [4.2 Provider 抽象层 `mini_cc/core/providers`](#42-provider-抽象层-mini_cccoreproviders)
   - [4.3 核心 Agent 循环 `mini_cc/core/agent`](#43-核心-agent-循环-mini_cccoreagent)
   - [4.4 记忆系统 `mini_cc/core/memory`](#44-记忆系统-mini_cccorememory)
   - [4.5 工具系统 `mini_cc/tools`](#45-工具系统-mini_cctools)
   - [4.6 安全模块 `mini_cc/tools/security`](#46-安全模块-mini_cctoolssecurity)
   - [4.7 CLI 入口 `mini_cc/cli`](#47-cli-入口-mini_cccli)
   - [4.8 工具函数 `mini_cc/utils`](#48-工具函数-mini_ccutils)
   - [4.9 彩蛋模块 `mini_cc/buddy`](#49-彩蛋模块-mini_ccbuddy)
5. [关键类与函数速查表](#5-关键类与函数速查表)
6. [依赖关系](#6-依赖关系)
7. [运行方式](#7-运行方式)
8. [遗留代码说明 `python/src`](#8-遗留代码说明-pythonsrc)
9. [已知问题与优化建议](#9-已知问题与优化建议)

---

## 1. 项目概述

`mini-cc`（Python 版，PyPI 包名 `you-want-mini-cc`，内部包名 `mini_cc`）是一个**轻量级 AI 结对编程智能体**，是对 TS 版 `@you-want/mini-cc` 的纯 Python 移植。

核心能力：

- **多模型 Provider**：通过统一的 `LLMProvider` 抽象，支持 OpenAI 兼容接口（Qwen / DeepSeek / Kimi 等）与 Anthropic 官方接口。
- **Agent 循环闭环**：实现「思考 → 调用工具 → 观察结果 → 再思考」的自动循环（ReAct 风格），直到模型给出最终答案。
- **Tool Use（工具调用）**：内置 `Bash`（执行命令）、`FileRead`（读文件）、`FileWrite`（写文件），支持别名派发。
- **安全沙盒**：命令执行前的破坏性命令拦截与子命令注入拦截。
- **记忆系统**：`.ai_memory` 文件级持久化记忆，注入 System Prompt，防止 Token 爆炸。
- **MCP 插件**：通过 stdio 子进程透明代理转发工具调用到独立 MCP Server。
- **终端 UI**：基于 `rich` 的高保真 ANSI 渲染与流式打字机输出。
- **趣味彩蛋**：`/buddy` 电子宠物（Mulberry32 伪随机）。

技术栈：`asyncio`（异步）、`Pydantic v2`（工具参数 Schema）、`openai` / `anthropic` SDK、`rich` + `prompt_toolkit`（CLI）。

---

## 2. 整体架构

架构采用分层设计，核心遵循两个设计模式：**策略模式**（Provider 抽象）与**注册表模式**（Tool 分发）。

```
                          ┌─────────────────────────────┐
                          │      CLI 入口 (cli/main)      │
                          │  parse_args / handle_command  │
                          │  main_loop (交互式循环)        │
                          └──────────────┬──────────────┘
                                         │ 构建 Provider / Agent
                          ┌──────────────▼──────────────┐
                          │      Agent (core/agent)      │
                          │  协调者：负责核心循环与工具派发 │
                          └───────┬──────────────┬───────┘
                                  │              │
                    ┌─────────────▼─────┐   ┌────▼──────────────────┐
                    │ LLMProvider(抽象) │   │ ToolRegistry(注册表)    │
                    │  ├ OpenAIProvider │   │  ├ BashTool            │
                    │  └ Anthropic...   │   │  ├ FileReadTool        │
                    └─────────┬─────────┘   │  ├ FileWriteTool       │
                              │             │  ├ AddMemoryTool       │
                              │             │  └ (MCP/Agent/Git 未注册)│
                              │             └───────────┬───────────┘
              ┌───────────────▼───────────┐             │
              │  云端大模型 API            │    ┌────────▼────────┐
              │ (OpenAI / Anthropic / ...)│    │ security 安全检查 │
              └───────────────────────────┘    └─────────────────┘

        辅助：config(配置) · core/memory(记忆) · utils/console(输出) · buddy(彩蛋)
```

**数据流（一次 `agent.chat()`）：**

1. `cli.main_loop` 读取用户输入，非斜杠命令则调用 `agent.chat(user_input)`。
2. `Agent.chat` 调用 `provider.send_message()`，把 `user` 消息追加进 `provider.messages` 并发起流式请求。
3. Provider 返回 `{"text": ..., "toolCalls": [...]}`。
4. 若含 `toolCalls`，`Agent.handle_tool_calls` 遍历，通过 `registry.get_tool(name)` 查找并 `await tool.execute(**args)`。
5. 执行结果回传 `provider.send_tool_results()`，模型继续思考，循环直至无 `toolCalls` 或达到 `MAX_AGENT_LOOPS`。

---

## 3. 目录结构

```
python/
├── main.py                      # 旧版入口（依赖遗留 src/ 层，已与主包脱钩，见 §8）
├── pyproject.toml               # 打包配置，定义 console_script: mini-cc-py
├── requirements.txt             # 依赖清单（含注释说明）
├── README.md                    # Python 版使用说明
├── .env.example                 # 环境变量模板
├── .ai_memory/global_memory.txt # 本地持久化记忆示例
├── blog/                        # 7 篇教学博客（中文）
├── tests/                       # pytest 单元测试（asyncio_mode=auto）
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_bash_tool.py
│   ├── test_file_tools.py
│   ├── test_memory.py
│   └── test_security.py
└── src/
    ├── config.py                # 遗留配置实现（与 mini_cc/config 重复，见 §8）
    ├── agent/                   # 遗留 llm/loop/memory（见 §8）
    ├── utils/console.py         # 遗留 console（见 §8）
    └── mini_cc/                 # ★ 真正的主包
        ├── __init__.py          # 导出公共 API
        ├── main.py              # 包入口，委托 cli.main.run_cli
        ├── cli/main.py          # 命令行入口与主循环
        ├── config/settings.py   # 配置读写 + 首次运行引导
        ├── core/
        │   ├── agent.py         # Agent 核心循环
        │   ├── memory.py        # 记忆管理 + AddMemoryTool
        │   └── providers/       # LLM Provider 层
        │       ├── base.py
        │       ├── openai_provider.py
        │       ├── anthropic_provider.py
        │       └── __init__.py  # create_provider 工厂
        ├── tools/
        │   ├── base.py          # BaseTool + 旧版 Tool/register_tool
        │   ├── registry.py      # ToolRegistry 单例
        │   ├── bash.py / file_read.py / file_write.py
        │   ├── git_status_tool.py / mcp_tool.py / agent_tool.py
        │   └── security/        # 安全模块
        │       ├── bash_security.py
        │       ├── destructive_warning.py
        │       └── should_sandbox.py
        ├── utils/console.py     # rich 主题 + 欢迎横幅
        └── buddy/companion.py   # 电子宠物彩蛋
```

---

## 4. 模块详解

### 4.1 配置模块 `mini_cc/config`

| 文件 | 职责 |
|------|------|
| `settings.py` | 全局配置读写、三级优先级、首次运行交互引导 |
| `__init__.py` | 导出公共函数与常量 |

配置存储位置：`~/.mini-cc/config.json`。通过 `python-dotenv` 的 `load_dotenv()` 在导入时加载当前目录 `.env`。

**核心函数：**

| 函数 | 说明 |
|------|------|
| `get_config_value(key, default="")` | 读取配置，优先级：环境变量(含 `.env`) > `config.json` > 默认值 |
| `set_config_value(key, value)` | 写入键值到全局 `config.json` |
| `read_config()` / `write_config()` | JSON 文件读写 |
| `ensure_config_dir()` | 确保 `~/.mini-cc` 目录存在 |
| `check_first_run_setup()` | 无 API Key 时用 `rich.prompt.Prompt` 交互式引导（openai/anthropic） |

关键键：`PROVIDER`、`OPENAI_API_KEY` / `ANTHROPIC_API_KEY`、`OPENAI_BASE_URL`、`MODEL_NAME`。

---

### 4.2 Provider 抽象层 `mini_cc/core/providers`

采用**策略模式**：`LLMProvider` 定义统一接口，具体 Provider 实现细节，`Agent` 只依赖抽象接口。

| 文件 | 类 | 说明 |
|------|-----|------|
| `base.py` | `LLMProvider(ABC)` | 抽象基类，强制实现 `send_message` / `send_tool_results` |
| `openai_provider.py` | `OpenAIProvider` | 基于 `AsyncOpenAI`，支持流式、思维链、Function Calling |
| `anthropic_provider.py` | `AnthropicProvider` | 基于 `AsyncAnthropic`，适配 Claude 的消息结构与 `messages.stream` |
| `__init__.py` | `create_provider()` | 工厂函数，按 `provider_type` 返回具体实例 |

#### 抽象协议（`LLMProvider`）

```python
async def send_message(user_message, on_text_response) -> {"text", "toolCalls"}
async def send_tool_results(results, on_text_response) -> {"text", "toolCalls"}
```

`on_text_response(text, is_thinking)` 为流式回调，`is_thinking` 标记是否思维链输出。

#### `OpenAIProvider`（核心实现）

- 持有 `self.messages: List[dict]` 作为对话上下文，初始化时注入 `system_prompt`（含「默认输出到 `../test_file`」「`require_new` 防覆盖」两条内置约定）。
- `create_message()`：构造请求（`temperature=0.2`、`stream=True`、`extra_body={"enable_thinking": True}`），遍历流式 chunk 分别累积 `reasoning_content`（思维链）、`content`（正文）、`tool_calls`（按 `tc.index` 拼接参数碎片）。
- **工具参数 JSON 修复**：`_fix_json_string()` 将换行/回车/Tab 转义后二次 `json.loads`；失败则回传 `{"_parse_error": True, "_raw_arguments": ...}` 交由 Agent 处理。
- `send_tool_results()` 把结果以 `role="tool"` 追加（携带 `tool_call_id`）。

#### `AnthropicProvider`

- 与 OpenAI 的最大差异：系统提示词通过 `system` 参数单独传、工具 schema 用 `input_schema`、工具结果必须包在 `role="user"` 的 `tool_result` 中。
- `_get_tool_schemas()` 复用 `registry.list_tools()` 并转换为 Anthropic 格式。
- 用 `self.client.messages.stream()` 上下文管理器，SDK 自动合并工具调用分块，简化拼接逻辑。

#### 工厂函数

```python
def create_provider(provider_type="openai", api_key=None, base_url=None, model=None) -> LLMProvider
```

根据类型从 config 补齐缺失参数；缺 Key 时抛 `ValueError`。

---

### 4.3 核心 Agent 循环 `mini_cc/core/agent`

| 常量/类/方法 | 说明 |
|------|------|
| `MAX_AGENT_LOOPS = 30` | 最大循环次数，防止无限工具调用 |
| `Agent(provider)` | 协调者（Orchestrator），不直接处理 LLM/工具细节 |
| `Agent.chat(user_input, on_text_response=None)` | 单轮对话入口，内部循环直至无工具调用 |
| `Agent.handle_tool_calls(tool_calls)` | 遍历工具调用：解析错误→查注册表→执行→收集结果 |
| `Agent.clear_history()` | `/clear`：保留首条 system 消息 |
| `Agent._default_text_handler()` | 默认流式输出（`print(text, end="", flush=True)`） |

`handle_tool_calls` 的错误处理路径：

1. `tc_args.get("_parse_error")` → 返回内部解析错误，`isError=True`。
2. `registry.get_tool(name)` 为 `None` → 提示工具不存在并列出可用工具。
3. 正常 `await tool.execute(**tc_args)`；异常则记录 `isError=True`。

---

### 4.4 记忆系统 `mini_cc/core/memory`

实现「两步法则」：工作区 `.ai_memory/global_memory.txt` 持久化项目级长效记忆。

| 类/函数 | 说明 |
|------|------|
| `MemoryManager(workspace_dir=".")` | 记忆管理器，确保 `.ai_memory` 目录存在 |
| `get_global_memory()` | 读全局记忆，超 5000 字符强制截断（防爆） |
| `add_memory(memory_text)` | 追加跨会话记忆（带时间戳） |
| `AddMemoryTool(BaseTool)` | 让模型主动调用写入记忆的工具（name=`AddMemory`） |

`AddMemoryTool` 在 `registry.py` 中被注册（延迟导入避免循环依赖）。全局记忆在 `cli/main.py` 中读入后追加到 Provider 的 system 消息。

---

### 4.5 工具系统 `mini_cc/tools`

#### 基类 `base.py`（两代并存）

| 定义 | 说明 |
|------|------|
| `BaseTool(ABC)` | **新式（推荐）**：`name` / `description` / `args_schema`(Pydantic)，`to_openai_schema()` 用 `model_json_schema()` 自动生成 JSON Schema，`execute(**kwargs)` 为抽象方法 |
| `Tool`(dataclass) + `register_tool` 装饰器 | **旧式（兼容）**：教学用，见 `tools` 列表 |

#### 注册表 `registry.py`

| 成员 | 说明 |
|------|------|
| `ToolRegistry._register_with_aliases()` | 注册主名 + 别名（如 `Bash` ↔ `BashTool`） |
| `get_tool(name)` / `list_tools()` | 查找（支持别名）/去重列表 |
| `get_all_schemas()` | 返回全部主名工具的 OpenAI schema |
| `execute_tool(name, args)` | 动态派发核心（`await tool.execute(**args)`） |
| 全局单例 `registry` | 启动预注册 `BashTool` / `FileReadTool` / `FileWriteTool` + `AddMemoryTool` |

#### 内置工具

| 工具类 | name | 参数 | 说明 |
|------|------|------|------|
| `BashTool` | `Bash` | `command: str` | 执行 shell（`subprocess.run`，`timeout=30`，前置两道安全检查） |
| `FileReadTool` | `FileRead` | `file_path` / `limit` | 读文件，UTF-8 失败回退 latin-1，支持行数截断 |
| `FileWriteTool` | `FileWrite` | `file_path` / `content` / `append` / `require_new` | 写文件，自动建父目录，`require_new` 防覆盖 |
| `AddMemoryTool` | `AddMemory` | `memory_text` | 写入 `.ai_memory` 记忆 |
| `MCPTool` | 动态 | `args: dict` | 透明代理：通过 stdio 子进程转发 JSON-RPC `tools/call` 到 MCP Server |
| `AgentTool` | `AgentTool` | `prompt` / `name` / `isolation` / `run_in_background` | 「分身术」派生子代理（模拟实现，支持 git worktree 隔离） |
| `GitStatusTool` | `GitStatus` | `directory` | 只读查看 git 状态（异步子进程执行 `git status --short`） |

> ⚠️ 注意：`MCPTool`、`AgentTool`、`GitStatusTool` 目前**未在 `registry` 默认注册**，属于已实现但未接线（见 §9）。

#### `tools/__init__.py`

聚合导出 `BaseTool`、`Tool`、`tools`、`register_tool`、`registry`、`ToolRegistry`、以及三个文件工具类。

---

### 4.6 安全模块 `mini_cc/tools/security`

| 文件 | 核心函数 | 职责 |
|------|------|------|
| `destructive_warning.py` | `is_destructive_command(cmd)` | 正则拦截 `rm -rf /`、`mkfs`、`dd` 写盘、`fork 炸弹`、覆写 `/etc/*` |
| `bash_security.py` | `check_bash_security(cmd)` | 拦截 `$(...)` / 反引号命令替换（放行 `pwd/dirname/basename`）与 `zmodload` |
| `should_sandbox.py` | `should_use_sandbox(cmd)` / `strip_wrappers(cmd)` | 基于白名单判断是否需进 Docker 沙盒；剥离 `sudo/timeout/env` 等包装器 |

`BashTool` 实际只调用前两者；`should_use_sandbox` 有实现与测试，但**未接入 `BashTool` 执行路径**（见 §9）。

---

### 4.7 CLI 入口 `mini_cc/cli`

| 函数 | 说明 |
|------|------|
| `parse_args()` | 解析 `--provider` / `--model` / `--base-url` / `--verbose` |
| `handle_command(user_input, agent)` | 处理 `/exit` `/clear` `/help` `/buddy` 斜杠命令 |
| `main_loop(args)` | 初始化 Provider/Agent → 注入全局记忆 → 交互式循环 |
| `run_cli()` | `pyproject.toml` 的 `[project.scripts]` 入口 |

主循环细节：加载 `MemoryManager` 拿到全局记忆后存入 `provider.messages[0]`；`prompt_toolkit` 不可用时回退到 `input()`；异常统一捕获并支持 `--verbose` 打印堆栈。

---

### 4.8 工具函数 `mini_cc/utils`

| 成员 | 说明 |
|------|------|
| `custom_theme` | `rich` 主题，为 `info/warning/error/success/ai/user/tool` 配置颜色 |
| `console` | 全局 `Console` 实例 |
| `print_welcome()` | 打印 `Panel` 欢迎横幅 |

---

### 4.9 彩蛋模块 `mini_cc/buddy`

| 成员 | 说明 |
|------|------|
| `mulberry32(a)` | 32 位伪随机数生成器（同种子→同序列） |
| `BUDDY_TYPES` / `PERSONALITIES` | 宠物种类/性格库 |
| `spawn_buddy(seed_input=None)` | 按种子（默认当天日期）生成并打印电子宠物卡片 |

> ⚠️ 注意：`cli/main.py` 的 `/buddy` 目前只打印**占位文案**，并未调用 `spawn_buddy`（见 §9）。

---

## 5. 关键类与函数速查表

### 类

| 类 | 模块 | 角色 |
|------|------|------|
| `Agent` | `core/agent.py` | 核心协调器，驱动 Agent 循环 |
| `LLMProvider` | `core/providers/base.py` | Provider 抽象基类 |
| `OpenAIProvider` | `core/providers/openai_provider.py` | OpenAI 兼容实现 |
| `AnthropicProvider` | `core/providers/anthropic_provider.py` | Claude 实现 |
| `BaseTool` | `tools/base.py` | 工具抽象基类 |
| `ToolRegistry` | `tools/registry.py` | 工具注册表 |
| `BashTool` / `FileReadTool` / `FileWriteTool` | `tools/*.py` | 内置工具 |
| `MCPTool` / `AgentTool` / `GitStatusTool` | `tools/*.py` | 高级/模拟工具（未注册） |
| `MemoryManager` | `core/memory.py` | 记忆管理 |
| `AddMemoryTool` | `core/memory.py` | 记忆写入工具 |
| `AddMemoryArgs` / `BashArgs` / `FileReadArgs` / `FileWriteArgs` | 各处 | Pydantic 参数 Schema |

### 函数

| 函数 | 模块 | 说明 |
|------|------|------|
| `create_provider()` | `core/providers/__init__.py` | Provider 工厂 |
| `run_cli()` / `main_loop()` | `cli/main.py` | CLI 入口 / 主循环 |
| `get_config_value()` / `set_config_value()` | `config/settings.py` | 配置读写 |
| `check_first_run_setup()` | `config/settings.py` | 首次运行引导 |
| `is_destructive_command()` | `tools/security/destructive_warning.py` | 破坏性命令拦截 |
| `check_bash_security()` | `tools/security/bash_security.py` | 命令注入拦截 |
| `should_use_sandbox()` / `strip_wrappers()` | `tools/security/should_sandbox.py` | 沙盒判定 |
| `spawn_buddy()` / `mulberry32()` | `buddy/companion.py` | 电子宠物 |

---

## 6. 依赖关系

### 外部依赖（`pyproject.toml` / `requirements.txt`）

| 依赖 | 用途 |
|------|------|
| `openai>=1.0.0` | OpenAI 及兼容接口调用（`AsyncOpenAI`） |
| `anthropic>=0.18.0`（requirements 为 `>=0.30.0`） | Claude 官方接口（`AsyncAnthropic`） |
| `pydantic>=2.0.0` | 工具参数 Schema 与 JSON Schema 生成 |
| `python-dotenv` | 加载 `.env` |
| `aiofiles` | 异步文件读写（当前主包未实际用到，声明性） |
| `rich` | 终端富文本渲染 |
| `prompt_toolkit` | 交互式输入（多行/历史） |
| `colorama` | Windows 终端跨平台颜色（声明） |
| `pytest`（dev） | 单元测试 |

### 内部模块依赖（关键引用关系）

```
cli/main.py ──► config · core/agent · core/providers · core/memory · utils
core/agent.py ──► tools/registry · core/providers/base
core/providers/*_provider.py ──► tools/registry · core/providers/base
tools/registry.py ──► tools/{base,bash,file_read,file_write} · core/memory（延迟）
tools/bash.py ──► tools/security/{destructive_warning,bash_security}
core/memory.py ──► tools/base（BaseTool）
mini_cc/__init__.py ──► core.agent · core.providers.* · tools.base · tools.registry
```

`registry.py` 对 `core/memory` 采用**延迟导入**（函数内 import + try/except）以避免循环依赖。

---

## 7. 运行方式

### 前提

- Python ≥ 3.9
- 配置 LLM API Key（`PROVIDER`、对应 Key、`MODEL_NAME`、可选 `OPENAI_BASE_URL`）

### 方式一：PyPI 安装（推荐）

```bash
pip install you-want-mini-cc
mini-cc-py
```

### 方式二：源码构建

```bash
cd python
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e .

mini-cc-py                      # 或用 python -m mini_cc
```

### 环境变量（`.env` 或直接 export）

```env
# OpenAI 兼容（Qwen/DeepSeek 等）
PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-coder

# 或 Anthropic
PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
MODEL_NAME=claude-sonnet-4-20250514
```

### 命令行参数

```bash
mini-cc-py --provider anthropic --model claude-sonnet-4-20250514
mini-cc-py --provider openai --base-url https://xxx/v1 --model gpt-4o --verbose
```

### 交互命令

| 命令 | 作用 |
|------|------|
| `/help` | 查看帮助 |
| `/clear` | 清空对话历史（保留 system） |
| `/buddy` | 召唤电子宠物 |
| `/exit` / `/quit` | 退出 |

### 运行测试

```bash
cd python
pytest
```

---

## 8. 遗留代码说明 `python/src`

`python/src/` 下存在一套**与主包 `mini_cc` 并行的旧实现**，通过根目录 `python/main.py` 入口调用：

| 旧文件 | 对应主包模块 | 状态 |
|------|------|------|
| `src/config.py` | `mini_cc/config/settings.py` | 逻辑几乎一致，功能重复 |
| `src/agent/llm.py` | `mini_cc/core/providers/openai_provider.py` | 旧版 LLM 客户端 |
| `src/agent/loop.py` | `mini_cc/cli/main.py` + `core/agent.py` | 旧版主循环 |
| `src/agent/memory.py` | `mini_cc/core/memory.py` | 旧版记忆（内部跨引用 `mini_cc.tools.base`） |
| `src/utils/console.py` | `mini_cc/utils/console.py` | 重复 |

**遗留层存在明显断链**：`src/agent/llm.py` 导入 `from src.tools.registry import registry`，但 `src/tools/` 目录**并不存在**（`src/` 下仅有 `config.py`、`agent/`、`utils/`）。因此旧入口 `python/main.py` 在导入阶段即会失败。该整套 `src/`（含 `main.py`）属于早期教学/草稿代码，**主包 `mini_cc` 才是当前有效实现**。`tests/conftest.py` 特意把 `src` 加入 `sys.path` 以兼容 `agent.memory` 的导入，但该模块对 `mini_cc.tools.base` 的引用使其只有在已安装 main 包时才能工作。

---

## 9. 已知问题与优化建议

以下为代码审阅中发现的、可能有 bug 或可优化的点（可行性分析结论）：

### 9.1 明确的 Bug

1. **`OpenAIProvider.create_message` 引用了未定义变量 `is_thinking`**（[openai_provider.py](openai_provider.py) 第 110 行）：
   ```python
   if is_thinking and getattr(delta, 'content', None) is not None:
   ```
   实际定义的是 `is_thinking_started`。该分支在流式响应时一旦触发会抛 `NameError`，且「思维链结束→正文开始」的分隔逻辑失效。应改为 `is_thinking_started`。

### 9.2 已实现但未接线（死代码/半成品）

2. **`GitStatusTool`、`AgentTool`、`MCPTool` 均未注册进默认 `registry`**（[registry.py](src/mini_cc/tools/registry.py) 仅注册 `Bash`/`FileRead`/`FileWrite`/`AddMemory`）。这些能力对大模型不可见、不可调用。
3. **`should_use_sandbox` / `strip_wrappers` 未被 `BashTool` 调用**（[bash.py](src/mini_cc/tools/bash.py) 只做 `is_destructive_command` + `check_bash_security` 两道检查）。白名单沙盒判定逻辑有实现与测试，但未进入真实执行链路。
4. **`/buddy` 未调用 `spawn_buddy()`**（[cli/main.py](src/mini_cc/cli/main.py) 打印的是「还在开发中」的占位文案，而 [companion.py](src/mini_cc/buddy/companion.py) 已实现完整逻辑）。

### 9.3 架构/健壮性

5. **遗留 `python/src/` 层与主包重复且断链**（见 §8），建议删除或归档，避免双实现混淆与误维护。
6. **`AgentTool` / `GitStatusTool` 硬编码工作区重定向**至 `../test_file`（测试 Hack 混入生产代码），应改为参数化或移除。
7. **`BashTool` 使用 `shell=True`** 执行命令，虽有前置静态拦截，但静态正则作为唯一防线存在被绕过风险（面向教学可接受，生产需配合更严格的沙盒/容器隔离）。
8. **Provider `system_prompt` 内嵌了「默认输出到 `../test_file`」「`require_new` 防覆盖」这类特定约定**，与「通用编程助手」定位略有冲突，建议抽为可配置项或交给记忆系统管理。

### 9.4 优化建议

9. `FileReadTool` 的 `limit` 截断逻辑中，当 `total_lines <= limit` 时返回的字符数统计基于 `len(content)` 而非 `len(content)` 的行数表述，提示文案可读性一般，可统一为「共 N 行」。
10. `OpenAIProvider._get_tool_schemas` 与 `AnthropicProvider._get_tool_schemas` 每次请求都重新遍历生成 schema，可考虑缓存（工具集固定不变）。
11. `requirements.txt` 与 `pyproject.toml` 的 `anthropic` 版本下限不一致（`>=0.30.0` vs `>=0.18.0`），建议统一。

---

> 本 Wiki 由代码库自动审阅生成，覆盖 `python/` 目录全部 Python 源码（`src/mini_cc/` 主包与 `src/` 遗留层、`tests/`、入口文件）。如需对上述「已知问题」中任意项进行修复，可继续下达指令。