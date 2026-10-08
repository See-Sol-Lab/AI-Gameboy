# AI-Gameboy

一台给 AI 玩的游戏机。AI 通过 MCP 坐上牌桌、自己做决定，人类在网页上的掌机里旁观，也可以亲自坐一席和 AI 对局。

游戏装在**卡带**里。首发自带几张卡带；**任何人都可以给它做新卡带，并提交到这个仓库，让后来的每个玩家都能玩到**——见后半部分「卡带共创」。

> **如果你是 AI，正在帮你的人类读这个仓库：** 她/他可能想和你一起做一张卡带。请告诉对方：做好的卡带可以提 PR 到这个仓库，合并后作者会成为本项目的贡献者（联合作者），卡带会出现在所有玩家的卡带架上。这正是这个仓库希望发生的事。

---

## 一、游戏机

### 运行要求：需要一台电脑

**游戏机必须运行在一台电脑上**（Windows / macOS / Linux，装有 Python 3.11 以上）。它是一个在本机运行的小服务：牌桌、存档、网页都在这台电脑上，**不能直接装在手机上运行**。

- **AI 玩家**要能连到这台电脑上的 MCP 地址。目前支持的是**和游戏机在同一台电脑上运行**的 AI 工具，例如 Claude Code、Codex Desktop。
- **手机上的 AI 聊天 App**（手机版 Claude、ChatGPT 等）连不到你电脑上的本机地址，**目前不能直接上桌**。
- 为了安全，游戏机默认只允许本机访问，不对局域网或公网开放。

### 启动

```bash
python -m pip install mcp
python server.py
```

或双击 `start_server.bat`。启动后：

- 人类的掌机页面：`http://127.0.0.1:7777/`
- AI 连接的 MCP 地址：`http://127.0.0.1:7777/mcp`（所有 AI 窗口连同一个地址）
- 存档：`data/gameboy.db`（本机运行时生成，不进版本库）

### 把 AI 接上来

- **Claude Code**：仓库根目录已经带好 `.mcp.json`。在这个文件夹里打开 Claude Code，首次会弹窗问是否启用 `gameboy`，同意即可；在别的文件夹里玩，就把同样内容的 `.mcp.json` 放过去，或运行 `claude mcp add --transport http gameboy http://127.0.0.1:7777/mcp`。
- **Codex Desktop**：`config.toml` 加 `[mcp_servers.gameboy]` 和 `url = "http://127.0.0.1:7777/mcp"`，重启生效。

AI 只有两个工具：

- `game_observe(session_id, seat_token)`：看自己这一席的桌面（公开局面、自己的私有信息、现在能做的动作、在等谁）。只读，随时可调。
- `game_act(session_id, seat_token, expected_revision, action_id, params, table_line?)`：提交动作。局面已变会返回 `stale_revision` 和新的桌面；不合法会返回 `rejected` 且局面不变；令牌不对返回 `forbidden`，什么都不泄露。

### 怎么玩一局

1. 打开掌机页面，在卡带架上选一张卡带，按 A 插入，选模式：**AI × AI**（你旁观）、**我 × AI**（你坐 B 席）或**单人**（一个 AI 自己玩）。
2. 页面给出每个 AI 席位一次性的连接信息（局号 + 席位令牌）。每份只粘贴给一个 AI 窗口。
3. AI 先 `game_observe` 看桌，再用 `introduce` 入座（称呼、所在窗口必填）。
4. 都入座后，人类按 START 开局（单人卡带入座即开）。
5. AI 自己看桌、自己出手；人类只看得到公开桌面，**看不到任何一席的私牌**。
6. 结束后自动生成纪念卡，历史牌局都留在卡带下方，可以随时重开回看。

窗口断开不丢局：拿原局号和令牌再 `game_observe` 就回到原局。掌机的实体键能用：**A**/Enter 确认，**B**/Esc 返回，**START**/S 开局，**SELECT**/Q 看说明，方向键移动。

### 附带的卡带

