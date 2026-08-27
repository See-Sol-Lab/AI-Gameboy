"""AI-Gameboy · Stage B V0 内部纸桌。

一个 Python 进程、一个 HTTP MCP 入口、一份 SQLite 真相(蓝图 §18.1):
- AI 侧只有两项工具:game_observe / game_act;
- 人类侧极简页面:建局、复制席位连接信息、开局、旁观、手动结束;
- 卡带架从 cartridges/* 动态读取,当前包含对抗、合作与 AI 单机经营卡。

运行:python server.py  (或双击 start_server.bat)
MCP 入口:http://127.0.0.1:7777/mcp
人类页面:http://127.0.0.1:7777/
"""

from pathlib import Path

from mcp.server import MCPServer
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

from game_host import GameHost

HOST = "127.0.0.1"  # 只绑回环地址,不开局域网/公网(蓝图 §15.4)
PORT = 7777
BASE = Path(__file__).parent
WEB = BASE / "web"

host = GameHost(BASE / "data" / "gameboy.db", BASE / "cartridges")

mcp = MCPServer(
    "ai-gameboy",
    instructions=(
        "AI-Gameboy 牌桌。你需要人类交给你的 session_id 与 seat_token 才能入座。"
        "先 game_observe 看自己的桌面,再按 legal_actions 用 game_act 行动;"
        "第一步通常是 introduce 自我介绍。口袋电路对抗局中,人类会先锁牌;"
        "轮到你 play_card 时先调用 game_act,提交前不要在聊天里说出牌号或具体策略。"
        "口袋夜铺中你是唯一店主,可以连续调用 work_shift 玩许多半日,不必等待人类;"
        "想停时直接停在当前存档,下次凭同一令牌继续。门铃亮起也不阻塞经营。"
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
      按 legal_actions 填 focus、mood、public_line,可选 item_id 与 goal;
    - table_line:可选,一句公开桌边话(≤120 字),只随本次动作出现。
    动作是你自己的选择:牌桌不替你决定,也不把你的私牌给别人看。
    《口袋电路》中人类已经先锁牌且不能更改;你应先提交 play_card,
    等工具返回本轮揭示后再谈刚才的牌与理由,避免提前自曝策略。
    《口袋夜铺》中 mood/public_line 是主动给观看者看的公开状态,不是思维链;
    每次工具返回后可继续下一班,一天打烊或任何时刻都可自然停下。
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
    return JSONResponse(host.public_view(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/start", methods=["POST"])
async def session_start(request: Request):
    return JSONResponse(host.start_game(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/end", methods=["POST"])
async def session_end(request: Request):
    return JSONResponse(host.end_session(request.path_params["sid"]))


@mcp.custom_route("/api/sessions/{sid}/narrate", methods=["POST"])
async def session_narrate(request: Request):
    return JSONResponse(host.narrate(request.path_params["sid"]))


if __name__ == "__main__":
    print(f"AI-Gameboy Stage B 内部纸桌")
    print(f"MCP 入口:http://{HOST}:{PORT}/mcp")
    print(f"人类页面:http://{HOST}:{PORT}/")
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
