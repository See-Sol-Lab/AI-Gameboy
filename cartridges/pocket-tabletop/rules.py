"""《口袋跑团》规则 v1.0(成熟定型的危机跑团卡)。

前身是《口袋穿越》v0.1–v0.2:随机世界皮肤 + 倒计时危机 + 双人跑团。
玩了九局,骨架已被验证好玩,项目作者拍板将其定格为独立成品卡——
此后《口袋穿越》走"掉进一部已存在的小说"的新路,这张卡则专供纯粹的
"世界出事了,两个人去解决"的经典跑团体验。

包含支线暗典版的全部修缮(源自 早期测试测试局验尸报告):
- 支线暗典:worldgen 时预写 2 条支线悬案(谜题+定死的谜底),谜底玩家不可见;
  一条绑剧情 NPC(在 1..10 幕中随机两个登场窗口,可错过、可翻盘),
  一条绑数值考验(默契/探索胜场/对抗胜场达标即自动揭示)。
- 悬事生命周期:hooks 由引擎全权管理 = 未解支线的谜题原句;荷官不得增殖同义悬事。
- 主线锁定即冻结:main_goal_locked 后进度与时钟不再变动(法则失效)。
- 提议停笔不再折算成休整:单方 end = 静候,不掷骰、不触发法则。
- 幕数走满由引擎强制结算,不再依赖双方同意。

与 v0.1 的机制完全相同(账本/骰子/法则/隐藏线/三类结局),区别只有一个:
世界、身份池、每一幕场景、结局文本改由叙事荷官(外部 API)按合同生成,
经宿主校验后以 apply_system() 写回。卡带仍是纯函数,永远碰不到网络与 key。

阶段机:worldgen → identities_gen → identity(玩家暗选)
        → scenegen → scene(玩家暗投) → …… → endinggen → finished
narration_request 挂在状态里;宿主在事务外调荷官,回填 narration_result。
荷官不可用时停在原地,人类一键重召(蓝图 §14.3)。

天赋/弱点/私密目标采用**菜单制**:荷官只能从引擎支持的机制代码里选,
自由发挥的只有血肉文案——数值预算天然一致,DS 写不出超模身份。
与宿主的唯一结构约定:full_state["phase"]。
"""

import hashlib
from copy import deepcopy

ACTION_TEXT_MAX = 120
LINE_MAX = 60
MAX_SCENES = 10
INTENTS = ["advance", "explore", "support", "confront", "recover"]
INTENT_NAMES = {"advance": "推进", "explore": "探索", "support": "支援",
                "confront": "对抗", "recover": "休整", "end": "停笔",
                "wait": "静候"}

# 经典危机跑团词库(《口袋穿越》v0.1 原池,权重均一):
# 这张卡的味道就是"世界出事了 → 倒计时 → 两个人去解决",词库刻意保持紧凑。
POOLS = {
    "form": [(x, 1) for x in
             ["现代都市", "架空古代", "未来都市", "末世废土", "深海文明", "蒸汽时代",
              "魔法大陆", "东方玄幻", "修仙世界", "梦境世界", "封闭空间", "时间夹层"]],
    "power": [(x, 1) for x in ["无超凡", "低武", "中武", "高武", "神话级"]],
    "kind": [(x, 1) for x in
             ["求生", "逃离", "护送", "寻物", "调查", "夺回", "守城", "潜入",
              "远征", "营救", "谈判"]],
    "mood": [(x, 1) for x in
             ["温暖", "轻快", "诡谲", "压抑", "壮烈", "荒诞", "史诗", "孤独", "黑色幽默"]],
    "variable": [(x, 1) for x in
                 ["时间不多了", "身份存疑", "资源枯竭", "世界正在遗忘",
                  "敌人会学习你们", "两人记忆不一致", "道路无法回头", "死亡会改变规则"]],
}

# 菜单制:荷官只能从这里选机制代码
GIFT_KINDS = {
    "explore_crit_item": "探索骰达到8时额外寻获一件物品",
    "support_synergy": "支援成功时默契额外+1",
    "advance_crit_clock": "推进骰达到8时本幕时钟不前进",
    "confront_no_law": "他的对抗不触发『对抗类』世界法则",
    "recover_heals_both": "休整成功时两人都恢复生命",
    "ones_are_fours": "骰出1时按4计",
}
FLAW_KINDS = {
    "advance_minus": "推进-1", "explore_minus": "探索-1",
    "support_minus": "支援-1", "confront_minus": "对抗-1",
    "confront_minus_danger5": "危险≥5时对抗-1", "six_feeds_danger": "骰出6时危险+1",
}
DRIVE_KINDS = {
    "shared_items>=3": "结局时共享行囊≥3件",
    "partner_full_vitality": "结局时同伴生命满格",
    "clock<=6": "结局时时钟≤6",
    "hooks_resolved>=2": "全局了结悬事≥2件",
    "both_alive": "结局时两人都活着",
    "hidden_triggered": "任一暗线被触发",
}


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


