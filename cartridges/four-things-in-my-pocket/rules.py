"""《口袋里的四样东西》V2 规则:纯函数,只接值、只回值。

V2 核心(设计稿 docs/four-things-v2-design.md):
- 出过的物品进入公共桌面,持续参与组合;前提写成公共物,引擎不用未公开设定判卷;
- 提交 = 物品 + 一句具体用法 + 组合对象(无 / 赌对面 / 桌面公共物);
- 配方表按标签模式确定性判定;配方外的组合由对面背书(限量章)或存疑;
- 第 2 轮结算后各抽 2 选 1;每轮引擎生成人话判词。

与宿主的唯一结构约定:full_state["phase"] 为 "playing" 或 "finished"。
"""

import random
from copy import deepcopy

TOTAL_ROUNDS = 4
USAGE_MAX = 80
CHIPS_PER_SEAT = 2

ITEMS = {
    "key":            {"name": "钥匙",   "tags": ["开启", "金属", "细小"]},
    "match":          {"name": "火柴",   "tags": ["火", "照明", "燃料", "一次性"]},
    "glass-bead":     {"name": "玻璃珠", "tags": ["反光", "透光", "细小", "易碎"]},
    "thread":         {"name": "线",     "tags": ["连接", "延伸", "细小", "捆扎"]},
    "compass":        {"name": "指南针", "tags": ["方向", "金属", "精密"]},
    "handkerchief":   {"name": "手帕",   "tags": ["柔软", "吸水", "遮挡", "包裹"]},
    "mirror":         {"name": "小镜子", "tags": ["反光", "信号", "平整", "易碎"]},
    "chalk":          {"name": "粉笔",   "tags": ["标记", "书写", "消耗"]},
    "whistle":        {"name": "口哨",   "tags": ["声音", "求援", "醒目"]},
    "wax":            {"name": "蜡块",   "tags": ["密封", "防水", "燃料", "塑形"]},
    "coin":           {"name": "硬币",   "tags": ["金属", "重量", "平整"]},
    "clockwork-bird": {"name": "发条鸟", "tags": ["声音", "移动", "机巧", "脆弱"]},
    "lodestone":      {"name": "磁石",   "tags": ["吸附", "金属", "指向"]},
    "knife":          {"name": "小刀",   "tags": ["切割", "金属", "精密"]},
    "paper":          {"name": "纸页",   "tags": ["书写", "轻薄", "燃料", "折叠"]},
    "cork":           {"name": "软木塞", "tags": ["漂浮", "密封", "轻巧"]},
}

