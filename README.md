# mini-codex

`mini-codex` 是一个**轻量级 AI 结对编程智能体**，用纯 Python 复刻并强化了 `@you-want/mini-cc`（Python 版）的架构。它由大语言模型（Claude、Qwen、DeepSeek、Kimi 等）驱动，在终端中提供流畅的结对编程体验。

> 本项目为独立实现，采用与其原型一致的**分层架构**：策略模式（Provider）+ 注册表模式（Tool），并额外补充了原项目未接线的能力（MCP、子代理、Git 状态、沙盒白名单、电子宠物彩蛋）。

## 核心特性

- **多模型 Provider**：统一 `LLMProvider` 抽象，支持 OpenAI 兼容接口（Qwen/DeepSeek/Kimi）与 Anthropic 官方接口。
- **Agent 循环闭环**：思考 -> 调用工具 -> 观察结果 -> 再思考，直至给出最终答案（上限 30 轮防死循环）。
- **Tool Use（工具调用）**：内置 `Bash` / `FileRead` / `FileWrite` / `AddMemory` / `GitStatus` / `AgentTool` / `MCPTool`。
- **安全机制**：破坏性命令拦截、子命令注入拦截、白名单沙盒判定三层防线。
- **记忆系统**：`.ai_memory` 文件级持久化记忆，注入 System Prompt，防 Token 爆炸。
- **MCP 插件**：通过 stdio 子进程透明代理转发工具调用到独立 MCP Server。
- **子代理（Agent 分身术）**：支持 `git worktree` 隔离与后台异步执行。
- **终端 UI**：基于 `rich` 的 ANSI 渲染与流式打字机输出。
- **趣味彩蛋**：`/buddy` 电子宠物（Mulberry32 伪随机）。

## 安装

### 方式一：源码构建

```bash
cd mini-codex
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -e .

mini-codex
```

### 方式二：直接运行

```bash
cd mini-codex
pip install -r requirements.txt  # 或 pip install -e .
python -m mini_codex
```

## 配置

在工作目录或用户主目录下创建 `.env`（或用 `~/.mini-codex/config.json`）：

```env
# OpenAI 兼容（Qwen/DeepSeek 等）
PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-coder

# 或 Anthropic
# PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-xxx
# MODEL_NAME=claude-sonnet-4-20250514
```

首次运行未配置 Key 时会进入交互式配置向导。

## 使用

```text
mini-codex --provider openai --model gpt-4o --verbose
```

进入 `>` 提示符后，直接用自然语言下指令即可。

| 命令 | 作用 |
|------|------|
| `/help` | 查看帮助 |
| `/clear` | 清空对话历史 |
| `/buddy` | 召唤电子宠物 |
| `/exit` / `/quit` | 退出 |

## MCP 插件接入

通过环境变量 `MINI_CODEX_MCP_SERVERS`（JSON 数组）声明 MCP 服务器，启动时会自动注册为工具：

```bash
export MINI_CODEX_MCP_SERVERS='[{"name":"fetch","description":"发起网络请求","command":"python -m my_mcp_server","input_schema":{"type":"object","properties":{"url":{"type":"string"}},"required":["url"]}}]'
```

## 运行测试

```bash
cd mini-codex
pytest
```

## 项目结构

```text
mini-codex/
├── pyproject.toml
├── src/mini_codex/
│   ├── cli/            # 命令行入口与主循环
│   ├── config/         # 配置管理
│   ├── core/           # Agent 循环、记忆、Provider 层
│   │   └── providers/  # OpenAI / Anthropic 实现
│   ├── tools/          # 工具系统 + 安全模块
│   ├── utils/          # 终端输出
│   └── buddy/          # 电子宠物彩蛋
└── tests/              # 单元测试
```

## 开源协议

MIT License