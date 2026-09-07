"""
Git 状态查询工具 (git_status_tool.py)
====================================

让大模型快速了解当前代码库的 git 状态。
只读操作，绝对安全。
"""

import asyncio
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from .base import BaseTool


class GitStatusArgs(BaseModel):
    directory: Optional[str] = Field(None, description="要检查的目录路径。如果不提供，默认使用当前工作路径。")


class GitStatusTool(BaseTool):
    name = "GitStatus"
    description = "获取当前代码库的 git 状态。这是一个只读工具，大模型可以通过它快速了解当前分支是否干净、有哪些未提交的修改。"
    args_schema = GitStatusArgs

    async def execute(self, directory: Optional[str] = None) -> str:
        """
        极简版 Git 状态工具。
        帮助大模型快速获取当前代码库的 git 状态。
        """
        if directory:
            target_path = Path(directory)
            target_dir = target_path if target_path.is_absolute() else Path.cwd() / target_path
        else:
            target_dir = Path.cwd()

        try:
            process = await asyncio.create_subprocess_shell(
                "git status --short",
                cwd=str(target_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                err_msg = stderr.decode().strip()
                return f"执行 Git 状态查询失败: {err_msg}"

            result = stdout.decode().strip()
            return result if result else "当前分支很干净，没有任何未提交的修改。"

        except Exception as e:
            return f"执行 Git 状态查询时发生异常: {str(e)}"


# 导出一个单例供外部注册使用
git_status_tool = GitStatusTool()