# ---------------- 建局与种子 ----------------

def _pick(seed, salt, pool):
    """加权抽签:pool 是 (词, 权重) 列表,seed 定死,可复现。"""
    total = sum(w for _, w in pool)
    h = int(hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest(), 16) % total
    for v, w in pool:
        h -= w
        if h < 0:
            return v
    return pool[-1][0]


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("这张卡只支持两名玩家")
    axes = {k: _pick(seed, k, POOLS[k]) for k in POOLS}
    return {
        "phase": "playing",
        "stage": "worldgen",
        "seed": seed,
        "axes": axes,
        "seats": list(seats),
        "world": None,
        "identity_pool": None,
        "identity_offers": {},
        "identities": {seats[0]: None, seats[1]: None},
        "scene_index": 0,
        "current_scene": None,
        "clock": 0, "progress": 0, "danger": 0, "synergy": 0,
        "main_goal_locked": False, "goal_locked_at_scene": None,
        "vitality": {seats[0]: 3, seats[1]: 3},
        "inventory": {seats[0]: [], seats[1]: [], "shared": []},
        "facts": [], "flags": [], "hooks": [],
        "hooks_resolved": 0, "hidden_fired": [],
        "side_quests": [],
        "wins": {"advance": 0, "explore": 0, "support": 0,
                 "confront": 0, "recover": 0},
        "pending": {}, "history": [],
        "prophecies": {seats[0]: [], seats[1]: []},   # 先知情报:私密撕页
        "prophecy_i": 0,
        "ending": None, "rolls_used": 0, "end_proposed_by": None,
        "end_streaks": {seats[0]: 0, seats[1]: 0},   # 连续三幕提停笔=强制结算
        "narration_request": {"kind": "gen_world", "context": {"axes": axes}},
    }


def _die(state):
    h = hashlib.sha256(f"{state['seed']}:d{state['rolls_used']}".encode())
    state["rolls_used"] += 1
    return int(h.hexdigest(), 16) % 6 + 1


def _identity(s, iid):
    return next(i for i in s["identity_pool"] if i["id"] == iid)


# ---------------- 支线暗典 ----------------

def _npc_windows(seed):
    """NPC 的两个登场窗口:1..MAX_SCENES 里随机两幕,seed 定死,可复现。"""
    w1 = int(hashlib.sha256(f"{seed}:npcw1".encode()).hexdigest(), 16) % MAX_SCENES + 1
    w2 = int(hashlib.sha256(f"{seed}:npcw2".encode()).hexdigest(), 16) % MAX_SCENES + 1
    if w2 == w1:
        w2 = w2 % MAX_SCENES + 1
    return sorted([w1, w2])


def _npc_due(s, scene_no):
    """本幕是否有剧情 NPC 登场(支线未解且撞上窗口)。"""
    for q in s.get("side_quests") or []:
        if q["unlock_kind"] == "npc" and q["status"] == "open" \
                and scene_no in q.get("windows", []):
            return q
    return None


def _quest_resolve(s, q, report, how):
    """支线了结:谜底从暗典掏出,写成既成事实,悬事划掉。"""
    q["status"] = "resolved"
    q["resolved_at"] = s["scene_index"]
    s["hooks_resolved"] += 1
    s["facts"].append(f"真相大白:{q['truth']}")
    if q["question"] in s["hooks"]:
        s["hooks"].remove(q["question"])
    report.append(f"◆ 悬事了结({how}):{q['question']}")
    report.append(f"  真相:{q['truth']}")


# ---------------- 荷官回填(宿主专用入口,玩家动作到不了这里) ----------------

