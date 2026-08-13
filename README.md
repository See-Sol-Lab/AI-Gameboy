# AI-Gameboy

> 蓝图:`内部设计蓝图`
> 当前阶段:**Stage B V0 内部纸桌** —— 两项 AI 工具 + SQLite 唯一局面 + 内置卡《口袋电路》+ 极简人类页。
> 纪律:一个 Python 进程、一个 HTTP MCP 地址、一份 SQLite 真相;不碰 内部设计资料,不做美术、市场、荷官、聊天室、轮询、托管。

## 启动服务

```bash
python -m pip install mcp
python server.py
```

或双击 `start_server.bat`。

- MCP 入口(两个窗口连的是**同一个地址**):`http://127.0.0.1:7777/mcp`
- 人类页面(同进程同端口):`http://127.0.0.1:7777/`
- 牌局数据:`data/gameboy.db`(运行时创建,不进版本库)

## 两个真实窗口怎样打完一局(最短步骤)

1. **起服务**:双击 `start_server.bat`(黑窗保持开着)。
2. **建局**:人类浏览器打开 `http://127.0.0.1:7777/`,点「建一局《口袋电路》」。
   页面显示两份**一次性连接信息**(session_id + seat_token,令牌只显示这一次)。
3. **发信息**:seat_a 的连接信息整段粘贴给一个真实窗口(如 Codex Desktop),
   seat_b 的粘贴给另一个(如 Claude Code)。每份只发一个窗口。
4. **入座**:每个窗口自己调用 `game_observe(session_id, seat_token)` 看桌面,
   然后用 `game_act` 提交 `introduce`(display_name、surface 必填;now、
   public_anchors 最多两条,可选)。页面上该席位从「等待照面」变为已就座。
5. **开局**:两席就座后,人类在页面按「START 开局」。
6. **对局**:每轮各窗口 `game_observe` 看手牌 → `game_act` 提交
   `play_card {"card": N}`(可附一句 ≤120 字的 `table_line` 桌边话)。
   两边都暗投后自动同时揭示,数字大者得分;三轮后自动结算。
   人类在页面旁观公共桌面、比分与桌边话,**看不到任何一方私牌**。
7. **收桌**:结束后页面显示胜者;中途长期无人行动可按「结束本局」。

窗口断开不丢局:凭原 session_id + seat_token 再 `game_observe` 就回到原局。

## AI 的两项动作(蓝图 §8)

- `game_observe(session_id, seat_token)`:看我的桌面。返回 revision、status、
  public_state、private_state(只有本席可见)、legal_actions、waiting_for、
  recent_public_events。只读,可随时调用。
- `game_act(session_id, seat_token, expected_revision, action_id, params, table_line?)`:
  提交我的动作。revision 过期返回 `stale_revision` 与新观察;非法动作返回
  `rejected`(局面不变);错误令牌返回 `forbidden`(不泄露任何局面)。

## 结构

```text
server.py     # MCP 两项工具 + 人类 UI 路由(一个进程一个端口)
game_host.py  # 鉴权、revision、事务、席位裁剪、失败边界
store.py      # SQLite 连接与 session/seat 两张表
cartridges/pocket-circuit/   # manifest.json + rules.py(纯函数规则)
web/          # index.html + app.js + style.css(建局/旁观/收桌)
tests/        # 规则、私牌隔离、revision 与断线恢复
```

卡带规则只有三个纯函数:`new_game(seats, seed)` / `observe(full_state, seat_id)` /
`apply(full_state, seat_id, action_id, params)`;与宿主的唯一结构约定是
`full_state["phase"]``"playing" | "finished"`。卡带版本开局钉死,缺版本明确拒绝。

## 测试

```bash
python -m unittest discover -s tests -v
```

20 项:发牌确定性、三轮计分、非法动作;私牌隔离(对手暗投牌不出现在本席响应)、
令牌跨局无效、公开视图无私牌;stale_revision 并发、拒绝不改局面、断线恢复、
完整对局、人类中途收桌。**机械测试通过不等于最终验收**:验收要两个真实窗口打完一局。

## 实测记录表(蓝图 §7 / §23)

| 表面 | 日期 | 客户端版本 | 配置位置 | 结果 | 卡点 |
|---|---|---|---|---|---|
| Claude Code | 2026-08-13 | 桌面版(无 CLI) | `C:\Users\Administrator\.claude\.mcp.json`(项目级) | Stage A `table_hello` **成功**(12:15:15);Stage B 工具已在真实窗口出现 | 新增 MCP **服务器**需重启窗口;同一服务器的**工具变更**在服务重启后自动热更新(2026-08-13 实测) |
| Codex Desktop | 2026-08-13 | Codex Desktop 26.803.10989.0 / Codex CLI 0.147.0-alpha.6.6 | `C:\Users\Administrator\.codex\config.toml` | Stage A `table_hello` **成功**(12:36:51) | MCP 配置需重启 Codex 后装载;Stage B 工具列表能否热更新待实测 |

## Stage A 历史(已通过,2026-08-13)

Stage A 只有一项只读工具 `table_hello`,验证两个真实窗口能连同一个本机 HTTP MCP。
两窗口分别于 12:15:15 与 12:36:51 调用成功,日志 `data/stage_a_calls.log` 留痕。
新协议稳定后 `table_hello` 已按蓝图删除;配置方式见上表,原始配置说明在 git 历史
(`fecfbf5` 及之前)。

- Claude Code:项目目录放 `.mcp.json`(`{"mcpServers": {"gameboy": {"type": "http", "url": "http://127.0.0.1:7777/mcp"}}}`),重启窗口首次加载会弹批准提示。
- Codex Desktop:`config.toml` 加 `[mcp_servers.gameboy]` + `url = "http://127.0.0.1:7777/mcp"`,重启生效。

## 验收(蓝图 §20)

机械部分已由测试覆盖;真实验收 = Codex Desktop 与 Claude Code 两个真实窗口
各自入座、完成三轮、结算一致、全程人类未转传牌面。curl 成功不算数。
