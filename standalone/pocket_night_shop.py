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
    "eNq1vXlTXFeWL/o/n4LLjRcFVVkuS7Jdbrn0ItzVrluKW1XuKLv79QuCIBCkJNpMzWDZV0EECDGPErMASSDQLAYJMSXDd7nF"
    "OZn5V32F9/uttc8++5w8CXL5PofDTjLP2ePaa/yttcvKyv7WNeSNP8mtDHuri/nJg791DX//8UeX/n744LcXs89G/dln2cEX"
    "f+vq/vyz06NRf3EwPz/hL6156yune2OnB1P5uZ389En24CSbGc9NrP2t605JyZdXS/25DW9q43SvKzv2wlvf+fvhgj/Yxbcf"
    "jPuLB9nMpP9wMTu1hQ68NxNe3ztv/QFe9bams6sH2Vcb3vhLf2zNn9rxel97h125Z3e8jUfe/ZH88oF3MO7Prnkns+zKH9zP"
    "94/nlke8oefe4nN/ZtMbv5cd28R4Tw+GTzM7+JB7f9c/mMgd72enR7zVu6cHq7mTOXSZfTPjL/X8/XDkdG/UXzjRgfpDa6eZ"
    "XX9gxus/8KbWc7Pj3mQ3eyorKyspqW9saW5tL71Z03azof5ayfXW5sbS2uaWH0vND3XpdAv/Lin55o9X//DtN6VXSivL8pm7"
    "/tx4Waq0zN/dwhqXVZX84evfX5Xf2tINDfylNd1SU9/KT221Nd+nm26k+bm2o7WmXT51tNxoramTj+31dT/qK7U/1jbIV3X1"
    "bY31bW1o+M9ff/0v2qu/+Mg77uWvp3uT/rvn/JQd2s9tvZJPPU9zB93yaXHX7x6WTzNv/R751Tue9e+Os7kv/6P6mz9+/a/V"
    "f/rq37/6E9r9VL76/b998+3Xf/7qr9X/fvWbqzLLz+X7f/7y29//EX99VlJy9duv/iwDKSnFP+Vlt2raa29K292L2ChvYSF7"
    "Zz/74K7f1ZVblsHhf9mFGa+v9/T4mTeQyS51gXq88TX/7bLXN++tj+DpfPek/2YQ24EXLqZKP0tJ6xj6s/v5+wP5/lEQQO79"
    "JojBn91J+Rvj3uoLkNLp4QPbJ3bafzRxuvfy9ODAW32A4bCbgb78/UdstyJlBvxdWlY5t76an5rPzz5n75m7+cnF/P01b2Re"
    "prLe43dl0HJ+6XHu5F5+fiQ79QiP5qe60b13vM5/QY49b+yIPw1GjHezi4/8N0/QAZYbrZMK5zbweirXNYJP/sIxj9TKKwwU"
    "D+Hp7LPN06NFECme9hY3/Zn9yIhBOa3XOa78wnOZ9z3/wQyXePaZt7Dt7R7LJh+ceKvb3vEA5p7yRrdxFLLT81hsf3cZ/+Lx"
    "7IM7+afzdsSfBCPOLa95a0f+Ypc3MYYlwwqatibGUto+ljm3jiHihHdhPfCQ/3rZH17zh7Y4jL0X3sHTyIiv1bfWyaAOD8gp"
    "BvuzJ725vi4+vHjgr2zm9x4pAQ9lt59xPkvL0tt6D7ryF5e8kVkca2/8FbfwyaaO+UKq9PNgzCAHbTL3pBeD58u2ZW9qC2ec"
    "S9m7460/xIrLrN5ibcjzHtzNnUzlBl56SxP+4/7IsBvS7e1pOawkzIFN9j46xDeOH+a6R05PluWwBytF7gR2tjioq4Yd9cZH"
    "vdVRf+eOPzbIAUyACc7aFb9kqfpgzzt8fHqyjoc5dLwZe8d/v3560OctPARH5m4qDWFUGAPIRqgKzH0vMvz2dE1tR4sOcTCb"
    "6cs9uZM94FnMTS7lRnb8pQ35bWnDO5jOTgUH8eAZGvfezIHc+ejR0+yrJCKRtkAq+aMJWW1pRZ/mCbr/iDs3dwwuf7o3zE0f"
    "f4PzlTvp55wGZvFkZKy1NY3p1hpZaizh8ChWO9cz4h2RoLILe9hM+W3wxenRfK5nByTkT296z4azmYGgF/zbYynjn4KB5qcX"
    "Qbt2bdm0EEP29Ws8j2XXblKk6aPXGB+ezi4OexP38Kh/726uqzdKyoaRg1thVUGM+UfvOKXN8fxkj/xwr9+wpfw8SOse++re"
    "9DbnpIcM/s0+BS/ZLGRuaCA3MMJxjj0iRWVG3U5Sp0d9RrR2z3qrWxDWZHcTI+iKR2S9x+seF8objnKLm80iO8AuObvjgdzJ"
    "Ym53g2MencZiZx+s5x+KXMD/sIfe6r6hBKzN6svc4Fvu6tpzu7SWtenzyi7C40o2OfscxzXX/xILgUXFWnrjT4XJv8Q7mITS"
    "FvgafooONp2uu9b8g/AKsNipAa6eqA75ye7swn35YeG+yA8ys8ug1dzTbmoE89vghf7gJLQIu7S/tUOdGgCzJhUc8rCm0Ea+"
    "Pzyt2bf3zcjBUZ/gnL8BE8oNHbH3sUz2fo+OIcocahr1bHVN5zPc5dzKTHZ8NNstpyrbh13fQFdgAWDz3Hssx+7W6cF67v1u"
    "oZgAi8WmQBXStfQHR1W/4aJme5/hNS4YhMXASX52G2MH1znd7wWB8PivbOrBOt1bzK2dRIbZ2NFWX2uW1Nskr84N3fFnh73j"
    "YWGJr0i/urAQo/muFX96G9IzlX1xAG7No3znCd7ABE4zYyAdKlaHj8GGCplwdhMaZH/IE/RpruHhAQ7T6f4jQ607EEpbKa8H"
    "5LpKCly4j8XFST49GPMmBry18cgMbjQ0f5/WI3eMLc9P7mTfDqq48weHvbVZ+W2k39ucyT557o9CHZpF2ypWlQPnnj3FGvlz"
    "j7yF44S1P1yiwJMWOG7tQQnCXx7JL63kJo78gQlSMJZclI3s4aTfu+KNz3kjInpt03bYTc3t6WvNzd/JyVp+n33c7XXd5/ih"
    "RINYtp/6i6/lXO4MecckyuxJJgWFl/qc0Ax+8GdfFLKJ0/2nubtDlk3ITs0f5Z/OoBfytrFNioqD2dO9jD83Jodi1EjsvWEh"
    "kq7s6yl/agMPR1lbR3t7c9N/1ojEgyD1M8uq6mQPjvzBJ+FhOJow5ELJ//BBvueIe5kZo+CYGPH2t08zfDq3/MRfHIVg8of7"
    "DFeKChE0BIOEp9IwkN4dHD1tVPs0mzALmZQhoUNPOukHe/FWZ0BI4KX+9FsdVFTy1TfdulmjOjObGN/3N6dIy2AiYHdv92SG"
    "vfvoDYq/YXeb4/79df/9bnZhwtK2ZSBGKVkf8Xqf0zZRNmLbE2kiWpBybOnQ6Heqf5ge1t/7R+tGhcFwq1SBrv6fV/8i6vxt"
    "6c4o0ZexxrM7OO4cLdVUfOEd3ceZMvYDtEB8lZ+H3ivPiJrFt0T1KdOxB1rMZeq4m95Jn9gWqhpID2venqyHEcGR50TasduN"
    "DORN0KKIFD4HSbI8IoMxfPuy8u3pE34pHJLf9D4DIfIby4w47EfvTvcngib1kHM8cpL4sD1A7Gn7aXZhXUZkiVQG/wxEpsaS"
    "2XF3+p0lJYEF45ootc0drfWq1+XeQ3a+gm5CGUdet+7tSjd+zzt/8JjiNLOT6zniGkM7pwg1wjMwl++U2XOZmfGHhlRw+kNz"
    "KmyhfYMqjCK19tyfWiN3Oh6AnqtEVumsYrjbZpurQIQfR/S5mzrufFfX6SGFDsxM//Fyrqvb2xsw4z7d3zTjPpnD0KH1Q1NX"
    "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"
    "FSX/H9Oerwo="
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
