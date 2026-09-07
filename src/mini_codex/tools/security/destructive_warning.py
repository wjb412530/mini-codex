import re

def is_destructive_command(command: str) -> bool:
    """
    检查是否是高危破坏性命令。
    大模型有时候会"产生幻觉"或者被恶意提示诱导，去执行 rm -rf / 之类的命令。
    我们在它真正丢给系统执行前，进行最后一道静态正则拦截。
    """
    parts = re.split(r';|&&|\|\|', command)

    for part in parts:
        cmd = part.strip()
        if not cmd:
            continue

        if re.search(r'\brm\s+(?:-[A-Za-z]*r[A-Za-z]*\s+-[A-Za-z]*f[A-Za-z]*|-[A-Za-z]*f[A-Za-z]*\s+-[A-Za-z]*r[A-Za-z]*|-[A-Za-z]*r[A-Za-z]*f[A-Za-z]*|-[A-Za-z]*f[A-Za-z]*r[A-Za-z]*)\s+/\*?(?:\s|$)', cmd):
            return True

        if re.search(r'\bmkfs\b', cmd):
            return True
        if re.search(r'\bdd\s+if=/dev/(?:zero|urandom)\s+of=/dev/[a-z]+', cmd):
            return True

        if ":(){" in cmd.replace(" ", ""):
            return True

        if re.search(r'>\s*/etc/(?:passwd|shadow|fstab|sudoers)', cmd):
            return True

    return False