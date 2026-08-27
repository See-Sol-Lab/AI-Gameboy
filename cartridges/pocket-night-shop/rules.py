"""《口袋夜铺》v0.1:AI 自主经营,人类观看并偶尔盲点一次门铃。

seat_a 是唯一店主,每次 work_shift 完成半日经营并立即存档;seat_b 是观看者,
没有日常经营权。门外一响由引擎预先暗定事件,人类只看见门铃亮起,点击 knock
后才与 AI 一同得知结果。门铃从不阻塞 AI 继续经营。
"""

import hashlib
from copy import deepcopy

SHIFTS = ["黄昏", "深夜"]
FOCI = ["sell", "repair", "scavenge", "curate", "upgrade", "tidy"]
MOODS = ["期待", "专注", "犹豫", "烦躁", "眷恋", "疲惫", "得意"]
MAX_SHOP_LEVEL = 3

ITEMS = [
    ("watch", "停在四点的怀表", "表盖内侧刻着一句没写完的道歉。", 2, 6),
    ("key", "认错门的黄铜钥匙", "它总在靠近陌生门锁时微微发热。", 3, 5),
    ("scarf", "雨天发暖的旧围巾", "线头很多,却还留着淡淡的皂香。", 2, 4),
    ("bird", "缺一片翅膀的机械鸟", "上紧发条后,它会朝北边叫一声。", 1, 8),
    ("letter", "写到一半的辞职信", "最后一行只有一个被反复涂掉的名字。", 3, 3),
    ("teacup", "有细裂纹的蓝茶杯", "杯底画着一座不存在的车站。", 2, 4),
    ("camera", "只拍到背影的相机", "剩余胶片数始终显示为七。", 1, 9),
    ("bell", "没有声音的小铃", "摇动时,附近的灰尘会轻轻离地。", 2, 6),
    ("shoe", "走过很远路的单只皮鞋", "鞋底夹着一张褪色车票。", 1, 5),
    ("seedbox", "生锈的种子铁盒", "盒盖写着:不要在晴天打开。", 2, 7),
    ("lamp", "怕黑的袖珍灯", "熄灯后反而会自己亮起。", 3, 5),
    ("musicbox", "少一节旋律的八音盒", "每逢整点,空缺的那节会从远处传来。", 1, 8),
    ("glove", "沾着银粉的旧手套", "指尖磨损得像曾经反复触碰星图。", 2, 5),
    ("notebook", "页码倒着长的账本", "越往后翻,日期反而越早。", 3, 6),
    ("buttonjar", "装满陌生纽扣的玻璃罐", "每一枚都像从不同年代的衣服上拆下。", 2, 4),
    ("tinwhale", "会叹气的铁皮鲸", "腹中藏着一小撮海盐。", 1, 7),
]

AMBIENT = [
    "雨水顺着招牌滴成一条细线,有路人在橱窗前停了很久。",
    "街灯坏了一盏,今晚进门的客人都比平常更沉默。",
    "隔壁面包房送来一小袋卖剩的硬面包,店里暂时有了香味。",
    "一辆末班车从巷口经过,玻璃跟着轻轻震了一阵。",
    "有人把价签翻到背面看了看,最后什么也没问。",
    "屋檐上的猫换了个位置,像在监督这间店有没有好好营业。",
    "风把门吹开一条缝,柜台上的纸屑排成了奇怪的一行。",
    "老钟慢了两分钟,整条街却像只有这里发现了。",
]

DOOR_EVENTS = [
    ("parcel", "门缝下推进来一个没有寄件人的小包裹。", "item"),
    ("cat", "一只湿漉漉的猫撞翻零钱罐,随后若无其事地卧在门垫上。", "lose_coin"),
    ("old_customer", "一位旧客人没有进门,只在玻璃外向店主认真鞠了一躬。", "reputation"),
    ("wrong_delivery", "远方商队把一件货误送到这里,收货单上的地址已经被雨泡掉。", "item"),
    ("bill", "门把手上挂着一张来路不明的维修账单,偏偏盖着本店的旧章。", "lose_coins"),
    ("leaf", "门打开后什么人也没有,窗台上只多了一片仍带雨水的红叶。", "none"),
    ("shelf", "墙后传来一声轻响,一块原本钉死的木板向里退了半寸。", "capacity"),
    ("coin", "门口放着一枚温热的旧硬币,两面都铸着月亮。", "coins"),
]


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


def _number(seed, *parts):
    raw = ":".join(str(x) for x in (seed, *parts))
    return int(hashlib.sha256(raw.encode()).hexdigest(), 16)


def _capacity(s):
    return 4 + s["shop_level"] * 2 + s["extra_capacity"]


