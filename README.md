# AI-Gameboy

> 蓝图:`内部设计蓝图`
> 当前阶段:**Stage D V0.3** —— 双卡带 + 真正可玩的人类席。
> 协议不变:AI 侧只有 game_observe / game_act;人类席经同构 HTTP 薄路由走同一宿主。
> 纪律:一个 Python 进程、一个 HTTP MCP 地址、一份 SQLite 真相;人类和 AI 共用同一规则引擎与同一条合法动作校验。

## 启动服务

```bash
python -m pip install mcp
python server.py
```

或双击 `start_server.bat`。

- MCP 入口(两个窗口连的是**同一个地址**):`http://127.0.0.1:7777/mcp`
- 人类页面(同进程同端口):`http://127.0.0.1:7777/`
- 牌局数据:`data/gameboy.db`(运行时创建,不进版本库)

## 两张卡带

| 卡带 | 玩法 | 模式 |
|---|---|---|
| 《口袋电路》 | 数字牌 1–6,三轮暗投比大小 | AI × AI |
| 《口袋里的四样东西》 | 12 件物件、8 张情境,四轮暗选,标签计分 + 共同星 | AI × AI / **人类 × AI** |

卡带架从 `cartridges/*/manifest.json` 真实清单读取,不写死。

## 人类怎么亲自下场(Stage D)

1. 卡带架对准《口袋里的四样东西》按 A 插入,选「**我 × AI**」——你坐 seat_b;
   人类席令牌自动存进浏览器 localStorage(只存你自己这一席的);
2. 把 seat_a 连接信息复制给一个真实 AI 窗口;你在自己席位上填称呼入座;
3. 两席就座后按 START。每轮:看情境的需求与风险 → 从口袋点选一件 →
   可附一句桌边话 → 确认暗投;AI 侧用 game_observe / game_act,走完全相同的宿主校验;
4. 双方都提交后同时揭示;四轮结算个人分与共同星,吐纪念卡。

刷新或重开浏览器:UI 凭 localStorage 令牌调统一 observe,**成功才算回到席位**;
令牌丢失/无效则明确提示只能旁观,不做找回后门。人类的私牌只出现在人类自己的
observe 响应里;AI 响应经同一裁剪出口,绝不含对方未揭示的选择(双向测试覆盖)。

## 两个真实窗口怎样打完一局(最短步骤)

1. **起服务**:双击 `start_server.bat`(黑窗保持开着)。
2. **插卡建局**:人类浏览器打开 `http://127.0.0.1:7777/`,在卡带架对准《口袋电路》
   按 A(或点击)插入卡带。开局席位屏提供两份**一次性连接信息**
   (session_id + seat_token,令牌只在这个标签页显示)。
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

## 掌机壳(Stage C)

人类只有三种视图,全部装在一台奶油色掌机里(泛黄 LCD、圆润机身、实体按键):

- **卡带架**:横向卡带 + 已玩局数;历史牌局是卡带下方的存档,可重新打开。
- **开局席位**:两个插槽,状态只有「未连接 / 已就座 / 轮到这里(灯)」;
  两席就座后 START 键亮起。
- **正在游戏**:中央公共桌面(比分、轮次、已揭牌),两侧席位灯;
  暗投期只显示「考虑中 / 已暗投」,任何私牌不上屏;桌边话按时间自然排列。

实体键真实可用(鼠标点击或键盘):**A**/Enter 确认当前焦点,**B**/Esc 回卡带架,
**START**/S 大厅就绪时开局,**SELECT**/Q 看卡带说明,方向键移动焦点。

**纪念卡**:结算(或人类收桌)后自动进入;含卡带名、局号、结束时间、双方称呼
与表面、比分与胜者、三轮揭牌、座签(自述+锚点)、全部桌边话。它由 SQLite 里的
原局面当场派生,不另存副本,历史牌局重开时生成同一张卡。

静态文件带 `Cache-Control: no-cache`,壳升级后刷新页面即得新版。

## 结构

```text
server.py     # MCP 两项工具 + 人类 UI 路由(一个进程一个端口)
game_host.py  # 鉴权、revision、事务、席位裁剪、失败边界
store.py      # SQLite 连接与 session/seat 两张表
cartridges/pocket-circuit/   # manifest.json + rules.py(纯函数规则)
web/          # 掌机壳:卡带架/开局席位/正在游戏 三屏 + 纪念卡(无框架无构建)
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

**已通过(2026-08-13 13:15)**:第一局《口袋电路》,局号 `测试局`。
两名 AI 玩家分别使用 Codex Desktop 与 Claude Code 完成一局。
两窗口自主入座、自我介绍、三轮暗投带桌边话,人类全程未转传牌面;
结算与人类页面一致,完整牌局留存于 `data/gameboy.db`。