# 情境:题面必须交代前提;前提落成 props(开局该轮入场的公共物)
SITUATIONS = {
    "ember-crossing": {
        "name": "渡火",
        "text": "你们脚边有一小堆快熄的炭火,要带着它渡过一条浅溪,到对岸的柴堆。",
        "props": [{"id": "ember", "name": "微弱的炭火", "tags": ["火"]}],
        "needs": ["防水", "持久火"], "risk": "吸水",
    },
    "narrow-slit": {
        "name": "一线天",
        "text": "墙上一道透光的窄缝,缝外是强烈的日光,对面有人在等你们的消息。",
        "props": [{"id": "sunlight", "name": "缝外的日光", "tags": ["照明"]}],
        "needs": ["送达", "细小"], "risk": "重量",
    },
    "wind-rising": {
        "name": "起风了",
        "text": "开阔的坡地上起了大风,远处的人看不见你们。",
        "props": [],
        "needs": ["信号", "醒目"], "risk": "一次性",
    },
    "dark-listener": {
        "name": "循声而来",
        "text": "有东西在黑暗里循着声音靠近,你们要让它扑空。",
        "props": [],
        "needs": ["遮挡", "引开"], "risk": "声音",
    },
    "pathless-wood": {
        "name": "无向之林",
        "text": "林中迷路,阴天看不见太阳,要找到方向并给自己留下来路的记号。",
        "props": [],
        "needs": ["方向", "标记"], "risk": "消耗",
    },
    "prove-together": {
        "name": "合作之证",
        "text": "天亮前要在这里留下『曾有两个人合作过』的证据,它得撑过风雨。",
        "props": [],
        "needs": ["留言", "持久"], "risk": "易碎",
    },
    "cold-night": {
        "name": "夜渡冷河",
        "text": "寒夜将至,河滩上只有一堆受潮的柴,你们必须生起能撑到天亮的火。",
        "props": [{"id": "wet-wood", "name": "潮湿的柴堆", "tags": ["燃料"]}],
        "needs": ["火", "持久火"], "risk": "脆弱",
    },
    "high-hook": {
        "name": "高处的绳结",
        "text": "要的东西挂在够不着的横梁上,梁上有一枚铁钩。",
        "props": [{"id": "iron-hook", "name": "横梁上的铁钩", "tags": ["金属"]}],
        "needs": ["够取", "延伸"], "risk": "易碎",
    },
    "downstream-message": {
        "name": "送出去的名字",
        "text": "要把你们的位置写下来,交给这条溪流,送到下游的人手里。",
        "props": [{"id": "stream", "name": "溪流", "tags": ["流动", "漂浮"]}],
        "needs": ["留言", "送达"], "risk": "吸水",
    },
    "dark-roll-call": {
        "name": "黑屋点名",
        "text": "全黑的屋子里两队人要确认彼此的位置,这里绝不能见明火。",
        "props": [],
        "needs": ["声音", "方向"], "risk": "火",
    },
    "one-knock": {
        "name": "一次机会的敲门",
        "text": "门里的人只认一次暗号,门缝里透出一线烛光;不能惊动街上的第三者。",
        "props": [{"id": "candlelight", "name": "门缝的烛光", "tags": ["照明"]}],
        "needs": ["信号", "精密"], "risk": "醒目",
    },
    "parting-gift": {
        "name": "分道礼",
        "text": "天亮就分头走了。给彼此留一句能带在身上、不会消失的话。",
        "props": [],
        "needs": ["留言", "持久"], "risk": "消耗",
    },
}

# 配方:标签模式制。self/other 均为「或」列表,列表元素是「且」组
RECIPES = [
    {"name": "借光聚束", "self": [["反光"], ["透光"]], "other": [["火"], ["照明"]],
     "grants": ["照明", "信号", "送达"]},
    {"name": "系与投", "self": [["连接"], ["延伸"]], "other": [["细小"], ["轻巧"]],
     "grants": ["送达", "延伸"]},
    {"name": "裹护", "self": [["包裹"], ["密封"], ["防水"]], "other": [[]],
     "grants": ["防水", "持久"]},
    {"name": "火种不灭", "self": [["火"]], "other": [["燃料"]],
     "grants": ["持久火", "照明"]},
    {"name": "远处发声", "self": [["声音"]], "other": [["连接"], ["延伸"]],
     "grants": ["引开", "信号"]},
    {"name": "浮针罗盘", "self": [["吸附"]], "other": [["细小", "金属"]],
     "grants": ["方向", "精密"]},
    {"name": "刻下痕迹", "self": [["切割"], ["书写"]], "other": [["平整"]],
     "grants": ["留言", "标记", "持久"]},
    {"name": "封缄", "self": [["书写"], ["折叠"]], "other": [["密封"]],
     "grants": ["留言", "送达", "防水"]},
    {"name": "声之发条", "self": [["机巧"], ["移动"]], "other": [["声音"]],
     "grants": ["引开", "醒目"]},
    {"name": "荡光", "self": [["反光"]], "other": [["移动"], ["机巧"]],
     "grants": ["醒目", "信号"]},
    {"name": "磁钓", "self": [["吸附"]], "other": [["延伸"], ["连接"]],
     "grants": ["够取", "送达"]},
    {"name": "浮台", "self": [["漂浮"]], "other": [["密封"], ["防水"]],
     "grants": ["防水", "送达"]},
]


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


# ---------------- 工具 ----------------

def _match(tags, alternatives):
    tags = set(tags)
    return any(all(t in tags for t in alt) for alt in alternatives)


def _find_recipe(tags_a, tags_b):
    """双向尝试所有配方;返回 (recipe, 正向?) 或 None。"""
    for r in RECIPES:
        if _match(tags_a, r["self"]) and _match(tags_b, r["other"]):
            return r
        if _match(tags_b, r["self"]) and _match(tags_a, r["other"]):
            return r
    return None


