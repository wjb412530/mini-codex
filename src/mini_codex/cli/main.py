"""
CLI 入口 (main.py)
=================

mini-codex 的命令行入口。
负责：
1. 解析命令行参数（--provider, --model, --verbose）
2. 初始化配置和 Provider
3. 创建 Agent 实例
4. 运行交互式对话循环

使用方式：
    mini-codex                         # 使用默认配置启动
    mini-codex --provider anthropic    # 使用 Anthropic Claude
    mini-codex --model gpt-4o-mini     # 指定模型
    mini-codex --verbose               # 显示详细日志
"""

import argparse
import asyncio
from typing import Optional

from rich.markup import escape


# ============================================================
# 命令行参数解析
# ============================================================

def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。

    支持 --provider / --model / --base-url / --verbose
    """
    parser = argparse.ArgumentParser(
        prog="mini-codex",
        description="mini-codex - AI 编程助手 (Python 版)",
        epilog="示例：mini-codex --provider openai --model gpt-4o"
    )
    parser.add_argument("--provider", choices=["openai", "anthropic"], default=None, help="LLM 提供商类型")
    parser.add_argument("--model", default=None, help="模型名称")
    parser.add_argument("--base-url", default=None, help="OpenAI 兼容接口的 base URL")
    parser.add_argument("--verbose", action="store_true", help="显示详细的调试日志")
    return parser.parse_args()


# ============================================================
# 交互式命令处理
# ============================================================

def handle_command(user_input: str, agent) -> Optional[str]:
    """
    处理特殊的斜杠命令。

    :param user_input: 用户输入
    :param agent: Agent 实例
    :return: 如果是命令，返回处理结果消息；否则返回 None
    """
    cmd = user_input.lower().strip()

    if cmd in ["/exit", "/quit"]:
        return "__EXIT__"

    if cmd == "/clear":
        agent.clear_history()
        return "[info]对话历史已清空，开启新话题。[/info]"

    if cmd == "/help":
        return (
            "[info]常用命令:[/info]\n"
            "  [bold yellow]/help[/bold yellow]   查看帮助\n"
            "  [bold yellow]/clear[/bold yellow]  清空对话历史\n"
            "  [bold yellow]/buddy[/bold yellow]  召唤电子宠物\n"
            "  [bold red]/exit[/bold red]    退出应用"
        )

    if cmd == "/buddy":
        from mini_codex.buddy.companion import spawn_buddy
        return spawn_buddy()

    return None  # 不是命令，交给 Agent 处理


# ============================================================
# 主循环
# ============================================================

async def main_loop(args: argparse.Namespace) -> None:
    """
    Agent 的主事件循环。

    流程：
    1. 初始化 Provider 和 Agent
    2. 等待用户输入
    3. 如果是斜杠命令，直接处理
    4. 否则发给 Agent，让它调用 LLM + 工具
    5. 循环直到用户退出
    """
    from mini_codex.config import check_first_run_setup, get_config_value
    from mini_codex.utils.console import console, print_welcome
    from mini_codex.core.agent import Agent
    from mini_codex.core.providers import create_provider
    from mini_codex.core.memory import MemoryManager

    check_first_run_setup()
    print_welcome()

    provider_type = args.provider or get_config_value("PROVIDER", "openai")
    model_name = args.model or get_config_value("MODEL_NAME")
    base_url = args.base_url or get_config_value("OPENAI_BASE_URL")

    try:
        provider = create_provider(
            provider_type=provider_type,
            model=model_name if model_name else None,
            base_url=base_url if base_url else None,
        )
    except Exception as e:
        console.print(f"[error]初始化 LLM Provider 失败: {e}[/error]")
        console.print("[info]提示：请先运行 `mini-codex` 完成首次配置，或设置环境变量 OPENAI_API_KEY / ANTHROPIC_API_KEY[/info]")
        return

    agent = Agent(provider)

    memory_manager = MemoryManager()
    global_memory = memory_manager.get_global_memory()

    if global_memory and hasattr(provider, 'messages') and provider.messages:
        first_msg = provider.messages[0]
        if first_msg.get("role") == "system":
            first_msg["content"] += f"\n\n=== 项目全局记忆 ===\n{global_memory}\n===================="

    console.print(f"[info]使用提供商: {provider_type} | 模型: {getattr(provider, 'model', 'unknown')}[/info]\n")

    try:
        from prompt_toolkit import PromptSession
        session = PromptSession()
    except ImportError:
        session = None

    while True:
        try:
            if session:
                user_input = await session.prompt_async("\n> ")
            else:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("\n> ")
                )

            user_input = user_input.strip()
            if not user_input:
                continue

            cmd_result = handle_command(user_input, agent)
            if cmd_result:
                if cmd_result == "__EXIT__":
                    console.print("[info]再见！👋[/info]")
                    break
                console.print(cmd_result)
                continue

            if args.verbose:
                console.print(f"[dim]>>> 发送给 LLM: {user_input[:100]}...[/dim]")

            await agent.chat(user_input)

        except KeyboardInterrupt:
            console.print("\n[info]再见！👋[/info]")
            break
        except EOFError:
            console.print("\n[info]再见！👋[/info]")
            break
        except Exception as e:
            console.print(f"[error]发生错误: {escape(str(e))}[/error]")
            if args.verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")


# ============================================================
# 入口函数
# ============================================================

def run_cli() -> None:
    """
    CLI 入口函数。

    解析命令行参数，然后启动异步主循环。
    这个函数是 pyproject.toml 中 [project.scripts] 的入口点。
    """
    args = parse_args()
    asyncio.run(main_loop(args))