import re

def check_bash_security(command: str) -> bool:
    """
    检查命令是否包含高危的子命令替换模式。
    这是防范大模型（或者恶意 Prompt 注入）通过 $(...) 或 `...`
    绕过外层安全包装器执行任意代码的关键防御机制。

    返回: bool
        - True: 包含被拦截的高危模式
        - False: 安全
    """
    if re.search(r'\$\((?!\s*(?:pwd|dirname|basename))[^)]+\)', command):
        return True

    if re.search(r'`(?!\s*(?:pwd|dirname|basename))[^`]+`', command):
        return True

    if "zmodload" in command:
        return True

    return False