def _item_card(item_id):
    it = ITEMS[item_id]
    return {"item_id": item_id, "name": it["name"], "tags": list(it["tags"])}


def _sit_card(sit_id):
    s = SITUATIONS[sit_id]
    return {"situation_id": sit_id, "name": s["name"], "text": s["text"],
            "needs": list(s["needs"]), "risk": s["risk"],
            "props": deepcopy(s["props"])}


def _other(state, seat):
    return [x for x in state["seats"] if x != seat][0]


def _field_entry(state, fid):
    for f in state["field"]:
        if f["field_id"] == fid:
            return f
    return None


def _add_props(state, sit_id):
    for p in SITUATIONS[sit_id]["props"]:
        if _field_entry(state, p["id"]) is None:
            state["field"].append({
                "field_id": p["id"], "name": p["name"], "tags": list(p["tags"]),
                "owner": None, "spent": False, "source": "prop",
            })


# ---------------- 发牌与保底 ----------------

def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("这张卡只支持两名玩家")
    for offset in range(500):
        s = _deal(seats, seed + offset)
        if _deal_reachable(s):
            return s
    raise ValueError("保底发牌失败:目录配置有问题")


def _deal(seats, seed):
    rng = random.Random(seed)
    item_ids = sorted(ITEMS)
    rng.shuffle(item_ids)
    situations = rng.sample(sorted(SITUATIONS), TOTAL_ROUNDS)
    state = {
        "phase": "playing",
        "step": "choose",            # choose | judge | draw
        "seed": seed,
        "seats": list(seats),
        "round": 1,
        "situations": situations,
        "hands": {seats[0]: sorted(item_ids[:4]), seats[1]: sorted(item_ids[4:8])},
        "pool": item_ids[8:],
        "chips": {seats[0]: CHIPS_PER_SEAT, seats[1]: CHIPS_PER_SEAT},
        "field": [],                 # 公共桌面:玩家出过的物品 + 情境公共物
        "pending": {},               # seat -> {item_id, usage, combo_target}
        "judging": [],               # 待背书提案
        "draw": None,                # 中场补牌:{offers: {seat: [id,id]}, picked: {seat: bool}}
        "revealed": [],
        "scores": {seats[0]: 0, seats[1]: 0},
        "stars": 0,
    }
    _add_props(state, situations[0])
    return state


def _deal_reachable(state):
    """保底:每轮的每个需求,在(已发 8 件 + 各轮公共物 + 配方)下至少有一条路。"""
    dealt = state["hands"][state["seats"][0]] + state["hands"][state["seats"][1]]
    sources = [set(ITEMS[i]["tags"]) for i in dealt]
    for sit_id in state["situations"]:
        sit = SITUATIONS[sit_id]
        pool = sources + [set(p["tags"]) for p in sit["props"]]
        for need in sit["needs"]:
            if any(need in tags for tags in pool):
                continue
            ok = False
            for r in RECIPES:
                if need not in r["grants"]:
                    continue
                for i, ta in enumerate(pool):
                    for j, tb in enumerate(pool):
                        if i != j and _match(ta, r["self"]) and _match(tb, r["other"]):
                            ok = True
                            break
                    if ok:
                        break
                if ok:
                    break
            if not ok:
                return False
    return True


# ---------------- 观察 ----------------

