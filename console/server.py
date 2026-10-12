"""AI-Gameboy · Stage B V0 内部纸桌。

一个 Python 进程、一个 HTTP MCP 入口、一份 SQLite 真相(蓝图 §18.1):
- AI 侧只有两项工具:game_observe / game_act;
- 人类侧极简页面:建局、复制席位连接信息、开局、旁观、手动结束;
- 卡带架从 cartridges/* 动态读取,当前包含对抗、合作与 AI 单机经营卡。

同一台游戏机的启动与接入:
  python -m console.server (或start_server.bat):启动本机入口。
  已配置 data/bridge.json 时,同一次启动自动连接已有固定隧道,让云端玩家也能入座。
  --bridge (或start_bridge.bat)是尚未配置固定入口时的临时试玩通道,不是另一个游戏版本。
  公网只开放 /mcp;人类页面和管理接口仍只有本机能打开。
MCP 入口:http://127.0.0.1:7777/mcp
人类页面:http://127.0.0.1:7777/
"""

import re
import json
import os
import signal
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from .game_host import GameHost
from .cartridges import locate

HOST = "127.0.0.1"  # 只绑回环地址;公网通过配置的外网通道进来,且只到 /mcp
PORT = 7777  # 固定接入约定：本地/开桥共用；占用时退出，不自动改端口
BASE = Path(__file__).resolve().parent.parent
WEB = Path(__file__).parent / "web"

host = GameHost(BASE / "data" / "gameboy.db", BASE / "cartridges")

mcp = MCPServer(
    "ai-gameboy",
    instructions=(
        "AI-Gameboy 牌桌。你需要人类交给你的 session_id 与 seat_token 才能入座。"
        "使用长期私有玩家连接时，首次用game_connect绑定人类交给你的席位；以后先game_resume恢复，"
        "无需记住或重复提交token，game_observe/game_act可省略席位信息。失忆后调用game_resume，不要新建存档。"
        "先 game_observe 看自己的桌面,再按 legal_actions 用 game_act 行动;"
        "第一步通常是 introduce 自我介绍。口袋电路对抗局中,人类会先锁牌;"
        "轮到你 play_card 时先调用 game_act,提交前不要在聊天里说出牌号或具体策略。"
        "口袋夜铺0.3只有一位AI玩家;每一轮最多行动20次，用满后停下来跟人类分享店况、结束这一轮回复，真实时间过1分30秒自动开始新一轮(没有办法自己清零);头两周建议一班一班 work_shift,别急着连淘;介绍后启动资金(两颗六面骰,11-66)由人类在网页按「🎲 掷启动资金」按钮来掷——请告诉人类去按,按完再 observe 开店;此外人类网页仅供观看。"
        "72种旧物分寻常/少见/奇珍/上古/遗世五阶,店铺最高5级；"
        "上古、遗世与24位专属来客从3级开放,86位来客各至多到访8次；"
        "一天五班：下午两班不接客且淘货半价，傍晚两班和深夜接客；可拆重复货merge、用星沙sand_repair、用限时卷轴teleport；"
        "work_shift经营一班,run_shifts连续淘货/修理/整理最多6班,"
        "可设reserve；stop_on接受new/rare/event字符串或数组,"
        "省略默认new+rare，[]关闭这三类停点，待选择事件、梦、卷轴、魔女和结局仍停；"
        "遇到pending_event用choose_event自行决定。"
        "图鉴永久保留,卖货也不会丢发现；探索不同地点补齐图鉴。"
        "close_for_now歇业、reopen_shop续档,不必等待人类。"
    ),
)


# ---------------- AI 的两项动作 ----------------

@mcp.tool()
def game_observe(session_id: str = "", seat_token: str = "", ctx: Context | None = None) -> dict:
    """看我的桌面:返回本局中只属于你这个席位的观察。

    session_id / seat_token 来自人类交给你的连接信息。长期私有连接绑定后可全部省略；失忆用game_resume。
    返回:revision(提交动作时原样带上)、status、public_state、
    private_state(只有你能看到,别人的私牌不会出现)、
    legal_actions(你现在能做什么)、waiting_for(在等谁)。
    只读、可随时调用;断开后凭原令牌调用即可回到原局。
    """
    binding, error = _credentials(ctx, session_id, seat_token)
    return error or host.observe(*binding)