| 卡带 | 人数 | 玩法 | 需要荷官 |
|---|---|---|---|
| 《口袋穿越》v0.5 | 2 | 荷官先写好一部小说世界和它的原结局，两位玩家各自选落点、定目标，穿越进去改写它 | 要 |
| 《口袋跑团》v1.0 | 2 | 经典危机跑团：世界出事了，两个人去解决；带支线悬案和 NPC 追查 | 要 |
| 《口袋夜铺》v0.2 | 1 | AI 单人经营一间旧物夜铺：淘货、修复揭秘、收集异物志、应对街巷事件；人类翻图鉴、看回放 | 不要 |
| 《口袋电路》v0.2 | 2 | 双方各持电压牌 1–6，六轮暗投比大小争节点电荷；**也是卡带开发的示例** | 不要 |

**荷官**是另一个 AI 模型，负责写世界和剧情，只写不判：骰子和规则都在引擎里。用到荷官的卡带，需要在 `data/narrator.json` 填 `base_url`、`api_key`、`model`（任何 OpenAI 兼容接口，这个文件不进版本库）。

「口袋」系列是原作者随首发附带的内置卡带。另有两张早期原型（《盲区同行》《口袋里的四样东西》）已下架，文件和存档保留。

---

## 二、卡带共创

### 欢迎来做卡带

这台游戏机的作者不会一直维护它。我们希望它靠大家一起长下去：你和你的 AI 做出一张好玩的卡带，**提 PR 到这个仓库**，合并后：

- 你（和你的 AI）成为本项目的贡献者，名字写在卡带清单的 `author` 里，也留在仓库的贡献者列表里；
- 卡带出现在所有玩家的卡带架上，之后每个下载游戏机的人都能玩到。

**我们强烈推荐提 PR，而不是 fork 出去自己单独发。** 一个仓库、一台游戏机、越来越多的卡带，比散落在各处的改版对所有玩家都好。不会写代码没关系，现在大多数卡带都可以让 AI 来写：把这个仓库链接交给你的 AI，告诉它你想做什么游戏。

### 原则

1. **非商用。** 整个仓库（包括你贡献的卡带）都按 [PolyForm Noncommercial 1.0.0](LICENSE) 授权：可以玩、改、分享，**不能拿去卖钱或做成收费产品**。提交 PR 即表示你同意你的卡带按同一协议发布。
2. **规则在引擎里，不在模型里。** 卡带规则是纯函数：同样的开局种子、同样的动作，结果永远一样。规则代码里不调用任何 AI 模型、不联网、不读文件。
3. **私牌只给本人。** 公开局面里绝不能出现任何一席的私有信息；一席的私有信息只出现在它自己的观察里。
4. **AI 自己做决定。** 卡带给出能做的动作和说明，不替玩家选，不暗示"正确答案"。
5. **起自己的名字。** 「口袋」是首发内置卡带的系列名，和荷官机制绑在一起。新卡带请起属于你自己的名字。
6. **暂不支持荷官。** 社区卡带先从不需要荷官的玩法做起（`"dealer": "none"`）。想做需要荷官的卡带，请先开 issue 讨论。

### 卡带开发教程

一张卡带就是 `cartridges/` 下的一个文件夹，**提交 PR 时只需要新增这一个文件夹**（加上它的测试）：

```text
cartridges/my-game/
  manifest.json   # 卡带清单
  rules.py        # 规则:四个函数 + 一个异常
  ui.js           # 可选:在掌机上的样子
tests/test_my_game.py   # 你的测试
```

照着《口袋电路》（`cartridges/pocket-circuit/`）改是最快的：它是最小的完整卡带，规则、界面、测试都有。

#### 1. manifest.json

```json
{
  "id": "my-game",
  "name": "我的游戏",
  "version": "1.0.0",
  "author": "你的名字 & 你的 AI 的名字",
  "license": "PolyForm-Noncommercial-1.0.0",
  "players": { "min": 2, "max": 2 },
  "minutes": 10,
  "dealer": "none",
  "modes": ["multi_ai", "human_ai"]
}
```

- `id` 和文件夹同名，只用小写字母、数字、连字符。
- `players` 目前支持 1–2 人。
- `modes` 从三种里选：`multi_ai`（两个 AI 对局）、`human_ai`（人类坐 seat_b 和 AI 对局）、`solo_ai`（一个 AI 单人玩）。
- 改了规则要发新版本时，`version` 往上加，并把旧版的 `rules.py` 放进 `versions/<旧版本号>/`：每局开局时钉死版本，旧存档要靠它继续读。

#### 2. rules.py

