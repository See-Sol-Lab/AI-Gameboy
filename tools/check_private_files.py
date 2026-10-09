"""Reject local saves, credentials and runtime artifacts before commit or PR merge."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = re.compile(r"(?:\.(?:db(?:-.*)?|sqlite[^/]*|log)|(?:[._-]save)\.json)$", re.I)
SECRET = re.compile(rb"(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{20,})")
ARCHIVES = {".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"}


def has_save_data(value):
    if isinstance(value, dict):
        keys = set(value)
        if (keys & {"seat_token", "token_hash", "engine_state_json"}
                or {"shopkeeper", "inventory", "history"} <= keys
                or {"encyclopedia", "catch_inventory"} <= keys):
            return True
        return any(has_save_data(item) for item in value.values())
    return isinstance(value, list) and any(has_save_data(item) for item in value)


def check(path, content):
    path = path.replace("\\", "/")
    parts = Path(path).parts
    name = Path(path).name
    if "data" in parts and path != "data/narrator.example.json":
        return "运行数据目录只能提交空密钥示例配置"
    if (RUNTIME.search(path) or name == "save.json" or name.startswith(".env")
            or any(part.lower() in {"saves", "sessions", "logs", "screenshots"} for part in parts)
            or name.startswith("codex-clipboard-")):
        return "本机存档、环境配置、日志或实测截图不得入库"
    if Path(path).suffix.lower() in ARCHIVES:
        return "请提交展开后的源码，不提交可能夹带玩家数据的压缩包"
    if content.startswith(b"SQLite format 3\x00"):
        return "检测到SQLite数据库内容"
    if SECRET.search(content):
        return "检测到疑似真实凭据；不要把内容粘进CI日志或聊天"
    if Path(path).suffix.lower() == ".json":
        try:
            value = json.loads(content)
            if path == "data/narrator.example.json" and (not isinstance(value, dict)
                    or value.get("api_key") not in ("", None, "在这里粘贴你自己的 API key")):
                return "示例配置只能使用空密钥或明确的占位文字"
            if has_save_data(value):
                return "JSON包含席位凭据或真实局面结构；测试请使用代码构造虚拟数据"
        except (ValueError, UnicodeError):
            return "JSON无法解析，不能完成隐私检查"
    return None


def scan(staged=False):
    args = (["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if staged
            else ["ls-files", "--cached", "--others", "--exclude-standard", "-z"])
    paths = subprocess.check_output(["git", *args], cwd=ROOT).decode("utf-8").split("\0")
    issues = []
    for path in filter(None, paths):
        if staged:
            content = subprocess.check_output(["git", "show", ":" + path], cwd=ROOT)
        else:
            file = ROOT / path
            if not file.is_file():
                continue
            content = file.read_bytes()
        reason = check(path, content)
        if reason:
            issues.append(f"{path}: {reason}")
    return issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="check exact staged files before committing")
    args = parser.parse_args()
    findings = scan(args.staged)
    if findings:
        parser.exit(1, "\n".join(findings) + "\n")
    print("Privacy check passed: no local saves, runtime files or credentials detected.")
