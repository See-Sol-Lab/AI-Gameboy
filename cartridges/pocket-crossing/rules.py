"""《口袋穿越》规则(Step 1:纯规则原型 + 假荷官)。

设计:docs/world-narrator-design.md(规则账本版)。
- 引擎维护唯一世界账本(进度/危险/生命/默契/时钟 + facts/flags/hooks);
- 每幕双方暗投 {意图, 自由行动描述, 物品?, 桌边留言?},引擎掷确定性骰裁决,
  形成不可修改的裁决单;Step 1 由内置假荷官(纯函数)把裁决单写成判词;
- 世界法则/隐藏线开局登记,只按结构化条件触发;
- HE / BE / TE 全部机器可判;双方同幕提交「end」意图 = 主动停笔进 TE。

Step 1 使用固定样例世界《遗忘之城》;Step 2 接真荷官时,样例数据被
gen_world/gen_identities/gen_scene 的校验产物替换,本模块机制不变。
与宿主的唯一结构约定:full_state["phase"]。
"""

import hashlib
from copy import deepcopy

ACTION_TEXT_MAX = 120
LINE_MAX = 60
INTENTS = ["advance", "explore", "support", "confront", "recover"]
INTENT_NAMES = {"advance": "推进", "explore": "探索", "support": "支援",
                "confront": "对抗", "recover": "休整", "end": "停笔"}

# ---------------- 样例世界(Step 1 固定;Step 2 由荷官生成) ----------------

WORLD = {
    "world_name": "遗忘之城",
    "premise": "你们在一座每天清晨都会忘掉一样东西的蒸汽城市里醒来。",
    "lore": ("雾都的锅炉从不熄火,可城市的记性一天比一天差:先是忘了一条巷子的名字,"
             "然后忘了河的走向。今晨,它忘掉了「明天」——日历停在今天,所有钟表拒绝走过午夜。"
             "遗忘局照常营业,声称一切都有存档;但存档塔的灯,昨夜亮了一整宿。"),
    "power_level": "低武",
    "public_goal": "在时钟走完之前,把被遗忘的「明天」找回来,放回城市的口袋。",
    "laws": [
        {"id": "law_listeners", "text": "大声与暴力会引来收忆人——对抗行动会喂浓雾(危险+1)。",
         "trigger_kind": "intent:confront", "cost_kind": "danger"},
        {"id": "law_nightfog", "text": "入夜后雾变浓——时钟走到 5 之后,每幕危险自动+1。",
         "trigger_kind": "clock>=5", "cost_kind": "danger"},
        {"id": "law_toll", "text": "在这座城里休息要交遗忘税——休整会被城市收走一段小记忆。",
         "trigger_kind": "intent:recover", "cost_kind": "flag"},
    ],
    "opening_facts": [
        "日历停在今天,午夜之后没有页码。",
        "遗忘局的存档塔彻夜亮灯。",
        "街上的钟表全部停在 23:59。",
    ],
    "hidden_threads": [
        {"id": "h-ledger", "required": {"flag": "found_the_ledger"},
         "effect_kind": "truth",
         "brief": "城市不是在遗忘——有人在一页一页撕掉它的账本。知道真相后,推进有方向了(此后推进骰+1)。"},
        {"id": "h-names", "required": {"synergy>=": 4},
         "effect_kind": "ending_modifier",
         "brief": "你们的名字被城市偷偷记进了新账本——它忘掉一切,也忘不掉你们(HE 变体)。"},
    ],
}

