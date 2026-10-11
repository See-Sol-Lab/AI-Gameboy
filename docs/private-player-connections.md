# 长期私有玩家连接（给负责安装的 Agent）

目标：每位AI安装自己的MCP一次，席位凭证由本机保存。模型失忆、传输断线或服务重启后调用 `game_resume`，就能回到已授权的局。不会新建存档，也不会公开席位token。

## 安装一次

**人类负责账号登录、确认安装和首次授权席位；电脑上的Agent负责启动、生成私有地址、检查连接。** 不要求人类手工改数据库或代码。以下命令中的Python须是Agent确认能正常运行的解释器。

### 给Agent的配置命令

掌机启动后，在仓库根目录执行（PowerShell）：

```powershell
$playerConfig = Join-Path $env:USERPROFILE 'Documents\AI-Gameboy-Private\web-player.json'
python tools/setup_player_connection.py --name '网页玩家' --output $playerConfig
```

若掌机通过单独配置的固定隧道接入，添加 `--public-mcp-url`，填写该玩家自己的真实固定入口：

```powershell
python tools/setup_player_connection.py --name '网页玩家' --output $playerConfig --public-mcp-url 'https://你的真实固定入口/mcp'
```

这只是格式示例，不能复制示例域名去安装。命令只打印私人文件位置，不打印秘密网址。打开生成的JSON，将完整 `mcp_url` 交到该玩家的连接器设置中。不要把它作为对话消息发给AI。文件已存在时命令拒绝再创建，正常重启无需重跑；切勿为了重新安装而删除原配置。

### 人类在ChatGPT网页点什么

1. 打开 [插件首页](https://chatgpt.com/plugins)，点 **＋ → 添加自定义MCP服务器**。
2. 名称填一个能区分玩家的名字，例如“游戏机 · 网页玩家”。连接选择服务器URL，将私人JSON里的完整 `mcp_url` 粘进去，保留 `?player=...`。
3. 认证选 **无认证 / No authentication**；地址中已经包含此玩家的连接凭证，不能分享。阅读风险提示后创建、安装。
4. 在聊天中通过 `@` 选中这一只私有插件。应有 `game_connect`、`game_resume`、`game_observe`、`game_act` 四个工具。
5. 初次发掌机生成的席位信息，并说明“先game_connect绑定，再按legal_actions入座”。之后只说“继续游戏，先game_resume”即可，不用反复补token。

旧App绑定型插件不一定能通过上传ZIP更换服务器地址。若当前入口无法编辑地址，一次性新建该玩家的私有连接，并保留旧插件直到新连接验收成功。可由具备插件创建能力的Agent协助；创建成功仍需确认安装和实际调用。步骤根据[OpenAI官方自定义MCP说明](https://developers.openai.com/api/docs/guides/custom-mcp-server)核对于2026-10-10。

### 安装与验收清单

1. 先启动掌机，并确认 `/api/bridge` 返回的是实际可达的MCP入口。云端AI若需要长期复用，先配置固定HTTPS入口；临时隧道重启后仍会换公网地址。
2. 在掌机本机向 `POST http://127.0.0.1:7777/api/player-connections` 提交JSON `{"name":"网页AI玩家"}`。此接口只允许本机使用，远程桥无法创建连接。返回的 `mcp_url` 带有随机玩家连接凭证，只有这一次会显示；它不是普通分享链接。保存在用户自己的连接器配置或仓库外私人文件中，别放到聊天、截图、Git或日志里。
3. 为该玩家安装自定义MCP，使用返回的完整URL（必须保留查询参数），认证选择“无认证”：实际访问权限由URL中的随机凭证授予。每位AI各创建一个连接，双人局不能共用。它可以沿用同一固定入口，但玩家地址各不相同。
4. 人类首次交给席位信息后，AI在自己的私有连接调用 `game_connect(session_id, seat_token)`。只有席位验证通过才保存绑定；错误token不会覆盖已有绑定。把令牌交给工具后，无需再抄进总结或每轮重复提交。
5. 验收：断开原MCP传输，重新连接，调用无参数 `game_resume`；核对恢复的局号、席位、revision与原局一致，返回JSON不含token。再按legal_actions调用 `game_act(expected_revision=..., action_id=..., params=...)`，省略session_id和seat_token。还需在实际云端客户端中验证它保留URL查询参数。

## 日常使用

- 忘记席位信息：先调用 `game_resume()`，也可以无参数 `game_observe()`。无需向人类索取旧聊天。
- 新开一局：仍在原来的玩家连接中，用人类授予的新席位信息调用 `game_connect`，主动换绑。私有地址保持不变；工具不会自行猜测“最新局”或切换到别人席位。
- 歇业、续档与经营动作继续按legal_actions执行。席位恢复不重置夜铺的人类发言额度。
- 原来的公共 `/mcp` 与手动席位令牌方式继续可用，但公共连接不能自动恢复。未经验证的请求不会获得任何玩家绑定或席位秘密。
- 凭证保存于本机被Git忽略的 `data/gameboy.db` 中；数据库仍是私人运行数据。保留数据库才能跨服务重启恢复，切勿上传或分享它。
- 私有URL遗失、泄漏或授权失效时，请由本机维护Agent与人类确认处理，不能尝试猜测凭证或遍历其他玩家席位。尚未绑定时会明确报错，不会自动发给陌生连接一个席位。

## 常见问题

- **找不到game_resume：** 确认服务已运行新版、选中了私有插件，然后在插件管理中刷新工具元数据。仅有旧版两工具时不要声称恢复已生效。
- **尚未绑定：** 对这条私有连接首次执行game_connect。旧版服务器只保存席位token的哈希，无法凭空找回已经丢失且从未绑定过的原token；请让本机Agent和人类确认处理，勿覆盖原档。新绑定后的长期局不再依赖聊天保存token。
- **403或连接失败：** Agent依次检查本机7777、固定隧道、私有URL是否完整。不要为排错公开URL，也不要删档重开。
- **换电脑：** 游戏数据库、私有配置和固定入口都需要按人类授权迁移；单独拉一份代码不会带走玩家的私人存档。
- **还没有固定公网入口：** [固定HTTPS接入教程](fixed-mcp-bridge.md)提供无自有域名的Cloudflare方案；也能先用临时桥试玩，但重开临时隧道仍需更新公网地址。
