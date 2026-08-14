"""《口袋里的四样东西》规则:纯函数,只接值、只回值(蓝图 §12)。

十二件固定物件、八张固定情境。每轮翻开一个情境(两个公开需求 + 一个公开风险),
双方从私牌各暗选一件,同时揭示:
- 物件标签命中需求,每项 +1;撞上风险 −1(个人分);
- 两件物件的标签合起来覆盖全部需求,双方共得一枚共同星;
- 用过的物件离开手牌。四轮后给出个人分、共同星和所有公开选择。
桌边话由宿主处理,不参与计分。

与宿主的唯一结构约定:full_state["phase"] 为 "playing" 或 "finished"。
"""

import random
from copy import deepcopy

TOTAL_ROUNDS = 4

ITEMS = {
    "key":            {"name": "钥匙",   "tags": ["开启", "金属", "细小"]},
    "match":          {"name": "火柴",   "tags": ["火", "照明", "一次性"]},
    "glass-bead":     {"name": "玻璃珠", "tags": ["反光", "标记", "易碎"]},
    "thread":         {"name": "线",     "tags": ["连接", "捆扎", "延伸"]},
    "compass":        {"name": "指南针", "tags": ["方向", "金属", "精密"]},
    "handkerchief":   {"name": "手帕",   "tags": ["柔软", "吸水", "遮挡"]},
    "mirror":         {"name": "小镜子", "tags": ["反射", "信号", "易碎"]},
    "chalk":          {"name": "粉笔",   "tags": ["书写", "标记", "消耗"]},
    "whistle":        {"name": "口哨",   "tags": ["声音", "求援", "暴露"]},
    "wax":            {"name": "蜡块",   "tags": ["密封", "燃烧", "塑形"]},
    "coin":           {"name": "硬币",   "tags": ["金属", "重量", "交换"]},
    "clockwork-bird": {"name": "发条鸟", "tags": ["声音", "移动", "脆弱"]},
}

SITUATIONS = {
    "blackout-archive": {
        "name": "停电的档案室",
        "text": "停电以后,你们被困在一间没有窗的档案室。",
        "needs": ["照明", "标记"], "risk": "易碎",
    },
    "wind-rising": {
        "name": "起风了",
        "text": "起风了,远处的人看不见你们。",
        "needs": ["信号", "声音"], "risk": "一次性",
    },
    "lasting-direction": {
        "name": "留下方向",
        "text": "必须给后来者留下一个不会立刻消失的方向。",
        "needs": ["方向", "标记"], "risk": "消耗",
    },
    "narrow-slit": {
        "name": "很窄的缝",
        "text": "你们只能让一件东西穿过一条很窄的缝。",
        "needs": ["细小", "连接"], "risk": "重量",
    },
    "dark-listener": {
        "name": "循声而来",
        "text": "有东西在黑暗里循着声音靠近。",
        "needs": ["遮挡", "柔软"], "risk": "声音",
    },
    "prove-together": {
        "name": "合作的证明",
        "text": "天亮前要证明这里曾经有两个人合作过。",
        "needs": ["书写", "标记"], "risk": "易碎",
    },
    "ember-crossing": {
        "name": "护送火种",
        "text": "要把一点火种护送过浅浅的溪流。",
        "needs": ["密封", "遮挡"], "risk": "吸水",
    },
    "cold-night": {
        "name": "寒夜",
        "text": "寒夜降临,你们必须一起撑到天亮。",
        "needs": ["火", "燃烧"], "risk": "脆弱",
    },
}


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("这张卡只支持两名玩家")
    rng = random.Random(seed)
    item_ids = sorted(ITEMS)
    rng.shuffle(item_ids)
    situations = rng.sample(sorted(SITUATIONS), TOTAL_ROUNDS)
    return {
        "phase": "playing",
        "seed": seed,
        "seats": list(seats),
        "round": 1,
        "hands": {seats[0]: sorted(item_ids[:4]), seats[1]: sorted(item_ids[4:8])},
        "situations": situations,   # 本局四轮的情境,开局钉死
        "pending": {},              # 本轮暗选:seat_id -> item_id
        "revealed": [],
        "scores": {seats[0]: 0, seats[1]: 0},
        "stars": 0,                 # 共同星
    }


def _item_card(item_id):
    it = ITEMS[item_id]
    return {"item_id": item_id, "name": it["name"], "tags": list(it["tags"])}


def _situation_card(sit_id):
    s = SITUATIONS[sit_id]
    return {"situation_id": sit_id, "name": s["name"], "text": s["text"],
            "needs": list(s["needs"]), "risk": s["risk"]}


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "phase": s["phase"],
        "round": s["round"],
        "total_rounds": TOTAL_ROUNDS,
        "scores": dict(s["scores"]),
        "stars": s["stars"],
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "situation": (_situation_card(s["situations"][s["round"] - 1])
                      if s["phase"] == "playing" else None),
        "revealed": deepcopy(s["revealed"]),
    }
    private = {
        "hand": [_item_card(i) for i in s["hands"][seat_id]],
        "my_pending": s["pending"].get(seat_id),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        waiting = [x for x in s["seats"] if x not in s["pending"]]
        if seat_id in waiting:
            legal = [{
                "action_id": "choose_item",
                "params": {"item_id": f"从你的手牌暗选一件,可选:{s['hands'][seat_id]}"},
            }]
    return {
        "public_state": public,
        "private_state": private,
        "legal_actions": legal,
        "waiting_for": waiting,
    }


def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    if action_id != "choose_item":
        raise IllegalAction(f"没有这个动作:{action_id};当前只有 choose_item")
    if seat_id in s["pending"]:
        raise IllegalAction("这一轮你已经暗选过了")
    item_id = params.get("item_id") if isinstance(params, dict) else None
    if not isinstance(item_id, str):
        raise IllegalAction("item_id 必须是字符串")
    if item_id not in s["hands"][seat_id]:
        raise IllegalAction("这件东西不在你的口袋里")

    s["pending"][seat_id] = item_id
    if len(s["pending"]) == 2:
        a, b = s["seats"]
        sit_id = s["situations"][s["round"] - 1]
        sit = SITUATIONS[sit_id]
        needs, risk = set(sit["needs"]), sit["risk"]
        points, choices = {}, {}
        for seat in (a, b):
            iid = s["pending"][seat]
            tags = set(ITEMS[iid]["tags"])
            points[seat] = len(tags & needs) - (1 if risk in tags else 0)
            choices[seat] = {"item_id": iid, "name": ITEMS[iid]["name"]}
            s["scores"][seat] += points[seat]
        union = set(ITEMS[s["pending"][a]]["tags"]) | set(ITEMS[s["pending"][b]]["tags"])
        joint = needs <= union
        if joint:
            s["stars"] += 1
        s["revealed"].append({
            "round": s["round"],
            "situation": {"situation_id": sit_id, "name": sit["name"]},
            "choices": choices,
            "points": points,
            "joint_star": joint,
        })
        s["hands"][a].remove(s["pending"][a])
        s["hands"][b].remove(s["pending"][b])
        s["pending"] = {}
        if s["round"] >= TOTAL_ROUNDS:
            s["phase"] = "finished"
        else:
            s["round"] += 1
    return s
