"""
工具注册表 (registry.py)
======================

工具注册表用于管理和分发所有可用的工具。
Agent 只需要和这个注册表打交道，不需要关心具体有多少工具。

设计模式：注册表模式（Registry Pattern）
- 所有工具在启动时注册到一个全局单例
- Agent 通过名称查找工具，实现动态分发
- 支持工具别名（如 "BashTool" 和 "Bash" 指向同一个工具）
"""

from typing import Dict, List, Optional
from .base import BaseTool
from .bash import BashTool
from .file_read import FileReadTool
from .file_write import FileWriteTool


class ToolRegistry:
    """
    工具注册表，用于管理和分发所有可用的工具。

    Agent 只需要和这个注册表打交道，不需要关心具体有多少工具。
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

        # 基础工具
        self._register_with_aliases(BashTool(), ["BashTool"])
        self._register_with_aliases(FileReadTool(), ["FileReadTool"])
        self._register_with_aliases(FileWriteTool(), ["FileWriteTool"])

        # 高级工具（Agent 分身术 / MCP 插件 / Git 状态）
        try:
            from .agent_tool import AgentTool
            self._register_with_aliases(AgentTool(), ["Agent", "SubAgent"])
        except ImportError:
            pass

        try:
            from .git_status_tool import GitStatusTool
            self._register_with_aliases(GitStatusTool(), ["Git", "GitStatusTool"])
        except ImportError:
            pass

        try:
            from .mcp_tool import load_mcp_tools_from_config
            for mcp_tool in load_mcp_tools_from_config():
                self.register(mcp_tool, aliases=[mcp_tool.name])
        except ImportError:
            pass

    def _register_with_aliases(self, tool: BaseTool, aliases: List[str] = None) -> None:
        """注册工具及其别名。"""
        self._tools[tool.name] = tool
        if aliases:
            for alias in aliases:
                self._tools[alias] = tool

    def register(self, tool: BaseTool, aliases: List[str] = None) -> None:
        """将工具加入注册表。"""
        self._register_with_aliases(tool, aliases)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """按名字获取工具（支持别名）"""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """
        获取所有已注册的工具（去重）。

        因为一个工具可能有多个别名，所以需要去重。
        """
        seen = set()
        unique_tools = []
        for tool in self._tools.values():
            if id(tool) not in seen:
                seen.add(id(tool))
                unique_tools.append(tool)
        return unique_tools

    def get_all_schemas(self) -> List[dict]:
        """
        获取所有已注册工具的 OpenAI 兼容 JSON Schema。
        这将被直接放入 LLM API 请求的 `tools` 字段中。
        """
        return [tool.to_openai_schema() for tool in self.list_tools()]

    async def execute_tool(self, name: str, args: dict) -> str:
        """
        根据大模型返回的名称和参数，动态找到对应的工具去执行。
        这就是 "Tool Use" 的核心分发逻辑！

        :param name: 工具名称（支持别名）
        :param args: 工具参数
        :return: 工具执行结果
        """
        tool = self.get_tool(name)
        if not tool:
            return f"系统错误: 找不到名为 '{name}' 的工具。大模型可能产生幻觉并编造了一个不存在的工具。"

        try:
            return await tool.execute(**args)
        except TypeError as e:
            return f"工具 '{name}' 参数错误: {str(e)}\n请检查参数是否正确。"
        except Exception as e:
            return f"工具 '{name}' 执行时发生异常: {str(e)}"


# 实例化一个全局单例，整个项目共用这一个注册表
registry = ToolRegistry()

# 注册记忆工具（延迟导入避免循环依赖）
try:
    from mini_codex.core.memory import AddMemoryTool
    registry.register(AddMemoryTool(), aliases=["AddMemoryTool"])
except ImportError:
    pass  # 如果 memory 模块尚未就绪，跳过