"""《口袋电路》v0.2:六轮节点竞标。

双方各持相同的电压牌 1–6。每轮公开一个节点价值,双方依次暗投一张未用牌;
高牌获得当前累计电荷,平局则电荷滚入下一节点。人类模式固定 seat_b,
因此每轮由 seat_b 先锁牌,seat_a 随后提交并立即揭牌,不给人类看牌改手的机会。
"""

import random
from copy import deepcopy

TOTAL_ROUNDS = 6
VOLTAGE_CARDS = [1, 2, 3, 4, 5, 6]
NODE_VALUES = [1, 2, 3, 4, 5, 6]


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("口袋电路只支持两名玩家")
    nodes = NODE_VALUES[:]
    random.Random(seed).shuffle(nodes)
    return {
        "phase": "playing",
        "seed": seed,
        "seats": list(seats),
        "lead_seat": seats[1],       # human_ai 固定 seat_b=人类;AI×AI 也沿用同一路径
        "round": 1,
        "node_order": nodes,
        "current_node": nodes[0],
        "stake": nodes[0],
        "hands": {seat: list(VOLTAGE_CARDS) for seat in seats},
        "pending": {},
        "revealed": [],
        "scores": {seats[0]: 0, seats[1]: 0},
    }


def _expected_seat(s):
    if not s["pending"]:
        return s["lead_seat"]
    return next(seat for seat in s["seats"] if seat not in s["pending"])


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "phase": s["phase"],
        "round": s["round"],
        "total_rounds": TOTAL_ROUNDS,
        "current_node": s["current_node"],
        "stake": s["stake"],
        "lead_seat": s["lead_seat"],
        "scores": dict(s["scores"]),
        "submitted": {seat: seat in s["pending"] for seat in s["seats"]},
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
        expected = _expected_seat(s)
        waiting = [expected]
        if seat_id == expected:
            second = bool(s["pending"])
            timing = ("对手已经锁牌且不能更改;提交后本轮立即揭示。"
                      if second else "你先锁牌;对手只能看到你已提交,看不到牌面。")
            legal = [{
                "action_id": "play_card",
                "params": {"card": f"{timing}从你的手牌选一张:{private['hand']}"},
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
    expected = _expected_seat(s)
    if seat_id != expected:
        raise IllegalAction(f"本轮应由 {expected} 先锁牌")
    card = params.get("card") if isinstance(params, dict) else None
    if isinstance(card, bool) or not isinstance(card, int):
        raise IllegalAction("card 必须是整数")
    if card not in s["hands"][seat_id]:
        raise IllegalAction("这张牌不在你的手牌里")

    s["pending"][seat_id] = card
    if len(s["pending"]) == 2:
        _resolve_round(s)
    return s


def _resolve_round(s):
    a, b = s["seats"]
    ca, cb = s["pending"][a], s["pending"][b]
    winner = a if ca > cb else b if cb > ca else None
    points = s["stake"] if winner else 0
    s["revealed"].append({
        "round": s["round"], "node": s["current_node"], "stake": s["stake"],
        "cards": {a: ca, b: cb}, "winner": winner, "points": points,
    })
    if winner:
        s["scores"][winner] += points
    s["hands"][a].remove(ca)
    s["hands"][b].remove(cb)
    s["pending"] = {}
    if s["round"] >= TOTAL_ROUNDS:
        s["phase"] = "finished"
        return
    s["round"] += 1
    s["current_node"] = s["node_order"][s["round"] - 1]
    if winner:
        s["stake"] = s["current_node"]
    else:
        s["stake"] += s["current_node"]


def _winner(s):
    a, b = s["seats"]
    if s["scores"][a] == s["scores"][b]:
        return None
    return a if s["scores"][a] > s["scores"][b] else b
