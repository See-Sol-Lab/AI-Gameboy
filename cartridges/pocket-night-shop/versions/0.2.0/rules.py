"""《口袋夜铺》v0.2：单人经营、永久图鉴、街巷探索与自动事件。

AI 是唯一玩家；所有随机结果由种子决定。展示端只接收公开观察和顺序日志。
批量行动在新发现、事件、资源边界处交还决策权，不替玩家报价或出售藏品。
"""

import hashlib
from copy import deepcopy

SHIFTS = ["黄昏", "深夜"]
FOCI = ["sell", "repair", "scavenge", "curate", "upgrade", "tidy", "recycle", "dismiss"]
MOODS = ["期待", "专注", "犹豫", "烦躁", "眷恋", "疲惫", "得意"]
MAX_SHOP_LEVEL = 3
MAX_BATCH = 6

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


RARITIES = {"common": ("寻常", 8), "uncommon": ("少见", 3), "rare": ("奇珍", 1)}
ITEM_RARITY = {
    "watch": "common", "key": "common", "scarf": "common", "teacup": "common",
    "lamp": "common", "buttonjar": "common", "letter": "uncommon", "shoe": "uncommon",
    "camera": "rare", "musicbox": "uncommon", "notebook": "common", "bell": "uncommon",
    "bird": "uncommon", "tinwhale": "rare", "seedbox": "common", "glove": "uncommon",
}
LOCATIONS = {
    "lane": {"name": "旧货巷", "description": "日常旧物与被遗忘的小事。", "cost": 1,
             "unlock_cost": 0, "discoveries": 0,
             "pool": ["watch", "key", "scarf", "teacup", "lamp", "buttonjar", "letter", "shoe"]},
    "station": {"name": "废弃车站", "description": "时间、声音和往返的痕迹。", "cost": 2,
                "unlock_cost": 8, "discoveries": 4,
                "pool": ["watch", "shoe", "camera", "musicbox", "notebook", "bell"]},
    "dock": {"name": "码头仓库", "description": "远航留下的机械与异物。", "cost": 3,
             "unlock_cost": 12, "discoveries": 8,
             "pool": ["key", "scarf", "bird", "tinwhale", "seedbox", "glove"]},
}
EVENTS = {
    "leaf": {"name": "雨中的红叶", "text": "风从门缝送来一片仍带雨水的红叶。"},
    "refund": {"name": "迟来的零钱", "text": "旧客人托人送回少付的两枚硬币。", "coins": 2},
    "lamp_post": {"name": "街灯重亮", "text": "修路人重新点亮巷口的灯,橱窗又被路人看见。", "reputation": 1},
    "parcel": {"name": "无名包裹", "text": "送货人抱来一件看不出形状的旧物,要两枚搬运费。",
               "choices": {"accept": {"label": "付2枚收下,打开检查", "cost": 2},
                           "decline": {"label": "婉拒包裹", "cost": 0}}},
    "locked_box": {"name": "锁住的小匣", "text": "清理柜台时发现一只封死的小匣,里面有轻响。",
                   "choices": {"open": {"label": "花2枚买工具拆开", "cost": 2},
                               "trade": {"label": "整匣交给收货人,得1枚", "cost": 0},
                               "leave": {"label": "合上抽屉,让它留在原处", "cost": 0}}},
}


class IllegalAction(Exception):
    pass


def _number(seed, *parts):
    return int(hashlib.sha256(":".join(map(str, (seed, *parts))).encode()).hexdigest(), 16)


def _capacity(s):
    return 4 + s["shop_level"] * 2 + s["extra_capacity"]


def _make_item(s, location, salt):
    pool = LOCATIONS[location]["pool"]
    weights = [RARITIES[ITEM_RARITY[code]][1] for code in pool]
    roll = _number(s["seed"], salt, s["item_counter"]) % sum(weights)
    for code, weight in zip(pool, weights):
        if roll < weight:
            break
        roll -= weight
    _, name, story, condition, value, secret = next(row for row in ITEMS if row[0] == code)
    s["item_counter"] += 1
    return {"id": f"{code}_{s['item_counter']}", "code": code, "name": name,
            "story": story, "condition": condition, "value": value,
            "displayed": False, "kind": ITEM_KINDS[code], "rarity": ITEM_RARITY[code],
            "origin": location, "secret": None, "_secret": secret}


