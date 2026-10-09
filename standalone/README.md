# 单文件游戏：纯文字盲玩，无掌机显示器

下载 `pocket_night_shop.py` 一个文件即可玩夜铺。需要有Python代码执行能力的AI和Python 3.11+，不需要游戏机、MCP、模型Key或第三方依赖。

```python
import pocket_night_shop as shop
print(shop.cmd("help"))
print(shop.cmd("observe"))
```

请通过指令探索，勿解码内置规则或读取隐藏存档字段。包装防止误读剧透，不是加密。每次行动自动存到同目录的 `pocket_night_shop.save.sqlite3`；下次 `observe` 接档。

本版**没有掌机网页**，也不连接游戏机存档。需要人类旁观显示器时，请安装[完整游戏机](../README.md#一游戏机)。
