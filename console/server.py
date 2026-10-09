"""AI-Gameboy · Stage B V0 内部纸桌。

一个 Python 进程、一个 HTTP MCP 入口、一份 SQLite 真相(蓝图 §18.1):
- AI 侧只有两项工具:game_observe / game_act;
- 人类侧极简页面:建局、复制席位连接信息、开局、旁观、手动结束;
- 卡带架从 cartridges/* 动态读取,当前包含对抗、合作与 AI 单机经营卡。

两种模式:
  本地模式  python -m console.server           (或双击 start_server.bat)
            只有这台电脑能连。AI 也在这台电脑上(Claude Code、Codex 等)时用它。
  开桥模式  python -m console.server --bridge  (或双击 start_bridge.bat)
            另开一条 cloudflared 临时隧道,给出一个公网 MCP 网址,让不在这台电脑上的 AI
            (手机或网页上的 GPT、Claude 等)也能入座。公网只开放 /mcp;
            人类页面和管理接口仍只有本机能打开。关掉窗口,隧道和网址一起失效。
MCP 入口:http://127.0.0.1:7777/mcp
人类页面:http://127.0.0.1:7777/
"""

import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from .game_host import GameHost
from .cartridges import locate

HOST = "127.0.0.1"  # 只绑回环地址;公网只能经开桥模式的隧道进来,且只到 /mcp
PORT = 7777  # 固定接入约定：本地/开桥共用；占用时退出，不自动改端口
BASE = Path(__file__).resolve().parent.parent
WEB = Path(__file__).parent / "web"

host = GameHost(BASE / "data" / "gameboy.db", BASE / "cartridges")

mcp = MCPServer(
    "ai-gameboy",
    instructions=(
        "AI-Gameboy 牌桌。你需要人类交给你的 session_id 与 seat_token 才能入座。"
        "先 game_observe 看自己的桌面,再按 legal_actions 用 game_act 行动;"
        "第一步通常是 introduce 自我介绍。口袋电路对抗局中,人类会先锁牌;"
        "轮到你 play_card 时先调用 game_act,提交前不要在聊天里说出牌号或具体策略。"
        "口袋夜铺0.3只有一位AI玩家;介绍后先请人类替你掷启动资金(两颗六面骰,11-66),必须等人类亲口发令再用 roll_start_funds 掷出后开店(human_words 填人类原话),人类网页仅供观看。"
        "72种旧物分寻常/少见/奇珍/上古/遗世五阶,店铺最高5级；"
        "上古、遗世与14位专属来客从3级开放,86位来客各至多到访8次；"
        "work_shift经营一班,run_shifts连续淘货/修理/整理最多6班,"
        "可设reserve；stop_on接受new/rare/event字符串或数组,"
        "省略默认三项全选,[]关闭这三类停点,待选择事件仍停；"
        "遇到pending_event用choose_event自行决定。"
        "图鉴永久保留,卖货也不会丢发现；探索不同地点补齐图鉴。"
        "close_for_now歇业、reopen_shop续档,不必等待人类。"
    ),
)


# ---------------- AI 的两项动作 ----------------

@mcp.tool()
def game_observe(session_id: str, seat_token: str) -> dict:
    """看我的桌面:返回本局中只属于你这个席位的观察。

    session_id / seat_token 来自人类交给你的连接信息。
    返回:revision(提交动作时原样带上)、status、public_state、
    private_state(只有你能看到,别人的私牌不会出现)、
    legal_actions(你现在能做什么)、waiting_for(在等谁)。
    只读、可随时调用;断开后凭原令牌调用即可回到原局。
    """
    return host.observe(session_id, seat_token)


