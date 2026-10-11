"""Create a private player connector and save its URL outside the public repository."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def setup(name, output, public_mcp_url=None):
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("私有连接配置必须保存到仓库外，不能进入Git")
    if output.exists():
        raise ValueError("私人配置已经存在，请复用它；不会覆盖或重复创建连接")
    if public_mcp_url:
        parsed = urlsplit(public_mcp_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path.rstrip("/") != "/mcp" or parsed.query or parsed.fragment:
            raise ValueError("公网入口须是完整HTTPS /mcp地址，不能带查询参数或片段")
    request = Request("http://127.0.0.1:7777/api/player-connections",
        data=json.dumps({"name": name}).encode(), headers={"content-type": "application/json"})
    with urlopen(request, timeout=15) as response:
        result = json.load(response)
    if result.get("result") != "ok":
        raise ValueError(result.get("reason", "创建连接失败"))
    if public_mcp_url:
        result["mcp_url"] = public_mcp_url.rstrip("/") + "?" + urlsplit(result["mcp_url"]).query
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    return output


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="为这一位AI起的连接名称")
    parser.add_argument("--output", required=True, help="仓库外的私人JSON文件；已存在时拒绝创建")
    parser.add_argument("--public-mcp-url", help="固定HTTPS入口；不填时用当前/api/bridge返回的入口")
    args = parser.parse_args()
    try:
        saved = setup(args.name, args.output, args.public_mcp_url)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
    print(f"已保存私人配置：{saved}")
    print("把文件内完整mcp_url保存在该玩家的连接器设置中；勿公开或放进聊天、Git、日志。")