@mcp.tool()
def game_act(session_id: str = "", seat_token: str = "", expected_revision: int = -1,
             action_id: str = "", params: dict | None = None,
             table_line: str = "", ctx: Context | None = None) -> dict:
    """提交我的动作。先用 game_observe 拿到最新 revision 和 legal_actions。

    - expected_revision:填你刚观察到的 revision;若已过期,返回
      stale_revision 与新观察,请重新决定后再提交;
    - 长期私有连接已经绑定时，session_id/seat_token可省略，不用把凭证写回聊天。
    - action_id / params:从 legal_actions 里选。大厅中是
      introduce(display_name、surface 必填,now、public_anchors 可选);
      开局后如 play_card,params 形如 {"card": 3};口袋夜铺的 work_shift
      focus 必填,按需要填 item_id/goal;sell 必须由店主填写 asking_price;
      mood、public_line 完全可选,真想公开表达时才写;
      run_shifts支持count(1-6)、reserve(现金保留线)、stop_on(字符串或数组);
      stop_on可填"new"或["new","rare"],仅支持new/rare/event;
      省略默认["new","rare"],填[]关闭这三类停点,待选择事件、梦、卷轴、魔女和结局仍停;
      choose_event回应当前event_id与choice;unlock_location用location解锁路线;
    - table_line:可选,一句公开桌边话(≤120 字),只随本次动作出现。
    动作是你自己的选择:牌桌不替你决定,也不把你的私牌给别人看。
    《口袋电路》中人类已经先锁牌且不能更改;你应先提交 play_card,
    等工具返回本轮揭示后再谈刚才的牌与理由,避免提前自曝策略。
    《口袋夜铺》中引擎会自动把行动与结果展示给观看者;沉默是正常玩法。
    mood/public_line 不是作业,只有真有反应时才写。每次工具返回后可继续下一班;
    随时可用 close_for_now 歇业,下次用 reopen_shop 继续。未决事件也能存档。
    """
    binding, error = _credentials(ctx, session_id, seat_token)
    return error or host.act(*binding, expected_revision, action_id, params, table_line)


def _player(ctx):
    return ctx.request_context.request.scope.get("gameboy_player") if ctx else None


def _credentials(ctx, session_id, seat_token):
    player = _player(ctx)
    if player:
        if not player["seat_token"]:
            return None, {"result": "rejected", "message": "此私有连接尚未绑定席位，请先 game_connect"}
        if (session_id and session_id != player["session_id"]) or (seat_token and seat_token != player["seat_token"]):
            return None, {"result": "forbidden", "message": "席位与此玩家连接不一致；换局请用 game_connect 授权绑定"}
        return (player["session_id"], player["seat_token"]), None
    return (session_id, seat_token), None


@mcp.tool()
def game_connect(session_id: str, seat_token: str, ctx: Context | None = None) -> dict:
    """首次入座或换局：在自己的长期私有MCP连接中绑定人类授予的席位。

    凭证只保存于本机工具侧，返回观察不含token；以后用game_resume或无参数game_observe续档。
    每位玩家各用自己的私有连接。公共/mcp不能使用此功能。
    """
    player = _player(ctx)
    if not player:
        return {"result": "forbidden", "message": "需要已安装的长期私有玩家连接"}
    return host.bind_connection(player["key_hash"], session_id, seat_token)


@mcp.tool()
def game_resume(ctx: Context | None = None) -> dict:
    """失忆、断线或重启后恢复自己的已授权席位。不需要任何参数，不返回token，不重建存档。

    返回session_id、seat_id以及当前revision、桌面和legal_actions；随后game_act可省略席位信息。
    未绑定或失效时明确报错，请找人类授权；不会猜测或进入其他人的席位。
    """
    player = _player(ctx)
    if not player:
        return {"result": "forbidden", "message": "需要已安装的长期私有玩家连接"}
    binding, error = _credentials(ctx, "", "")
    return error or {"session_id": player["session_id"], "seat_id": player["seat_id"],
                     **host.observe(*binding)}


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


@mcp.custom_route("/api/player-connections", methods=["POST"])
async def player_connections(request: Request):
    """Local-only setup: the private address is shown once, then stored by the connector."""
    body = await _json_body(request)
    result = host.create_connection(body.get("name", ""))
    if result["result"] == "ok":
        key = result.pop("connection_key")
        base = BRIDGE["mcp_url"] or f"http://{HOST}:{PORT}/mcp"
        result["mcp_url"] = base + "?" + urlencode({"player": key})
        result["note"] = "私有地址是连接凭证，仅显示这一次；请保存在该玩家的插件配置中，勿发到聊天或公开分享。"
    return JSONResponse(result)


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


