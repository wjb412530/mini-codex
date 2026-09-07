"""
子代理工具 (agent_tool.py)
=======================

「Agent 分身术」：允许大模型派生出子代理来完成特定任务。
支持：
- git worktree 隔离沙箱（isolation='worktree'）
- 后台异步执行（run_in_background=True）
"""

import os
import time
import asyncio
import tempfile
from typing import Optional, Literal
from pathlib import Path
from pydantic import BaseModel, Field
from .base import BaseTool


class AgentArgs(BaseModel):
    prompt: str = Field(..., description="给子代理的任务指令。")
    name: Optional[str] = Field("SubAgent", description="子代理的代号（例如：BugFixer_1）。")
    isolation: Literal['worktree', 'none'] = Field('none', description='隔离模式。"worktree" 会创建一个临时的 git worktree 作为沙箱工作区。')
    run_in_background: Optional[bool] = Field(False, description="是否在后台异步运行。")


class AgentTool(BaseTool):
    name = "AgentTool"
    description = "派生子代理（Agent 分身术）。当你遇到需要独立试错的子任务，或者需要跑大量测试时，你可以派生一个小弟。支持 isolation: 'worktree' 隔离沙箱，以防弄脏主分支。"
    args_schema = AgentArgs

    async def execute(self, prompt: str, name: str = "SubAgent", isolation: str = "none", run_in_background: bool = False) -> str:
        """
        分身术：派生子代理执行任务，支持后台运行和 git worktree 沙箱隔离。
        """
        workspace_dir = Path.cwd()
        work_dir = workspace_dir
        worktree_path = ""

        # 【分身术核心 1】: 绝对隔离 (isolation: 'worktree')
        if isolation == "worktree":
            try:
                branch_name = f"agent-sandbox-{int(time.time() * 1000)}"
                tmp_dir = tempfile.gettempdir()
                worktree_path = os.path.join(tmp_dir, f"mini-codex-worktree-{branch_name}")

                process = await asyncio.create_subprocess_shell(
                    f"git worktree add -b {branch_name} {worktree_path}",
                    cwd=str(work_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    err_msg = stderr.decode().strip()
                    return f"创建隔离沙箱失败：{err_msg}\n请确保当前目录是一个干净的 Git 仓库。"

                work_dir = Path(worktree_path)
            except Exception as e:
                return f"创建隔离沙箱发生系统异常：{str(e)}"

        async def sub_agent_task() -> str:
            # 模拟启动子代理的过程（真实环境会启动一个新的 Agent 实例或子进程）
            await asyncio.sleep(3)

            result = f"任务 \"{prompt}\" 已完成！(模拟返回)"

            # 任务完成后，如果是 worktree 隔离，自动清理战场
            if isolation == "worktree" and worktree_path:
                try:
                    cleanup_proc = await asyncio.create_subprocess_shell(
                        f"git worktree remove -f {worktree_path}",
                        cwd=str(workspace_dir),
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await cleanup_proc.communicate()
                except Exception:
                    pass

            return result

        # 【分身术核心 2】: 异步执行 (run_in_background: True)
        if run_in_background:
            asyncio.create_task(sub_agent_task())
            return f"子代理 '{name}' 已成功派生，并开始在后台静默执行任务。你可以继续当前对话，无需等待它结束。"
        else:
            return await sub_agent_task()


# 导出一个单例供外部注册使用
agent_tool = AgentTool()