def _make_item(seed, serial, salt):
    template = ITEMS[_number(seed, salt, serial) % len(ITEMS)]
    code, name, story, condition, value = template
    return {
        "id": f"{code}_{serial}", "name": name, "story": story,
        "condition": condition, "value": value, "displayed": False,
    }


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("口袋夜铺需要一位 AI 店主和一位人类观看者")
    state = {
        "phase": "playing", "seed": seed, "seats": list(seats),
        "shopkeeper": seats[0], "observer": seats[1],
        "day": 1, "shift_index": 0, "coins": 12, "reputation": 0,
        "shop_level": 1, "extra_capacity": 0,
        "inventory": [], "item_counter": 0,
        "mood": "期待", "current_goal": "先让这间店安稳开过第一个夜晚",
        "public_line": "先把灯点起来,看看今晚会有什么走进门。",
        "history": [], "diary": [],
        "door_signal": None, "door_count": 0, "door_history": [],
    }
    for index in range(3):
        state["item_counter"] += 1
        state["inventory"].append(
            _make_item(seed, state["item_counter"], f"start{index}"))
    return state


def _item(s, item_id):
    return next((item for item in s["inventory"] if item["id"] == item_id), None)


def _legal_hint(s):
    items = [{"id": item["id"], "name": item["name"],
              "condition": item["condition"], "value": item["value"],
              "displayed": item["displayed"]} for item in s["inventory"]]
    return {
        "focus": f"必填:{FOCI} 之一",
        "item_id": f"sell/repair/curate 时必填,从库存选:{items}",
        "mood": f"必填:{MOODS} 之一,这是给观看者看的公开心情灯",
        "public_line": "必填:店主此刻愿意公开的一句话(1-80字,不是隐藏思维链)",
        "goal": "可选:更新一个公开经营目标(1-60字)",
    }


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "phase": s["phase"], "day": s["day"], "shift": SHIFTS[s["shift_index"]],
        "coins": s["coins"], "reputation": s["reputation"],
        "shop_level": s["shop_level"], "capacity": _capacity(s),
        "inventory": deepcopy(s["inventory"]),
        "mood": s["mood"], "current_goal": s["current_goal"],
        "public_line": s["public_line"],
        "recent_history": deepcopy(s["history"][-10:]),
        "diary": deepcopy(s["diary"][-8:]),
        "door_waiting": s["door_signal"] is not None,
        "door_history": deepcopy(s["door_history"][-6:]),
    }
    if seat_id == s["shopkeeper"]:
        private = {"role": "shopkeeper", "resume_summary": {
            "day": s["day"], "shift": SHIFTS[s["shift_index"]],
            "coins": s["coins"], "goal": s["current_goal"],
            "last_events": [x["text"] for x in s["history"][-3:]],
        }}
        legal = [{"action_id": "work_shift", "params": _legal_hint(s)}]
    else:
        private = {"role": "observer"}
        legal = ([{"action_id": "knock", "params": {}}]
                 if s["door_signal"] is not None else [])
    waiting = [s["shopkeeper"]]
    if s["door_signal"] is not None:
        waiting.append(s["observer"])
    return {"public_state": public, "private_state": private,
            "legal_actions": legal, "waiting_for": waiting}


def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    params = params if isinstance(params, dict) else {}
    if action_id == "work_shift":
        if seat_id != s["shopkeeper"]:
            raise IllegalAction("观看者不能替店主经营")
        _work_shift(s, params)
    elif action_id == "knock":
        if seat_id != s["observer"]:
            raise IllegalAction("店主不能替窗外的人按门铃")
        _knock(s)
    else:
        raise IllegalAction(f"没有这个动作:{action_id}")
    return s


def _work_shift(s, params):
    focus = params.get("focus")
    mood = params.get("mood")
    line = params.get("public_line")
    goal = params.get("goal")
    if focus not in FOCI:
        raise IllegalAction(f"focus 须是 {FOCI} 之一")
    if mood not in MOODS:
        raise IllegalAction(f"mood 须是 {MOODS} 之一")
    if not isinstance(line, str) or not 1 <= len(line.strip()) <= 80:
        raise IllegalAction("public_line 须是1到80字")
    if goal is not None and (not isinstance(goal, str)
                             or not 1 <= len(goal.strip()) <= 60):
        raise IllegalAction("goal 须是1到60字")

    before = {"coins": s["coins"], "reputation": s["reputation"]}
    report = _do_focus(s, focus, params.get("item_id"))
    ambient = AMBIENT[_number(s["seed"], "ambient", s["day"],
                              s["shift_index"]) % len(AMBIENT)]
    s["mood"] = mood
    s["public_line"] = line.strip()
    if goal is not None:
        s["current_goal"] = goal.strip()
    entry = {
        "day": s["day"], "shift": SHIFTS[s["shift_index"]], "focus": focus,
        "text": report, "ambient": ambient,
        "coins_delta": s["coins"] - before["coins"],
        "reputation_delta": s["reputation"] - before["reputation"],
    }
    s["history"].append(entry)
    _maybe_spawn_door(s)
    _advance_time(s)


