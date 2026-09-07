from mini_codex.core.memory import MemoryManager

def test_memory_manager(tmp_path):
    manager = MemoryManager(workspace_dir=str(tmp_path))

    assert manager.memory_dir.exists()
    assert manager.global_memory_file.exists()

    content = manager.get_global_memory()
    assert "系统全局记忆" in content

    manager.add_memory("测试约定：永远使用 4 个空格缩进。")
    content = manager.get_global_memory()
    assert "测试约定：永远使用 4 个空格缩进。" in content

    junk = "a" * 6000
    manager.add_memory(junk)
    content = manager.get_global_memory()

    assert len(content) <= 5000 + 50
    assert "(记忆过长被截断)" in content