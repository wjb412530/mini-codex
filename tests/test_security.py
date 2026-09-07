import pytest
from mini_codex.tools.security.bash_security import check_bash_security
from mini_codex.tools.security.destructive_warning import is_destructive_command
from mini_codex.tools.security.should_sandbox import strip_wrappers, should_use_sandbox

def test_check_bash_security():
    assert check_bash_security("echo $(pwd)") == False
    assert check_bash_security("cd `dirname $0`") == False

    assert check_bash_security("echo $(ls -la)") == True
    assert check_bash_security("echo `cat /etc/passwd`") == True

    assert check_bash_security("zmodload zsh/net/tcp") == True

def test_destructive_command():
    assert is_destructive_command("rm -rf /") == True
    assert is_destructive_command("sudo rm -rf /*") == True
    assert is_destructive_command("rm -f -r /") == True
    assert is_destructive_command("mkfs.ext4 /dev/sda") == True
    assert is_destructive_command("dd if=/dev/zero of=/dev/sda") == True
    assert is_destructive_command(":(){ :|:& };:") == True
    assert is_destructive_command("echo 'hack' > /etc/shadow") == True

    assert is_destructive_command("rm -rf ./node_modules") == False
    assert is_destructive_command("rm test.txt") == False

def test_strip_wrappers():
    assert strip_wrappers("sudo -u root timeout 10 ls -la") == "ls -la"
    assert strip_wrappers("watch -n 1 ls") == "ls"
    assert strip_wrappers("ENV_VAR=1 time node index.js") == "node index.js"
    assert strip_wrappers("npm run build") == "npm run build"

def test_should_use_sandbox():
    assert should_use_sandbox("ls -la") == False
    assert should_use_sandbox("grep -r 'test' .") == False
    assert should_use_sandbox("sudo timeout 10 git status") == False

    assert should_use_sandbox("cd src && ls -la") == False

    assert should_use_sandbox("curl http://example.com") == True
    assert should_use_sandbox("wget http://example.com") == True
    assert should_use_sandbox("python script.py | awk '{print $1}'") == True