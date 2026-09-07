"""
MCP 透明代理工具 (mcp_tool.py)
============================

Model Context Protocol (MCP) 工具。
它不是执行本地 Python 代码，而是将大模型的请求通过 stdio 转发给另外一个独立的 MCP Server 进程。
"""

import os
import json
import asyncio
from pydantic import BaseModel, Field
from typing import Dict, Any, List

from .base import BaseTool


class MCPToolArgs(BaseModel):
    # MCP 工具的参数是动态的，用 dict 接收
    args: Dict[str, Any] = Field(default_factory=dict, description="传递给 MCP 插件的参数字典")


class MCPTool(BaseTool):
    """
    透明代理工具 (Model Context Protocol)

    将大模型的请求通过 stdio 转发给独立的 MCP Server 进程。
    """

    def __init__(self, name: str, description: str, server_command: str, args_schema: dict):
        self.name = name
        self.description = description
        self.server_command = server_command
        self._custom_schema = args_schema
        self.args_schema = MCPToolArgs

    def to_openai_schema(self) -> dict:
        """重写 schema 生成逻辑，直接使用从 MCP Server 读来的真实 Schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._custom_schema
            }
        }

    async def execute(self, **kwargs) -> str:
        """
        核心逻辑：当大模型想调用这个 MCP 工具时，
        启动 MCP Server 进程，把 JSON-RPC 请求发给它，并读取 stdout 响应。
        """
        try:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": self.name,
                    "arguments": kwargs
                }
            }

            req_str = json.dumps(request) + "\n"

            process = await asyncio.create_subprocess_shell(
                self.server_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate(input=req_str.encode('utf-8'))

            if process.returncode != 0:
                err_msg = stderr.decode('utf-8').strip()
                return f"MCP 插件执行失败 (退出码 {process.returncode}): {err_msg}"

            resp_str = stdout.decode('utf-8').strip()

            try:
                lines = [line for line in resp_str.split('\n') if line.strip().startswith('{')]
                if not lines:
                    return f"MCP 插件返回格式错误: {resp_str}"

                resp_data = json.loads(lines[-1])

                if "error" in resp_data:
                    return f"MCP 插件业务错误: {resp_data['error'].get('message', '未知错误')}"

                result_content = resp_data.get("result", {}).get("content", [])
                if not result_content:
                    return "MCP 插件执行成功，但没有返回内容。"

                texts = [item.get("text", "") for item in result_content if item.get("type") == "text"]
                return "\n".join(texts)

            except json.JSONDecodeError:
                return f"无法解析 MCP 插件响应: {resp_str}"

        except Exception as e:
            return f"调用 MCP 插件时发生系统错误: {str(e)}"


def load_mcp_tools_from_config() -> List[MCPTool]:
    """
    从环境变量 MINI_CODEX_MCP_SERVERS (JSON 数组) 加载 MCP 工具定义。
    返回对应的一组 MCPTool 实例，供 registry 注册。
    """
    raw = os.environ.get("MINI_CODEX_MCP_SERVERS", "")
    if not raw:
        return []

    try:
        servers = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(servers, list):
        return []

    tools = []
    for s in servers:
        tools.append(MCPTool(
            name=s["name"],
            description=s.get("description", ""),
            server_command=s["command"],
            args_schema=s.get("input_schema", {"type": "object", "properties": {}}),
        ))
    return tools