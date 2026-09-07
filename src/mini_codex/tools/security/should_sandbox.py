import re

# 允许绕过沙盒直接在宿主机执行的命令白名单
SAFE_COMMANDS = {
    "ls", "cat", "echo", "pwd", "whoami", "uname", "date", "cd",
    "grep", "find", "wc", "head", "tail", "less", "more", "sort", "uniq",
    "git", "node", "npm", "yarn", "pnpm", "python", "python3", "pip", "pytest",
    "rustc", "cargo", "go", "java", "javac", "mvn", "gradle",
    "which", "type", "whereis", "stat"
}

# 常见的命令包装器（它们本身不是命令，而是用来修饰命令的）
WRAPPERS = {
    "timeout", "sudo", "watch", "nohup", "time", "env", "xargs", "stdbuf", "nice"
}


def strip_wrappers(cmd: str) -> str:
    """
    剥离命令包装器，提取出最核心的真实命令。
    例如将 'sudo -u root timeout -s SIGKILL 10 ls -la' 剥离为 'ls -la'。
    """
    parts = cmd.split()
    if not parts:
        return cmd

    while parts:
        first_word = parts[0]
        if first_word in WRAPPERS:
            parts.pop(0)

            while parts:
                if parts[0].startswith('-'):
                    parts.pop(0)
                    if parts and not parts[0].startswith('-') and parts[0] not in SAFE_COMMANDS and parts[0] not in WRAPPERS:
                        parts.pop(0)
                elif parts[0].isdigit():
                    parts.pop(0)
                else:
                    break
            continue

        if '=' in first_word and not first_word.startswith('-'):
            parts.pop(0)
            continue

        break

    return " ".join(parts) if parts else cmd


def should_use_sandbox(command: str) -> bool:
    """
    判断一个命令是否需要放入安全沙盒（Docker 容器）中执行。

    策略：
    如果剥离包装器后的核心命令在 SAFE_COMMANDS 白名单中，
    则认为它是开发工具链或基础查询命令，允许在宿主机直接执行（返回 False）。
    否则，返回 True，表示需要放入沙盒隔离。
    """
    parts = re.split(r';|&&|\|\||\|', command)

    for part in parts:
        cmd = part.strip()
        if not cmd:
            continue

        stripped_cmd = strip_wrappers(cmd)

        words = stripped_cmd.split()
        if not words:
            continue

        base_cmd = words[0]

        if base_cmd not in SAFE_COMMANDS:
            return True

    return False