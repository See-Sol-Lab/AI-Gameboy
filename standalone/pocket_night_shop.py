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
    "eNq1vXlTXFeWL/q/PgWXjhcFVVm2Jdkut1x6Ee5q9y3FrSp3lN397guCIBCkJNpMzWDZV0EECDGPErMASSDQLAYJMSXDd7nF"
    "OZn5V3+F9/uttc8++5w8Cbh8n8NhJ5nn7HHtNf7W2qWlpX/rHPTGnuaWh7yVhfzE/t86h3745KPL/3Xw8HeXss9H/Jnn2YGX"
    "f+vs+uLzk8MRf2EgPzfuL656a8snu6Mn+5P52e381HF2/zibGcuNr/6t8+6FC19dK/Fn173J9ZPdzuzoS29t+78O5v2BTr79"
    "cMxf2M9mJvxHC9nJTXTgvR33et97aw/xqrc5lV3Zz75e98Ze+aOr/uS21/PGO+jMPb/rrT/2Hgznl/a9/TF/ZtU7nmFX/sBe"
    "vm8stzTsDb7wFl740xve2P3s6AbGe7I/dJLZxofch3v+/njuaC87Neyt3DvZX8kdz6LL7Ntpf7H7vw6GT3ZH/PljHag/uHqS"
    "2fH7p72+fW9yLTcz5k10safS0tILF+oampta2kpuVbfeqq+7fuFGS1NDSU1T808l5ofadLqZf1+48O0fr/3Ld9+WXC2pKM1n"
    "7vmzY6WpklJ/ZxNrXFp54V+++cM1+a01XV/PX1rSzdV1LfzUWlP9Q7rxZpqfa9pbqtvkU3vzzZbqWvnYVlf7k75S81NNvXxV"
    "W9faUNfaiob//M03/6y9+guPvaMe/nqyO+G/f8FP2cG93OZr+dT9LLffJZ8WdvyuIfk0/c7vll+9oxn/3hib++p/Vn37x2/+"
    "tepPX//7139Cu5/JV3/4t2+/++bPX/+16t+vfXtNZvmFfP9PX333hz/ir88vXLj23dd/loFcKME/ZaW3q9tqbknbXQvYKG9+"
    "Pnt3L/vwnt/ZmVuSweF/2flpr7fn5Oi515/JLnaCeryxVf/dktc7560N4+l814T/dgDbgRcupUo+T0nrGPrzB/kH/fm+ERBA"
    "7sMGiMGf2U7562PeykuQ0snBQ9sndtp/PH6y++pkf99beYjhsJv+3vyDx2y3PGUG/H1aVjm3tpKfnMvPvGDvmXv5iYX8g1Vv"
    "eE6mstbtd2bQcn7xSe74fn5uODv5GI/mJ7vQvXe0xn9Bjt1v7Yg/C0aMd7MLj/23T9EBlhutkwpn1/F6Ktc5jE/+/BGP1PJr"
    "DBQP4ens842TwwUQKZ72Fjb86b3IiEE5LTc4rvz8C5n3ff/hNJd45rk3v+XtHMkm7x97K1veUT/mnvJGtnAUslNzWGx/Zwn/"
    "4vHsw7v5Z3N2xJ8GI84trXqrh/5Cpzc+iiXDCpq2xkdT2j6WObeGIeKEd2I98JD/ZskfWvUHNzmM3Zfe/rPIiK/XtdTKoA72"
    "ySkG+rLHPbneTj68sO8vb+R3HysBD2a3nnM+i0vS21o3uvIXFr3hGRxrb+w1t/Dpho75Yqrki2DMIAdtMve0B4Pny7Zlb3IT"
    "Z5xL2bPtrT3Cisus3mFtyPMe3ssdT+b6X3mL4/6Tvsiw69NtbWk5rCTM/g32PjLIN44e5bqGT46X5LAHK0XuBHa2MKCrhh31"
    "xka8lRF/+64/OsABjIMJztgVv2ypen/XO3hycryGhzl0vBl7x/+wdrLf680/AkfmbioNYVQYA8hGqArMfTcy/LZ0dU17sw5x"
    "IJvpzT29m93nWcxNLOaGt/3Fdfltcd3bn8pOBgdx/zka997Ogtz56OGz7OskIpG2QCr5w3FZbWlFn+YJevCYOzd7BC5/sjvE"
    "TR97i/OVO+7jnPpn8GRkrDXVDemWallqLOHQCFY71z3sHZKgsvO72Ez5beDlyeFcrnsbJORPbXjPh7KZ/qAX/NttKeMfg4Hm"
    "pxZAu3Zt2bQQQ/bNGzyPZdduUqTpwzcYH57OLgx54/fxqH//Xq6zJ0rKhpGDW2FVQYz5x+85pY2x/ES3/HC/z7Cl/BxI6z77"
    "6trwNmalhwz+zT4DL9koZG5oINc/zHGOPiZFZUbcTlInh71GtHbNeCubENZkd+PD6IpHZK3b6xoTyhuKcotbTSI7wC45u6P+"
    "3PFCbmedYx6ZwmJnH67lH4lcwP+wh97KnqEErM3Kq9zAO+7q6gu7tJa16fPKLsLjSjY58wLHNdf3CguBRcVaemPPhMm/wjuY"
    "hNIW+Bp+ig42na693vSj8Aqw2Ml+rp6oDvmJruz8A/lh/oHIDzKzK6DV3LMuagRzW+CF/sAEtAi7tL+zQ53sB7MmFRzwsKbQ"
    "Rr4vPK3Zdw/MyMFRn+KcvwUTyg0esvfRTPZBt44hyhyqG/RsdU7lM9zl3PJ0dmwk2yWnKtuLXV9HV2ABYPPceyzHzubJ/lru"
    "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"
    "eHlpaexclV/4/wD5GYxW"
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