IDENTITIES = [
    {"id": "retriever", "name": "失物招领员", "origin": "在遗忘局地下室工作了九年,没丢过一件东西。",
     "specialty": "explore", "gift": {"kind": "explore_crit_item", "text": "探索骰达到 8 时,额外寻获一件物品"},
     "flaw": {"kind": "confront_minus_danger5", "text": "危险≥5 时对抗-1(她见过收忆人的脸)"},
     "secret_drive": {"kind": "shared_items>=3", "text": "让共享行囊攒满三件东西——东西齐了,人就不算丢"},
     "starting_item": {"id": "brass-lamp", "name": "黄铜检索灯", "use": ["explore"]}},
    {"id": "nightwatch", "name": "守夜人", "origin": "他守的那条街,是城里最后一条记得自己名字的街。",
     "specialty": "support", "gift": {"kind": "support_synergy", "text": "支援成功时,默契额外+1"},
     "flaw": {"kind": "advance_minus", "text": "推进-1(他习惯留在原地守着)"},
     "secret_drive": {"kind": "partner_full_vitality", "text": "把同伴完好无损地带到结局"},
     "starting_item": {"id": "tin-flask", "name": "铁皮暖壶", "use": ["recover", "support"]}},
    {"id": "courier", "name": "信使", "origin": "全城只有她还记得每一条巷子忘掉前的名字。",
     "specialty": "advance", "gift": {"kind": "advance_crit_clock", "text": "推进骰达到 8 时,本幕时钟不前进"},
     "flaw": {"kind": "explore_minus", "text": "探索-1(赶路的人不回头看)"},
     "secret_drive": {"kind": "clock<=6", "text": "在时钟走到 7 之前送达结局——迟到的信等于没送"},
     "starting_item": {"id": "folded-map", "name": "折叠地图", "use": ["advance", "explore"]}},
    {"id": "locksmith", "name": "拆锁匠", "origin": "收忆人认识他,他给收忆人修过锁。",
     "specialty": "confront", "gift": {"kind": "confront_no_law", "text": "他的对抗不触发收忆人法则"},
     "flaw": {"kind": "support_minus", "text": "支援-1(独来独往惯了)"},
     "secret_drive": {"kind": "hooks_resolved>=2", "text": "亲手了结至少两桩没人管的悬事"},
     "starting_item": {"id": "master-hook", "name": "万能钩", "use": ["confront"]}},
    {"id": "medic", "name": "雾行医士", "origin": "药箱里有一格上了锁,她说那格装的是自己的事。",
     "specialty": "recover", "gift": {"kind": "recover_heals_both", "text": "休整成功时,两人都恢复生命"},
     "flaw": {"kind": "confront_minus", "text": "对抗-1(发过不伤人的誓)"},
     "secret_drive": {"kind": "both_alive", "text": "两个人都活着看到结局,一个都不能少"},
     "starting_item": {"id": "med-kit", "name": "随行药箱", "use": ["recover"]}},
    {"id": "gambler", "name": "赌徒", "origin": "他跟这座城打赌:你忘什么都行,别忘了欠我的。",
     "specialty": "advance", "gift": {"kind": "ones_are_fours", "text": "骰出 1 时按 4 计"},
     "flaw": {"kind": "six_feeds_danger", "text": "骰出 6 时危险+1(他赢得太大声)"},
     "secret_drive": {"kind": "hidden_triggered", "text": "亲眼见到这座城藏起来的那条暗线"},
     "starting_item": {"id": "loaded-dice", "name": "灌铅骰子", "use": ["advance", "confront"]}},
]