@mcp.custom_route("/api/sessions/{sid}/rescue", methods=["POST"])
async def session_rescue(request: Request):
    return JSONResponse(host.rescue_shop(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/roll_funds", methods=["POST"])
async def session_roll_funds(request: Request):
    return JSONResponse(host.roll_start_funds(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/narrate", methods=["POST"])
async def session_narrate(request: Request):
    return JSONResponse(host.narrate(request.path_params["sid"]))


# ---------------- 同一游戏机的本机与云端入口 ----------------

BRIDGE = {"mcp_url": None}


@mcp.custom_route("/api/bridge", methods=["GET"])
async def bridge_info(request: Request):
    return JSONResponse({"mode": "bridge" if BRIDGE["mcp_url"] else "local",
                         "mcp_url": BRIDGE["mcp_url"] or f"http://{HOST}:{PORT}/mcp",
                         "local_mcp_url": f"http://{HOST}:{PORT}/mcp",
                         "remote_mcp_url": BRIDGE["mcp_url"],
                         "remote_kind": BRIDGE.get("kind")})


def load_fixed_bridge():
    path = BASE / "data" / "bridge.json"
    if not path.exists():
        return None
    config = json.loads(path.read_text("utf-8"))
    if not isinstance(config, dict) or set(config) != {"mcp_url", "tunnel_id", "wrangler_profile"}:
        raise ValueError("data/bridge.json须包含mcp_url、tunnel_id、wrangler_profile")
    if not all(isinstance(value, str) for value in config.values()):
        raise ValueError("固定桥配置字段须为字符串")
    url = urlsplit(config["mcp_url"])
    if (url.scheme != "https" or not url.hostname or url.path != "/mcp" or url.query or url.fragment
            or url.username or url.password):
        raise ValueError("固定入口须为不含私有玩家凭证的HTTPS /mcp地址")
    if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", config["tunnel_id"]):
        raise ValueError("固定Tunnel ID须为UUID")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", config["wrangler_profile"]):
        raise ValueError("Wrangler profile名称只能使用字母、数字、下划线和连字符")
    return config


def stop_fixed_tunnel(proc):
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    else:
        os.killpg(proc.pid, signal.SIGTERM)


def open_fixed_tunnel(config):
    npx = shutil.which("npx")
    if not npx or not find_cloudflared():
        raise RuntimeError("固定桥需要已安装的Node.js/npx与cloudflared，请让本机Agent完成安装")
    command = [npx, "--yes", "wrangler@4.149.0", "tunnel", "run", config["tunnel_id"],
               "--profile", config["wrangler_profile"], "--log-level", "info"]
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {"start_new_session": True}
    if sys.platform == "win32":
        command = ["cmd.exe", "/d", "/c", *command]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", **options)
    ready = threading.Event()
    connected = {"ok": False}

    def read():
        # Drain vendor output, but never publish authentication URLs or credentials into game logs.
        for line in proc.stdout:
            if "Registered tunnel connection" in line:
                connected["ok"] = True
                ready.set()
        ready.set()

    threading.Thread(target=read, daemon=True).start()
    if not ready.wait(30) or not connected["ok"] or proc.poll() is not None:
        stop_fixed_tunnel(proc)
        raise RuntimeError("固定隧道30秒内未连通。请检查网络及该Wrangler profile授权；不会改用临时地址")
    return proc


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
                reason = "公网只开放 /mcp，管理接口仅限本机"
            elif (path.startswith("/api/") and scope["method"] != "GET"
                  and b"origin" in headers and headers[b"origin"] not in self.LOCAL_ORIGINS):
                reason = "只接受掌机本机页面发来的操作"
            if reason:
                await JSONResponse({"result": "forbidden", "reason": reason},
                                   status_code=403)(scope, receive, send)
                return
            if path in ("/mcp", "/mcp/"):
                query = parse_qs(scope.get("query_string", b"").decode("utf-8"), keep_blank_values=True)
                if "player" in query:
                    keys = query["player"]
                    player = host.connection(keys[0]) if len(keys) == 1 and keys[0] else None
                    if not player:
                        await JSONResponse({"result": "forbidden", "message": "玩家连接凭证无效"},
                                           status_code=403)(scope, receive, send)
                        return
                    scope = dict(scope, query_string=b"", gameboy_player=player)
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
    fixed = load_fixed_bridge()
    if fixed and bridge:
        raise ValueError("已有固定桥配置，直接启动游戏机即可；请勿同时再创建临时桥")
    BRIDGE.update(mcp_url=None, kind=None)
    print("AI-Gameboy")
    if fixed:
        tunnel = open_fixed_tunnel(fixed)
        BRIDGE.update(mcp_url=fixed["mcp_url"], kind="fixed")
        public = urlsplit(fixed["mcp_url"]).netloc
        hosts.append(public)
        origins.append(f"https://{public}")
    elif bridge:
        tunnel, public = open_tunnel()
        BRIDGE.update(mcp_url=f"https://{public}/mcp", kind="temporary")
        hosts.append(public)
        origins.append(f"https://{public}")
    security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                         allowed_hosts=hosts, allowed_origins=origins)
    app = Guard(mcp.streamable_http_app(transport_security=security, host=HOST))
    print(f"人类页面(只有本机能打开):http://{HOST}:{PORT}/")
    print(f"本机AI入口:http://{HOST}:{PORT}/mcp")
    if BRIDGE["mcp_url"]:
        print("云端AI入口（同一台游戏机）:")
        print(f"    {BRIDGE['mcp_url']}")
        print("把它加进那个 AI 的连接器/开发者应用里,再把席位连接信息发给它。")
        print("固定入口可在下次启动时复用；隧道随游戏机关闭。" if fixed else
              "临时入口只在本窗口开着时有效，下次启动会换网址。")
    else:
        print("云端入口尚未配置；本机AI照常用自己的席位入座。")
    try:
        uvicorn.run(app, host=HOST, port=PORT, access_log=False)
    finally:
        if tunnel and fixed:
            stop_fixed_tunnel(tunnel)
        elif tunnel:
            tunnel.terminate()


if __name__ == "__main__":
    serve(bridge="--bridge" in sys.argv[1:])
