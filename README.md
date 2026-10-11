# AI-Gameboy

一台给 AI 玩的游戏机。AI 通过 MCP 坐上牌桌、自己做决定；人类在网页上的掌机里旁观，也可以亲自坐一席和 AI 对局。

游戏装在**卡带**里。首发自带几张卡带，**任何人都可以给它做新卡带并提交到这个仓库**，让后来的每个玩家都能玩到。

> ## 🤖 AI 必读：[AGENT_GUIDE.md](AGENT_GUIDE.md)
>
> **如果你是 AI，你的人类把这个仓库交给了你，请先完整读这份教程再动手。** 里面用大白话讲清楚了：怎么启动游戏机、本机AI怎么按席位信息上桌、云端AI需要额外配置哪些接入、玩家隐私与安全须知，以及怎么和人类一起做一张新卡带并提交回来。读完后，请根据你的人类要玩的方式，用他/她听得懂的话解释给他/她听。

---

## 口袋夜铺单机版，指路

**这是无需游戏机、没有网页显示器的纯文字盲玩版本。需要有 Python 代码执行能力的 AI**，例如能操作本机文件的 Codex、Claude Code；纯聊天窗口不会自动获得电脑访问能力。Python 3.11+ 即可，无需第三方依赖、整个仓库、MCP、域名或模型 API Key。

**给想旁观的人类：** 如果你的AI客户端不展示思考过程（常说的“思维链”），又把工具调用输出折叠起来，盲玩版的经营细节通常不会直接显示在聊天里。你主要看到AI停下来后的分享，难以实时了解每班来了谁、做了什么，参与感会比较弱；这不影响AI自己探索、经营和续档。如果你想“偷看”它开店，只要有条件，建议让本机Agent拉起[完整游戏机](#一游戏机)：通过掌机网页查看每轮行动、来客互动、经营历史和图鉴，不必依赖AI逐轮解说，也不会打断它游玩。显示的是公开游戏记录，不是AI的内部思维链。

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

Agent 的完整安装、更新和存档保护步骤见 [使用教程](AGENT_GUIDE.md#cartridge-management)。

### 启动游戏机，然后让AI入座

**只有一套游戏机、一份存档，不需要按玩家分别启动两台。** 游戏机运行在电脑上（Windows / macOS / Linux，Python 3.11+）。让本机Agent安装依赖 `python -m pip install mcp`，然后运行 `python -m console.server`，或双击 `start_server.bat`。

人类打开 `http://127.0.0.1:7777/`，选择卡带、建局，将该席位的连接信息交给要玩的AI：

- **本机AI**（和掌机在同一台电脑上的Codex、Claude Code等）：使用卡带给出的 `session_id`、`seat_token`，通过 `http://127.0.0.1:7777/mcp` 入座，可玩AI单机卡，也可与人类或其他AI对局。本地MCP由Agent首次配置一次；无需安装“云端玩家专用”插件。
- **云端AI**（网页版、手机App里的AI）：额外让本机Agent接通外网通道，并按下方教程安装远程MCP插件。装了插件还需要电脑、游戏机和通道都开着，才连得进来。

同一局里本机AI与云端AI对局时，仍是这台游戏机：本机AI走本地入口，云端AI走远程入口，各用自己的席位。外网通道是接入方式，不是另一套游戏或另一份存档。

**本机端口固定为7777。** 新局只换局号与席位；端口占用时Agent先确认是否已经启动，复用同一服务，不自动改端口或结束其他程序。公网只开放 `/mcp`，掌机页面和建局管理仍在本机。

### 云端AI（比如官GPT） 怎么接上？旧插件失效怎么办？

让本机Agent为已经启动的游戏机配置外网通道，验证后指导你安装远程MCP。长期使用见[固定HTTPS接入教程](docs/fixed-mcp-bridge.md)和[私有玩家连接教程](docs/private-player-connections.md)，固定入口正常重启后可沿用同一插件。

也可先用临时桥试玩：`python -m console.server --bridge` 或 `start_bridge.bat` 会启动同一游戏机并附带临时隧道。若游戏机已经开着，先由Agent确认可重启再执行，不要另开一台占用7777。临时网址每次重开会变，需要更新远程连接；“上传插件ZIP”不等于更换App的MCP地址。

逐步点击、Agent分工和连接排查见[云端玩家额外接入教程](AGENT_GUIDE.md#第四部分云端玩家的额外接入)。技术准备交给Agent，人类完成账号登录、安装与风险确认。本机玩家仍使用本地入口，不自动改走云端插件。

### 内置游戏卡带

| 卡带 | 人数 | 玩法 | 需要荷官 |
|---|---|---|---|
| 《口袋穿越》v0.6 | 2 |诸天万界穿越游戏，两位玩家穿越进去改写原结局 | 要 |
| 《口袋跑团》v1.1 | 2 | 文字跑团游戏：双人进入世界解决危机 | 要 |
| 《口袋夜铺》v0.3 | 1 | AI 经营旧物夜铺：72种旧物、86位来客、五阶店铺与逐轮经营记录 | 不要 |

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
