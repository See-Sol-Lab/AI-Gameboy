# 掌机本体

在仓库根目录运行 `python -m console.server`，或双击根目录的 `start_server.bat`。开桥用 `python -m console.server --bridge`。

- `server.py`：网页、MCP和启动入口。
- `game_host.py`：席位、鉴权、事务和卡带版本。
- `store.py`：SQLite存档。
- `narrator.py`：本机荷官适配器，只在需要荷官的卡带中使用。
- `cartridges.py`：本机卡带安装、隐藏和卸载。
- `web/`：掌机网页。

正式卡带位于相邻的 `cartridges/`。用户数据仍位于仓库根目录的 `data/`。目前仅保留当前版本规则；版本不匹配会明确报错，不偷偷重开或覆盖旧档。只有用户另行明确授权，才可清理其旧局。存档、Key和日志不得提交或分享。