def _do_focus(s, focus, item_id):
    item = _item(s, item_id)
    if focus in ("sell", "repair", "curate") and not item:
        raise IllegalAction(f"{focus} 须给出库存中的 item_id")
    if focus == "sell":
        price = item["value"] + item["condition"] + s["shop_level"]
        s["coins"] += price
        s["reputation"] += 1
        s["inventory"].remove(item)
        return f"店主把「{item['name']}」交给了今晚的新主人,收入{price}枚硬币。"
    if focus == "repair":
        if item["condition"] >= 3:
            raise IllegalAction("这件旧物已经修到最好")
        if s["coins"] < 1:
            raise IllegalAction("至少需要1枚硬币买修补材料")
        s["coins"] -= 1
        item["condition"] += 1
        item["value"] += 2
        return f"「{item['name']}」被修好了一些,旧伤没有消失,却又能继续使用。"
    if focus == "scavenge":
        if len(s["inventory"]) >= _capacity(s):
            raise IllegalAction("店里已经放不下更多旧物")
        if s["coins"] < 1:
            raise IllegalAction("至少留1枚硬币支付搬运费")
        s["coins"] -= 1
        s["item_counter"] += 1
        found = _make_item(s["seed"], s["item_counter"],
                           f"day{s['day']}shift{s['shift_index']}")
        s["inventory"].append(found)
        return f"店主从旧货巷带回「{found['name']}」:{found['story']}"
    if focus == "curate":
        if item["displayed"]:
            raise IllegalAction("这件旧物已经在橱窗里")
        if sum(1 for x in s["inventory"] if x["displayed"]) >= s["shop_level"] + 1:
            raise IllegalAction("橱窗已经摆满")
        item["displayed"] = True
        s["reputation"] += 1
        return f"店主把「{item['name']}」摆进橱窗,没有标价。"
    if focus == "upgrade":
        if s["shop_level"] >= MAX_SHOP_LEVEL:
            raise IllegalAction("店铺已经扩建到当前上限")
        cost = 10 * s["shop_level"]
        if s["coins"] < cost:
            raise IllegalAction(f"扩建需要{cost}枚硬币")
        s["coins"] -= cost
        s["shop_level"] += 1
        return f"店主花掉{cost}枚硬币,把夜铺扩建到了{ s['shop_level'] }级。"
    s["coins"] += 1
    return "店主清点货架、擦净柜台,从抽屉深处找回了1枚滚丢的硬币。"


def _maybe_spawn_door(s):
    if s["door_signal"] is not None:
        return
    n = _number(s["seed"], "door", s["day"], s["shift_index"])
    if n % 3:
        return
    event = DOOR_EVENTS[(n // 3) % len(DOOR_EVENTS)]
    s["door_count"] += 1
    s["door_signal"] = {"id": f"door_{s['door_count']}", "event": event[0]}


def _advance_time(s):
    if s["shift_index"] == 0:
        s["shift_index"] = 1
        return
    upkeep = 2 + s["shop_level"]
    paid = min(s["coins"], upkeep)
    s["coins"] -= paid
    if paid < upkeep:
        s["reputation"] = max(0, s["reputation"] - 1)
    s["diary"].append({"day": s["day"], "mood": s["mood"],
                       "text": s["public_line"], "upkeep": paid})
    s["day"] += 1
    s["shift_index"] = 0


def _knock(s):
    signal = s["door_signal"]
    if signal is None:
        raise IllegalAction("门外现在没有动静")
    event = next(e for e in DOOR_EVENTS if e[0] == signal["event"])
    _, text, effect = event
    result = text
    if effect == "item":
        if len(s["inventory"]) < _capacity(s):
            s["item_counter"] += 1
            item = _make_item(s["seed"], s["item_counter"], signal["id"])
            s["inventory"].append(item)
            result += f" 包裹里是「{item['name']}」。"
        else:
            s["coins"] += 2
            result += " 店里实在放不下,送货人留下2枚保管费。"
    elif effect == "lose_coin":
        lost = min(1, s["coins"])
        s["coins"] -= lost
        result += f" 零钱少了{lost}枚,门口却从此多了个常住客。"
    elif effect == "reputation":
        s["reputation"] += 2
        result += " 这件小事后来在街坊间传开,声望+2。"
    elif effect == "lose_coins":
        lost = min(2, s["coins"])
        s["coins"] -= lost
        result += f" 店主最后还是付了{lost}枚硬币。"
    elif effect == "capacity":
        s["extra_capacity"] += 1
        result += " 墙后竟空出一个窄小暗格,库存上限+1。"
    elif effect == "coins":
        s["coins"] += 3
        result += " 硬币在柜台上化成了3枚寻常零钱。"
    s["door_history"].append({"day": s["day"], "id": signal["id"],
                              "text": result})
    s["door_signal"] = None
