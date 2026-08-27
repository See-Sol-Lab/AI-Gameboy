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
    ("watch", "停在四点的怀表", "表盖内侧刻着一句没写完的道歉。", 2, 6,
     "秒针重新走动时,每天只会在四点替某个人多停一分钟。"),
    ("key", "认错门的黄铜钥匙", "它总在靠近陌生门锁时微微发热。", 2, 5,
     "它真正认得的不是门,而是曾经被人认真称作家的地方。"),
    ("scarf", "雨天发暖的旧围巾", "线头很多,却还留着淡淡的皂香。", 2, 4,
     "补好最后一个线头后,围巾会记住最近一次拥抱的温度。"),
    ("bird", "缺一片翅膀的机械鸟", "上紧发条后,它会朝北边叫一声。", 1, 8,
     "新翅膀装好后,机械鸟唱出的其实是一串很旧的返航坐标。"),
    ("letter", "写到一半的辞职信", "最后一行只有一个被反复涂掉的名字。", 2, 3,
     "纸张修复后,被涂掉的名字浮了回来,却不是写信人的上司。"),
    ("teacup", "有细裂纹的蓝茶杯", "杯底画着一座不存在的车站。", 2, 4,
     "裂纹补齐后,杯底车站的钟会显示下一班错过的列车。"),
    ("camera", "只拍到背影的相机", "剩余胶片数始终显示为七。", 1, 9,
     "镜头修复后拍出的第七张背影,会转过头看向拍摄者。"),
    ("bell", "没有声音的小铃", "摇动时,附近的灰尘会轻轻离地。", 2, 6,
     "铃舌复原后仍没有声音,但所有遗失物会同时朝它偏一下。"),
    ("shoe", "走过很远路的单只皮鞋", "鞋底夹着一张褪色车票。", 1, 5,
     "鞋底补好后,它会在门边自动转向另一只鞋所在的方向。"),
    ("seedbox", "生锈的种子铁盒", "盒盖写着:不要在晴天打开。", 2, 7,
     "锈锁修开后,盒里只有一粒会在雨声中发芽的玻璃种子。"),
    ("lamp", "怕黑的袖珍灯", "熄灯后反而会自己亮起。", 2, 5,
     "线路接好后才发现,它照亮的是房间里最久没人碰过的东西。"),
    ("musicbox", "少一节旋律的八音盒", "每逢整点,空缺的那节会从远处传来。", 1, 8,
     "簧片补齐后,远处的缺拍也同时消失,像两只盒子终于合奏。"),
    ("glove", "沾着银粉的旧手套", "指尖磨损得像曾经反复触碰星图。", 2, 5,
     "缝好指尖后,银粉会在桌面落成一幅每天缓慢变化的星图。"),
    ("notebook", "页码倒着长的账本", "越往后翻,日期反而越早。", 2, 6,
     "书脊复原后,空白首页出现了店主明天才会记下的一笔支出。"),
    ("buttonjar", "装满陌生纽扣的玻璃罐", "每一枚都像从不同年代的衣服上拆下。", 2, 4,
     "罐口修好后,其中一枚纽扣会在旧主人经过门外时轻敲玻璃。"),
    ("tinwhale", "会叹气的铁皮鲸", "腹中藏着一小撮海盐。", 1, 7,
     "发条完全顺开后,铁皮鲸第一次没有叹气,而是唱出一小段潮声。"),
]

ITEM_KINDS = {
    "watch": "时间", "key": "归处", "scarf": "陪伴", "bird": "机械",
    "letter": "记忆", "teacup": "日常", "camera": "记忆", "bell": "寻物",
    "shoe": "远行", "seedbox": "生长", "lamp": "照明", "musicbox": "音乐",
    "glove": "星图", "notebook": "账目", "buttonjar": "旧衣", "tinwhale": "机械",
}

