# AI-Gameboy

> 蓝图:`内部设计蓝图`
> 当前阶段:**Stage A 表面通电检查** —— 只验证两个真实窗口能连上同一个本机 HTTP MCP。
> 本仓库现在没有游戏:不写牌局、不建 UI、不碰 内部设计资料。

## 启动服务

```bash
python -m pip install mcp
python server.py
```

入口(两个窗口连的是**同一个地址**):`http://127.0.0.1:7777/mcp`

只有一项只读工具:`table_hello(who)` —— 返回座位名称;`who` 填窗口自报名。
每次调用会在 `data/stage_a_calls.log` 留一行时间戳。

## 配置 Claude Code

有 CLI 时:

```bash
claude mcp add --transport http gameboy http://127.0.0.1:7777/mcp
```

桌面版无 CLI 时(2026-08-13 实测本机即此情况):在项目根目录写 `.mcp.json`:

```json
{
  "mcpServers": {
    "gameboy": { "type": "http", "url": "http://127.0.0.1:7777/mcp" }
  }
}
```

**MCP 配置只在会话启动时加载,不热加载**——写完必须重启窗口,首次加载会弹批准提示。
然后在 Claude Code 真实窗口里让它调用 `table_hello`,`who` 填 `"Claude Code"`。

## 配置 Codex Desktop

`C:\Users\Administrator\.codex\config.toml` 加:

```toml
[mcp_servers.gameboy]
url = "http://127.0.0.1:7777/mcp"
```

重启 Codex 后让它调用 `table_hello`,`who` 填 `"Codex Desktop"`。

若当前版本不认 `url`(只支持 stdio),**原地停**:把版本号与报错记入下表。
是否加 stdio→HTTP 桥,由项目团队 决定,不擅自施工。

## 实测记录表(蓝图 §7 / §23)

| 表面 | 日期 | 客户端版本 | 配置位置 | table_hello 结果 | 卡点 |
|---|---|---|---|---|---|
| Claude Code | 2026-08-13 | 桌面版(无 CLI) | `C:\Users\Administrator\.claude\.mcp.json`(项目级) | 待窗口重启后调用 | MCP 配置不热加载,需重启窗口;`claude` 不在 PATH |
| Codex Desktop | 待实测 | | | | |

## Stage A 验收

- 两个**真实窗口**各自调用成功,结果出现在各自窗口界面里;
- `data/stage_a_calls.log` 的时间戳与两次调用对得上;
- curl / 机械客户端成功**不算**验收(蓝图 §7.1);
- 任一边接不通:记录卡点,停。不换裸 API,不假装成功。

Stage A 通过后,另行授权 Stage B(两项工具 + SQLite + 《口袋电路》)。
