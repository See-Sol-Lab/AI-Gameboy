"""《盲区同行》规则:纯函数,只接值、只回值。

核心(初版设计与精简版):同一现场,两份不完整的真相。
- 两套私密视野(地形/回声),各 3 条见闻;见闻必须"钉上桌"才产生规则效果;
- 每拍一次暗提交:{钉出的见闻, 姿态, 目标, 短台词?, 背书?},双方齐了同时揭示;
- 四种姿态(推进/护持/转向/探明)一幕各用一次;组合矩阵决定结构后果,
  台词决定这件事在小说里长什么样;
- 余波牌三张(顺势/代价/回声),构成公开、顺序未知,每拍翻一张;
- 背书(每人一次,盲用):赌本拍,若翻出代价则由你的信任挡下;
- 进度 0–5 达成目标;压力 0–4 世界先行动;三拍未竟不判负,只留钩子。

MVP 场景:《失物邮局》。与宿主的唯一结构约定:full_state["phase"]。
"""

import random
from copy import deepcopy

TOTAL_BEATS = 3
STANCES = ["推进", "护持", "转向", "探明"]
LINE_MAX = 40

SCENE = {
    "id": "lost-post-office",
    "name": "失物邮局",
    "intro": ("一座半淹在黑水里的旧邮局仍在自动分拣邮件。一封装着「明日第一束晨光」的信,"
              "正随传送带滑向玻璃焚信炉。三拍之后,邮局将彻底沉入水下。"),
    "goal": "在邮局沉没之前,取回晨光信。",
    "objects": {
        "conveyor": "分拣传送带",
        "hatch": "维修舱门",
        "bell": "屋顶铜钟",
        "clerk": "回执员",
        "furnace": "玻璃焚信炉",
    },
    "packets": {
        "terrain": {"name": "地形视野", "facts": [
            {"id": "t-hatch",
             "text": "维修舱门没有上锁;传送带一旦停下,它会自动弹开。",
             "boost": {"stance": "推进", "target": "conveyor", "effect": "progress"}},
            {"id": "t-chain",
             "text": "传送带的配重链连着屋顶铜钟,鲁莽拉动会把它敲响。",
             "boost": {"stance": "护持", "target": "bell", "effect": "pressure"}},
            {"id": "t-floor",
             "text": "谁踩上分拣大厅的地板,谁最近写下的一个名字就会被抹掉。",
             "boost": {"stance": "转向", "target": "conveyor", "effect": "shield"}},
        ]},
        "echo": {"name": "回声视野", "facts": [
            {"id": "e-clerk",
             "text": "回执员会服从任何被表述成『退回误投件』的请求。",
             "boost": {"stance": "转向", "target": "clerk", "effect": "progress"}},
            {"id": "e-furnace",
             "text": "焚信炉害怕仍然封口的邮件;把未拆的信递近它,火会暂时后退。",
             "boost": {"stance": "护持", "target": "furnace", "effect": "pressure"}},
            {"id": "e-bell",
             "text": "铜钟一旦真的敲响,所有从未送达的信都会醒来,要求现场有人成为收件人。",
             "boost": {"stance": "探明", "target": "bell", "effect": "memory"}},
        ]},
    },
    "third_path": {
        "id": "return-chute", "name": "退件通道",
        "fact": {"id": "path-open",
                 "text": "墙后亮起一条从未启用过的退件通道。",
                 "boost": {"stance": "推进", "target": "return-chute",
                           "effect": "progress"}},
    },
    "costs": {
        "conveyor": "传送带猛地一颤,配重链擦响了铜钟一角",
        "hatch": "舱门弹开的瞬间灌进一股黑水",
        "bell": "钟舌擦过钟壁,一封死信睁开了眼睛",
        "clerk": "回执员起了疑心,把窗口关小了一半",
        "furnace": "炉火突然窜高,烤焦了最近的一叠信",
        "return-chute": "退件通道深处传来不明的水声",
    },
    "endings": {
        "success": "晨光信被取了出来。原本的回程已被黑水淹没,但你们打开的路成了新的出口。",
        "pressure": "世界先动了手:邮局轰然倾斜,你们带着伤退出来——信纸湿了一角,晨光还在。",
        "incomplete": "三拍用尽,邮局沉入黑水。晨光信没有被取回——但分拣机还在水下运转,这个机会某天会再浮上来。",
    },
}