CUSTOMERS = [
    ("courier", "赶末班车的邮差", "想找一件能陪人走远路的旧物。",
     "他把一张折过很多次的车票攥得很紧。", ["远行", "时间", "归处"], 10),
    ("teacher", "退休的夜校老师", "想买一件还能留住声音或记忆的东西。",
     "她问价前先数了三遍零钱,但没有嫌任何东西贵。", ["记忆", "音乐"], 8),
    ("mechanic", "袖口沾油的修理工", "想看看这店里有没有真正古怪的机械。",
     "他不爱寒暄,检查齿轮时却非常耐心。", ["机械", "寻物"], 13),
    ("widow", "总带两把伞的老妇人", "想找一件适合空房间的日常旧物。",
     "她只问东西修好后会不会太吵。", ["日常", "陪伴", "照明"], 9),
    ("student", "住在阁楼的学生", "需要能帮自己记账、照明或继续生长的东西。",
     "口袋里有奖学金信,鞋底却已经磨穿。", ["账目", "照明", "生长"], 7),
    ("tailor", "戴圆眼镜的裁缝", "专门寻找与旧衣和手工有关的小东西。",
     "他摸过布料边缘后,往往愿意为真正的旧工艺多付一点。", ["旧衣", "陪伴"], 11),
    ("sailor", "很久没见海的水手", "想买一件能证明远方仍然存在的旧物。",
     "他身上的硬币不多,却带着一枚可以抵价的银扣。", ["远行", "机械", "星图"], 9),
    ("clerk", "从档案馆晚归的职员", "想找与时间、记录或失物有关的东西。",
     "她知道旧物行情,但会为准确回答问题的店主放宽预算。", ["时间", "账目", "寻物"], 12),
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
    code, name, story, condition, value, secret = template
    return {
        "id": f"{code}_{serial}", "name": name, "story": story,
        "condition": condition, "value": value, "displayed": False,
        "kind": ITEM_KINDS[code],
        "secret": None, "_secret": secret,
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
        "shift_count": 0,
        "mood": None, "current_goal": "先让这间店安稳开过第一个夜晚",
        "public_line": None,
        "history": [], "diary": [],
        "door_signal": None, "door_count": 0, "door_history": [],
        "customer": None, "customer_count": 0, "customer_book": {},
        "weekly": [], "resting": False, "last_checkpoint": None,
    }
    for index in range(3):
        state["item_counter"] += 1
        state["inventory"].append(
            _make_item(seed, state["item_counter"], f"start{index}"))
    _ensure_state(state)
    return state


def _ensure_state(s):
    s.setdefault("customer", None)
    s.setdefault("customer_count", 0)
    s.setdefault("customer_book", {})
    s.setdefault("weekly", [])
    s.setdefault("resting", False)
    s.setdefault("last_checkpoint", None)
    for item in s.get("inventory", []):
        code = item["id"].rsplit("_", 1)[0]
        item.setdefault("kind", ITEM_KINDS.get(code, "奇物"))
    if s["customer"] is None:
        _spawn_customer(s)


def _spawn_customer(s):
    n = _number(s["seed"], "customer", s["customer_count"], s["day"])
    cid, name, request, clue, wants, base_budget = CUSTOMERS[n % len(CUSTOMERS)]
    book = s["customer_book"].setdefault(
        cid, {"id": cid, "name": name, "visits": 0, "deals": 0, "trust": 0})
    book["visits"] += 1
    budget = base_budget + (n // len(CUSTOMERS)) % 4 - 1 + book["trust"]
    s["customer_count"] += 1
    s["customer"] = {
        "id": cid, "name": name, "request": request, "clue": clue,
        "visits": book["visits"], "patience": 2,
        "_wants": list(wants), "_budget": max(3, budget),
    }


def _item(s, item_id):
    return next((item for item in s["inventory"] if item["id"] == item_id), None)


def _public_item(item):
    public = {key: deepcopy(item[key]) for key in
              ("id", "name", "story", "condition", "value", "displayed", "kind")}
    if item.get("secret"):
        public["secret"] = item["secret"]
    return public


def _public_customer(customer):
    return {key: deepcopy(customer[key]) for key in
            ("id", "name", "request", "clue", "visits", "patience")}


def _legal_hint(s):
    items = [{"id": item["id"], "name": item["name"],
              "kind": item["kind"], "condition": item["condition"], "value": item["value"],
              "displayed": item["displayed"]} for item in s["inventory"]]
    return {
        "focus": f"必填:{FOCI} 之一",
        "item_id": f"sell/repair/curate 时必填,从库存选:{items}",
        "asking_price": "sell 时必填:店主自己报一个正整数价格;客人的真实预算不可见",
        "mood": f"可选:{MOODS} 之一;真有感受时才更新公开心情灯",
        "public_line": "可选:店主真想公开说时写一句(1-80字);沉默完全合法",
        "goal": "可选:更新一个公开经营目标(1-60字)",
    }


def observe(full_state, seat_id):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    _ensure_state(s)
    public = {
        "phase": s["phase"], "day": s["day"], "shift": SHIFTS[s["shift_index"]],
        "coins": s["coins"], "reputation": s["reputation"],
        "shop_level": s["shop_level"], "capacity": _capacity(s),
        "inventory": [_public_item(item) for item in s["inventory"]],
        "customer": _public_customer(s["customer"]),
        "customer_book": deepcopy(list(s["customer_book"].values())),
        "weekly": deepcopy(s["weekly"][-8:]),
        "resting": s["resting"],
        "last_checkpoint": deepcopy(s["last_checkpoint"]),
        "current_goal": s["current_goal"],
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
        if s["resting"]:
            legal = [{"action_id": "reopen_shop", "params": {}}]
        else:
            legal = [{"action_id": "work_shift", "params": _legal_hint(s)}]
            if s["shift_index"] == 0:
                legal.append({"action_id": "close_for_now", "params": {}})
    else:
        private = {"role": "observer"}
        legal = ([{"action_id": "knock", "params": {}}]
                 if s["door_signal"] is not None else [])
    waiting = [] if s["resting"] else [s["shopkeeper"]]
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
    _ensure_state(s)
    params = params if isinstance(params, dict) else {}
    if action_id == "work_shift":
        if seat_id != s["shopkeeper"]:
            raise IllegalAction("观看者不能替店主经营")
        if s["resting"]:
            raise IllegalAction("夜铺已经歇业,先重新开门")
        _work_shift(s, params)
    elif action_id == "close_for_now":
        if seat_id != s["shopkeeper"]:
            raise IllegalAction("只有店主能决定歇业")
        if s["shift_index"] != 0:
            raise IllegalAction("请在一天打烊后的黄昏存档点歇业")
        s["resting"] = True
        s["last_checkpoint"] = {
            "day": s["day"], "coins": s["coins"],
            "reputation": s["reputation"], "goal": s["current_goal"],
            "week": (s["weekly"][-1]["week"] if s["weekly"] else None),
        }
    elif action_id == "reopen_shop":
        if seat_id != s["shopkeeper"]:
            raise IllegalAction("只有店主能重新开门")
        if not s["resting"]:
            raise IllegalAction("夜铺并未歇业")
        s["resting"] = False
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
    if mood is not None and mood not in MOODS:
        raise IllegalAction(f"mood 须是 {MOODS} 之一")
    if line is not None and (not isinstance(line, str)
                             or not 1 <= len(line.strip()) <= 80):
        raise IllegalAction("public_line 须是1到80字")
    if goal is not None and (not isinstance(goal, str)
                             or not 1 <= len(goal.strip()) <= 60):
        raise IllegalAction("goal 须是1到60字")

    before = {"coins": s["coins"], "reputation": s["reputation"]}
    report = _do_focus(s, focus, params.get("item_id"), params.get("asking_price"))
    if s["customer"] is None:
        _spawn_customer(s)
    ambient = AMBIENT[_number(s["seed"], "ambient", s["day"],
                              s["shift_index"]) % len(AMBIENT)]
    if mood is not None:
        s["mood"] = mood
    if line is not None:
        s["public_line"] = line.strip()
    if goal is not None:
        s["current_goal"] = goal.strip()
    entry_day = s["day"]
    entry_shift = SHIFTS[s["shift_index"]]
    _maybe_spawn_door(s)
    closing = _advance_time(s)
    if closing:
        report += f" 打烊维护应付{closing['due']}枚,实际付了{closing['paid']}枚。"
    s["shift_count"] = s.get("shift_count", len(s["history"])) + 1
    s["history"].append({
        "seq": s["shift_count"], "day": entry_day, "shift": entry_shift,
        "focus": focus, "text": report, "ambient": ambient,
        "coins_delta": s["coins"] - before["coins"],
        "reputation_delta": s["reputation"] - before["reputation"],
        "reaction": ({"mood": mood, "text": line.strip() if line else None}
                     if mood is not None or line is not None else None),
    })


def _do_focus(s, focus, item_id, asking_price):
    item = _item(s, item_id)
    if focus in ("sell", "repair", "curate") and not item:
        raise IllegalAction(f"{focus} 须给出库存中的 item_id")
    if focus == "sell":
        if isinstance(asking_price, bool) or not isinstance(asking_price, int) \
                or asking_price <= 0:
            raise IllegalAction("sell 须给出正整数 asking_price")
        customer = s["customer"]
        book = s["customer_book"][customer["id"]]
        if item["kind"] not in customer["_wants"]:
            customer["patience"] -= 1
            result = (f"{customer['name']}认真看过「{item['name']}」,说这不是自己在找的"
                      f"那类东西。")
            if customer["patience"] <= 0:
                result += " 对方礼貌告辞,这次没有成交。"
                s["customer"] = None
            return result
        if asking_price <= customer["_budget"]:
            s["coins"] += asking_price
            s["reputation"] += 1
            s["inventory"].remove(item)
            book["deals"] += 1
            book["trust"] = min(5, book["trust"] + 1)
            s["customer"] = None
            result = (f"{customer['name']}接受了{asking_price}枚硬币的报价,"
                      f"带走「{item['name']}」。")
            if book["deals"] == 3:
                result += " 这位客人已经把夜铺当成会再来的地方。"
            return result
        customer["patience"] -= 1
        result = (f"{customer['name']}听完{asking_price}枚的报价后沉默了一会,"
                  "东西是对的,价钱却还没谈拢。")
        if customer["patience"] <= 0:
            result += " 对方最终离开了夜铺。"
            s["customer"] = None
        else:
            result += " 对方没有走,店主还有一次重新报价的机会。"
        return result
    if focus == "repair":
        if item["condition"] >= 3:
            raise IllegalAction("这件旧物已经修到最好")
        if s["coins"] < 1:
            raise IllegalAction("至少需要1枚硬币买修补材料")
        s["coins"] -= 1
        item["condition"] += 1
        item["value"] += 2
        result = f"「{item['name']}」被修好了一些,旧伤没有消失,却又能继续使用。"
        if item["condition"] == 3 and item.get("_secret") and not item.get("secret"):
            item["secret"] = item["_secret"]
            item["value"] += 3
            result += f" 完全修复后才发现:{item['secret']}"
        return result
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
        return None
    upkeep = 2 + s["shop_level"]
    paid = min(s["coins"], upkeep)
    s["coins"] -= paid
    if paid < upkeep:
        s["reputation"] = max(0, s["reputation"] - 1)
    s["diary"].append({
        "day": s["day"], "text": f"打烊时硬币{s['coins']}枚,声望{s['reputation']}。",
        "upkeep": paid,
    })
    if s["day"] % 7 == 0:
        s["weekly"].append({
            "week": s["day"] // 7, "through_day": s["day"],
            "coins": s["coins"], "reputation": s["reputation"],
            "shop_level": s["shop_level"], "inventory": len(s["inventory"]),
            "deals": sum(row["deals"] for row in s["customer_book"].values()),
        })
    s["day"] += 1
    s["shift_index"] = 0
    return {"due": upkeep, "paid": paid}


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