SCENES = [
    {"title": "雾站台", "text": "末班车到站,却没有人下车。站牌上的地名正在一个字一个字变淡。",
     "crisis": "在站名彻底消失前,弄清你们身处何处、该往哪去。",
     "objects": [{"id": "sign", "name": "褪色的站牌", "hint": "还剩最后两个字"},
                 {"id": "locker", "name": "寄存柜", "hint": "有一格没锁,里面有热气"},
                 {"id": "conductor", "name": "打盹的站务员", "hint": "帽檐下露出一截白发"}],
     "questions": ["末班车为什么空着进站?"]},
    {"title": "遗忘局大厅", "text": "取号机吐出的号码全是「0」。柜台后的职员对每个来客说:您预约的是昨天。",
     "crisis": "从只认「昨天」的窗口里,问出「明天」的下落。",
     "objects": [{"id": "queue", "name": "取号机", "hint": "吐出的纸条背面有字"},
                 {"id": "clerk-window", "name": "三号窗口", "hint": "职员的袖口沾着墨"},
                 {"id": "archive-door", "name": "存档塔小门", "hint": "门缝里漏出灯光"}],
     "questions": ["存档塔的灯为什么亮了一整夜?"]},
    {"title": "失物长廊", "text": "货架一眼望不到头,摆满这座城忘掉的东西:一条河的声音、一场没下完的雪。",
     "crisis": "在成千上万件失物里,找到「明天」被登记在哪一排。",
     "objects": [{"id": "ledger-desk", "name": "登记台", "hint": "台账摊开着,最后一页被撕掉了"},
                 {"id": "shelf-9", "name": "第九排货架", "hint": "标签写着「时间类」"},
                 {"id": "echo-jar", "name": "装着河声的罐子", "hint": "贴着借条"}],
     "questions": ["台账最后一页被谁撕走了?"]},
    {"title": "雾巷", "text": "巷子在雾里改变走向。身后传来收忆人的铃铛声,不紧不慢,像在清点什么。",
     "crisis": "甩开清点者,或者弄清它到底在清点什么。",
     "objects": [{"id": "bell-sound", "name": "铃铛声", "hint": "每响一下,雾就沉一分"},
                 {"id": "chalk-marks", "name": "墙上的粉笔记号", "hint": "有人在雾里留过路标"},
                 {"id": "side-door", "name": "半开的侧门", "hint": "门后是干燥的空气"}],
     "questions": ["收忆人清点的清单上有没有你们?"]},
    {"title": "档案塔", "text": "塔内没有楼梯,只有不断上升的纸页,像一场向上下的雪。每一页都写着城市的一天。",
     "crisis": "在纸雪里找到写着「明天」的那一页——或它被撕剩的边角。",
     "objects": [{"id": "paper-snow", "name": "上升的纸页", "hint": "有几页边缘整齐,是被裁掉的"},
                 {"id": "tower-keeper", "name": "塔顶的影子", "hint": "它翻页的手很稳"},
                 {"id": "torn-edge", "name": "撕痕", "hint": "新鲜的,墨迹未干"}],
     "questions": ["塔顶翻页的是谁?"]},
    {"title": "地下运河", "text": "被城市忘掉的河在地下继续流。船夫收的船费不是钱——是一件你记得而城市忘了的事。",
     "crisis": "付得起船费,渡过这条不该存在的河。",
     "objects": [{"id": "ferryman", "name": "船夫", "hint": "他的斗篷下没有脚"},
                 {"id": "toll-box", "name": "船费匣", "hint": "里面全是些微弱发光的碎片"},
                 {"id": "far-bank", "name": "对岸", "hint": "有钟声,走着的钟"}],
     "questions": ["对岸为什么有还在走的钟?"]},
    {"title": "钟楼", "text": "全城唯一还在走的钟在这里,但它在倒着走。钟摆每摆一下,城市就年轻一秒,也空一分。",
     "crisis": "让钟重新向前——或者弄清是谁把它拨反的。",
     "objects": [{"id": "pendulum", "name": "倒摆的钟摆", "hint": "摆锤上刻着局徽"},
                 {"id": "winding-key", "name": "上弦匙", "hint": "挂在够不着的横梁上"},
                 {"id": "keeper-desk", "name": "守钟人的桌子", "hint": "抽屉里有一页台账"}],
     "questions": ["把钟拨反,是为了留住什么?"]},
    {"title": "明日之门", "text": "档案塔顶端,一扇用日历纸糊成的门。门后透出一种谁都没见过、却谁都认识的光。",
     "crisis": "把「明天」放回城市的口袋——用你们一路带来的一切。",
     "objects": [{"id": "calendar-door", "name": "日历纸门", "hint": "糊门的纸页全是同一天"},
                 {"id": "tomorrow-light", "name": "门后的光", "hint": "暖的,像刚烤好的面包"},
                 {"id": "last-page", "name": "门楣上的空白页", "hint": "在等一行字"}],
     "questions": ["谁来写下最后一行?"]},
]


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


# ---------------- 建局 ----------------

