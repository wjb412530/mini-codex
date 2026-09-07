import pytest
import os
from mini_codex.tools.file_read import FileReadTool
from mini_codex.tools.file_write import FileWriteTool

@pytest.mark.asyncio
async def test_file_write_and_read(tmp_path):
    test_file = str(tmp_path / "test_dir" / "test_file.txt")
    content = "Hello Mini-Codex!"
    writer = FileWriteTool()
    res_write = await writer.execute(file_path=test_file, content=content)
    assert "成功" in res_write
    assert os.path.exists(test_file)

    reader = FileReadTool()
    res_read = await reader.execute(file_path=test_file)
    assert "Hello Mini-Codex!" in res_read

@pytest.mark.asyncio
async def test_file_read_truncate(tmp_path):
    test_file = str(tmp_path / "long_file.txt")
    content = "\n".join([f"Line {i}" for i in range(1200)])
    with open(test_file, "w") as f:
        f.write(content)

    reader = FileReadTool()
    res_read = await reader.execute(file_path=test_file, limit=1000)
    assert "Line 999" in res_read
    assert "Line 1000" not in res_read
    assert "截断" in res_read or "第 1 到 1000 行" in res_read