def apply_system(full_state, action_id, payload):
    s = deepcopy(full_state)
    if action_id != "narration_result":
        raise IllegalAction("未知系统动作")
    req = s.get("narration_request")
    if not req or payload.get("kind") != req["kind"]:
        raise IllegalAction("没有与之匹配的荷官请求")
    data = payload["data"]
    kind = req["kind"]
    if kind == "gen_world":
        data = dict(data)
        data["power_level"] = s["axes"]["power"]   # 常量由引擎注入,不劳荷官复读
        s["world"] = data
        s["milestones_done"] = []
        s["facts"] = list(data["opening_facts"])
        # 支线暗典入库:谜底与登场窗口只有引擎知道,悬事 = 谜题原句
        quests = []
        for q in data.get("side_quests", []):
            q = dict(q)
            q["status"] = "open"
            if q["unlock_kind"] == "npc":
                q["windows"] = _npc_windows(s["seed"])
            quests.append(q)
        s["side_quests"] = quests
        s["hooks"] = [q["question"] for q in quests]
        s["narration_request"] = {"kind": "gen_identities",
                                  "context": {"world": _world_brief(s)}}
        s["stage"] = "identities_gen"
    elif kind == "gen_identities":
        s["identity_pool"] = data
        order = sorted([i["id"] for i in data], key=lambda x: hashlib.sha256(
            f"{s['seed']}:{x}".encode()).hexdigest())
        s["identity_offers"] = {s["seats"][0]: order[:2],
                                s["seats"][1]: order[2:4]}
        s["narration_request"] = None
        s["stage"] = "identity"
    elif kind == "gen_scene":
        s["current_scene"] = data
        s["scene_index"] += 1
        s["narration_request"] = None
        s["stage"] = "scene"
    elif kind == "render_ending":
        s["ending"]["text"] = data["text"]
        s["narration_request"] = None
        s["phase"] = "finished"
        s["stage"] = "finished"
    return s


COST_GLOSS = {"danger": "危险+1", "progress": "进度-1",
              "clock": "时钟+1", "flag": "留下印记", "vitality": "生命受创"}


def _law_gloss(law):
    tk = law["trigger_kind"]
    if tk.startswith("intent:"):
        when = f"有人【{INTENT_NAMES.get(tk[7:], tk[7:])}】时"
    elif tk.startswith("clock>="):
        when = f"时钟≥{tk[7:]}后每幕"
    elif tk.startswith("danger>="):
        when = f"危险≥{tk[8:]}后每幕"
    else:
        when = tk
    return f"{law['text']}(判定:{when} {COST_GLOSS.get(law['cost_kind'], '')})"


def _world_brief(s):
    w = s["world"]
    return {"world_name": w["world_name"], "premise": w["premise"],
            "lore": w["lore"], "power_level": w["power_level"],
            "public_goal": w["public_goal"],
            "clock_text": w.get("clock_text"),
            "laws": [_law_gloss(l) for l in w["laws"]]}


def _milestones(s):
    return (s["world"] or {}).get("milestones", [])


def _current_milestone(s):
    for m in _milestones(s):
        if m["id"] not in s.get("milestones_done", []):
            return m
    return None


def _scene_context(s, last_report):
    # 桌边留言是玩家之间的真实闲聊,永远不进荷官的眼(§DS永远不能)
    if last_report:
        last_report = [l for l in last_report if "留言:「" not in l]
    cur = _current_milestone(s)
    ms = _milestones(s)
    pacing = None
    if s.get("main_goal_locked"):
        remaining = max(0, MAX_SCENES - s["scene_index"])
        pacing = (f"余波幕:公开目标已经达成,主线结局已锁定。还可行动{remaining}幕;"
                  "余下的戏全在支线:未解悬事的答案早已写在暗典里,由引擎按解锁条件揭示,"
                  "你不负责回答也不负责加谜——只推演现场。承认主线成果,不要再制造新的主线门槛。")
    elif s["progress"] >= 8 or (cur and ms and cur is ms[-1]):
        pacing = "决胜幕:终点已在眼前,本幕危机必须是通往目标的最后一道阻碍,不得新增支线人物或新谜团。"
    elif s["clock"] >= 6:
        pacing = "收束幕:时间无多,收拢已有线索,不再展开新方向。"
    chron = (s["world"] or {}).get("chronicle") or []
    idx = min(s["scene_index"], len(chron) - 1) if chron else -1
    chronicle_now = (f"第{chron[idx].get('chapter', idx + 1)}章"
                     f"《{chron[idx]['title']}》:{chron[idx]['event']}"
                     if idx >= 0 else None)
    npc = _npc_due(s, s["scene_index"] + 1)
    return {
        "npc_onstage": ({"name": npc["npc"]["name"], "desc": npc["npc"]["desc"],
                         "question": npc["question"]} if npc else None),
        "open_questions": [q["question"] for q in s.get("side_quests") or []
                           if q["status"] == "open"],
        "pacing": pacing,
        "milestones": [{"text": m["text"],
                        "done": m["id"] in s.get("milestones_done", [])}
                       for m in _milestones(s)],
        "current_milestone": cur["text"] if cur else None,
        "chronicle_now": chronicle_now,
        "world": _world_brief(s),
        "scene_index": s["scene_index"] + 1,
        "tracks": {"progress": s["progress"], "danger": s["danger"],
                   "synergy": s["synergy"], "clock": s["clock"],
                   "vitality": dict(s["vitality"])},
        "main_goal_locked": s.get("main_goal_locked", False),
        "turns_remaining": max(0, MAX_SCENES - s["scene_index"]),
        "identities": [
            {"name": _identity(s, s["identities"][x])["name"],
             "specialty": _identity(s, s["identities"][x])["specialty"]}
            for x in s["seats"] if s["identities"][x]],
        "facts": s["facts"][-8:],
        "hooks": list(s["hooks"]),
        "last_report": last_report,
    }