# 组合矩阵:姿态无序对 -> 结构后果(台词只决定它长什么样)
COMBOS = {
    frozenset(["推进"]): {"progress": 3, "pressure": 2},          # 推进+推进
    frozenset(["推进", "护持"]): {"progress": 2, "special": "soft_cost"},
    frozenset(["推进", "转向"]): {"progress": 2, "pressure": 1},
    frozenset(["推进", "探明"]): {"progress": 1, "special": "boosted_extra"},
    frozenset(["护持"]): {"pressure": -1, "special": "peek"},
    frozenset(["护持", "转向"]): {"progress": 1, "pressure": -1},
    frozenset(["护持", "探明"]): {"progress": 1, "special": "defuse"},
    frozenset(["转向"]): {"progress": 1, "pressure": -1},
    frozenset(["转向", "探明"]): {"progress": 1, "special": "third_path"},
    frozenset(["探明"]): {"progress": 1, "special": "strong_memory"},
}


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("这张卡只支持两名玩家")
    rng = random.Random(seed)
    packet_names = ["terrain", "echo"]
    rng.shuffle(packet_names)
    omens = ["顺势", "代价", "回声"]
    rng.shuffle(omens)
    return {
        "phase": "playing",
        "seed": seed,
        "seats": list(seats),
        "beat": 1,
        "packets": {seats[0]: packet_names[0], seats[1]: packet_names[1]},
        "facts": {s: [f["id"] for f in SCENE["packets"][packet_names[i]]["facts"]]
                  for i, s in enumerate(seats)},
        "pinned": [],                  # {fact, owner, beat}
        "stances_left": {s: list(STANCES) for s in seats},
        "endorse_left": {s: 1 for s in seats},
        "pending": {},                 # seat -> 提交包(揭示前私密)
        "progress": 0,
        "pressure": 0,
        "omens": omens,
        "omen_i": 0,
        "peeked": False,
        "objects_open": list(SCENE["objects"]),
        "beats_log": [],
        "ending": None,
        "memory": None,
        "_memory_candidate": None,
    }


def _fact_by_id(fid):
    for p in SCENE["packets"].values():
        for f in p["facts"]:
            if f["id"] == fid:
                return f
    if fid == SCENE["third_path"]["fact"]["id"]:
        return SCENE["third_path"]["fact"]
    return None


