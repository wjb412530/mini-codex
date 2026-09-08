"""
LLM 提供商模块 (providers)
========================

提供统一的 LLM 接口，支持多个模型提供商。

- OpenAIProvider：OpenAI 兼容协议（默认，支持 Qwen / DeepSeek / Kimi 等国内大模型）
- AnthropicProvider：Claude 官方协议（可选，惰性导入，需额外安装 anthropic）
"""

from typing import Optional
from .base import LLMProvider
from .openai_provider import OpenAIProvider


def create_provider(
    provider_type: str = "openai",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMProvider:
    """
    Provider 工厂函数。

    根据类型创建对应的 Provider 实例。

    :param provider_type: 提供商类型 ("openai" 或 "anthropic")
    :param api_key: API 密钥
    :param base_url: API 基础 URL（OpenAI 兼容接口）
    :param model: 模型名称
    :return: LLMProvider 实例
    """
    if provider_type == "anthropic":
        # 惰性导入：仅在真正使用 Claude 时才要求 anthropic 依赖
        from mini_codex.config import get_config_value
        from .anthropic_provider import AnthropicProvider
        key = api_key or get_config_value("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        m = model or get_config_value("MODEL_NAME", "claude-sonnet-4-20250514")
        return AnthropicProvider(api_key=key, model=m)
    else:
        from mini_codex.config import get_config_value
        key = api_key or get_config_value("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY 未配置")
        url = base_url or get_config_value("OPENAI_BASE_URL", "https://api.openai.com/v1")
        m = model or get_config_value("MODEL_NAME", "gpt-4o")
        show_thinking = get_config_value("SHOW_THINKING", "true").strip().lower() not in ("false", "0", "no", "off")
        return OpenAIProvider(api_key=key, base_url=url, model=m, show_thinking=show_thinking)


__all__ = [
    'LLMProvider',
    'OpenAIProvider',
    'create_provider',
]