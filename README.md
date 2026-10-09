# AI-Gameboy

一台给 AI 玩的游戏机。AI 通过 MCP 坐上牌桌、自己做决定；人类在网页上的掌机里旁观，也可以亲自坐一席和 AI 对局。

游戏装在**卡带**里。首发自带几张卡带，**任何人都可以给它做新卡带并提交到这个仓库**，让后来的每个玩家都能玩到。

## 只想玩夜铺？单文件版（纯文字盲玩，无掌机显示）

**这是无需游戏机、没有网页显示器的纯文字盲玩版本。需要有 Python 代码执行能力的 AI**，例如能操作本机文件的 Codex、Claude Code；纯聊天窗口不会自动获得电脑访问能力。Python 3.11+ 即可，无需第三方依赖、整个仓库、MCP、域名或模型 API Key。

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

### 先看目录：本体、游戏卡、样例分开

| 入口 | 放什么 |
|---|---|
| [console/](console/) | 掌机本体：网页、MCP、存档宿主和荷官适配器 |
| [cartridges/](cartridges/) | 默认附带的三张正式卡带，每张一个独立文件夹；社区卡带也安装到这里 |
| [examples/](examples/) | 开发样例《口袋电路》，不出现在玩家卡带架 |
| [standalone/](standalone/) | 无掌机显示的单文件盲玩游戏 |

完整下载默认带《口袋穿越》《口袋跑团》《口袋夜铺》。玩家不必阅读本体源码，把本仓库和玩法要求交给有本机操作能力的 Agent 即可。

### 只下载自己想玩的卡

不需要下载全仓库。让 Agent 在**新的安装目录**执行，例如只装有显示器的夜铺：

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/See-Sol-Lab/AI-Gameboy.git
cd AI-Gameboy
git sparse-checkout set console data cartridges/pocket-night-shop
```

以后想加其他首发卡，可以执行 `git sparse-checkout add cartridges/pocket-crossing` 或 `git sparse-checkout add cartridges/pocket-tabletop`。这只下载本体和选中的卡带文件。已有存档的安装请先检查依赖，不要通过缩小 sparse 范围移除仍有存档的卡带。

### 不喜欢某张卡？隐藏或卸载

让 Agent 在仓库根目录操作：

```sh
python -m console.cartridges list
python -m console.cartridges hide pocket-crossing
python -m console.cartridges show pocket-crossing
python -m console.cartridges install /path/to/downloaded-card
```

- `hide`：从卡带架收起，保留游戏文件与全部旧局；`show` 恢复显示。
- `install`：复制一张已下载、检查过的卡带文件夹，不覆盖同id卡带。安装第三方规则前，Agent 应说明来源并获得人类同意。
- `uninstall`：确认人类同意后运行 `python -m console.cartridges uninstall <卡带id> --yes`，会删除整张卡的目录。只要还有任何局引用它（包括已结束的局），就会拒绝；请改用 `hide`。**这些命令不删除玩家存档或荷官Key。**

操作后刷新卡带架即可。Agent 的完整安装、更新和存档保护步骤见 [使用教程](AGENT_GUIDE.md#cartridge-management)。

### 先选模式

游戏机**必须运行在一台电脑上**（Windows / macOS / Linux，Python 3.11 以上），不能装在手机上。选模式只看一件事：**有没有哪个 AI 不在这台电脑上？**

| 情况 | 模式 | 启动 |
|---|---|---|
| 所有 AI 都在这台电脑上（Claude Code、Codex Desktop 等），包括人类和电脑上的 AI 玩、电脑上的两个 AI 对局 | **本地模式** | `python -m console.server` 或双击 `start_server.bat` |
| 只要有一个 AI 在手机或网页上（手机版 / 网页版 GPT、Claude 等） | **开桥模式** | `python -m console.server --bridge` 或双击 `start_bridge.bat`（需先装 cloudflared） |

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

**荷官**是另一个 AI 模型，负责写世界和剧情，只写不判。用到荷官的卡带需要在 `data/narrator.json` 填 `base_url`、`api_key`、`model`（任何 OpenAI 兼容接口，该文件不进版本库）。「口袋」系列是原作者随首发附带的内置卡带。

### 收藏通关剧情

《口袋穿越》《口袋跑团》结局页有收藏提示。告诉帮你启动游戏机的Agent“帮我收藏这一局的剧情”，给它局号，再选 **MD或TXT**，即可整理成只含剧情、角色行动与对白的本地收藏，或留作小说素材。无需额外模型Key，原存档不改动，收藏文件保存在仓库外、不自动上传。[Agent操作流程](docs/story-collection.md)

### 玩家隐私与提交检查

游戏存档、席位令牌、荷官Key、运行日志和本机实测截图属于玩家私人数据，**不上传、不随卡带分享，也不放进PR**。`data/` 仅允许空密钥的 `narrator.example.json` 模板；其他运行文件和数据库默认被Git忽略。

Agent 提交前先检查暂存文件，运行 `python tools/check_private_files.py --staged`；推送前再次人工核对变更和作者邮箱。每个push和PR也会自动检查数据库、存档JSON、凭据、日志及夹带数据的压缩包。社区卡带只提交代码、清单、虚拟数据测试和必要公开说明，不提交真实游玩记录。自动检查不能代替人工审查，合并前两者都要通过。

本仓库现仅保留每张卡带的当前规则，退役原型和旧版规则已移除，不再提供旧版夜铺升级入口。旧版存档不能自动套用当前规则；未来如有不兼容更新，应先向玩家说明并另行设计迁移，不能擅自删除玩家存档。私人恢复备份应放在仓库外，不能提交。

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

完整的开发教程（卡带结构、规则函数、界面、测试、提交步骤）在 [AGENT_GUIDE.md 第六部分](AGENT_GUIDE.md#第六部分帮人类做一张新卡带)。最快的做法是照着开发样例《口袋电路》（`examples/pocket-circuit/`）改；样例不会出现在玩家卡带架。

---

## 项目结构

```text
console/         # 掌机本体，网页在 console/web/
cartridges/      # 三张首发卡 + 安装的社区卡，每张一个文件夹
examples/        # 开发样例，不上玩家卡带架
standalone/      # 单文件纯文字盲玩版，无掌机网页
data/            # 本机存档、隐藏清单和荷官配置；私人文件不提交
tools/           # 卡带检查与单文件生成工具
tests/           # 测试:python -m unittest discover -s tests
AGENT_GUIDE.md   # 给 AI 的使用与开发教程
```

## 协议

[PolyForm Noncommercial 1.0.0](LICENSE)。Copyright See-Sol-Lab and the AI-Gameboy contributors.
