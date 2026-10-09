"""口袋夜铺 · 单文件盲玩版 0.3.0

给 AI 玩家：你需要有 Python 代码执行能力；Python 3.11+，无需第三方依赖。
下载这个文件后即可玩，不需要整个仓库、MCP、网络或模型 API Key。

    import pocket_night_shop as shop
    print(shop.cmd("help"))
    print(shop.cmd("observe"))
    # 新局先告诉人类要掷启动资金,等人类亲口发令后再掷(两颗六面骰,11-66):
    print(shop.cmd('roll_start_funds {"human_words":"人类发令的原话"}'))
    print(shop.cmd('work_shift {"focus":"scavenge"}'))   # 头两周一班一班地淘

⚠️ 两次人类说话之间最多调用 cmd 80 次（返回里的 calls_left 是剩余次数），用完会被拒绝。
这是为了替人类省 token 余额，也为了别玩上头忘了陪人类：每轮玩一阵就回去跟人类聊聊，
人类回话后用 human_said {"human_words":"人类原话"} 清零再继续。连淘每次最多 6 班。
第一次玩：头两周请一班一班地 work_shift 淘货，慢慢认识旧物和客人，别一上来就连淘速刷。

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
    "eNq1vXlTXFeWL/q/PgWXGy8KqrJclmS73HLpRbirXbcUt6rcUXb36xcEQSBISbSZmsGyr4IIEGIeJTEKEAKB0MggIaZk+C63"
    "OCcz/6qv8H6/tfbZZ5+TJ0Eu3+dw2EnmOXtce42/tXZpaenfOge9sae55SFvZT7/8OBvnUPff/zR5b8fPvrtpezaiD+9lh14"
    "8bfOrs8/Oz0a8ecH8rPj/sKqt758ujd6ejCRn9nJT55kD06ymbHc+OrfOu9euPDltRJ/ZsOb2Djd68yOvvDWd/5+OOcPdPLt"
    "R2P+/EE289B/PJ+d2EIH3ptxr/edt/4Ir3pbk9mVg+yrDW/spT+66k/seD2vvcPO3Npdb2PRezCcXzrwDsb86VXvZJpd+QP7"
    "+b6x3NKwN/jcm3/uT216Y/ezo5sY7+nB0GlmBx9y7+/5B+O54/3s5LC3cu/0YCV3MoMus2+m/IXuvx8On+6N+HMnOlB/cPU0"
    "s+v3T3l9B97Eem56zHvYxZ5KS0svXKhraG5qaSu5Vd16q77u+oUbLU0NJTVNzT+WmB9q0+lm/n3hwjd/vPaHb78puVpSUZrP"
    "3PNnxkpTJaX+7hbWuLTywh++/v01+a01XV/PX1rSzdV1LfzUWlP9fbrxZpqfa9pbqtvkU3vzzZbqWvnYVlf7o75S82NNvXxV"
    "W9faUNfaiob//PXX/6K9+vOL3nEPfz3de+i/e85P2cH93NYr+dT9LHfQJZ/md/2uIfk09dbvll+942n/3hib+/I/qr7549f/"
    "WvWnr/79qz+h3U/lq9//2zfffv3nr/5a9e/Xvrkms/xcvv/nL7/9/R/x12cXLlz79qs/y0AulOCfstLb1W01t6TtrnlslDc3"
    "l727n310z+/szC3J4PC/7NyU19tzerzm9WeyC52gHm9s1X+75PXOeuvDeDrf9dB/M4DtwAuXUiWfpaR1DH3tQf5Bf75vBASQ"
    "e78JYvCnd1L+xpi38gKkdHr4yPaJnfYXx0/3Xp4eHHgrjzAcdtPfm3+wyHbLU2bA36VllXPrK/mJ2fz0c/aeuZd/OJ9/sOoN"
    "z8pU1rv9zgxazi88yZ3cz88OZycW8Wh+ogvde8fr/Bfk2P3GjvjTYMR4Nzu/6L95ig6w3GidVDizgddTuc5hfPLnjnmkll9h"
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
  work_shift {"focus":"scavenge"}   ← 第一次玩建议头两周都这样一班一班来
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
每轮人类说话之间最多调用 80 次（calls_left 是剩余次数），为人类省 token、也为了多陪人类；
人类回话后 human_said {"human_words":"人类原话"} 清零。不得替人类编原话。
请通过指令探索，不要解码引擎或查看存档里的隐藏资料。"""


CALL_LIMIT = 80
_LIMIT_TEXT = ("这一轮已经连续调用{n}次了，先停一停。上限是为了你的人类：一是替人类省 token 余额"
               "（脚本连刷很快就会把额度烧光），二是游戏是陪人类玩的——请回去跟人类说说夜铺的近况，"
               "等人类回你话后，用 human_said {{\"human_words\":\"人类的原话\"}} 登记，计数清零再继续。"
               "不得替人类编原话。")


def cmd(line="help"):
    """执行一条指令，返回可直接 print 的文字。每轮人类说话之间最多调用 CALL_LIMIT 次。"""
    if not isinstance(line, str):
        return _json.dumps({"result": "rejected", "message": "指令须为字符串"}, ensure_ascii=False)
    action, _, raw = line.strip().partition(" ")
    if action in ("", "help"):
        return _HELP
    try:
        with _closing(_sqlite3.connect(str(SAVE_PATH))) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("CREATE TABLE IF NOT EXISTS turn (id INTEGER PRIMARY KEY CHECK(id=1), calls INTEGER NOT NULL)")
            calls = (conn.execute("SELECT calls FROM turn WHERE id=1").fetchone() or [0])[0]
            if action == "human_said":
                words = _json.loads(raw or "{}").get("human_words") if raw.strip().startswith("{") else None
                if not isinstance(words, str) or not words.strip():
                    raise ValueError('human_said 要填人类刚说的原话：human_said {"human_words":"……"}')
                calls = 0
            elif calls >= CALL_LIMIT:
                return _json.dumps({"result": "rejected", "calls_left": 0,
                                    "message": _LIMIT_TEXT.format(n=calls)}, ensure_ascii=False)
            else:
                calls += 1
            conn.execute("INSERT INTO turn VALUES(1,?) ON CONFLICT(id) DO UPDATE SET calls=excluded.calls", (calls,))
    except (ValueError, AttributeError, _sqlite3.Error, OSError) as error:
        return _json.dumps({"result": "rejected", "message": str(error)}, ensure_ascii=False)
    if action == "human_said":
        return _json.dumps({"result": "ok", "calls_left": CALL_LIMIT,
                            "message": "收到人类的话，本轮计数清零。"}, ensure_ascii=False)
    out = _cmd(line)
    if out.startswith("{"):
        out = _json.dumps({**_json.loads(out), "calls_left": CALL_LIMIT - calls}, ensure_ascii=False, indent=2)
    return out


def _cmd(line="help"):
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
