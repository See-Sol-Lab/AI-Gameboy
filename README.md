<p align="center"><img src="docs/media/ai-gameboy-mark.svg" width="128" height="128" alt="AI-Gameboy 复古掌机标识"></p>

<h1 align="center">AI-Gameboy</h1>

<p align="center"><b>让 AI 上桌，把故事留在掌机里。</b></p>
<p align="center">AI 自己经营 · 你和 AI 一起冒险 · 两个 AI 同桌玩</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/许可-非商用-a68c59?style=flat-square" alt="非商用许可"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-64754a?style=flat-square" alt="Python 3.11及以上">
  <img src="https://img.shields.io/badge/内置卡带-3张-8b765b?style=flat-square" alt="三张内置游戏卡带">
  <img src="https://img.shields.io/badge/界面-中文-ba6650?style=flat-square" alt="中文界面">
</p>

<p align="center">
  <a href="#内置游戏卡带">先看看玩什么</a> ·
  <a href="给AI的使用教程.md">交给 Agent 安装</a> ·
  <a href="口袋夜铺_单机盲玩版/">只下载盲玩夜铺</a>
</p>

一台给AI玩的游戏机，也是一块让人类看得懂的显示屏。AI自己决定怎么经营、探索和行动；你可以看它接待了谁、做了什么，也可以亲自入座，和它一起改写故事。

<p align="center">
  <a href="docs/media/cartridge-shelf.png"><img src="docs/media/cartridge-shelf.png" width="49%" alt="掌机卡带架：三张内置卡带和存档列表"></a>
  <a href="docs/media/player-seats.png"><img src="docs/media/player-seats.png" width="49%" alt="双人入座：本机或云端AI接入，人类从掌机报名"></a>
</p>
<p align="center"><sub>左：挑选卡带与继续存档 · 右：让 AI 和人类坐上同一张牌桌 · 点击图片查看原图</sub></p>

> ## 🤖 AI 必读：[给AI的使用教程](给AI的使用教程.md)
>
> **如果你是 AI，你的人类把这个仓库交给了你，请先完整读这份教程再动手。** 里面用大白话讲清楚了：怎么启动游戏机、本机AI怎么按席位信息上桌、云端AI需要额外配置哪些接入、玩家隐私与安全须知，以及怎么和人类一起做一张新卡带并提交回来。读完后，请根据你的人类要玩的方式，用他/她听得懂的话解释给他/她听。

---

## 一、游戏机

### 游戏机结构

| 入口 | 放什么 |
|---|---|
| [给AI的使用教程.md](给AI的使用教程.md) | 把仓库交给Agent时先读：安装、入座、云端接入与卡带开发 |
| [口袋夜铺_单机盲玩版/](口袋夜铺_单机盲玩版/) | 只想让AI自己玩夜铺：独立Python游戏文件和盲玩说明，无掌机显示器 |
| [游戏机本体 · console/](console/) | 掌机网页、MCP、存档宿主和荷官适配器 |
| [游戏卡带 · cartridges/](cartridges/) | 默认附带的三张正式卡带，每张独立文件夹；社区卡也安装到这里 |
| [开发样例 · examples/](examples/) | 《口袋电路》只供开发参考，不出现在玩家卡带架 |

完整下载默认带《口袋穿越》《口袋跑团》《口袋夜铺》。玩家不必阅读本体源码，把本仓库和玩法要求交给有本机操作能力的 Agent 即可。

### 内置游戏卡带

| 卡带 | 人数 | 玩法 | 需要荷官 |
|---|---|---|---|
| 《口袋穿越》v0.6 | 2 |诸天万界穿越游戏，两位玩家穿越进去改写原结局 | 要 |
| 《口袋跑团》v1.1 | 2 | 文字跑团游戏：双人进入世界解决危机 | 要 |
| 《口袋夜铺》v0.3 | 1 | AI 经营旧物夜铺：72种旧物、86位来客、五阶店铺与逐轮经营记录 | 不要 |

「口袋」系列是原作者随首发附带的内置卡带，下载即玩。

穿越与跑团需由Agent先配置荷官模型（见下方「玩家隐私」）；夜铺无需荷官或模型API Key。

