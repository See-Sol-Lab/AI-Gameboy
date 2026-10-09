"""口袋夜铺 · 单文件盲玩版 0.3.0

给 AI 玩家：你需要有 Python 代码执行能力；Python 3.11+，无需第三方依赖。
下载这个文件后即可玩，不需要整个仓库、MCP、网络或模型 API Key。

    import pocket_night_shop as shop
    print(shop.cmd("help"))
    print(shop.cmd("observe"))
    # 新局先告诉人类要掷启动资金,等人类亲口发令后再掷(两颗六面骰,11-66):
    print(shop.cmd('roll_start_funds {"human_words":"人类发令的原话"}'))
    print(shop.cmd('run_shifts {"focus":"scavenge","count":6,"stop_on":"new"}'))

只根据 observe 返回的 legal_actions 和结果自己决定；无需每轮发表感想。
不要解码下面的 _RULES_B64，也不要打开原仓库规则或读取存档里的隐藏字段，
那会提前揭露旧物、秘密与客人需求。通过淘货、修复和相遇慢慢发现。
这只是防误读的盲玩包装，不是加密或防作弊安全措施。

每次行动自动保存到本文件旁的 pocket_night_shop.save.sqlite3。
下次导入同一文件并调用 observe 即可继续。无需保持 Python 进程一直运行。
保存目录需可写；只复制 .py 不会带走已有存档，迁移时也要备份 .sqlite3。
独立版与掌机各有自己的存档，本版没有掌机网页。

命令行也能用：python pocket_night_shop.py observe
本文件由 tools/build_night_shop.py 生成，请维护原规则和模板后重新生成。
Copyright See-Sol-Lab and the AI-Gameboy contributors.
License: PolyForm Noncommercial 1.0.0，完整协议附在文件末尾。
"""
import base64 as _base64
from contextlib import closing as _closing
import json as _json
from pathlib import Path as _Path
import secrets as _secrets
import sqlite3 as _sqlite3
import sys as _sys
import zlib as _zlib

VERSION = "0.3.0"
SAVE_PATH = _Path(__file__).resolve().with_name("pocket_night_shop.save.sqlite3")
_RULES_B64 = (
    "eNq1vXlTXFeWL/q/PgWXGy8KqrJclmS73HLpRbjrul45blW5o8rd0S8IgkCQkmgzNYNlX4UiQIh5lJgFCIFAaGSQEFMyfJdb"
    "nJOZf/VXeL/fWvvss8/Jk4DL9zkcdpJ5zh7XXuNvrV1aWvr3jgFv9FluedBbmc+PH/y9Y/D7jz+6+l+Hj397Jbs27E+vZftf"
    "/r2j8/PPTo+G/fn+/OyYv7DqrS+f7o2cHkzkZ3bykyfZg5NsZjQ3tvr3jvuXLn35dYk/s+FNbJzudWRHXnrrO/91OOf3d/Dt"
    "x6P+/EE2M+4/mc9ObKED7+2Y1/PeW3+MV72tyezKQfb1hjf6yh9Z9Sd2vO433mFHbu2+t7HoPRrKLx14B6P+9Kp3Ms2u/P79"
    "fO9obmnIG3jhzb/wpza90YfZkU2M9/Rg8DSzgw+5Dw/8g7Hc8X52cshbeXB6sJI7mUGX2bdT/kLXfx0One4N+3MnOlB/YPU0"
    "s+v3TXm9B97Eem561BvvZE+lpaWXLtU1NDe1tJXcrm69XV9349LNlqaGkpqm5h9LzA+16XQz/7506W9//PoP3/6t5HpJRWk+"
    "88CfGS1NlZT6u1tY49LKS3/45vdfy2+t6fp6/tKSbq6ua+Gn1prq79ONt9L8XNPeUt0mn9qbb7VU18rHtrraH/WVmh9r6uWr"
    "2rrWhrrWVjT852+++R/aqz+/6B1389fTvXH//Qt+yg7s57Zey6eu57mDTvk0v+t3DsqnqXd+l/zqHU/7D0bZ3Jf/XvW3P37z"
    "L1V/+urfvvoT2v1Uvvr9v/7t22/+/NVfq/7t6799LbP8XL7/5y+//f0f8ddnly59/e1Xf5aBXCrBP2Wld6rbam5L253z2Chv"
    "bi57fz/7+IHf0ZFbksHhf9m5Ka+n+/R4zevLZBc6QD3e6Kr/bsnrmfXWh/B0vnPcf9uP7cALV1Iln6WkdQx97VH+UV++dxgE"
    "kPuwCWLwp3dS/saot/ISpHR6+Nj2iZ32F8dO916dHhx4K48xHHbT15N/tMh2y1NmwN+lZZVz6yv5idn89Av2nnmQH5/PP1r1"
    "hmZlKutdfkcGLecXnuZOHuZnh7ITi3g0P9GJ7r3jdf4Lcux6a0f8aTBivJudX/TfPkMHWG60Tiqc2cDrqVzHED75c8c8Usuv"
    "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"
)
_engine = {"__name__": "_night_shop_rules"}
exec(compile(_zlib.decompress(_base64.b64decode(_RULES_B64)).decode("utf-8"),
             "<night-shop-blind-rules>", "exec"), _engine)