def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("这张卡只支持两名玩家")
    order = _shuffled_ids(seed)
    return {
        "phase": "playing",
        "stage": "identity",           # identity -> scene
        "seed": seed,
        "seats": list(seats),
        "scene_index": 0,              # 1 起算;identity 阶段为 0
        "clock": 0, "progress": 0, "danger": 0, "synergy": 0,
        "vitality": {seats[0]: 3, seats[1]: 3},
        "identity_offers": {seats[0]: order[:2], seats[1]: order[2:4]},
        "identities": {seats[0]: None, seats[1]: None},
        "inventory": {seats[0]: [], seats[1]: [], "shared": []},
        "facts": list(WORLD["opening_facts"]),
        "flags": [],
        "hooks": [],
        "hooks_resolved": 0,
        "hidden_fired": [],
        "pending": {},
        "history": [],
        "ending": None,
        "rolls_used": 0,
        "end_proposed_by": None,
    }


def _shuffled_ids(seed):
    ids = [i["id"] for i in IDENTITIES]
    order = sorted(ids, key=lambda x: hashlib.sha256(
        f"{seed}:{x}".encode()).hexdigest())
    return order


def _die(state):
    """确定性骰:同一局面同一顺位必然同点,事后可验证引擎没作弊。"""
    h = hashlib.sha256(f"{state['seed']}:d{state['rolls_used']}".encode())
    state["rolls_used"] += 1
    return int(h.hexdigest(), 16) % 6 + 1


def _identity(iid):
    return next(i for i in IDENTITIES if i["id"] == iid)


# ---------------- 观察 ----------------