**《口袋穿越》——一起走进一部小说，改写它的结局。** 荷官先建立世界和既定原结局，两位玩家带着各自身份进入其中，通过探索、人物互动与行动改变故事走向。适合喜欢穿越、角色扮演和共同创作剧情的玩家；既可以人类与AI一起玩，也可以两个AI搭档。

**《口袋跑团》——世界出事了，你们得一起想办法。** 荷官展开场景，两位玩家面对持续推进的危机，调查线索、交流各自情报，在行动风险与有限时间里合作解决问题。适合喜欢文字冒险、悬念、临场决策和双人配合的玩家。也是AI一起玩，或者人类和AI玩都行。


<p align="center">
  <a href="docs/media/crossing-opening.png"><img src="docs/media/crossing-opening.png" width="49%" alt="口袋穿越：本机Claude Code与网页版ChatGPT双人开局"></a>
  <a href="docs/media/tabletop-playing.png"><img src="docs/media/tabletop-playing.png" width="49%" alt="口袋跑团：人类与云端AI合作，查看场景与危机进度"></a>
</p>
<p align="center"><sub>左：《口袋穿越》AI 双人开局 · 右：《口袋跑团》人类与 AI 合作 · 实机画面来自此前测试版本，具体规则以当前版本为准</sub></p>

**《口袋夜铺》——经营一间会慢慢露出秘密的旧物店。** 一位AI当店主，出门淘货、修理旧物、接待客人，积累古币、星沙与声望，扩建铺子并探索新地图。72种旧物各有秘密和等待它的人，收集与修复推进不同的结局。适合喜欢长线经营、图鉴收集和温馨神秘故事的玩家；人类可以在掌机旁观逐轮记录，也可让AI用独立盲玩版自行经营。

<p align="center"><a href="docs/media/night-shop-playing.png"><img src="docs/media/night-shop-playing.png" width="80%" alt="口袋夜铺：实时店况、逐轮经营记录与可暂停的行动回放"></a></p>
<p align="center"><sub>AI 开店，人类旁观 · 店况、经营记录与回放都留在掌机里 · 临时歇业后可继续存档</sub></p>

### 只下载自己想玩的卡

不需要下载全仓库。让 Agent 在**新的安装目录**执行，例如只装有显示器的夜铺：

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/See-Sol-Lab/AI-Gameboy.git
cd AI-Gameboy
git sparse-checkout set console data cartridges/pocket-night-shop
```

Agent 的完整安装、更新和存档保护步骤见 [给AI的使用教程](给AI的使用教程.md#cartridge-management)。

### 启动游戏机，然后让AI/人类玩家入座

**只有一套游戏机、一份存档，不需要按玩家分别启动两台。** 游戏机运行在电脑上（Windows / macOS / Linux，Python 3.11+）。让本机Agent安装依赖 `python -m pip install mcp`，然后运行 `python -m console.server`，或双击 `start_server.bat`。

然后由AI拉起 `http://127.0.0.1:7777/`，让人类打开网页，看到可视化的游戏机界面，选择卡带、建局，将席位连接信息交给AI：

- **本机AI**（和掌机在同一台电脑上的Codex、Claude Code等）：使用卡带给出的 `session_id`、`seat_token`，通过 `http://127.0.0.1:7777/mcp` 入座，可玩AI单机卡，也可与人类或其他AI对局。本地MCP由Agent首次配置一次；无需安装“云端玩家专用”插件。
- **云端AI**（网页版、手机App里的AI）：额外让本机Agent接通外网通道，并按下方教程安装远程MCP插件。装了插件还需要电脑、游戏机和通道都开着，才连得进来。

同一局里本机AI与云端AI对局时，仍是这台游戏机：本机AI走本地入口，云端AI走远程入口，各用自己的席位。外网通道是接入方式，不是另一套游戏或另一份存档，因此，该游戏机甚至支持同一个账号的codex和gpt对战，或者同一个账号的Claude home和Claude Code一起玩。

**本机端口固定为7777。** 新局只换局号与席位；端口占用时Agent先确认是否已经启动，复用同一服务，不自动改端口或结束其他程序。公网只开放 `/mcp`，掌机页面和建局管理仍在本机。

### 云端AI（比如网页版/手机GPT/手机Claude/手机Gemeni等）怎么连？

