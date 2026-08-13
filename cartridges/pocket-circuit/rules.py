"""《口袋电路》规则:纯函数,只接值、只回值(蓝图 §10.2 / §11)。

不读数据库、不碰网络、不接触席位令牌。
与宿主的唯一结构约定:full_state["phase"] 为 "playing" 或 "finished"。

规则:数字牌 1–6 按种子洗开,两人各得三张互不重复的私牌;
每轮双方各暗投一张,两边都提交后同时揭示,数字大者得一分;三轮结算。
"""

import random
from copy import deepcopy

TOTAL_ROUNDS = 3
DECK = [1, 2, 3, 4, 5, 6]


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("口袋电路只支持两名玩家")
    order = DECK[:]
    random.Random(seed).shuffle(order)
    return {
        "phase": "playing",
        "seed": seed,
        "seats": list(seats),
        "round": 1,
        "hands": {seats[0]: sorted(order[:3]), seats[1]: sorted(order[3:])},
        "pending": {},   # 本轮已暗投:seat_id -> 牌;对方提交前不揭示
        "revealed": [],  # 已揭示轮:{round, cards, winner}
        "scores": {seats[0]: 0, seats[1]: 0},
    }


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "phase": s["phase"],
        "round": s["round"],
        "total_rounds": TOTAL_ROUNDS,
        "scores": dict(s["scores"]),
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "revealed": deepcopy(s["revealed"]),
    }
    if s["phase"] == "finished":
        public["winner"] = _winner(s)
    private = {
        "hand": list(s["hands"][seat_id]),
        "my_pending": s["pending"].get(seat_id),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        waiting = [x for x in s["seats"] if x not in s["pending"]]
        if seat_id in waiting:
            legal = [{
                "action_id": "play_card",
                "params": {"card": f"从你的手牌选一张暗投:{private['hand']}"},
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
    if action_id != "play_card":
        raise IllegalAction(f"没有这个动作:{action_id};当前只有 play_card")
    if seat_id in s["pending"]:
        raise IllegalAction("这一轮你已经暗投过了")
    card = params.get("card") if isinstance(params, dict) else None
    if isinstance(card, bool) or not isinstance(card, int):
        raise IllegalAction("card 必须是整数")
    if card not in s["hands"][seat_id]:
        raise IllegalAction("这张牌不在你的手牌里")

    s["pending"][seat_id] = card
    if len(s["pending"]) == 2:
        a, b = s["seats"]
        ca, cb = s["pending"][a], s["pending"][b]
        winner = a if ca > cb else b
        s["revealed"].append({"round": s["round"], "cards": {a: ca, b: cb}, "winner": winner})
        s["scores"][winner] += 1
        s["hands"][a].remove(ca)
        s["hands"][b].remove(cb)
        s["pending"] = {}
        if s["round"] >= TOTAL_ROUNDS:
            s["phase"] = "finished"
        else:
            s["round"] += 1
    return s


def _winner(s):
    a, b = s["seats"]
    return a if s["scores"][a] > s["scores"][b] else b
