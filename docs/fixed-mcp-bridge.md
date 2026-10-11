# 给云端AI配置固定HTTPS入口

本机Agent直接连 `http://127.0.0.1:7777/mcp` 即可。只有运行在云端的AI需要能从互联网访问的HTTPS入口，且客户端本身必须支持远程MCP。

固定入口和私有玩家连接分工不同：固定入口保证正常重启后网址不变；[私有玩家连接](private-player-connections.md)负责把授权席位留在工具侧。只有其中一项，不能同时解决换网址与忘token。

## 无自有域名：Cloudflare Workers VPC

路径：玩家自己的 `workers.dev` Worker → VPC Service → 同一命名Tunnel → 玩家电脑 `127.0.0.1:7777/mcp`。不需要把游戏数据库、荷官API Key或模型服务搬到云端，也不改玩家已有网站或DNS。Worker只转发游戏请求。

截至2026-10-10，Workers VPC仍在beta，beta期间可在所有Workers套餐免费使用；Worker本身仍受套餐配额限制，不能承诺永久免费或无限调用。Agent安装前核对[官方入门](https://developers.cloudflare.com/workers-vpc/get-started/)和[费用说明](https://developers.cloudflare.com/workers-vpc/platform/pricing/)，任何收费升级须由人类决定。

## Agent负责做，人类负责确认

1. 人类注册、登录自己的Cloudflare账号。Agent核对Node.js、Wrangler与cloudflared是否已安装；只在获准范围内安装依赖。
2. 使用独立Wrangler profile（例如gameboy）完成官方OAuth授权。核对最小实际权限：account:read、user:read、workers_scripts:write、connectivity:admin；刷新授权所需权限由官方流程提示。不要给其他项目复用或扩大权限。OAuth本机回调等待时间有限，让人类准备好后再开启登录。
3. 创建命名Tunnel并记录它的真实ID。使用已配置的profile执行 `wrangler tunnel create ai-gameboy-fixed --profile gameboy`。已有对应Tunnel时复用，切勿每次开机创建新的。
4. 创建HTTP VPC Service，选刚才的Tunnel，只指向 `127.0.0.1` 的HTTP端口7777。命令形式：`wrangler vpc service create ai-gameboy-local --type http --tunnel-id <真实TunnelID> --ipv4 127.0.0.1 --http-port 7777 --profile gameboy`。尖括号是占位说明，由Agent换成真实值；不要再将HTTPS端口也设成7777。
5. 在仓库外私人部署目录保存Worker配置：唯一Worker名称、实际账号ID、当前compatibility_date、`main`指向下方转发脚本；`workers_dev=true`，`observability.enabled=false`，`vpc_services`的binding为GAMEBOY、service_id为上一步真实ID。账号配置和授权凭证不提交游戏仓库。
6. 复制并使用[只转发MCP的脚本](../tools/bridge_worker.mjs)，先部署验证再用真实玩家席位验收。运行 `wrangler deploy --profile gameboy`，保存官方输出的实际workers.dev网址，MCP路径为 `/mcp`。
7. 日常开机只需启动同一Tunnel（`wrangler tunnel run <真实TunnelID> --profile gameboy`）和掌机（`python -m console.server`）。固定桥已经单独运行时，不再加 `--bridge` 创建临时隧道。电脑与这两个进程要保持运行；不默认安装系统服务、开机自启或自动重启机制。
8. 用[私有玩家连接配置命令](private-player-connections.md)加 `--public-mcp-url` 生成各玩家自己的地址，再指导人类安装。人类不需要读日志找ID或自己编辑Python。

上面的Wrangler命令用于表达配置流程，Agent应先核对已安装版本的帮助和官方命令参考，再执行账号写入。命名Tunnel、VPC Service、Worker首次配置一次即可；日常重启复用已有资源，不更改插件网址。每位玩家用自己的账号和资源，不借用项目作者的服务。

## 发布前真实验收

- 本机网页可打开，公网只接受 `/mcp`、`/mcp/`；`/`、`/api/sessions`、静态文件等都被拒绝。
- 初始化与列工具通过；私有URL查询参数完整转发。日志不能记录私有URL、请求体或token。
- 第一次game_connect授权、game_resume恢复、无token的game_act实际成功。
- 两位玩家各只恢复自己的席位，非法凭证返回拒绝。
- 分别重启掌机和Tunnel，再用同一个URL恢复同一存档。
- 在真实云端客户端里安装并调用一次。普通MCP客户端通过，不等于ChatGPT插件已经安装和验收。

如果当前Cloudflare账号不支持该方案、beta功能变更或客户端不能保持完整私有URL，应明确说明实际限制，先继续用本机连接或临时桥。不要悄悄开放管理接口、上传荷官Key或改为项目作者代托管玩家数据库。