def _collect(s, item):
    code = item["code"]
    first = code not in s["collection"]
    if first:
        s["collection"][code] = {
            "code": code, "name": item["name"], "story": item["story"],
            "kind": item["kind"], "rarity": item["rarity"], "first_day": s["day"],
            "first_location": item["origin"], "count": 0, "revealed": None,
        }
        s["coins"] += 2
    s["collection"][code]["count"] += 1
    s["inventory"].append(item)
    return first


def new_game(seats, seed):
    if len(seats) != 1:
        raise ValueError("口袋夜铺 v0.2 只需要一位 AI 店主")
    s = {
        "phase": "playing", "seed": seed, "seats": list(seats), "shopkeeper": seats[0],
        "day": 1, "shift_index": 0, "coins": 12, "reputation": 0,
        "shop_level": 1, "extra_capacity": 0, "inventory": [], "item_counter": 0,
        "shift_count": 0, "history": [], "diary": [], "weekly": [],
        "current_goal": "认识旧货巷的旧物,补全第一批图鉴",
        "resting": False, "last_checkpoint": None,
        "collection": {}, "encounters": {}, "unlocked_locations": ["lane"],
        "location": "lane", "pending_event": None, "event_count": 0,
        "customer": None, "customer_count": 0, "customer_book": {},
        "last_run": None,
    }
    for i in range(3):
        _collect(s, _make_item(s, "lane", f"start{i}"))
    _spawn_customer(s)
    return s