_HELP = """口袋夜铺 · 你是独自经营旧物铺的店主。
observe / status：看店况、库存、当前客人和 legal_actions（可做动作）。
新局第一步：掷启动资金（两颗六面骰，十位+个位，11-66枚古币）。先停下告诉人类，
等人类亲口说“掷”，再 roll_start_funds {"human_words":"人类原话"}；不得替人类发令。
行动格式：动作名 + JSON对象。按刚才的 legal_actions 填参数，例如：
  work_shift {"focus":"tidy"}
  run_shifts {"focus":"scavenge","count":6,"stop_on":"new"}
  work_shift {"focus":"repair","item_id":"从库存选"}
  work_shift {"focus":"sell","item_id":"从库存选","asking_price":5}
遇到 pending_event，先 choose_event，event_id 和 choice 从观察中选。
close_for_now：歇业；reopen_shop：接着开店。随时退出，动作已经自动保存。
collection / encounters / customers：只查已经发现的图鉴、见闻、顾客簿。
history 0：从头查公开经营记录，每次最多100条；history 100 继续往后查。
new_game {"seed":17}：仅在没有存档时创建指定种子的新局；绝不覆盖旧档。
未开局时 observe 会自动创建一局。没有必须完成的回合数，店主自己决定目标。
stop_on 接受 new/rare/event 字符串或数组；省略默认三项全选，[]关闭这三类
停点，遇到必须选择的事件仍会停。公开目标 goal、心情 mood、public_line 都可省略。
请通过指令探索，不要解码引擎或查看存档里的隐藏资料。"""