def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    cur_sit = _sit_card(s["situations"][s["round"] - 1]) if s["phase"] == "playing" else None
    public = {
        "phase": s["phase"],
        "step": s["step"],
        "round": s["round"],
        "total_rounds": TOTAL_ROUNDS,
        "scores": dict(s["scores"]),
        "stars": s["stars"],
        "chips": dict(s["chips"]),
        "situation": cur_sit,
        "field": deepcopy(s["field"]),
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "revealed": deepcopy(s["revealed"]),
    }
    if s["step"] == "judge":
        public["pending_reveal"] = {
            "choices": {x: {"item_id": p["item_id"], "name": ITEMS[p["item_id"]]["name"],
                            "usage": p["usage"], "combo_target": p["combo_target"]}
                        for x, p in s["pending"].items()},
            "proposals": [{"proposer": j["proposer"], "judge": j["judge"],
                           "usage": s["pending"][j["proposer"]]["usage"],
                           "verdict": j["verdict"]}
                          for j in s["judging"]],
        }
    private = {
        "hand": [_item_card(i) for i in s["hands"][seat_id]],
        "my_pending": deepcopy(s["pending"].get(seat_id)),
        "chips_left": s["chips"][seat_id],
        "draw_offers": ([_item_card(i) for i in s["draw"]["offers"][seat_id]]
                        if s["step"] == "draw" and s["draw"]
                        and not s["draw"]["picked"][seat_id] else None),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        if s["step"] == "choose":
            waiting = [x for x in s["seats"] if x not in s["pending"]]
            if seat_id in waiting:
                usable_field = [f["field_id"] for f in s["field"] if not f["spent"]]
                legal = [{
                    "action_id": "choose_item",
                    "params": {
                        "item_id": f"从你的手牌选一件:{s['hands'][seat_id]}",
                        "usage": f"必填:一句具体用法(≤{USAGE_MAX}字)。解释是正式动作,会参与结算与裁决",
                        "combo_target": ("可选:'partner'=与对面这轮的牌组合(赌);"
                                         f"'field:<id>'=与桌面公共物组合,可用:{usable_field};省略=单打"),
                    },
                }]
        elif s["step"] == "judge":
            for j in s["judging"]:
                if j["verdict"] is None:
                    waiting.append(j["judge"])
                    if j["judge"] == seat_id:
                        needs = SITUATIONS[s["situations"][s["round"] - 1]]["needs"]
                        legal = [{
                            "action_id": "judge",
                            "params": {
                                "verdict": "'endorse'(花1章,认可这个非常规组合)或 'doubt'(存疑,记录在案)",
                                "needs": f"endorse 时必填:该解释实际覆盖的需求,从 {needs} 里选 1-2 个",
                                "提案": s["pending"][j["proposer"]]["usage"],
                                "你的章": s["chips"][seat_id],
                            },
                        }]
        elif s["step"] == "draw":
            for x in s["seats"]:
                if not s["draw"]["picked"][x]:
                    waiting.append(x)
            if seat_id in waiting:
                legal = [{
                    "action_id": "draw_pick",
                    "params": {"item_id": f"补牌二选一:{s['draw']['offers'][seat_id]}"},
                }]
    return {
        "public_state": public,
        "private_state": private,
        "legal_actions": legal,
        "waiting_for": sorted(set(waiting)),
    }


# ---------------- 动作 ----------------

def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    params = params if isinstance(params, dict) else {}

    if action_id == "choose_item":
        _apply_choose(s, seat_id, params)
    elif action_id == "judge":
        _apply_judge(s, seat_id, params)
    elif action_id == "draw_pick":
        _apply_draw(s, seat_id, params)
    else:
        raise IllegalAction(f"没有这个动作:{action_id}")
    return s


def _apply_choose(s, seat_id, params):
    if s["step"] != "choose":
        raise IllegalAction(f"现在是 {s['step']} 阶段,不能出牌")
    if seat_id in s["pending"]:
        raise IllegalAction("这一轮你已经暗选过了")
    item_id = params.get("item_id")
    if not isinstance(item_id, str) or item_id not in s["hands"][seat_id]:
        raise IllegalAction("这件东西不在你的口袋里")
    usage = params.get("usage")
    if not isinstance(usage, str) or not usage.strip():
        raise IllegalAction("usage 必填:说一句你打算怎么用它")
    usage = usage.strip()
    if len(usage) > USAGE_MAX:
        raise IllegalAction(f"usage 过长:≤{USAGE_MAX} 字")
    target = params.get("combo_target")
    if target is not None:
        if not isinstance(target, str):
            raise IllegalAction("combo_target 须是字符串")
        if target != "partner":
            if not target.startswith("field:"):
                raise IllegalAction("combo_target 只能是 'partner' 或 'field:<id>'")
            f = _field_entry(s, target[6:])
            if f is None:
                raise IllegalAction("桌面上没有这件公共物")
            if f["spent"]:
                raise IllegalAction(f"「{f['name']}」已经耗尽,组不了")
    s["pending"][seat_id] = {"item_id": item_id, "usage": usage,
                             "combo_target": target}
    if len(s["pending"]) == 2:
        _reveal(s)


def _apply_judge(s, seat_id, params):
    if s["step"] != "judge":
        raise IllegalAction("现在没有待裁决的提案")
    duty = next((j for j in s["judging"]
                 if j["judge"] == seat_id and j["verdict"] is None), None)
    if duty is None:
        raise IllegalAction("没有等你裁决的提案")
    verdict = params.get("verdict")
    if verdict == "doubt":
        duty["verdict"] = "doubt"
    elif verdict == "endorse":
        if s["chips"][seat_id] < 1:
            raise IllegalAction("你的背书章用完了")
        needs_all = SITUATIONS[s["situations"][s["round"] - 1]]["needs"]
        chosen = params.get("needs")
        if (not isinstance(chosen, list) or not 1 <= len(chosen) <= 2
                or not all(isinstance(n, str) and n in needs_all for n in chosen)
                or len(set(chosen)) != len(chosen)):
            raise IllegalAction(f"endorse 须指定该解释覆盖的需求(1-2个,只能从 {needs_all} 里选)")
        s["chips"][seat_id] -= 1
        duty["verdict"] = "endorse"
        duty["granted"] = list(chosen)
    else:
        raise IllegalAction("verdict 只能是 'endorse' 或 'doubt'")
    if all(j["verdict"] is not None for j in s["judging"]):
        _settle(s)


def _apply_draw(s, seat_id, params):
    if s["step"] != "draw":
        raise IllegalAction("现在不是补牌阶段")
    if s["draw"]["picked"][seat_id]:
        raise IllegalAction("你已经补过牌了")
    item_id = params.get("item_id")
    if not isinstance(item_id, str) or item_id not in s["draw"]["offers"][seat_id]:
        raise IllegalAction(f"只能从 {s['draw']['offers'][seat_id]} 里二选一")
    s["hands"][seat_id].append(item_id)
    s["hands"][seat_id].sort()
    s["draw"]["picked"][seat_id] = True
    if all(s["draw"]["picked"].values()):
        s["draw"] = None
        _advance(s)


# ---------------- 揭示 → 裁决 → 结算 ----------------

def _resolve_combo(s, seat_id):
    """返回 (fired combo dict | None, proposal 需背书? bool)。"""
    p = s["pending"][seat_id]
    target = p["combo_target"]
    if target is None:
        return None, False
    my_tags = ITEMS[p["item_id"]]["tags"]
    if target == "partner":
        other = _other(s, seat_id)
        other_tags = ITEMS[s["pending"][other]["item_id"]]["tags"]
        other_owner = other
        other_name = ITEMS[s["pending"][other]["item_id"]]["name"]
    else:
        f = _field_entry(s, target[6:])
        if f is None or f["spent"]:
            return None, False  # 桌面变故:组合结构性不成立
        other_tags, other_owner, other_name = f["tags"], f["owner"], f["name"]
    recipe = _find_recipe(my_tags, other_tags)
    if recipe:
        contributors = [seat_id]
        if other_owner is not None and other_owner != seat_id:
            contributors.append(other_owner)
        return {"kind": "recipe", "name": recipe["name"],
                "grants": list(recipe["grants"]), "contributors": contributors,
                "with": other_name, "proposer": seat_id}, False
    return None, True


def _reveal(s):
    s["judging"] = []
    s["_fired"] = []
    for seat in s["seats"]:
        fired, needs_judge = _resolve_combo(s, seat)
        if fired:
            s["_fired"].append(fired)
        elif needs_judge:
            s["judging"].append({"proposer": seat, "judge": _other(s, seat),
                                 "verdict": None})
    if s["judging"]:
        s["step"] = "judge"
    else:
        _settle(s)


def _settle(s):
    sit_id = s["situations"][s["round"] - 1]
    sit = SITUATIONS[sit_id]
    needs, risk = sit["needs"], sit["risk"]
    fired = s.pop("_fired", [])
    doubts = []
    endorse_bonus = {x: 0 for x in s["seats"]}
    for j in s["judging"]:
        p = s["pending"][j["proposer"]]
        if j["verdict"] == "endorse":
            fired.append({"kind": "endorsed", "name": "背书组合",
                          "grants": list(j["granted"]),
                          "contributors": [j["proposer"]],
                          "with": p["combo_target"] or "",
                          "proposer": j["proposer"]})
            endorse_bonus[j["judge"]] += 1
        else:
            doubts.append({"proposer": j["proposer"], "usage": p["usage"]})

    points, eff_tags, risk_hit = {}, {}, {}
    report = [f"—— 第 {s['round']} 轮 · {sit['name']} ——"]
    for seat in s["seats"]:
        p = s["pending"][seat]
        raw = set(ITEMS[p["item_id"]]["tags"])
        eff = set(raw)
        miao = 0
        for c in fired:
            if seat in c["contributors"]:
                eff |= set(c["grants"])
                if set(c["grants"]) & set(needs):
                    miao = 1
        eff_tags[seat] = eff
        covered = [n for n in needs if n in eff]
        risk_hit[seat] = risk in raw
        pts = len(covered) - (1 if risk_hit[seat] else 0) + miao + endorse_bonus[seat]
        points[seat] = pts
        s["scores"][seat] += pts
        name = ITEMS[p["item_id"]]["name"]
        line = f"{seat} 掏出「{name}」:{p['usage']}"
        report.append(line)
        detail = []
        if covered:
            detail.append(f"命中需求[{'、'.join(covered)}]")
        else:
            detail.append("没有命中需求")
        if risk_hit[seat]:
            detail.append(f"踩中风险[{risk}] −1")
        if miao:
            detail.append("妙解 +1")
        if endorse_bonus[seat]:
            detail.append("识解之功 +1")
        report.append("  " + ";".join(detail) + f" → {points[seat]:+d}")
    for c in fired:
        who = "、".join(c["contributors"])
        report.append(f"组合「{c['name']}」成立({who} × {c['with']}),带来[{'、'.join(c['grants'])}]")
    for d in doubts:
        report.append(f"{d['proposer']} 的提案被存疑,原文记录在案")

    union = eff_tags[s["seats"][0]] | eff_tags[s["seats"][1]]
    star = all(n in union for n in needs) and not any(risk_hit.values())
    if star:
        s["stars"] += 1
        report.append("两件东西合起来盖住了所有需求,而且干干净净——共同星 ★+1")
    else:
        missing = [n for n in needs if n not in union]
        if missing:
            report.append(f"差一步:需求[{'、'.join(missing)}]没被盖住,无星")
        else:
            report.append("需求都盖住了,但有人踩了风险——这颗星飞了")

    s["revealed"].append({
        "round": s["round"],
        "situation": {"situation_id": sit_id, "name": sit["name"]},
        "choices": {x: {"item_id": s["pending"][x]["item_id"],
                        "name": ITEMS[s["pending"][x]["item_id"]]["name"],
                        "usage": s["pending"][x]["usage"],
                        "combo_target": s["pending"][x]["combo_target"]}
                    for x in s["seats"]},
        "points": points,
        "combos": [{k: c[k] for k in ("kind", "name", "grants", "contributors", "with")}
                   for c in fired],
        "doubts": doubts,
        "joint_star": star,
        "report": report,
    })
    # 出过的物品进入公共桌面(一次性入桌即耗尽)
    for seat in s["seats"]:
        iid = s["pending"][seat]["item_id"]
        s["hands"][seat].remove(iid)
        s["field"].append({
            "field_id": iid, "name": ITEMS[iid]["name"],
            "tags": list(ITEMS[iid]["tags"]), "owner": seat,
            "spent": "一次性" in ITEMS[iid]["tags"], "source": "play",
        })
    s["pending"] = {}
    s["judging"] = []

    if s["round"] >= TOTAL_ROUNDS:
        s["phase"] = "finished"
        s["step"] = "choose"
    elif s["round"] == 2:
        s["step"] = "draw"
        s["draw"] = {
            "offers": {s["seats"][0]: s["pool"][:2], s["seats"][1]: s["pool"][2:4]},
            "picked": {x: False for x in s["seats"]},
        }
        s["pool"] = s["pool"][4:]
    else:
        _advance(s)


def _advance(s):
    s["round"] += 1
    s["step"] = "choose"
    _add_props(s, s["situations"][s["round"] - 1])