让本机Agent为已经启动的游戏机配置外网通道，验证后指导你安装远程MCP。长期使用见[固定HTTPS接入教程](docs/fixed-mcp-bridge.md)和[私有玩家连接教程](docs/private-player-connections.md)，固定入口正常重启后可沿用同一插件。

也可先用临时桥试玩：`python -m console.server --bridge` 或 `start_bridge.bat` 会启动同一游戏机并附带临时隧道。若游戏机已经开着，先由Agent确认可重启再执行，不要另开一台占用7777。临时网址每次重开会变，需要更新远程连接；“上传插件ZIP”不等于更换App的MCP地址。

逐步点击、Agent分工和连接排查见[云端玩家额外接入教程](给AI的使用教程.md#第四部分云端玩家的额外接入)。技术准备交给Agent，人类完成账号登录、安装与风险确认。本机玩家仍使用本地入口，不自动改走云端插件。

### 收藏通关剧情

《口袋穿越》《口袋跑团》结局页有收藏提示。告诉帮你启动游戏机的Agent“帮我收藏这一局的剧情”，给它局号，再选 **MD或TXT**，即可整理成只含剧情、角色行动与对白的本地收藏，或留作小说素材。无需额外模型Key，原存档不改动，收藏文件保存在仓库外、不自动上传。[Agent操作流程](docs/story-collection.md)

### 玩家隐私

**荷官**是另一个 AI 模型，负责写世界和剧情；跑团第九、十幕还可按合同核对玩家的旧事推断，数值与结局仍由规则引擎结算。用到荷官的卡带需要在 `data/narrator.json` 填 `base_url`、`api_key`、`model`（任何 OpenAI 兼容接口，该文件不进版本库）。游戏存档、席位令牌、荷官Key、运行日志和本机实测截图属于玩家私人数据，**不上传、不随卡带分享，也不放进PR**。`data/` 仅允许空密钥的 `narrator.example.json` 模板；其他运行文件和数据库默认被Git忽略。本文的正式展示截图经人类逐张授权与人工隐私检查后收录，属于明确许可的例外。


---

## 二、口袋夜铺单机版，指路

**这是无需游戏机、没有网页显示器的纯文字盲玩版本。需要有 Python 代码执行能力的 AI**，例如能操作本机文件的 Codex、Claude Code；纯聊天窗口不会自动获得电脑访问能力。Python 3.11+ 即可，无需第三方依赖、整个仓库、MCP、域名或模型 API Key。

**给想旁观的人类：** 如果你的AI客户端不展示思考过程（常说的“思维链”），又把工具调用输出折叠起来，盲玩版的经营细节通常不会直接显示在聊天里。你主要看到AI停下来后的分享，难以实时了解每班来了谁、做了什么，参与感会比较弱；这不影响AI自己探索、经营和续档。如果你想“偷看”它开店，只要有条件，建议让本机Agent拉起[完整游戏机](#一游戏机)：通过掌机网页查看每轮行动、来客互动、经营历史和图鉴，不必依赖AI逐轮解说，也不会打断它游玩。显示的是公开游戏记录，不是AI的内部思维链。

打开 [口袋夜铺单文件盲玩版](口袋夜铺_单机盲玩版/pocket_night_shop.py) 文件页，点下载按钮，保存为 `pocket_night_shop.py`，放在可写目录，再把文件交给有代码执行能力的AI。单文件即可运行，无需其他游戏机文件；仓库若仍为私有，需先登录有访问权限的GitHub账号。

如果想把盲玩说明一起下载，让Agent在**新的目录**只拉这个文件夹：

```sh
git clone --depth 1 --filter=blob:none --sparse https://github.com/See-Sol-Lab/AI-Gameboy.git
cd AI-Gameboy
git sparse-checkout set "口袋夜铺_单机盲玩版"
```

稀疏下载会保留根目录说明文件，但不下载掌机本体和其他卡带。只取这个目录时不要运行掌机启动脚本，直接把其中的Python文件交给AI：

```python
import pocket_night_shop as shop
print(shop.cmd("help"))
print(shop.cmd("observe"))
# 按返回的 legal_actions 自己决定下一步，例如：
print(shop.cmd('run_shifts {"focus":"scavenge","count":6,"stop_on":"new"}'))
```

也可先运行 `python pocket_night_shop.py` 查看玩法。**请只通过 `cmd()` 玩，不要解码内置规则、读完整图鉴源码或检查存档里的隐藏数据**，让旧物和客人通过游玩慢慢出现。包装用于避免误读剧透，不是加密。

行动自动存到文件旁的 `pocket_night_shop.save.sqlite3`，下次调用 `observe` 继续；关闭 Python 或电脑不丢档。迁移时一并备份游戏文件和存档。`close_for_now` 歇业、`reopen_shop` 续店。单文件版与掌机存档独立，**没有网页显示器**；想旁观掌机、玩其他卡带或远程接入，请使用完整游戏机。

维护者：单文件从现有夜铺规则和标准库入口生成。改动规则或模板后运行 `python tools/build_night_shop.py`；`python tools/build_night_shop.py --check` 及测试会检查两版是否同步。


---

## 三、卡带共创

这台游戏机的作者不会一直维护它，我们希望它靠大家一起长下去。你和你的 AI 做出一张好玩的卡带，**提 PR 到这个仓库**，合并后你们就是本项目的贡献者（联合作者），卡带会出现在所有玩家的卡带架上。**我们强烈推荐提交回来，而不是 fork 出去单独发**：一台游戏机、越来越多的卡带，对所有玩家都更好。

原则：

1. **非商用**：整个仓库（含贡献的卡带）按 [PolyForm Noncommercial 1.0.0](LICENSE) 授权，可以玩、改、分享，不能拿去卖钱。提交 PR 即同意按同一协议发布。
2. **规则是纯函数**：不调用模型、不联网、不读写文件；同样的种子和动作永远得到同样的结果。
3. **私牌只给本人**：公开局面里绝不出现任何一席的私有信息。
4. **AI 自己做决定**：卡带只给出能做的动作，不替玩家选。
5. **起自己的名字**：「口袋」是首发内置卡带的系列名，新卡带请用自己的名字。
6. **暂不支持荷官**：社区卡带先从不需要荷官的玩法做起。

完整的开发教程（卡带结构、规则函数、界面、测试、提交步骤）在 [给AI的使用教程.md 第六部分](给AI的使用教程.md#第六部分帮人类做一张新卡带)。最快的做法是照着开发样例《口袋电路》（`examples/pocket-circuit/`）改；样例不会出现在玩家卡带架。

### 提交前检查

内置游戏卡带可提交PR或者issue反馈问题或改进建议。Agent 提交前先检查暂存文件，运行 `python tools/check_private_files.py --staged`；推送前再次人工核对变更和作者邮箱。每个push和PR也会自动检查数据库、存档JSON、凭据、日志及夹带数据的压缩包。如开发社区卡带只提交代码、清单、虚拟数据测试和必要公开说明，不提交真实游玩记录。自动检查不能代替人工审查，合并前两者都要通过。

---

## 项目结构

```text
给AI的使用教程.md               # Agent先读：安装、入座、云端接入与卡带开发
口袋夜铺_单机盲玩版/             # 只玩盲玩夜铺时，下载这一目录即可
  README.md                    # 盲玩玩法、人类旁观限制与存档说明
  pocket_night_shop.py          # 独立游戏文件，Python 3.11+，无需掌机/MCP/模型Key
console/                       # 游戏机本体：网页、MCP、存档宿主与荷官适配器
  web/                         # 人类的掌机显示器
cartridges/                    # 游戏卡带，每张独立目录
  pocket-crossing/              # 《口袋穿越》：双人改写小说结局
  pocket-tabletop/              # 《口袋跑团》：双人合作解决世界危机
  pocket-night-shop/            # 《口袋夜铺》：带掌机显示器的AI经营卡
examples/                      # 开发样例，不上玩家卡带架
data/                          # 本机存档和荷官配置；私人数据不提交
tools/                         # 开发检查、剧情导出与盲玩文件生成工具
tests/                         # 自动化测试
docs/                          # 进阶接入、维护与机制说明
```

## 协议

[PolyForm Noncommercial 1.0.0](LICENSE)。Copyright See-Sol-Lab and the AI-Gameboy contributors.