def _obj_name(oid):
    if oid == SCENE["third_path"]["id"]:
        return SCENE["third_path"]["name"]
    return SCENE["objects"].get(oid, oid)


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    flipped = s["omens"][:s["omen_i"]]
    public = {
        "phase": s["phase"],
        "scene": {"id": SCENE["id"], "name": SCENE["name"],
                  "intro": SCENE["intro"], "goal": SCENE["goal"]},
        "beat": s["beat"],
        "total_beats": TOTAL_BEATS,
        "progress": s["progress"],
        "pressure": s["pressure"],
        "objects": [{"id": o, "name": _obj_name(o)} for o in s["objects_open"]],
        "packet_holders": {x: SCENE["packets"][s["packets"][x]]["name"]
                           for x in s["seats"]},
        "pinned": [{"fact_id": p["fact"]["id"], "text": p["fact"]["text"],
                    "boost": p["fact"]["boost"], "owner": p["owner"],
                    "beat": p["beat"]} for p in s["pinned"]],
        "omens_flipped": flipped,
        "omens_composition": sorted(s["omens"]),
        "omen_peek": (s["omens"][s["omen_i"]]
                      if s["peeked"] and s["omen_i"] < len(s["omens"]) else None),
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "stances_left": deepcopy(s["stances_left"]),   # 双方剩余姿态公开:可读对方节奏
        "endorse_left": dict(s["endorse_left"]),
        "beats_log": deepcopy(s["beats_log"]),
        "ending": s["ending"],
        "ending_text": SCENE["endings"].get(s["ending"]) if s["ending"] else None,
        "memory": s["memory"],
    }
    my_packet = SCENE["packets"][s["packets"][seat_id]]
    private = {
        "packet": my_packet["name"],
        "facts": [deepcopy(f) for f in my_packet["facts"]
                  if f["id"] in s["facts"][seat_id]],
        "my_pending": deepcopy(s["pending"].get(seat_id)),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        waiting = [x for x in s["seats"] if x not in s["pending"]]
        if seat_id in waiting:
            legal = [{
                "action_id": "commit",
                "params": {
                    "fact_id": f"必填:本拍钉上桌的见闻,从你未公开的里选:{s['facts'][seat_id]}",
                    "stance": f"必填:本幕未用过的姿态,剩:{s['stances_left'][seat_id]}",
                    "target_id": f"必填:本拍作用对象:{s['objects_open']}",
                    "line": f"可选:一句公开台词(≤{LINE_MAX}字,揭示时亮出;别用它倒底牌)",
                    "endorse": (f"可选 true:盲背书本拍(剩 {s['endorse_left'][seat_id]} 次)"
                                "——若翻出『代价』,由你的信任挡下"),
                },
            }]
    return {"public_state": public, "private_state": private,
            "legal_actions": legal, "waiting_for": waiting}


def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本幕已结束")
    if action_id != "commit":
        raise IllegalAction(f"没有这个动作:{action_id};本卡只有 commit")
    if seat_id in s["pending"]:
        raise IllegalAction("这一拍你已经提交过了")
    params = params if isinstance(params, dict) else {}

    fact_id = params.get("fact_id")
    if not isinstance(fact_id, str) or fact_id not in s["facts"][seat_id]:
        raise IllegalAction(f"fact_id 必须是你未公开的见闻之一:{s['facts'][seat_id]}")
    stance = params.get("stance")
    if stance not in s["stances_left"][seat_id]:
        raise IllegalAction(f"姿态不可用,剩余:{s['stances_left'][seat_id]}")
    target = params.get("target_id")
    if target not in s["objects_open"]:
        raise IllegalAction(f"target_id 必须是当前对象之一:{s['objects_open']}")
    line = params.get("line", "")
    if not isinstance(line, str):
        raise IllegalAction("line 须是字符串")
    line = line.strip()
    if len(line) > LINE_MAX:
        raise IllegalAction(f"公开台词过长:≤{LINE_MAX} 字")
    endorse = bool(params.get("endorse"))
    if endorse and s["endorse_left"][seat_id] < 1:
        raise IllegalAction("你的背书已经用过了")

    s["pending"][seat_id] = {"fact_id": fact_id, "stance": stance,
                             "target_id": target, "line": line,
                             "endorse": endorse}
    if len(s["pending"]) == 2:
        _resolve(s)
    return s


def _resolve(s):
    a, b = s["seats"]
    pa, pb = s["pending"][a], s["pending"][b]
    report = [f"—— 第 {s['beat']} 拍 ——"]

    # 1. 钉见闻(双方本拍所选,同时公开)
    for seat, p in ((a, pa), (b, pb)):
        fact = _fact_by_id(p["fact_id"])
        s["facts"][seat].remove(p["fact_id"])
        s["pinned"].append({"fact": deepcopy(fact), "owner": seat,
                            "beat": s["beat"]})
        report.append(f"{seat} 钉出见闻:{fact['text']}")
    # 2. 亮姿态与台词
    for seat, p in ((a, pa), (b, pb)):
        s["stances_left"][seat].remove(p["stance"])
        if p["endorse"]:
            s["endorse_left"][seat] -= 1
        line = f",并说:「{p['line']}」" if p["line"] else ""
        report.append(f"{seat} 亮出【{p['stance']}】,指向"
                      f"「{_obj_name(p['target_id'])}」{line}")

    combo = COMBOS[frozenset([pa["stance"], pb["stance"]])]
    d_progress = combo.get("progress", 0)
    d_pressure = combo.get("pressure", 0)
    special = combo.get("special")
    report.append(f"姿态咬合【{pa['stance']}×{pb['stance']}】")

    # 3. 已钉见闻的机械加成(谁的行动踩中,谁都算;每条每拍至多一次)
    shield = False
    boost_hit = False
    for pin in s["pinned"]:
        bo = pin["fact"]["boost"]
        for p in (pa, pb):
            if p["stance"] == bo["stance"] and p["target_id"] == bo["target"]:
                boost_hit = True
                if bo["effect"] == "progress":
                    d_progress += 1
                    report.append(f"见闻应验({pin['fact']['id']}):进度 +1")
                elif bo["effect"] == "pressure":
                    d_pressure -= 1
                    report.append(f"见闻应验({pin['fact']['id']}):压力 -1")
                elif bo["effect"] == "shield":
                    shield = True
                    report.append(f"见闻应验({pin['fact']['id']}):本拍代价被挡下")
                elif bo["effect"] == "memory":
                    s["_memory_candidate"] = s["beat"]
                    report.append(f"见闻应验({pin['fact']['id']}):这一拍会被长久记住")
                break
    if special == "boosted_extra" and boost_hit:
        d_progress += 1
        report.append("探明借力:进度再 +1")

    # 4. 翻余波
    omen = s["omens"][s["omen_i"]]
    s["omen_i"] += 1
    s["peeked"] = False
    report.append(f"余波翻出【{omen}】")
    if omen == "代价":
        endorsed = pa["endorse"] or pb["endorse"]
        blocked = endorsed or shield or special in ("soft_cost", "defuse")
        if blocked:
            how = ("背书的信任" if endorsed else
                   "护持的手" if special in ("soft_cost", "defuse") else "预先的警觉")
            report.append(f"代价袭来,被{how}挡下")
        else:
            d_pressure += 1
            for p in (pa, pb):
                report.append(f"代价:{SCENE['costs'].get(p['target_id'], '暗处传来响动')}")
    elif omen == "回声":
        s["_memory_candidate"] = s["beat"]
        report.append("这一拍的痕迹,被世界收进了口袋")
    if special == "strong_memory":
        s["_memory_candidate"] = s["beat"]
        report.append("双探明:你们看清的东西,世界也看清了你们")
    if special == "peek":
        s["peeked"] = True
        if s["omen_i"] < len(s["omens"]):
            report.append(f"双护持:提前看见下一张余波是【{s['omens'][s['omen_i']]}】")
    if special == "third_path":
        tp = SCENE["third_path"]
        if tp["id"] not in s["objects_open"]:
            s["objects_open"].append(tp["id"])
            s["pinned"].append({"fact": deepcopy(tp["fact"]), "owner": None,
                                "beat": s["beat"]})
            report.append(f"转向×探明:第三条路打开——「{tp['name']}」")

    # 5. 结算轨道
    s["progress"] = max(0, min(5, s["progress"] + d_progress))
    s["pressure"] = max(0, min(4, s["pressure"] + d_pressure))
    report.append(f"进度 {s['progress']}/5 · 压力 {s['pressure']}/4")

    s["beats_log"].append({
        "beat": s["beat"], "omen": omen,
        "commits": {x: deepcopy(s["pending"][x]) for x in s["seats"]},
        "report": report,
    })
    s["pending"] = {}

    # 6. 终局判定
    if s["progress"] >= 5:
        _finish(s, "success")
    elif s["pressure"] >= 4:
        _finish(s, "pressure")
    elif s["beat"] >= TOTAL_BEATS:
        _finish(s, "incomplete")
    else:
        s["beat"] += 1


def _finish(s, ending):
    s["phase"] = "finished"
    s["ending"] = ending
    cand = s["_memory_candidate"]
    lines = []
    if cand:
        beat = next(x for x in s["beats_log"] if x["beat"] == cand)
        for seat in s["seats"]:
            c = beat["commits"][seat]
            if c["line"]:
                lines.append(f"{seat} 说过:「{c['line']}」")
    if ending == "success":
        head = "失物邮局记住了这两位旅客:他们没有偷走黎明,而是替它找到了出口。"
        tail = "以后,任何被送错地方的门,都会先为他们打开一次。"
    elif ending == "pressure":
        head = "失物邮局在倾斜中记住了他们撤退时回头的样子。"
        tail = "水退之后,门口会留着两双擦干的鞋印。"
    else:
        head = "失物邮局沉入水下,但分拣机记得还有一封信没人来取。"
        tail = "某个涨潮的夜里,它会把机会重新浮上来。"
    s["memory"] = {"text": " ".join([head] + lines + [tail]),
                   "ending": ending, "beat": cand}