def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    other = [x for x in s["seats"] if x != seat_id][0]
    idents_public = {}
    for x in s["seats"]:
        if s["identities"][x]:
            it = _identity(s["identities"][x])
            idents_public[x] = {"name": it["name"], "origin": it["origin"],
                                "specialty": INTENT_NAMES[it["specialty"]],
                                "gift": it["gift"]["text"],
                                "flaw": it["flaw"]["text"]}
        else:
            idents_public[x] = None
    scene = SCENES[s["scene_index"] - 1] if s["stage"] == "scene" else None
    public = {
        "phase": s["phase"], "stage": s["stage"],
        "world": {k: WORLD[k] for k in
                  ("world_name", "premise", "lore", "power_level", "public_goal")},
        "laws": [l["text"] for l in WORLD["laws"]],
        "tracks": {"progress": s["progress"], "danger": s["danger"],
                   "synergy": s["synergy"], "clock": s["clock"],
                   "vitality": dict(s["vitality"])},
        "scene_index": s["scene_index"], "scene": deepcopy(scene),
        "identities": idents_public,
        "inventory": deepcopy(s["inventory"]),
        "facts": list(s["facts"]),
        "hooks": list(s["hooks"]),
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "end_proposed_by": s["end_proposed_by"],
        "history": [{"scene_index": h["scene_index"], "title": h["title"],
                     "report": h["report"]} for h in s["history"]],
        "ending": deepcopy(s["ending"]),
    }
    my_ident = s["identities"][seat_id]
    private = {
        "identity_offers": ([deepcopy(_identity(i)) for i in
                             s["identity_offers"][seat_id]]
                            if s["stage"] == "identity" and not my_ident else None),
        "secret_drive": (_identity(my_ident)["secret_drive"]["text"]
                         if my_ident else None),
        "my_pending": deepcopy(s["pending"].get(seat_id)),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        if s["stage"] == "identity":
            waiting = [x for x in s["seats"] if not s["identities"][x]]
            if seat_id in waiting:
                legal = [{"action_id": "choose_identity",
                          "params": {"identity_id":
                                     f"暗选其一:{s['identity_offers'][seat_id]}"}}]
        else:
            waiting = [x for x in s["seats"] if x not in s["pending"]]
            if seat_id in waiting:
                my_items = [i["id"] for i in s["inventory"][seat_id]] + \
                           [i["id"] for i in s["inventory"]["shared"]]
                legal = [{"action_id": "commit", "params": {
                    "intent": f"必填:{INTENTS} 之一;或 'end'=提议就此停笔(双方同幕都选才生效)",
                    "action": f"必填:这一步你具体怎么做(≤{ACTION_TEXT_MAX}字,自由描述)",
                    "item_id": f"可选:动用一件物品,标签匹配意图时骰+1,可用:{my_items}",
                    "line": f"可选:一句桌边留言(≤{LINE_MAX}字,给同伴看的,不参与判定)",
                }}]
    return {"public_state": public, "private_state": private,
            "legal_actions": legal, "waiting_for": waiting}


# ---------------- 动作 ----------------

def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    params = params if isinstance(params, dict) else {}
    if action_id == "choose_identity":
        _apply_identity(s, seat_id, params)
    elif action_id == "commit":
        _apply_commit(s, seat_id, params)
    else:
        raise IllegalAction(f"没有这个动作:{action_id}")
    return s


def _apply_identity(s, seat_id, params):
    if s["stage"] != "identity":
        raise IllegalAction("身份已定,现在该行动了")
    if s["identities"][seat_id]:
        raise IllegalAction("你已经选过身份了")
    iid = params.get("identity_id")
    if iid not in s["identity_offers"][seat_id]:
        raise IllegalAction(f"只能从你抽到的两张里选:{s['identity_offers'][seat_id]}")
    s["identities"][seat_id] = iid
    item = deepcopy(_identity(iid)["starting_item"])
    s["inventory"][seat_id].append(item)
    if all(s["identities"].values()):
        s["stage"] = "scene"
        s["scene_index"] = 1
        names = {x: _identity(s["identities"][x])["name"] for x in s["seats"]}
        s["facts"].append(f"{names[s['seats'][0]]}与{names[s['seats'][1]]}在雾站台上认出了彼此的行囊。")


def _apply_commit(s, seat_id, params):
    if s["stage"] != "scene":
        raise IllegalAction("先选身份")
    if seat_id in s["pending"]:
        raise IllegalAction("这一幕你已经提交过了")
    intent = params.get("intent")
    if intent != "end" and intent not in INTENTS:
        raise IllegalAction(f"intent 须是 {INTENTS} 之一或 'end'")
    action = params.get("action", "")
    if intent != "end":
        if not isinstance(action, str) or not action.strip():
            raise IllegalAction("action 必填:说清你具体怎么做")
        if len(action.strip()) > ACTION_TEXT_MAX:
            raise IllegalAction(f"action 过长:≤{ACTION_TEXT_MAX} 字")
    item_id = params.get("item_id")
    if item_id is not None:
        mine = [i["id"] for i in s["inventory"][seat_id]] + \
               [i["id"] for i in s["inventory"]["shared"]]
        if item_id not in mine:
            raise IllegalAction(f"这件东西不在你能拿到的行囊里:{mine}")
    line = params.get("line", "")
    if not isinstance(line, str) or len(line.strip()) > LINE_MAX:
        raise IllegalAction(f"line 须是字符串且 ≤{LINE_MAX} 字")
    s["pending"][seat_id] = {"intent": intent,
                             "action": (action or "").strip(),
                             "item_id": item_id, "line": line.strip()}
    if len(s["pending"]) == 2:
        _resolve(s)


# ---------------- 裁决(引擎掷骰 → 裁决单 → 假荷官判词) ----------------

def _modifiers(s, seat_id, intent, item_id, other_intent):
    ident = _identity(s["identities"][seat_id])
    mods, notes = 0, []
    if ident["specialty"] == intent:
        mods += 1
        notes.append("身份擅长+1")
    if item_id:
        item = next((i for i in s["inventory"][seat_id] + s["inventory"]["shared"]
                     if i["id"] == item_id), None)
        if item and intent in item.get("use", []):
            mods += 1
            notes.append(f"{item['name']}+1")
        elif item:
            notes.append(f"{item['name']}帮不上这种忙")
    if other_intent == "support":
        mods += 1
        notes.append("同伴支援+1")
    fk = ident["flaw"]["kind"]
    if (fk == "advance_minus" and intent == "advance") or \
       (fk == "explore_minus" and intent == "explore") or \
       (fk == "support_minus" and intent == "support") or \
       (fk == "confront_minus" and intent == "confront"):
        mods -= 1
        notes.append("身份弱点-1")
    if fk == "confront_minus_danger5" and intent == "confront" and s["danger"] >= 5:
        mods -= 1
        notes.append("身份弱点-1")
    if s["danger"] >= 7:
        mods -= 1
        notes.append("高危环境-1")
    if "truth_known" in s["flags"] and intent == "advance":
        mods += 1
        notes.append("真相在手+1")
    return mods, notes


def _tier(total):
    if total <= 3:
        return "failure"
    if total <= 5:
        return "mixed_success"
    if total <= 7:
        return "success"
    return "critical_success"


TIER_NAMES = {"failure": "失败", "mixed_success": "勉强成功",
              "success": "成功", "critical_success": "卓越成功"}


def _resolve(s):
    a, b = s["seats"]
    pa, pb = s["pending"][a], s["pending"][b]
    scene = SCENES[s["scene_index"] - 1]
    report = [f"—— 第 {s['scene_index']} 幕 · {scene['title']} ——"]

    # 主动停笔
    if pa["intent"] == "end" and pb["intent"] == "end":
        report.append("两人对视一眼,把故事合上了。")
        _log(s, scene, {a: pa, b: pb}, {}, report)
        _finish(s, "TE", "mutual_end")
        return
    for seat, p in ((a, pa), (b, pb)):
        if p["intent"] == "end":
            s["end_proposed_by"] = seat
            p["intent"] = "recover"
            p["_proposed_end"] = True
            report.append(f"{seat} 提议就此停笔——另一人还想再走一程。")

    slip = {"outcome": {}, "progress_delta": 0, "danger_delta": 0,
            "clock_delta": 1, "synergy_delta": 0,
            "vitality_delta": {a: 0, b: 0}, "facts_added": [],
            "flags_added": [], "hooks_added": [], "hooks_resolved": 0,
            "items_gained": []}

    tiers = {}
    for seat, p, other_p in ((a, pa, pb), (b, pb, pa)):
        ident = _identity(s["identities"][seat])
        die = _die(s)
        if ident["gift"]["kind"] == "ones_are_fours" and die == 1:
            die = 4
        if ident["flaw"]["kind"] == "six_feeds_danger" and die == 6:
            slip["danger_delta"] += 1
        mods, notes = _modifiers(s, seat, p["intent"], p["item_id"], other_p["intent"])
        total = die + mods
        tier = _tier(total)
        tiers[seat] = tier
        slip["outcome"][seat] = tier
        name = ident["name"]
        report.append(f"{name}【{INTENT_NAMES[p['intent']]}】:{p['action'] or '(静静停下)'}")
        report.append(f"  骰{die}{'+' if mods >= 0 else ''}{mods}={total}"
                      f"({'、'.join(notes) if notes else '无修正'}) → {TIER_NAMES[tier]}")
        if p["line"]:
            report.append(f"  {name}留言:「{p['line']}」")
        # 分意图结算
        it = p["intent"]
        if tier == "failure":
            slip["danger_delta"] += 1
            if it == "confront":
                slip["vitality_delta"][seat] -= 1
                report.append(f"  代价:{name}挂了彩(生命-1),雾更浓了")
            else:
                report.append("  代价:雾更浓了(危险+1)")
        elif tier == "mixed_success":
            if it == "advance":
                slip["progress_delta"] += 1
            elif it == "explore":
                slip["progress_delta"] += 1
            if scene["questions"]:
                hook = scene["questions"][0]
                if hook not in s["hooks"]:
                    slip["hooks_added"].append(hook)
                    report.append(f"  但留下悬事:{hook}")
        elif tier in ("success", "critical_success"):
            if it == "advance":
                slip["progress_delta"] += 2 if tier == "success" else 3
            elif it == "explore":
                slip["progress_delta"] += 1
                if tier == "critical_success":
                    if "found_the_ledger" not in s["flags"] and \
                            "found_the_ledger" not in slip["flags_added"]:
                        slip["flags_added"].append("found_the_ledger")
                        report.append("  在最不可能的地方,翻到了那本被撕的台账")
                    if ident["gift"]["kind"] == "explore_crit_item":
                        item = {"id": f"found-{s['rolls_used']}",
                                "name": "无人认领的怀表", "use": ["advance"]}
                        slip["items_gained"].append((seat, item))
                        report.append(f"  {name}顺手寻获:{item['name']}")
            elif it == "confront":
                slip["progress_delta"] += 1
                slip["danger_delta"] -= 1
                report.append("  挡路的东西退了半步(危险-1)")
            elif it == "recover":
                heal = [seat]
                if ident["gift"]["kind"] == "recover_heals_both":
                    heal = [a, b]
                    report.append("  医士的手很稳:两人都缓了过来")
                for h in heal:
                    slip["vitality_delta"][h] += 1
            if tier == "critical_success":
                if s["hooks"]:
                    slip["hooks_resolved"] += 1
                    resolved = s["hooks"][0]
                    report.append(f"  顺手了结了悬事:{resolved}")
                if it == "advance" and ident["gift"]["kind"] == "advance_crit_clock":
                    slip["clock_delta"] = 0
                    report.append("  信使抄了近路:这一幕没有花掉时钟")

    # 协作与法则
    ia, ib = pa["intent"], pb["intent"]
    both_ok = all(t in ("success", "critical_success", "mixed_success")
                  for t in tiers.values())
    if both_ok and (("support" in (ia, ib)) or
                    {"advance", "explore"} == {ia, ib} or ia == ib == "advance"):
        slip["synergy_delta"] += 1
    if "support" in (ia, ib):
        for seat, p in ((a, pa), (b, pb)):
            if p["intent"] == "support" and tiers[seat] in ("success", "critical_success"):
                if _identity(s["identities"][seat])["gift"]["kind"] == "support_synergy":
                    slip["synergy_delta"] += 1
    for law in WORLD["laws"]:
        tk = law["trigger_kind"]
        if tk.startswith("intent:"):
            want = tk.split(":")[1]
            for seat, p in ((a, pa), (b, pb)):
                if p["intent"] != want:
                    continue
                if want == "confront" and _identity(
                        s["identities"][seat])["gift"]["kind"] == "confront_no_law":
                    report.append("  收忆人认出了拆锁匠,铃铛没有响")
                    continue
                if law["cost_kind"] == "danger":
                    slip["danger_delta"] += 1
                    report.append(f"  法则应验:{law['text']}")
                elif law["cost_kind"] == "flag":
                    tag = f"memory_paid_{s['scene_index']}"
                    slip["flags_added"].append(tag)
                    slip["facts_added"].append("城市收走了一段小小的记忆作为税。")
                    report.append("  法则应验:遗忘税已缴")
        elif tk == "clock>=5" and s["clock"] >= 5:
            slip["danger_delta"] += 1
            report.append("  法则应验:夜雾渐浓(危险+1)")

    # 记账
    s["progress"] = max(0, min(10, s["progress"] + slip["progress_delta"]))
    s["danger"] = max(0, min(10, s["danger"] + slip["danger_delta"]))
    s["synergy"] = max(0, min(5, s["synergy"] + slip["synergy_delta"]))
    s["clock"] = min(8, s["clock"] + slip["clock_delta"])
    for seat in (a, b):
        s["vitality"][seat] = max(0, min(3, s["vitality"][seat]
                                          + slip["vitality_delta"][seat]))
    for f in slip["flags_added"]:
        if f not in s["flags"]:
            s["flags"].append(f)
    s["facts"].extend(slip["facts_added"])
    s["hooks"].extend(slip["hooks_added"])
    for _ in range(slip["hooks_resolved"]):
        if s["hooks"]:
            s["hooks"].pop(0)
            s["hooks_resolved"] += 1
    for seat, item in slip["items_gained"]:
        s["inventory"][seat].append(item)

    # 隐藏线
    for th in WORLD["hidden_threads"]:
        if th["id"] in s["hidden_fired"]:
            continue
        req = th["required"]
        hit = ("flag" in req and req["flag"] in s["flags"]) or \
              ("synergy>=" in req and s["synergy"] >= req["synergy>="])
        if hit:
            s["hidden_fired"].append(th["id"])
            s["facts"].append(th["brief"])
            report.append(f"◆ 暗线浮出:{th['brief']}")
            if th["id"] == "h-ledger":
                s["flags"].append("truth_known")

    report.append(f"账本:进度{s['progress']}/10 危险{s['danger']}/10 "
                  f"默契{s['synergy']}/5 时钟{s['clock']}/8 "
                  f"生命 {s['vitality'][a]}/{s['vitality'][b]}")
    _log(s, scene, {a: pa, b: pb}, slip, report)

    # 结局判定(§11)
    alive = [x for x in s["seats"] if s["vitality"][x] > 0]
    if len(alive) == 0:
        _finish(s, "BE", "all_down")
    elif s["danger"] >= 10 and s["progress"] < 10:
        _finish(s, "BE", "world_lost")
    elif s["progress"] >= 10 and len(alive) == 2:
        _finish(s, "HE", "goal")
    elif s["progress"] >= 10:
        _finish(s, "TE", "sacrifice")
    elif s["clock"] >= 8:
        _finish(s, "TE", "out_of_time")
    else:
        s["scene_index"] = min(s["scene_index"] + 1, len(SCENES))


def _log(s, scene, commits, slip, report):
    s["history"].append({
        "scene_index": s["scene_index"], "title": scene["title"],
        "commits": deepcopy(commits), "slip": deepcopy(slip),
        "report": report,
    })
    s["pending"] = {}


# ---------------- 结局(Step 1:假荷官成文) ----------------

ENDINGS = {
    ("HE", "goal"): "你们把「明天」放回了城市的口袋。午夜过后,日历轻轻翻了一页——全城的钟表同时迈出停了很久的那一步。",
    ("BE", "all_down"): "雾合拢的地方,铃铛声停了。收忆人的清单上多了两个名字,而城市明天醒来,不会记得少了谁。",
    ("BE", "world_lost"): "雾没过了钟楼的尖顶。城市忘掉了最后一样东西——它自己。",
    ("TE", "sacrifice"): "「明天」回到了城市的口袋,但渡口只回来了一个人。走着的钟每到午夜,都会为另一个名字停摆一秒。",
    ("TE", "out_of_time"): "时钟走完了。城市保住了今天,却没能等到明天——不过失物长廊的台账上,你们的搜寻被登记在册:悬案,未结。",
    ("TE", "mutual_end"): "故事停在这里。往后的雾里,偶尔会有人说见过两个旅人的背影——他们走得不急,像还会回来。",
}


def _finish(s, kind, reason):
    s["phase"] = "finished"
    text = ENDINGS[(kind, reason)]
    if kind == "HE" and "h-names" in s["hidden_fired"]:
        text += " 而在新账本的第一页,城市偷偷写下了两个名字——它可以忘掉一切,但忘不掉你们。"
    drives = {}
    for seat in s["seats"]:
        ident = _identity(s["identities"][seat]) if s["identities"][seat] else None
        if not ident:
            continue
        d = ident["secret_drive"]
        ok = False
        if d["kind"] == "shared_items>=3":
            ok = len(s["inventory"]["shared"]) >= 3
        elif d["kind"] == "partner_full_vitality":
            other = [x for x in s["seats"] if x != seat][0]
            ok = s["vitality"][other] >= 3
        elif d["kind"] == "clock<=6":
            ok = s["clock"] <= 6
        elif d["kind"] == "hooks_resolved>=2":
            ok = s["hooks_resolved"] >= 2
        elif d["kind"] == "both_alive":
            ok = all(s["vitality"][x] > 0 for x in s["seats"])
        elif d["kind"] == "hidden_triggered":
            ok = bool(s["hidden_fired"])
        drives[seat] = {"text": d["text"], "achieved": ok,
                        "identity": ident["name"]}
    s["ending"] = {"kind": kind, "reason": reason, "text": text,
                   "secret_drives": drives,
                   "world_name": WORLD["world_name"], "seed": s["seed"]}
