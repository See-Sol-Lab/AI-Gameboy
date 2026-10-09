# 单文件游戏：纯文字盲玩，无掌机显示器

下载 `pocket_night_shop.py` 一个文件即可玩夜铺。需要有Python代码执行能力的AI和Python 3.11+，不需要游戏机、MCP、模型Key或第三方依赖。

```python
import pocket_night_shop as shop
print(shop.cmd("help"))
print(shop.cmd("observe"))
```

请通过指令探索，勿解码内置规则或读取隐藏存档字段。包装防止误读剧透，不是加密。每次行动自动存到同目录的 `pocket_night_shop.save.sqlite3`；下次 `observe` 接档。

**第一次玩**：头两周建议一班一班地 `work_shift` 淘货，一件旧物、一位客人慢慢认识；别一上来就开 6 班连淘速刷，熟悉以后再用 `run_shifts` 省事。

**调用上限**：两次人类说话之间最多调用 `cmd` 80 次，连淘每次最多 6 班。这是为了替人类省 token 余额（用 API 的 AI 写个连刷脚本，额度一下就烧光了），也为了别让 AI 玩上头、忘了回来陪人类。用完后 AI 要回去跟人类聊聊，人类回话后用 `human_said {"human_words":"人类原话"}` 清零再继续。

本版**没有掌机网页**，也不连接游戏机存档。需要人类旁观显示器时，请安装[完整游戏机](../README.md#一游戏机)。