# ---------------- 观察 ----------------

def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    idents_public = {}
    for x in s["seats"]:
        if s["identities"][x]:
            it = _identity(s, s["identities"][x])
            idents_public[x] = {"name": it["name"], "origin": it["origin"],
                                "specialty": INTENT_NAMES[it["specialty"]],
                                "gift": it["gift"]["text"],
                                "flaw": it["flaw"]["text"]}
        else:
            idents_public[x] = None
    req = s.get("narration_request")
    public = {
        "phase": s["phase"], "stage": s["stage"],
        "axes": s["axes"],
        "world": _world_brief(s) if s["world"] else None,
        "narration_pending": req["kind"] if req else None,
        "tracks": {"progress": s["progress"], "danger": s["danger"],
                   "synergy": s["synergy"], "clock": s["clock"],
                   "vitality": dict(s["vitality"])},
        "main_goal_locked": s.get("main_goal_locked", False),
        "goal_locked_at_scene": s.get("goal_locked_at_scene"),
        "scene_index": s["scene_index"],
        "scene": deepcopy(s["current_scene"]) if s["stage"] == "scene" else None,
        "identities": idents_public,
        "inventory": deepcopy(s["inventory"]),
        "facts": list(s["facts"]),
        "hooks": list(s["hooks"]),
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "end_proposed_by": s["end_proposed_by"],
        "history": [{"scene_index": h["scene_index"], "title": h["title"],
                     "report": h["report"]} for h in s["history"]],
        "ending": deepcopy(s["ending"]),
        # 原典只在全书终了时揭晓——这一刻是穿越者的对账时刻
        "chronicle_reveal": (
            {"chapters": deepcopy((s["world"] or {}).get("chronicle", [])),
             "original_ending": (s["world"] or {}).get("original_ending"),
             # 支线对账:解开的、错过的,谜底与钥匙一并摊牌
             "side_quests": [
                 {"question": q["question"], "truth": q["truth"],
                  "status": q["status"], "unlock_kind": q["unlock_kind"],
                  "npc_name": (q.get("npc") or {}).get("name"),
                  "windows": q.get("windows"),
                  "stat": q.get("stat")}
                 for q in s.get("side_quests") or []]}
            if s["phase"] == "finished" and s["world"] else None),
    }
    my_ident = s["identities"][seat_id]
    my_drive = None
    if my_ident:
        d = _identity(s, my_ident)["secret_drive"]
        my_drive = f"{d['text']}(判定:{DRIVE_KINDS.get(d['kind'], d['kind'])})"
    offers = None
    if s["stage"] == "identity" and not my_ident:
        offers = []
        for i in s["identity_offers"].get(seat_id, []):
            card = deepcopy(_identity(s, i))
            card["secret_drive"]["text"] += \
                f"(判定:{DRIVE_KINDS.get(card['secret_drive']['kind'], '')})"
            offers.append(card)
    private = {
        "identity_offers": offers,
        "secret_drive": my_drive,
        "my_pending": deepcopy(s["pending"].get(seat_id)),
        "prophecies": deepcopy(s.get("prophecies", {}).get(seat_id, [])),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        if req:
            waiting = ["narrator"]
        elif s["stage"] == "identity":
            waiting = [x for x in s["seats"] if not s["identities"][x]]
            if seat_id in waiting:
                legal = [{"action_id": "choose_identity",
                          "params": {"identity_id":
                                     f"暗选其一:{s['identity_offers'][seat_id]}"}}]
        elif s["stage"] == "scene":
            waiting = [x for x in s["seats"] if x not in s["pending"]]
            if seat_id in waiting:
                my_items = [i["id"] for i in s["inventory"][seat_id]] + \
                           [i["id"] for i in s["inventory"]["shared"]]
                commit_params = {
                    "intent": f"必填:{INTENTS} 之一;或 'end'=提议停笔(双方同幕都选才生效)",
                    "action": f"必填:这一步你具体怎么做(≤{ACTION_TEXT_MAX}字)",
                    "item_id": f"可选:动用一件物品,标签匹配意图时骰+1,可用:{my_items}",
                    "line": f"可选:一句桌边留言(≤{LINE_MAX}字,不参与判定)",
                }
                npc = _npc_due(s, s["scene_index"])
                if npc:
                    commit_params["target"] = (
                        f"可选:'npc'=本幕追查登场人物「{npc['npc']['name']}」"
                        "(成功即揭开其知晓的悬事;此人不会久留)")
                legal = [{"action_id": "commit", "params": commit_params}]
    return {"public_state": public, "private_state": private,
            "legal_actions": legal, "waiting_for": waiting}


# ---------------- 玩家动作 ----------------

def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    if s.get("narration_request"):
        raise IllegalAction("荷官执笔中,请稍候(人类界面可一键召荷官)")
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
        raise IllegalAction("现在不是选身份的时候")
    if s["identities"][seat_id]:
        raise IllegalAction("你已经选过身份了")
    iid = params.get("identity_id")
    if iid not in s["identity_offers"][seat_id]:
        raise IllegalAction(f"只能从你抽到的两张里选:{s['identity_offers'][seat_id]}")
    s["identities"][seat_id] = iid
    s["inventory"][seat_id].append(deepcopy(_identity(s, iid)["starting_item"]))
    if all(s["identities"].values()):
        names = [_identity(s, s["identities"][x])["name"] for x in s["seats"]]
        s["facts"].append(f"{names[0]}与{names[1]}在这个陌生的世界里认出了彼此。")
        s["stage"] = "scenegen"
        s["narration_request"] = {"kind": "gen_scene",
                                  "context": _scene_context(s, None)}


def _apply_commit(s, seat_id, params):
    if s["stage"] != "scene":
        raise IllegalAction("现在不是行动阶段")
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
    target = params.get("target")
    if target is not None:
        if target != "npc":
            raise IllegalAction("target 只支持 'npc'")
        if not _npc_due(s, s["scene_index"]):
            raise IllegalAction("本幕没有可追查的剧情人物")
        if intent == "end":
            raise IllegalAction("提议停笔的同时不能追查人物")
    s["pending"][seat_id] = {"intent": intent, "action": (action or "").strip(),
                             "item_id": item_id, "line": line.strip(),
                             "target": target}
    if len(s["pending"]) == 2:
        _resolve(s)


# ---------------- 裁决 ----------------

def _modifiers(s, seat_id, intent, item_id, other_intent):
    ident = _identity(s, s["identities"][seat_id])
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
    if fk == f"{intent}_minus":
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
    scene = s["current_scene"]
    report = [f"—— 第 {s['scene_index']} 幕 · {scene['title']} ——"]

    if pa["intent"] == "end" and pb["intent"] == "end":
        report.append("两人对视一眼,把故事合上了。")
        _log(s, scene, {a: pa, b: pb}, {}, report)
        alive = [x for x in s["seats"] if s["vitality"][x] > 0]
        if s.get("main_goal_locked"):
            _finish(s, "HE" if len(alive) == 2 else "TE",
                    "goal" if len(alive) == 2 else "sacrifice")
        else:
            _finish(s, "TE", "mutual_end")
        return
    streaks = s.setdefault("end_streaks", {a: 0, b: 0})
    for seat, p in ((a, pa), (b, pb)):
        if p["intent"] == "end":
            # 单方停笔=静候:不掷骰、不折算休整、不触发任何法则
            s["end_proposed_by"] = seat
            p["intent"] = "wait"
            streaks[seat] = streaks.get(seat, 0) + 1
            report.append(f"{seat} 提议就此停笔,静静等着——另一人还想再走一程。"
                          f"(连提三幕即强制收卷,已 {streaks[seat]}/3)")
        else:
            streaks[seat] = 0

    slip = {"outcome": {}, "progress_delta": 0, "danger_delta": 0,
            "clock_delta": 0 if s.get("main_goal_locked") else 1,
            "synergy_delta": 0,
            "vitality_delta": {a: 0, b: 0}, "facts_added": [],
            "flags_added": [], "hooks_added": [], "hooks_resolved": 0,
            "items_gained": []}
    tiers = {}
    for seat, p, other_p in ((a, pa, pb), (b, pb, pa)):
        if p["intent"] == "wait":
            tiers[seat] = "wait"
            slip["outcome"][seat] = "wait"
            continue
        ident = _identity(s, s["identities"][seat])
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
        it = p["intent"]
        if tier == "failure":
            slip["danger_delta"] += 1
            if it == "confront":
                slip["vitality_delta"][seat] -= 1
                report.append(f"  代价:{name}挂了彩(生命-1),局势更险了")
            else:
                report.append("  代价:局势更险了(危险+1)")
        elif tier == "mixed_success":
            if it in ("advance", "explore"):
                slip["progress_delta"] += 1
            # v0.3:悬事由暗典管理,勉强成功不再增殖新问号
        else:
            s.setdefault("wins", {}).setdefault(it, 0)
            s["wins"][it] += 1
            if it == "advance":
                slip["progress_delta"] += 2 if tier == "success" else 3
            elif it == "explore":
                slip["progress_delta"] += 1
                if tier == "critical_success":
                    if "found_the_key_truth" not in s["flags"] and \
                            "found_the_key_truth" not in slip["flags_added"]:
                        slip["flags_added"].append("found_the_key_truth")
                        report.append("  在最不可能的地方,摸到了这世界藏起来的一角真相")
                    if ident["gift"]["kind"] == "explore_crit_item":
                        item = {"id": f"found-{s['rolls_used']}",
                                "name": "路上寻获的小物", "use": ["advance"]}
                        slip["items_gained"].append((seat, item))
                        report.append(f"  {name}顺手寻获:{item['name']}")
                    # 先知情报:撕一页原典,私密塞给探到的人
                    chron = (s["world"] or {}).get("chronicle") or []
                    if s["prophecy_i"] < len(chron):
                        page = chron[s["prophecy_i"]]
                        s["prophecy_i"] += 1
                        s["prophecies"][seat].append(
                            f"原典第{page.get('chapter', '?')}章《{page['title']}》:{page['event']}")
                        report.append(f"  ◆ {name}瞥见了这个世界原本的样子(私密情报,仅其本人可见)")
            elif it == "confront":
                slip["progress_delta"] += 1
                slip["danger_delta"] -= 1
                report.append("  挡路的东西退了半步(危险-1)")
            elif it == "recover":
                heal = [seat]
                if ident["gift"]["kind"] == "recover_heals_both":
                    heal = [a, b]
                    report.append("  一双稳当的手:两人都缓了过来")
                for hseat in heal:
                    slip["vitality_delta"][hseat] += 1
            if tier == "critical_success":
                if it == "advance" and ident["gift"]["kind"] == "advance_crit_clock":
                    slip["clock_delta"] = 0
                    report.append("  抄了近路:这一幕没有花掉时钟")

    # 剧情 NPC 窗口:追查者按本幕骰果裁决;最后一个窗口错过即永久埋没
    due = _npc_due(s, s["scene_index"])
    if due:
        npc_name = due["npc"]["name"]
        pursuers = [(seat, p) for seat, p in ((a, pa), (b, pb))
                    if p.get("target") == "npc"]
        if any(tiers[seat] in ("success", "critical_success")
               for seat, _ in pursuers):
            _quest_resolve(s, due, report, f"从{npc_name}口中问出")
        elif any(tiers[seat] == "mixed_success" for seat, _ in pursuers):
            report.append(f"  {npc_name}只留下半句话,便隐入人群——话没说完。")
        elif pursuers:
            report.append(f"  {npc_name}被惊动,消失在暗处。")
        else:
            report.append(f"  {npc_name}在人群边缘停了停,无人上前,他转身离去。")
        if due["status"] == "open" and s["scene_index"] >= max(due["windows"]):
            due["status"] = "lost"
            report.append(f"◆ {npc_name}再也不会出现了——某段真相就此埋没。")

    ia, ib = pa["intent"], pb["intent"]
    both_ok = all(t != "failure" for t in tiers.values())
    if both_ok and (("support" in (ia, ib)) or {"advance", "explore"} == {ia, ib}
                    or ia == ib == "advance"):
        slip["synergy_delta"] += 1
    for seat, p in ((a, pa), (b, pb)):
        if p["intent"] == "support" and tiers[seat] in ("success", "critical_success") \
                and _identity(s, s["identities"][seat])["gift"]["kind"] == "support_synergy":
            slip["synergy_delta"] += 1

    for law in s["world"]["laws"]:
        tk = law["trigger_kind"]
        if tk.startswith("intent:"):
            want = tk.split(":", 1)[1]
            for seat, p in ((a, pa), (b, pb)):
                if p["intent"] != want:
                    continue
                if want == "confront" and _identity(
                        s, s["identities"][seat])["gift"]["kind"] == "confront_no_law":
                    report.append("  这条法则认得他,没有应验")
                    continue
                _apply_law_cost(s, slip, law, report)
        elif tk.startswith("clock>=") and s["clock"] >= int(tk[7:]):
            _apply_law_cost(s, slip, law, report)
        elif tk.startswith("danger>=") and s["danger"] >= int(tk[8:]):
            _apply_law_cost(s, slip, law, report)

    if s.get("main_goal_locked"):
        # 主线锁定即冻结:进度与时钟是主线的账,余波幕不再改写
        slip["progress_delta"] = 0
        slip["clock_delta"] = 0
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
    for h in slip["hooks_added"]:
        if h not in s["hooks"]:   # 悬事永不重复
            s["hooks"].append(h)

    # 数值考验支线:账本更新完毕后对表,条件一到,真相自动大白
    for q in s.get("side_quests") or []:
        if q["status"] == "open" and q["unlock_kind"] == "stat":
            (k, v), = list(q["stat"].items())
            cur = s["synergy"] if k == "synergy>=" \
                else s.get("wins", {}).get(k.split("_wins")[0], 0)
            if cur >= v:
                _quest_resolve(s, q, report, "数值考验通过")

    for seat, item in slip["items_gained"]:
        s["inventory"][seat].append(item)

    for th in s["world"].get("hidden_threads", []):
        if th["id"] in s["hidden_fired"]:
            continue
        req = th["required"]
        hit = ("flag" in req and req["flag"] in s["flags"]) or \
              ("synergy>=" in req and s["synergy"] >= req["synergy>="]) or \
              ("progress>=" in req and s["progress"] >= req["progress>="]) or \
              ("danger>=" in req and s["danger"] >= req["danger>="])
        if hit:
            s["hidden_fired"].append(th["id"])
            s["facts"].append(th["brief"])
            report.append(f"◆ 暗线浮出:{th['brief']}")
            if th.get("effect_kind") == "truth":
                if "truth_known" not in s["flags"]:
                    s["flags"].append("truth_known")

    # 战果入账:成功即既成事实,荷官不得否认(早期测试报告 §3)
    for seat, p in ((a, pa), (b, pb)):
        if tiers[seat] in ("success", "critical_success") and p["action"]:
            ident = _identity(s, s["identities"][seat])
            s["facts"].append(f"[第{s['scene_index']}幕]{ident['name']}已做到:{p['action'][:50]}")
    # 里程碑判定:任一玩家本幕成功 → 当前里程碑达成;全部达成 → 锁定主线结局
    cur = _current_milestone(s)
    if cur and any(t in ("success", "critical_success") for t in tiers.values()):
        s["milestones_done"].append(cur["id"])
        s["progress"] = min(10, s["progress"] + 2)
        s["facts"].append(f"里程碑达成:{cur['text']}")
        report.append(f"◆ 里程碑达成:{cur['text']}(进度+2)")
        if _milestones(s) and not _current_milestone(s):
            s["progress"] = 10
            if not s.get("main_goal_locked"):
                s["main_goal_locked"] = True
                s["goal_locked_at_scene"] = s["scene_index"]
                if any(q["status"] == "open" for q in s.get("side_quests") or []):
                    report.append("◆ 公开目标全部达成——主线结局已锁定,余下回合可自由探索支线!")
                else:
                    report.append("◆ 公开目标全部达成,支线亦已尽数了结——尘埃落定。")

    report.append(f"账本:进度{s['progress']}/10 危险{s['danger']}/10 "
                  f"默契{s['synergy']}/5 时钟{s['clock']}/8 "
                  f"生命 {s['vitality'][a]}/{s['vitality'][b]}")
    _log(s, scene, {a: pa, b: pb}, slip, report)

    alive = [x for x in s["seats"] if s["vitality"][x] > 0]
    locked = s.get("main_goal_locked")
    if len(alive) == 0:
        _finish(s, "BE", "all_down")
    elif locked and not any(q["status"] == "open"
                            for q in s.get("side_quests") or []):
        # 余账清空:主线已锁且支线尽数了结/埋没——当场收卷,不再发空转幕
        _finish(s, "HE" if len(alive) == 2 else "TE",
                "goal" if len(alive) == 2 else "sacrifice")
    elif max(s.get("end_streaks", {}).values() or [0]) >= 3:
        # 三辞而别:一人连提三幕停笔,引擎替这段散伙收卷
        if locked:
            _finish(s, "HE" if len(alive) == 2 else "TE",
                    "goal" if len(alive) == 2 else "sacrifice")
        else:
            _finish(s, "TE", "insist_end")
    elif s["scene_index"] >= MAX_SCENES:
        # 幕数走满,引擎强制收卷——不看任何人脸色
        if locked:
            _finish(s, "HE" if len(alive) == 2 else "TE",
                    "goal" if len(alive) == 2 else "sacrifice")
        else:
            _finish(s, "TE", "out_of_time")
    elif s["danger"] >= 10:
        # 危险溢出:主线未成是世界失守;主线已成则是余波中被迫收场
        if locked:
            _finish(s, "HE" if len(alive) == 2 else "TE",
                    "goal" if len(alive) == 2 else "sacrifice")
        else:
            _finish(s, "BE", "world_lost")
    elif s["clock"] >= 8 and not locked:
        _finish(s, "TE", "out_of_time")
    else:
        s["stage"] = "scenegen"
        s["narration_request"] = {"kind": "gen_scene",
                                  "context": _scene_context(s, s["history"][-1]["report"])}


def _apply_law_cost(s, slip, law, report):
    ck = law["cost_kind"]
    if ck in ("progress", "clock") and s.get("main_goal_locked"):
        report.append(f"  法则失效(主线已锁定):{law['text']}")
        return
    if ck == "danger":
        slip["danger_delta"] += 1
        report.append(f"  法则应验:{law['text']}")
    elif ck == "vitality":
        pass  # 生命型法则代价由失败结算承担,MVP 不重复扣
    elif ck == "clock":
        slip["clock_delta"] += 1
        report.append(f"  法则应验:{law['text']}(时钟+1)")
    elif ck == "progress":
        slip["progress_delta"] -= 1
        report.append(f"  法则应验:{law['text']}(进度-1)")
    elif ck == "flag":
        tag = f"law_{law['id']}_{s['scene_index']}"
        if tag not in slip["flags_added"]:
            slip["flags_added"].append(tag)
            report.append(f"  法则应验:{law['text']}")


def _log(s, scene, commits, slip, report):
    s["history"].append({
        "scene_index": s["scene_index"], "title": scene["title"],
        "commits": deepcopy(commits), "slip": deepcopy(slip),
        "report": report,
    })
    s["pending"] = {}


REASON_NAMES = {"goal": "目标达成", "all_down": "无人生还", "world_lost": "世界失守",
                "sacrifice": "有人没能回来", "out_of_time": "时钟走完",
                "mutual_end": "双双停笔", "insist_end": "三辞而别"}


def _finish(s, kind, reason):
    drives = {}
    for seat in s["seats"]:
        if not s["identities"][seat]:
            continue
        ident = _identity(s, s["identities"][seat])
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
    s["ending"] = {"kind": kind, "reason": reason,
                   "reason_name": REASON_NAMES[kind_reason_key(kind, reason)],
                   "text": None,   # 待荷官成文
                   "secret_drives": drives,
                   "world_name": s["world"]["world_name"] if s["world"] else "未名之地",
                   "seed": s["seed"], "axes": s["axes"]}
    s["stage"] = "endinggen"
    s["narration_request"] = {
        "kind": "render_ending",
        "context": {
            "world": _world_brief(s), "kind": kind, "reason": reason,
            "reason_name": REASON_NAMES[kind_reason_key(kind, reason)],
            "tracks": {"progress": s["progress"], "danger": s["danger"],
                       "synergy": s["synergy"], "clock": s["clock"],
                       "vitality": dict(s["vitality"])},
            "identities": [_identity(s, s["identities"][x])["name"]
                           for x in s["seats"] if s["identities"][x]],
            "facts": s["facts"][-10:],
            "main_goal_locked": s.get("main_goal_locked", False),
            "goal_locked_at_scene": s.get("goal_locked_at_scene"),
            "unresolved_hooks": list(s["hooks"]),
            # 支线对账单:解开的谜底可入文;未解开的谜底禁止入文
            "side_quests": [
                {"question": q["question"], "truth": q["truth"],
                 "status": q["status"],
                 "npc_name": (q.get("npc") or {}).get("name")}
                for q in s.get("side_quests") or []],
            "hidden_fired": [th["brief"] for th in
                             (s["world"].get("hidden_threads", []) if s["world"] else [])
                             if th["id"] in s["hidden_fired"]],
            "scene_titles": [h["title"] for h in s["history"]],
            "original_ending": (s["world"] or {}).get("original_ending"),
            "chronicle_titles": [c["title"] for c in
                                 (s["world"] or {}).get("chronicle", [])],
        },
    }


def kind_reason_key(kind, reason):
    return reason
