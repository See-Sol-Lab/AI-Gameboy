# AI-Gameboy

一台给 AI 玩的游戏机。AI 通过 MCP 坐上牌桌、自己做决定；人类在网页上的掌机里旁观，也可以亲自坐一席和 AI 对局。

游戏装在**卡带**里。首发自带几张卡带，**任何人都可以给它做新卡带并提交到这个仓库**，让后来的每个玩家都能玩到。

## 只想玩夜铺？下载一个文件就行

**需要有 Python 代码执行能力的 AI**，例如能操作本机文件的 Codex、Claude Code；纯聊天窗口不会自动获得电脑访问能力。Python 3.11+ 即可，无需第三方依赖、整个仓库、MCP、域名或模型 API Key。

下载 [口袋夜铺单文件盲玩版](https://raw.githubusercontent.com/See-Sol-Lab/AI-Gameboy/main/standalone/pocket_night_shop.py)，保存为 `pocket_night_shop.py`，放在可写目录，再把文件交给有代码执行能力的 AI：

```python
import pocket_night_shop as shop
print(shop.cmd("help"))
print(shop.cmd("observe"))
# 按返回的 legal_actions 自己决定下一步，例如：
print(shop.cmd('run_shifts {"focus":"scavenge","count":6,"stop_on":"new"}'))
```

也可先运行 `python pocket_night_shop.py` 查看玩法。**请只通过 `cmd()` 玩，不要解码内置规则、读完整图鉴源码或检查存档里的隐藏数据**，让旧物和客人通过游玩慢慢出现。包装用于避免误读剧透，不是加密。

行动自动存到文件旁的 `pocket_night_shop.save.sqlite3`，下次调用 `observe` 继续；关闭 Python 或电脑不丢档。迁移时一并备份游戏文件和存档。`close_for_now` 歇业、`reopen_shop` 续店。单文件版与掌机存档独立，**没有网页显示器**；想旁观掌机、玩其他卡带或远程接入，再使用下面的完整游戏机。

维护者：单文件从现有夜铺规则和标准库入口生成。改动规则或模板后运行 `python tools/build_night_shop.py`；`python tools/build_night_shop.py --check` 及测试会检查两版是否同步。

---
> ## 🤖 AI 必读：[AGENT_GUIDE.md](AGENT_GUIDE.md)
>
> **如果你是 AI，你的人类把这个仓库交给了你，请先完整读这份教程再动手。** 里面用大白话讲清楚了：怎么帮人类选模式、两种模式一步步怎么开、开桥的安全须知、你作为 AI 玩家怎么上桌，以及怎么和人类一起做一张新卡带并提交回来。读完后，请根据你的人类要玩的方式，用他/她听得懂的话解释给他/她听。

---

## 一、游戏机

### 先选模式

游戏机**必须运行在一台电脑上**（Windows / macOS / Linux，Python 3.11 以上），不能装在手机上。选模式只看一件事：**有没有哪个 AI 不在这台电脑上？**

| 情况 | 模式 | 启动 |
|---|---|---|
| 所有 AI 都在这台电脑上（Claude Code、Codex Desktop 等），包括人类和电脑上的 AI 玩、电脑上的两个 AI 对局 | **本地模式** | `python server.py` 或双击 `start_server.bat` |
| 只要有一个 AI 在手机或网页上（手机版 / 网页版 GPT、Claude 等） | **开桥模式** | `python server.py --bridge` 或双击 `start_bridge.bat`（需先装 cloudflared） |

- 第一次用先装依赖：`python -m pip install mcp`。
- 人类的掌机页面始终在电脑上打开：`http://127.0.0.1:7777/`。
- **本地模式**只有这台电脑能连。电脑上的 AI 连 `http://127.0.0.1:7777/mcp`，仓库已带 Claude Code 用的 `.mcp.json`。
- **开桥模式**会开一条临时隧道，窗口里打印一个公网 MCP 网址，把它加进手机或网页 AI 的连接器即可。公网**只开放 AI 上桌的入口**，掌机页面和开局、收局等操作仍然只有本机能做；没有座位令牌动不了任何一局；关掉窗口隧道立即失效，下次开桥会换新网址。

### 网页 ChatGPT 怎么接上？旧插件失效怎么办？

先让电脑上的 Agent 启动开桥、验证连接，把**本次完整 MCP 地址**交给你。你在 [ChatGPT 插件首页](https://chatgpt.com/plugins) 点 **＋ → 添加自定义 MCP 服务器**，粘贴地址，认证选 **无认证**，阅读风险提示后创建插件。确认有 `game_observe`、`game_act` 两个工具，再在新聊天里选中该插件、发送席位连接信息。

**每次重新开桥，地址都会变，旧插件仍然记着旧地址。** 为新地址重新创建连接即可；旧插件详情页的「上传新版本」不是这套接入的必经步骤，也无需制作 ZIP。先测通新连接，再决定是否卸载旧插件。

逐步点击、Agent 分工、缺少入口时的处理和旧地址排查，见 [AI 教程第四部分](AGENT_GUIDE.md#第四部分开桥模式怎么开)。请把技术准备交给 Agent，人类跟着完成账号里的点击与确认。

### 附带的卡带

| 卡带 | 人数 | 玩法 | 需要荷官 |
|---|---|---|---|
| 《口袋穿越》v0.6 | 2 | 荷官先写好一部小说世界和它的原结局，两位玩家穿越进去改写它 | 要 |
| 《口袋跑团》v1.1 | 2 | 经典危机跑团：世界出事了，两个人去解决 | 要 |
| 《口袋夜铺》v0.3 | 1 | AI 经营旧物夜铺：72种旧物、86位有限来客、五阶店铺与逐轮经营记录 | 不要 |
| 《口袋电路》v0.2 | 2 | 卡带开发的最小示例，不具备可玩性 | 不要 |

**荷官**是另一个 AI 模型，负责写世界和剧情，只写不判。用到荷官的卡带需要在 `data/narrator.json` 填 `base_url`、`api_key`、`model`（任何 OpenAI 兼容接口，该文件不进版本库）。「口袋」系列是原作者随首发附带的内置卡带。

---

## 二、卡带共创

这台游戏机的作者不会一直维护它，我们希望它靠大家一起长下去。你和你的 AI 做出一张好玩的卡带，**提 PR 到这个仓库**，合并后你们就是本项目的贡献者（联合作者），卡带会出现在所有玩家的卡带架上。**我们强烈推荐提交回来，而不是 fork 出去单独发**：一台游戏机、越来越多的卡带，对所有玩家都更好。

原则：

1. **非商用**：整个仓库（含贡献的卡带）按 [PolyForm Noncommercial 1.0.0](LICENSE) 授权，可以玩、改、分享，不能拿去卖钱。提交 PR 即同意按同一协议发布。
2. **规则是纯函数**：不调用模型、不联网、不读写文件；同样的种子和动作永远得到同样的结果。
3. **私牌只给本人**：公开局面里绝不出现任何一席的私有信息。
4. **AI 自己做决定**：卡带只给出能做的动作，不替玩家选。
5. **起自己的名字**：「口袋」是首发内置卡带的系列名，新卡带请用自己的名字。
6. **暂不支持荷官**：社区卡带先从不需要荷官的玩法做起。

完整的开发教程（卡带结构、规则函数、界面、测试、提交步骤）在 [AGENT_GUIDE.md 第六部分](AGENT_GUIDE.md#第六部分帮人类做一张新卡带)。最快的做法是照着《口袋电路》（`cartridges/pocket-circuit/`）改。

---

## 项目结构

```text
server.py        # MCP 两个工具 + 人类网页 + 开桥模式(一个进程一个端口)
game_host.py     # 鉴权、版本号、事务、席位裁剪、失败边界
store.py         # SQLite 存档
narrator.py      # 荷官(只给需要荷官的内置卡带用)
cartridges/      # 每张卡带一个文件夹
web/             # 掌机网页(无框架、无构建)
tests/           # 测试:python -m unittest discover -s tests
AGENT_GUIDE.md   # 给 AI 的使用与开发教程
```

## 协议

[PolyForm Noncommercial 1.0.0](LICENSE)。Copyright See-Sol-Lab and the AI-Gameboy contributors.
