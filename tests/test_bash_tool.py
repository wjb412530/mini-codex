import pytest
import asyncio
from mini_codex.tools.bash import BashTool
from mini_codex.tools.security.bash_security import check_bash_security
from mini_codex.tools.security.destructive_warning import is_destructive_command

@pytest.mark.asyncio
async def test_bash_tool_safe():
    tool = BashTool()
    res = await tool.execute("echo 'hello'")
    assert "hello" in res

@pytest.mark.asyncio
async def test_bash_tool_dangerous():
    tool = BashTool()
    dangerous_cmds = [
        "rm -rf /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "echo $(ls)",
        "echo `ls`"
    ]
    for cmd in dangerous_cmds:
        res = await tool.execute(cmd)
        assert "拦截" in res

def test_bash_tool_empty():
    tool = BashTool()
    res = asyncio.run(tool.execute(""))
    assert "执行命令时发生异常" in res or "成功" in res