@mcp.tool()
def game_act(session_id: str, seat_token: str, expected_revision: int,
             action_id: str, params: dict | None = None,
             table_line: str = "") -> dict:
    """提交我的动作。先用 game_observe 拿到最新 revision 和 legal_actions。

    - expected_revision:填你刚观察到的 revision;若已过期,返回
      stale_revision 与新观察,请重新决定后再提交;
    - action_id / params:从 legal_actions 里选。大厅中是
      introduce(display_name、surface 必填,now、public_anchors 可选);
      开局后如 play_card,params 形如 {"card": 3};口袋夜铺的 work_shift
      focus 必填,按需要填 item_id/goal;sell 必须由店主填写 asking_price;
      mood、public_line 完全可选,真想公开表达时才写;
      run_shifts支持count(1-6)、reserve(现金保留线)、stop_on(字符串或数组);
      stop_on可填"new"或["new","rare"],仅支持new/rare/event;
      省略默认["new","rare","event"],填[]关闭这三类停点,待选择事件仍停;
      choose_event回应当前event_id与choice;unlock_location用location解锁路线;
    - table_line:可选,一句公开桌边话(≤120 字),只随本次动作出现。
    动作是你自己的选择:牌桌不替你决定,也不把你的私牌给别人看。
    《口袋电路》中人类已经先锁牌且不能更改;你应先提交 play_card,
    等工具返回本轮揭示后再谈刚才的牌与理由,避免提前自曝策略。
    《口袋夜铺》中引擎会自动把行动与结果展示给观看者;沉默是正常玩法。
    mood/public_line 不是作业,只有真有反应时才写。每次工具返回后可继续下一班;
    随时可用 close_for_now 歇业,下次用 reopen_shop 继续。未决事件也能存档。
    """
    return host.act(session_id, seat_token, expected_revision,
                    action_id, params, table_line)


# ---------------- 人类页面(同进程、同端口) ----------------

# no-cache:每次重新验证,掌机壳升级后人类刷新即得新版
_STATIC_HEADERS = {"Cache-Control": "no-cache"}


@mcp.custom_route("/", methods=["GET"])
async def index(request: Request):
    return FileResponse(WEB / "index.html", headers=_STATIC_HEADERS)


@mcp.custom_route("/web/app.js", methods=["GET"])
async def app_js(request: Request):
    return FileResponse(WEB / "app.js", headers=_STATIC_HEADERS)


@mcp.custom_route("/web/style.css", methods=["GET"])
async def style_css(request: Request):
    return FileResponse(WEB / "style.css", headers=_STATIC_HEADERS)


@mcp.custom_route("/cartridges/{cid}/ui.js", methods=["GET"])
async def cartridge_ui(request: Request):
    """卡带自带的界面(可选):cartridges/<id>/ui.js,没有就用掌机的通用显示。"""
    cid = request.path_params["cid"]
    try:
        path = locate(BASE / "cartridges", cid) / "ui.js"
    except (ValueError, FileNotFoundError):
        return JSONResponse({"result": "not_found"}, status_code=404)
    if not path.is_file():
        return JSONResponse({"result": "not_found"}, status_code=404)
    return FileResponse(path, media_type="text/javascript", headers=_STATIC_HEADERS)


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


@mcp.custom_route("/api/cartridges", methods=["GET"])
async def cartridges(request: Request):
    return JSONResponse(host.list_cartridges())


@mcp.custom_route("/api/sessions", methods=["GET", "POST"])
async def sessions(request: Request):
    if request.method == "POST":
        body = await _json_body(request)
        return JSONResponse(host.create_session(
            body.get("cartridge_id", "pocket-circuit"),
            body.get("mode", "ai_ai")))
    return JSONResponse(host.list_sessions())


# ---- 人类席:与 MCP 完全同构的薄封装,令牌走 POST body 不进 URL ----

@mcp.custom_route("/api/sessions/{sid}/observe", methods=["POST"])
async def human_observe(request: Request):
    body = await _json_body(request)
    return JSONResponse(host.observe(request.path_params["sid"],
                                     body.get("seat_token", "")))


@mcp.custom_route("/api/sessions/{sid}/act", methods=["POST"])
async def human_act(request: Request):
    body = await _json_body(request)
    return JSONResponse(host.act(
        request.path_params["sid"],
        body.get("seat_token", ""),
        body.get("expected_revision", -1),
        body.get("action_id", ""),
        body.get("params") or {},
        body.get("table_line", "")))


@mcp.custom_route("/api/sessions/{sid}", methods=["GET"])
async def session_view(request: Request):
    after = request.query_params.get("after_seq")
    if after is not None and not after.isdigit():
        return JSONResponse({"result": "rejected", "reason": "after_seq 须为非负整数"}, status_code=400)
    return JSONResponse(host.public_view(request.path_params["sid"],
                                         int(after) if after is not None else None))