def cmd(line="help"):
    """执行一条指令，返回可直接 print 的文字；每个动作完成后存档。"""
    if not isinstance(line, str):
        return _json.dumps({"result": "rejected", "message": "指令须为字符串"}, ensure_ascii=False)
    action, _, raw = (line.strip() or "help").partition(" ")
    if action == "help":
        return _HELP
    try:
        if action == "history":
            after = int(raw or "0")
            if after < 0:
                raise ValueError("历史游标须为非负整数")
            params = {}
        else:
            params = _json.loads(raw) if raw.strip() else {}
            if not isinstance(params, dict):
                raise ValueError("动作参数须为JSON对象")
        allowed = {"observe", "status", "collection", "encounters", "customers", "history", "new_game",
                   "roll_start_funds", "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}
        if action not in allowed:
            raise ValueError("未知指令，请先 cmd('help')")
        with _closing(_sqlite3.connect(str(SAVE_PATH))) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS shop (id INTEGER PRIMARY KEY CHECK(id=1), version TEXT NOT NULL, state TEXT NOT NULL)")
            row = conn.execute("SELECT version,state FROM shop WHERE id=1").fetchone()
            if row and row[0] != VERSION:
                raise ValueError("存档版本与游戏不一致，请使用对应版本的单文件；旧档保持不变")
            if row and action == "new_game":
                raise ValueError("已有存档，new_game不会覆盖；请继续observe，或在另一目录建立新铺子")
            if row:
                state = _json.loads(row[1])
            else:
                seed = params.get("seed", _secrets.randbits(32)) if action == "new_game" else _secrets.randbits(32)
                if type(seed) is not int:
                    raise ValueError("seed须为整数")
                state = _engine["new_game"](["seat_a"], seed)
            if action in {"roll_start_funds", "work_shift", "run_shifts", "choose_event", "unlock_location", "close_for_now", "reopen_shop"}:
                state = _engine["apply"](state, "seat_a", action, params)
            view = _engine["observe"](state, "seat_a")
            public = view["public_state"]
            if action == "history":
                result = {"result": "ok", "total": public["journal_total"],
                          "entries": _engine["history_since"](state, after)}
            elif action in ("collection", "encounters"):
                result = {"result": "ok", action: public[action]}
            elif action == "customers":
                result = {"result": "ok", "summary": public["customer_collection"], "entries": public["customer_book"]}
            else:
                result = {"result": "ok", "version": VERSION, **view}
            conn.execute("INSERT INTO shop VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state",
                         (VERSION, _json.dumps(state, ensure_ascii=False)))
        return _json.dumps(result, ensure_ascii=False, indent=2)
    except (ValueError, _engine["IllegalAction"], _sqlite3.Error, OSError) as error:
        return _json.dumps({"result": "rejected", "message": str(error)}, ensure_ascii=False)


_LICENSE = """# PolyForm Noncommercial License 1.0.0

<https://polyformproject.org/licenses/noncommercial/1.0.0>

## Acceptance

In order to get any license under these terms, you must agree to them as both strict obligations and conditions to all your licenses.
## Copyright License

The licensor grants you a copyright license for the software to do everything you might do with the software that would otherwise infringe the licensor's copyright in it for any permitted purpose.  However, you may only distribute the software according to [Distribution License](#distribution-license) and make changes or new works based on the software according to [Changes and New Works License](#changes-and-new-works-license).
## Distribution License

The licensor grants you an additional copyright license to distribute copies of the software.  Your license to distribute covers distributing the software with changes and new works permitted by [Changes and New Works License](#changes-and-new-works-license).
## Notices

You must ensure that anyone who gets a copy of any part of the software from you also gets a copy of these terms or the URL for them above, as well as copies of any plain-text lines beginning with `Required Notice:` that the licensor provided with the software.  For example:

> Required Notice: Copyright Yoyodyne, Inc. (http://example.com)
## Changes and New Works License

The licensor grants you an additional copyright license to make changes and new works based on the software for any permitted purpose.

## Patent License

The licensor grants you a patent license for the software that covers patent claims the licensor can license, or becomes able to license, that you would infringe by using the software.

## Noncommercial Purposes

Any noncommercial purpose is a permitted purpose.

## Personal Uses

Personal use for research, experiment, and testing for the benefit of public knowledge, personal study, private entertainment, hobby projects, amateur pursuits, or religious observance, without any anticipated commercial application, is use for a permitted purpose.

## Noncommercial Organizations

Use by any charitable organization, educational institution, public research organization, public safety or health organization, environmental protection organization, or government institution is use for a permitted purpose regardless of the source of funding or obligations resulting from the funding.

## Fair Use

You may have "fair use" rights for the software under the law. These terms do not limit them.

## No Other Rights

These terms do not allow you to sublicense or transfer any of your licenses to anyone else, or prevent the licensor from granting licenses to anyone else.  These terms do not imply any other licenses.

## Patent Defense

If you make any written claim that the software infringes or contributes to infringement of any patent, your patent license for the software granted under these terms ends immediately. If your company makes such a claim, your patent license ends immediately for work on behalf of your company.

## Violations

The first time you are notified in writing that you have violated any of these terms, or done anything with the software not covered by your licenses, your licenses can nonetheless continue if you come into full compliance with these terms, and take practical steps to correct past violations, within 32 days of receiving notice.  Otherwise, all your licenses end immediately.

## No Liability

***As far as the law allows, the software comes as is, without any warranty or condition, and the licensor will not be liable to you for any damages arising out of these terms or the use or nature of the software, under any kind of legal claim.***

## Definitions

The **licensor** is the individual or entity offering these terms, and the **software** is the software the licensor makes available under these terms.

**You** refers to the individual or entity agreeing to these terms.

**Your company** is any legal entity, sole proprietorship, or other kind of organization that you work for, plus all organizations that have control over, are under the control of, or are under common control with that organization.  **Control** means ownership of substantially all the assets of an entity, or the power to direct its management and policies by vote, contract, or otherwise.  Control can be direct or indirect.

**Your licenses** are all the licenses granted to you for the software under these terms.

**Use** means anything you do with the software requiring one of your licenses.

Required Notice: Copyright See-Sol-Lab and the AI-Gameboy contributors (https://github.com/See-Sol-Lab/AI-Gameboy)"""

if __name__ == "__main__":
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8")
    print(cmd(" ".join(_sys.argv[1:]) or "help"))
