"""
mini_codex 包初始化文件

这个文件告诉 Python 这是一个可导入的包。
我们在这里导出公共 API。

注意：anthropic 为可选依赖，仅在真正使用 Claude（provider=anthropic）时才会
惰性导入。因此只使用 OpenAI 兼容协议（国内大模型如 Qwen / DeepSeek）时
无需安装 anthropic。
"""

__version__ = "0.1.0"
__author__ = "mini-codex"

# 导出核心模块
from .core.agent import Agent
from .core.providers.base import LLMProvider
from .core.providers.openai_provider import OpenAIProvider
from .tools.base import BaseTool
from .tools.registry import ToolRegistry, registry

__all__ = [
    "Agent",
    "LLMProvider",
    "OpenAIProvider",
    "BaseTool",
    "ToolRegistry",
    "registry",
]