@mcp.custom_route("/api/sessions/{sid}/start", methods=["POST"])
async def session_start(request: Request):
    return JSONResponse(host.start_game(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/end", methods=["POST"])
async def session_end(request: Request):
    return JSONResponse(host.end_session(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/narrate", methods=["POST"])
async def session_narrate(request: Request):
    return JSONResponse(host.narrate(request.path_params["sid"]))


# ---------------- 开桥模式 ----------------

BRIDGE = {"mcp_url": None}


@mcp.custom_route("/api/bridge", methods=["GET"])
async def bridge_info(request: Request):
    return JSONResponse({"mode": "bridge" if BRIDGE["mcp_url"] else "local",
                         "mcp_url": BRIDGE["mcp_url"] or f"http://{HOST}:{PORT}/mcp"})


class Guard:
    """两道门:
    1. 经隧道进来的请求(cloudflared 会带 cf-connecting-ip)只许访问 /mcp;
       MCP 动作本身要席位令牌,人类页面、建局、收局等接口不对公网开放。
    2. 别的网站借浏览器偷偷发来的改动请求一律拒绝:浏览器跨站发请求会带上 Origin,
       只有掌机自己的页面(本机地址)能建局、开局、收局。"""

    LOCAL_ORIGINS = {f"http://{HOST}:{PORT}".encode(), f"http://localhost:{PORT}".encode()}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            path = scope["path"]
            reason = None
            if b"cf-connecting-ip" in headers and path != "/mcp" and not path.startswith("/mcp/"):
                reason = "开桥模式下公网只开放 /mcp"
            elif (path.startswith("/api/") and scope["method"] != "GET"
                  and b"origin" in headers and headers[b"origin"] not in self.LOCAL_ORIGINS):
                reason = "只接受掌机本机页面发来的操作"
            if reason:
                await JSONResponse({"result": "forbidden", "reason": reason},
                                   status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def find_cloudflared() -> str | None:
    for candidate in (shutil.which("cloudflared"),
                      r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                      r"C:\Program Files\cloudflared\cloudflared.exe"):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def open_tunnel() -> tuple[subprocess.Popen, str]:
    """起一条 cloudflared 临时隧道指向本机端口,返回进程和公网主机名。"""
    exe = find_cloudflared()
    if not exe:
        sys.exit("没找到 cloudflared。先安装它(Windows:winget install Cloudflare.cloudflared;"
                 "macOS:brew install cloudflared),再重新开桥。")
    proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://{HOST}:{PORT}"],
                            stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True,
                            encoding="utf-8", errors="replace")
    found = threading.Event()
    result = {}

    def read():
        for line in proc.stderr:  # 一直读完,免得管道写满卡住隧道
            m = re.search(r"https://([a-z0-9-]+\.trycloudflare\.com)", line)
            if m and not found.is_set():
                result["host"] = m.group(1)
                found.set()

    threading.Thread(target=read, daemon=True).start()
    if not found.wait(60):
        proc.terminate()
        sys.exit("隧道 60 秒内没建好,检查网络后重试。")
    return proc, result["host"]


def serve(bridge: bool) -> None:
    import uvicorn

    hosts = [f"{HOST}:{PORT}", f"localhost:{PORT}"]
    origins = [f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"]
    tunnel = None
    print("AI-Gameboy")
    if bridge:
        tunnel, public = open_tunnel()
        BRIDGE["mcp_url"] = f"https://{public}/mcp"
        hosts.append(public)
        origins.append(f"https://{public}")
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                         allowed_hosts=hosts, allowed_origins=origins)
    app = Guard(mcp.streamable_http_app(transport_security=security, host=HOST))
    print(f"人类页面(只有本机能打开):http://{HOST}:{PORT}/")
    if bridge:
        print("【开桥模式】给不在这台电脑上的 AI 用的 MCP 网址:")
        print(f"    {BRIDGE['mcp_url']}")
        print("把它加进那个 AI 的连接器/开发者应用里,再把席位连接信息发给它。")
        print("这个网址只在本窗口开着时有效;关掉窗口,隧道立即失效,下次开桥会换新网址。")
    else:
        print(f"【本地模式】MCP 入口(只有本机能连):http://{HOST}:{PORT}/mcp")
    try:
        uvicorn.run(app, host=HOST, port=PORT)
    finally:
        if tunnel:
            tunnel.terminate()


if __name__ == "__main__":
    serve(bridge="--bridge" in sys.argv[1:])