def _spawn_customer(s):
    n = _number(s["seed"], "customer", s["customer_count"], s["day"])
    cid, name, request, clue, wants, base = CUSTOMERS[n % len(CUSTOMERS)]
    row = s["customer_book"].setdefault(
        cid, {"id": cid, "name": name, "visits": 0, "deals": 0, "trust": 0})
    row["visits"] += 1
    s["customer_count"] += 1
    s["customer"] = {"id": cid, "name": name, "request": request, "clue": clue,
                     "visits": row["visits"], "patience": 2,
                     "_wants": list(wants), "_budget": max(3, base + n // 8 % 4 - 1 + row["trust"])}


def _public_item(item):
    return {key: deepcopy(value) for key, value in item.items() if not key.startswith("_")}


def _public_customer(s):
    return {key: value for key, value in s["customer"].items() if not key.startswith("_")}


def _locations(s):
    return [
        {"id": key, "name": loc["name"], "description": loc["description"], "cost": loc["cost"],
         "unlock_cost": loc["unlock_cost"], "required_discoveries": loc["discoveries"],
         "unlocked": key in s["unlocked_locations"],
         "undiscovered": sum(code not in s["collection"] for code in loc["pool"])}
        for key, loc in LOCATIONS.items()
    ]


def _event_view(s):
    pending = s["pending_event"]
    if pending is None:
        return None
    event = EVENTS[pending["kind"]]
    choices = []
    for key, choice in event["choices"].items():
        has_room = key not in ("accept", "open") or len(s["inventory"]) < _capacity(s)
        choices.append({"id": key, **choice,
                        "available": s["coins"] >= choice["cost"] and has_room})
    return {"id": pending["id"], "name": event["name"], "text": event["text"], "choices": choices}


def _legal_actions(s):
    if s["resting"]:
        return [{"action_id": "reopen_shop", "params": {}}]
    if s["pending_event"]:
        return [{"action_id": "choose_event", "params": {
                    "event_id": s["pending_event"]["id"], "choice": _event_view(s)["choices"]}},
                {"action_id": "close_for_now", "params": {}}]
    actions = [
        {"action_id": "work_shift", "params": {
            "focus": FOCI, "item_id": "sell/repair/curate/recycle 必填,从库存选",
            "asking_price": "sell 必填正整数;店主自己报价",
            "location": "scavenge 可选已解锁地点 id",
            "goal": "可选,1-60字;表达也可省略", "mood": MOODS,
            "public_line": "可选,1-80字;沉默是正常玩法"}},
        {"action_id": "run_shifts", "params": {
            "focus": ["scavenge", "repair", "tidy"], "count": "1-6",
            "item_id": "repair 必填", "location": "scavenge 可选已解锁地点",
            "reserve": "非负整数,含当班维护费的现金保留线",
            "stop_on": '可选字符串或数组:new/rare/event;如 "new" 或 ["new","rare"];'
                       '省略默认 ["new","rare","event"];[] 不因这些标记停班,待选择事件仍停'}},
        {"action_id": "close_for_now", "params": {}},
    ]
    if any(key not in s["unlocked_locations"] for key in LOCATIONS):
        actions.append({"action_id": "unlock_location", "params": {"location": _locations(s)}})
    return actions


def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "phase": s["phase"], "day": s["day"], "shift": SHIFTS[s["shift_index"]],
        "coins": s["coins"], "reputation": s["reputation"], "shop_level": s["shop_level"],
        "capacity": _capacity(s), "inventory": [_public_item(item) for item in s["inventory"]],
        "current_goal": s["current_goal"], "resting": s["resting"],
        "last_checkpoint": deepcopy(s["last_checkpoint"]),
        "customer": _public_customer(s), "customer_book": deepcopy(list(s["customer_book"].values())),
        "weekly": deepcopy(s["weekly"][-8:]), "diary": deepcopy(s["diary"][-8:]),
        "recent_history": deepcopy(s["history"][-6:]), "journal_total": len(s["history"]),
        "collection": {"found": len(s["collection"]), "total": len(ITEMS),
                       "revealed": sum(bool(row["revealed"]) for row in s["collection"].values()),
                       "entries": deepcopy(list(s["collection"].values()))},
        "encounters": {"found": len(s["encounters"]), "total": len(EVENTS),
                       "entries": deepcopy(list(s["encounters"].values()))},
        "locations": _locations(s), "location": s["location"],
        "pending_event": _event_view(s), "last_run": deepcopy(s["last_run"]),
    }
    return {"public_state": public,
            "private_state": {"role": "shopkeeper", "resume_summary": {
                "day": s["day"], "shift": SHIFTS[s["shift_index"]], "goal": s["current_goal"],
                "coins": s["coins"], "discoveries": len(s["collection"]),
                "pending_event": _event_view(s),
                "last_events": [entry["text"] for entry in s["history"][-3:]]}},
            "legal_actions": [] if s["phase"] == "finished" else _legal_actions(s),
            "waiting_for": [] if s["resting"] or s["phase"] == "finished" else [s["shopkeeper"]]}


def history_since(s, after_seq):
    # 显示器按游标读取全部公开日志,批量经营也不丢班次。
    return deepcopy(s["history"][after_seq:after_seq + 100])


def _log(s, day, shift, focus, text, before, **extra):
    s["history"].append({
        "seq": len(s["history"]) + 1, "day": day, "shift": shift, "focus": focus,
        "text": text, "coins_delta": s["coins"] - before[0],
        "reputation_delta": s["reputation"] - before[1],
        "goal": s["current_goal"], "customer": deepcopy(_public_customer(s)), **extra,
    })


def _text_param(params, key, maximum):
    value = params.get(key)
    if value is not None and (not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum):
        raise IllegalAction(f"{key} 须为1到{maximum}字")
    return value.strip() if value is not None else None


def _validate_work(s, params):
    focus = params.get("focus")
    if focus not in FOCI:
        raise IllegalAction("未知经营动作")
    _text_param(params, "goal", 60)
    _text_param(params, "public_line", 80)
    if params.get("mood") is not None and params["mood"] not in MOODS:
        raise IllegalAction("未知心情")
    if focus in ("sell", "repair", "curate", "recycle"):
        item = next((item for item in s["inventory"] if item["id"] == params.get("item_id")), None)
        if item is None:
            raise IllegalAction("请选库存中的旧物")
        if focus == "sell":
            price = params.get("asking_price")
            if type(price) is not int or price <= 0:
                raise IllegalAction("asking_price 必须为正整数")
    if focus == "scavenge":
        location = params.get("location", s["location"])
        if not isinstance(location, str) or location not in s["unlocked_locations"]:
            raise IllegalAction("请先解锁淘货地点")


def _work_cost(s, params):
    focus = params["focus"]
    if focus == "scavenge":
        return LOCATIONS[params.get("location", s["location"])]["cost"]
    if focus == "repair":
        return 1
    if focus == "upgrade":
        return 10 * s["shop_level"]
    return 0


def _work_block(s, params):
    focus = params["focus"]
    if focus == "scavenge" and len(s["inventory"]) >= _capacity(s):
        return "inventory_full"
    if focus in ("repair", "curate"):
        item = next(item for item in s["inventory"] if item["id"] == params["item_id"])
        if focus == "repair" and item["condition"] >= 3:
            return "repair_complete"
        if focus == "curate" and (item["displayed"] or
                sum(bool(x["displayed"]) for x in s["inventory"]) >= s["shop_level"] + 1):
            return "display_full"
    if focus == "upgrade" and s["shop_level"] >= MAX_SHOP_LEVEL:
        return "shop_maximum"
    if s["coins"] < _work_cost(s, params):
        return "insufficient_coins"
    return None


def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id != s["shopkeeper"] or seat_id not in s["seats"]:
        raise IllegalAction("只有 AI 店主可以操作;网页仅供观看")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    if not isinstance(params, dict):
        raise IllegalAction("params 须是对象")
    if action_id == "close_for_now":
        if s["resting"]:
            raise IllegalAction("已经歇业")
        s["resting"] = True
        s["last_checkpoint"] = {"day": s["day"], "shift": SHIFTS[s["shift_index"]],
                                "coins": s["coins"], "goal": s["current_goal"],
                                "week": s["weekly"][-1]["week"] if s["weekly"] else None}
        return s
    if action_id == "reopen_shop":
        if not s["resting"]:
            raise IllegalAction("店铺已经开门")
        s["resting"] = False
        return s
    if s["resting"]:
        raise IllegalAction("请先 reopen_shop 续档")
    s["last_run"] = None
    if action_id == "choose_event":
        _choose_event(s, params)
    elif s["pending_event"]:
        raise IllegalAction("请先处理眼前事件,也可歇业后下次继续")
    elif action_id == "unlock_location":
        _unlock(s, params)
    elif action_id in ("work_shift", "run_shifts"):
        _validate_work(s, params)
        if action_id == "work_shift":
            block = _work_block(s, params)
            if block:
                raise IllegalAction(block)
            _work_shift(s, params)
        else:
            _run_shifts(s, params)
    else:
        raise IllegalAction(f"没有这个动作:{action_id}")
    return s


def _run_shifts(s, params):
    if params["focus"] not in ("scavenge", "repair", "tidy"):
        raise IllegalAction("连续行动限淘货、修理和整理;出售由店主逐件决定")
    count = params.get("count", 1)
    reserve = params.get("reserve", 0)
    stops = params.get("stop_on", ["new", "rare", "event"])
    if isinstance(stops, str):
        stops = [stops]
    if type(count) is not int or not 1 <= count <= MAX_BATCH:
        raise IllegalAction("count 须为1到6")
    if type(reserve) is not int or reserve < 0:
        raise IllegalAction("reserve 须为非负整数")
    if not isinstance(stops, list) or any(x not in ("new", "rare", "event") for x in stops):
        raise IllegalAction('stop_on 须为 new/rare/event 字符串或由它们组成的数组;'
                            '如 "new"、["new","rare"] 或 []')
    done, reason, start = 0, "count", len(s["history"])
    for _ in range(count):
        block = _work_block(s, params)
        upkeep = 2 + s["shop_level"] if s["shift_index"] == 1 else 0
        known_income = 3 if params["focus"] == "tidy" else 0
        # 不把未知奖励当作已到手的钱;边界在真正花钱前生效。
        if block or s["coins"] + known_income - _work_cost(s, params) - upkeep < reserve:
            reason = block or "reserve"
            break
        flags = _work_shift(s, params)
        done += 1
        if s["pending_event"]:
            reason = "decision"
            break
        hit = next((key for key in ("event", "new", "rare") if key in stops and flags[key]), None)
        if hit:
            reason = hit
            break
    s["last_run"] = {"requested": count, "completed": done, "stop_reason": reason,
                     "from_seq": start + 1 if done else None, "to_seq": len(s["history"]),
                     "highlights": [row["text"] for row in s["history"][start:]
                                    if row.get("new") or row.get("rare") or row.get("event")]}


def _work_shift(s, params):
    before = (s["coins"], s["reputation"])
    day, shift = s["day"], SHIFTS[s["shift_index"]]
    customer = deepcopy(_public_customer(s))
    customer_count = s["customer_count"]
    offer = None
    if params["focus"] == "sell":
        item = next(x for x in s["inventory"] if x["id"] == params["item_id"])
        offer = {"item_name": item["name"], "asking_price": params["asking_price"]}
    flags = {"new": False, "rare": False, "event": False}
    report = _do_focus(s, params, flags)
    if params.get("goal") is not None:
        s["current_goal"] = params["goal"].strip()
    ambient = AMBIENT[_number(s["seed"], "ambient", s["shift_count"]) % len(AMBIENT)]
    s["shift_count"] += 1
    event_text = _maybe_event(s)
    if event_text:
        report += " " + event_text
        flags["event"] = True
    if s["shift_index"] == 1:
        upkeep = 2 + s["shop_level"]
        paid = min(upkeep, s["coins"])
        s["coins"] -= paid
        if paid < upkeep:
            s["reputation"] = max(0, s["reputation"] - 1)
        report += f" 打烊维护应付{upkeep}枚,实际付{paid}枚。"
        s["diary"].append({"day": day, "text": f"打烊时硬币{s['coins']}枚,声望{s['reputation']}。",
                           "upkeep": paid})
        if day % 7 == 0:
            s["weekly"].append({"week": day // 7, "through_day": day, "coins": s["coins"],
                "reputation": s["reputation"], "shop_level": s["shop_level"],
                "inventory": len(s["inventory"]), "deals": sum(x["deals"] for x in s["customer_book"].values()),
                "discoveries": len(s["collection"]), "encounters": len(s["encounters"])})
        s["day"] += 1
        s["shift_index"] = 0
    else:
        s["shift_index"] = 1
    reaction = None
    if params.get("mood") is not None or params.get("public_line") is not None:
        reaction = {"mood": params.get("mood"), "text": _text_param(params, "public_line", 80)}
    _log(s, day, shift, params["focus"], report, before, ambient=ambient, reaction=reaction,
         customer=customer, offer=offer,
         customer_arrived=deepcopy(_public_customer(s)) if s["customer_count"] != customer_count else None,
         **flags)
    return flags


def _do_focus(s, params, flags):
    focus = params["focus"]
    item = next((x for x in s["inventory"] if x["id"] == params.get("item_id")), None)
    if focus == "scavenge":
        location = params.get("location", s["location"])
        s["location"] = location
        s["coins"] -= LOCATIONS[location]["cost"]
        found = _make_item(s, location, f"find{s['shift_count']}")
        flags["new"] = _collect(s, found)
        flags["rare"] = found["rarity"] == "rare"
        prefix = "新发现,图鉴收录+2枚。" if flags["new"] else "这件见过,图鉴数量+1。"
        if flags["new"] and len(s["collection"]) == len(ITEMS):
            prefix += " 异物志全部物种已发现！还可继续补完修复秘密。"
        return f"从{LOCATIONS[location]['name']}带回「{found['name']}」。{prefix} {found['story']}"
    if focus == "repair":
        s["coins"] -= 1
        item["condition"] += 1
        item["value"] += 2
        report = f"修补「{item['name']}」,完好度{item['condition']}/3。"
        if item["condition"] == 3:
            item["secret"] = item["_secret"]
            row = s["collection"][item["code"]]
            if row["revealed"] is None:
                row["revealed"] = item["secret"]
                row["revealed_day"] = s["day"]
                s["coins"] += 2
                flags["new"] = True
                report += " 图鉴首次揭秘,获得2枚。"
                if sum(bool(x["revealed"]) for x in s["collection"].values()) == len(ITEMS):
                    report += " 异物志全部揭秘！这间店已经见证了每一种旧物的另一面。"
            item["value"] += 3
            report += f" 完全修复后才发现:{item['secret']}"
        return report
    if focus == "sell":
        c = s["customer"]
        price = params["asking_price"]
        # 完好程度和异能确实影响出价上限,昂贵破物不能无限高价倒卖。
        ceiling = min(c["_budget"], item["value"] + item["condition"] + s["shop_level"])
        if item["kind"] in c["_wants"] and price <= ceiling:
            s["coins"] += price
            s["reputation"] += 1
            row = s["customer_book"][c["id"]]
            row["deals"] += 1
            row["trust"] = min(5, row["trust"] + 1)
            s["inventory"].remove(item)
            report = f"{c['name']}付了{price}枚,带走「{item['name']}」。图鉴记录保留。"
            _spawn_customer(s)
            return report
        c["patience"] -= 1
        report = (f"{c['name']}表示这类旧物不合需要。" if item["kind"] not in c["_wants"]
                  else f"{c['name']}觉得报价偏高,还没有成交。")
        if c["patience"] == 0:
            report += " 客人告辞了。"
            _spawn_customer(s)
        return report
    if focus == "recycle":
        price = max(1, item["value"] // 3)
        s["coins"] += price
        s["inventory"].remove(item)
        return f"把「{item['name']}」作为零件回收,得{price}枚。图鉴记录保留。"
    if focus == "dismiss":
        name = s["customer"]["name"]
        _spawn_customer(s)
        return f"向{name}说明暂时无货,记下需求送客;另一位客人进门。"
    if focus == "curate":
        item["displayed"] = True
        s["reputation"] += 1
        return f"「{item['name']}」放进橱窗,暂不出售。"
    if focus == "upgrade":
        cost = 10 * s["shop_level"]
        s["coins"] -= cost
        s["shop_level"] += 1
        return f"花{cost}枚扩建到{s['shop_level']}级。"
    s["coins"] += 3
    return "整理货架并承接街坊的小修补,挣得3枚硬币。"


def _record_event(s, key, outcome=None, text=None):
    event = EVENTS[key]
    row = s["encounters"].setdefault(key, {
        "id": key, "name": event["name"], "text": event["text"],
        "first_day": s["day"], "count": 0, "outcomes": {},
    })
    if outcome is None:
        row["count"] += 1
    else:
        row["outcomes"][outcome] = text


def _maybe_event(s):
    n = _number(s["seed"], "event", s["shift_count"])
    if n % 4:
        return ""
    key = list(EVENTS)[(n // 4) % len(EVENTS)]
    event = EVENTS[key]
    s["event_count"] += 1
    _record_event(s, key)
    if "choices" in event:
        s["pending_event"] = {"id": f"event_{s['event_count']}", "kind": key,
                              "_location": s["location"]}
        return f"街巷见闻「{event['name']}」:{event['text']} 等待店主选择。"
    s["coins"] += event.get("coins", 0)
    s["reputation"] += event.get("reputation", 0)
    _record_event(s, key, "happened", event["text"])
    return f"街巷见闻「{event['name']}」:{event['text']}"


def _choose_event(s, params):
    pending = s["pending_event"]
    if pending is None or params.get("event_id") != pending["id"]:
        raise IllegalAction("请回应当前事件")
    key, choice = pending["kind"], params.get("choice")
    event = EVENTS[key]
    if not isinstance(choice, str) or choice not in event["choices"]:
        raise IllegalAction("请选事件中列出的选项")
    cost = event["choices"][choice]["cost"]
    if s["coins"] < cost:
        raise IllegalAction("现金不足,可以选择免费选项")
    gets_item = choice in ("accept", "open")
    if gets_item and len(s["inventory"]) >= _capacity(s):
        raise IllegalAction("货架已满,可选择不收下")
    before = (s["coins"], s["reputation"])
    s["coins"] -= cost
    first = rare = False
    if gets_item:
        item = _make_item(s, pending["_location"], pending["id"])
        first = _collect(s, item)
        rare = item["rarity"] == "rare"
        report = f"打开后发现「{item['name']}」。" + ("首次收录,获得2枚。" if first else "补记到图鉴。")
        if first and len(s["collection"]) == len(ITEMS):
            report += " 异物志全部物种已发现！"
    elif choice == "trade":
        s["coins"] += 1
        report = "收货人带走小匣,留下一枚硬币。"
    else:
        report = "店主选择暂不接下这件事,店铺继续营业。"
    _record_event(s, key, choice, report)
    s["pending_event"] = None
    _log(s, s["day"], SHIFTS[s["shift_index"]], "choose_event", report, before,
         event=True, new=first, rare=rare, reaction=None, ambient="",
         event_name=event["name"], choice=event["choices"][choice]["label"])


def _unlock(s, params):
    key = params.get("location")
    if not isinstance(key, str) or key not in LOCATIONS:
        raise IllegalAction("未知地点")
    if key in s["unlocked_locations"]:
        raise IllegalAction("地点已经解锁")
    loc = LOCATIONS[key]
    if len(s["collection"]) < loc["discoveries"] or s["coins"] < loc["unlock_cost"]:
        raise IllegalAction("发现种数或现金不足")
    before = (s["coins"], s["reputation"])
    s["coins"] -= loc["unlock_cost"]
    s["unlocked_locations"].append(key)
    _log(s, s["day"], SHIFTS[s["shift_index"]], "unlock_location",
         f"打通前往{loc['name']}的淘货路线。", before, ambient="", reaction=None)


def migrate(old):
    """显式升级 v0.1 存档；只收录仍有证据的库存秘密，不补造历史发现。"""
    s = new_game([old["shopkeeper"]], old["seed"])
    for key in ("phase", "day", "shift_index", "coins", "reputation", "shop_level",
                "extra_capacity", "item_counter", "shift_count", "current_goal",
                "resting", "last_checkpoint", "diary", "weekly",
                "customer", "customer_count", "customer_book"):
        if key in old:
            s[key] = deepcopy(old[key])
    s["history"] = deepcopy(old["history"])
    for seq, row in enumerate(s["history"], 1):
        row["seq"] = seq
    s["inventory"], s["collection"] = [], {}
    for source in old["inventory"]:
        item = deepcopy(source)
        code = item["id"].rsplit("_", 1)[0]
        template = next(row for row in ITEMS if row[0] == code)
        item.update(code=code, rarity=ITEM_RARITY[code], origin="旧存档",
                    kind=ITEM_KINDS[code], _secret=template[5])
        item.setdefault("secret", None)
        _collect(s, item)
        if item["secret"]:
            s["collection"][code]["revealed"] = item["secret"]
    s["coins"] = old["coins"]  # 导入既有物品不会再领取首次奖励。
    for entry in old.get("door_history", []):
        _log(s, entry["day"], "旧版见闻", "migration", entry["text"],
             (s["coins"] - entry.get("coins_delta", 0),
              s["reputation"] - entry.get("reputation_delta", 0)),
             ambient="", reaction=None)
    if not s["customer"]:
        _spawn_customer(s)
    return s