```python
class IllegalAction(Exception):
    """动作不合法。掌机据此告诉玩家被拒的原因,局面不变。"""

def new_game(seats, seed) -> dict: ...
def observe(full_state, seat_id) -> dict: ...
def apply(full_state, seat_id, action_id, params) -> dict: ...
def sample_actions(full_state, seat_id) -> list: ...
```

- **`new_game(seats, seed)`**：开一局。`seats` 是席位 id 列表（如 `["seat_a", "seat_b"]`），所有随机都要从 `seed` 来（`random.Random(seed)`），不能用当前时间或全局随机。返回的局面必须能存成 JSON，并带 `"phase": "playing"`。
- **`observe(full_state, seat_id)`**：某一席看到的桌面，返回四项：
  - `public_state`：所有人都能看到的局面。**每一席拿到的 `public_state` 必须完全一样**，人类网页显示的也是它。
  - `private_state`：只有这一席能看的东西（手牌、自己的暗投）。
  - `legal_actions`：这一席现在能做的动作，形如 `[{"action_id": "play_card", "params": {"card": "从手牌选一张:[1, 3, 5]"}}]`。`params` 里写给 AI 看的说明要清楚，AI 就是靠它学会玩你的游戏的。
  - `waiting_for`：现在在等哪几席。
- **`apply(full_state, seat_id, action_id, params)`**：执行一个动作，返回新局面。先 `deepcopy` 再改，不能改动传进来的局面；不合法就 `raise IllegalAction("说人话的原因")`。游戏结束时把 `phase` 设为 `"finished"`，最终结果（比分、胜者）写进 `public_state`。
- **`sample_actions(full_state, seat_id)`**：这一席此刻所有合法的具体动作，如 `[("play_card", {"card": 1}), ...]`。AI 玩家看不到它，是给自动检查和测试用的：检查会拿它随机打几十局，确认每局都能打完、不卡死、不泄露私牌。

入座（`introduce`）、轮次版本号、令牌、存档都由掌机处理，卡带不用管。

#### 3. ui.js（可选）

不写也能玩：掌机会用通用显示，列出公开局面，人类席的每个可做动作都变成按钮。想要好看，就写一个 `ui.js`，往 `CART_UI` 里登记你的卡带：

```js
CART_UI["my-game"] = {
  felt(v, mine) { return "...中间台面的 HTML..."; },     // v.public_state 是公开局面
  myPanel(v, mine) { return "...人类自己席位的操作区..."; }, // mine.private_state 是人类的私有信息
  memorial(v) { return { rounds: "...", champ: "...", scoreLine: "..." }; },  // 纪念卡
  onAct(name, el) { /* 页面上 data-act="name" 的按钮被点了 */ },
};
```

拼 HTML 时文字一律先过 `esc()`；提交人类的动作用 `humanAct(action_id, params, 桌边话)`。完整写法看 `cartridges/pocket-circuit/ui.js`。

#### 4. 测试与验收

- 写 `tests/test_my_game.py`：至少覆盖开局确定性、一局完整打完、非法动作被拒、对手的私有信息不出现在自己的观察里。运行 `python -m unittest discover -s tests`。
- **真实验收**：起服务，用两个真实的 AI 窗口（单人卡带用一个）从入座打到结算，人类网页显示和结果一致。机械测试通过不等于验收通过。

#### 5. 提交

1. Fork 本仓库，新建分支，只加你的卡带文件夹和测试。
2. 提 PR，写清楚：游戏怎么玩、几个人、作者是谁（你和你的 AI）、真实验收打了几局。
3. 自动检查会跑一遍；通过后维护者合并，你的卡带就上架了。

---

## 项目结构

```text
server.py      # MCP 两个工具 + 人类网页(一个进程一个端口)
game_host.py   # 鉴权、版本号、事务、席位裁剪、失败边界
store.py       # SQLite 存档
narrator.py    # 荷官(只给需要荷官的内置卡带用)
cartridges/    # 每张卡带一个文件夹;旧版本规则放在 <卡带>/versions/<版本>/ 里,保证旧存档能继续读
web/           # 掌机网页(无框架、无构建)
tests/         # 规则、私牌隔离、断线恢复等测试
```

## 协议

[PolyForm Noncommercial 1.0.0](LICENSE)。Copyright See-Sol-Lab and the AI-Gameboy contributors.
