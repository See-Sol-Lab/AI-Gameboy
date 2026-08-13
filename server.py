"""AI-Gameboy · Stage A 通电检查服务。

只验证一件事:Codex Desktop 与 Claude Code 的真实窗口
能否连上同一个本机 Streamable HTTP MCP 入口。

- 只有一项只读工具 table_hello,返回座位名称;
- 不建牌局、不存游戏状态、不碰 内部设计资料;
- Stage B 开工前,本文件可整体替换。

运行:python server.py
入口:http://127.0.0.1:7777/mcp
"""

from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HOST = "127.0.0.1"  # 只绑回环地址,不开局域网/公网
PORT = 7777
LOG_FILE = Path(__file__).parent / "data" / "stage_a_calls.log"

# Stage A 的座位只是名称:没有令牌、没有私牌、没有牌局
SEATS = [
    {"seat_id": "seat_a", "name": "A 席(靠窗)"},
    {"seat_id": "seat_b", "name": "B 席(靠门)"},
]

mcp = FastMCP("ai-gameboy", host=HOST, port=PORT)


def _log(line: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@mcp.tool()
def table_hello(who: str = "unknown") -> dict:
    """看一眼牌桌(Stage A 通电检查,只读)。

    who:请自报你所在的窗口,例如 "Codex Desktop" 或 "Claude Code"。
    返回座位名称与服务器时间;不创建牌局,不改变任何状态。
    """
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    _log(f"{now}  table_hello  who={who!r}")
    return {
        "table": "AI-Gameboy",
        "stage": "A(通电检查)",
        "seats": SEATS,
        "server_time": now,
        "note": "本工具只读。真实验收 = 两个真实窗口各自调用成功,且服务端日志时间能对上。",
    }


if __name__ == "__main__":
    print(f"AI-Gameboy Stage A 通电检查:http://{HOST}:{PORT}/mcp")
    print(f"调用日志:{LOG_FILE}")
    mcp.run(transport="streamable-http")
