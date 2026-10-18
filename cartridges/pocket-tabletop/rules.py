"""跑团2.0：预写节点、三维检定、固定事实和玩家改写的世界。纯函数，不联网。"""
from copy import deepcopy
import hashlib
from console.tabletop_contract import ending_kind

INTENTS = ["advance", "explore", "support", "confront", "recover"]
INTENT_NAMES = dict(zip(INTENTS, ["推进", "探索", "支援", "对抗", "休整"]))
ATTR_NAMES = {"wisdom": "智慧", "stamina": "体力", "luck": "幸运"}
RESULT_NAMES = {"success": "成功", "partial": "部分成功", "failure": "失败"}
POOLS = {
    "form": [(x, 1) for x in ["现代都市", "架空古代", "未来都市", "深海文明", "魔法大陆", "修仙世界", "梦境世界"]],
    "power": [(x, 1) for x in ["无超凡", "低武", "中武", "高武", "神话级"]],
    "kind": [(x, 1) for x in ["逃离", "护送", "寻物", "调查", "守城", "营救", "谈判"]],
    "mood": [(x, 1) for x in ["温暖", "轻快", "诡谲", "壮烈", "荒诞", "史诗"]],
    "variable": [(x, 1) for x in ["时间不多了", "身份存疑", "世界正在遗忘", "敌人会学习你们", "死亡会改变规则"]],
}


class IllegalAction(Exception):
    pass


def _number(seed, salt, sides):
    return int(hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest(), 16) % sides


def _die(s):
    result = _number(s["seed"], f"roll:{s['rolls_used']}", 6) + 1
    s["rolls_used"] += 1
    return result


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("需要两位玩家")
    axes = {k: v[_number(seed, k, len(v))][0] for k, v in POOLS.items()}
    return {
        "ruleset": 2, "phase": "playing", "stage": "worldgen", "seed": seed, "axes": axes,
        "seats": list(seats), "world": None, "identity_pool": [], "identity_offers": {},
        "identities": {x: None for x in seats}, "attrs": {}, "vitality": {x: 3 for x in seats},
        "inventory": {**{x: [] for x in seats}, "shared": []}, "item_owners": {},
        "nodes": {}, "events": {}, "side_quests": [], "location_id": None, "npc": None,
        "scene_index": 0, "current_scene": None, "danger": 0, "rolls_used": 0,
        "facts": [], "world_changes": [], "history": [], "pending": {}, "ending": None,
        "narration_request": {"kind": "tt_world", "context": {"axes": axes}},
    }


def _identity(s, seat):
    return next(i for i in s["identity_pool"] if i["id"] == s["identities"][seat])


def _main_complete(s):
    return bool(s["nodes"]) and all(n["done"] for n in s["nodes"].values())


def _main_current(s):
    return next((n for n in (s["world"] or {}).get("main_nodes", []) if not s["nodes"][n["id"]]["done"]), None)


def _story_view(q, own=False):
    known = q["owner"] == "npc" or own or q["status"] == "resolved"
    return {"id": q["id"], "owner": q["owner"], "question": q["question"] if known else "尚未揭示的身份旧事",
            "status": q["status"], "clue_count": len(q["found_clues"]),
            "clues": [deepcopy(q["clues"][i]) for i in q["found_clues"]] if known else [],
            "truth": q["truth"] if q["status"] == "resolved" else None}


def _check(s, seat, spec, p):
    attr, die = spec["attribute"], _die(s)
    bonus = int(_identity(s, seat)["specialty"] == p["intent"])
    if p["item_id"]:
        item = next(i for i in s["inventory"][seat] + s["inventory"]["shared"] if i["id"] == p["item_id"])
        bonus += int(p["intent"] in item["use"])
    bonus += int(any(x != seat and other["intent"] == "support" for x, other in s["pending"].items()))
    score = s["attrs"][seat][attr] + die + bonus
    result = "success" if score >= spec["target"] else "partial" if score >= spec["target"] - 2 else "failure"
    return {"attribute": attr, "base": s["attrs"][seat][attr], "die": die, "bonus": bonus,
            "total": score, "target": spec["target"], "result": result}


def _give(s, iid):
    if iid not in s["item_owners"]:
        s["inventory"]["shared"].append(deepcopy(next(i for i in s["world"]["items"] if i["id"] == iid)))
        s["item_owners"][iid] = "shared"


def _snapshot(s, stop=False):
    current = _main_current(s)
    objects = [{"id": p["id"], "name": p["name"]} for p in s["world"]["locations"] if p["id"] == s["location_id"]]
    if s["npc"]["available"] and s["npc"]["location_id"] == s["location_id"]:
        objects.append({"id": "npc", "name": s["npc"]["name"]})
    if current and current["location_id"] == s["location_id"]:
        objects.extend({"id": iid, "name": next(i["name"] for i in s["world"]["items"] if i["id"] == iid)}
                       for iid in current["item_ids"] if iid not in s["item_owners"])
    hidden = []
    public_texts = set(s["facts"])
    public_texts.update(q["clues"][i]["text"] for q in s["side_quests"] if q["owner"] == "npc" or q["status"] == "resolved" for i in q["found_clues"])
    for q in s["side_quests"]:
        if q["status"] != "resolved":
            if q["truth"] not in public_texts:
                hidden.append(q["truth"])
            hidden.extend(c["text"] for i, c in enumerate(q["clues"]) if c["text"] not in public_texts and (q["owner"] != "npc" or i not in q["found_clues"]))
    return {
        "world": {k: s["world"][k] for k in ("world_name", "premise", "lore", "public_goal")},
        "turn": s["scene_index"], "location_id": s["location_id"], "npc": deepcopy(s["npc"]),
        "main_complete": _main_complete(s), "main_nodes": [dict(n, **s["nodes"][n["id"]]) for n in s["world"]["main_nodes"]],
        "open_story_ids": [q["id"] for q in s["side_quests"] if q["status"] != "resolved"],
        "danger": s["danger"], "vitality": dict(s["vitality"]), "stop_requested": stop,
        "item_owners": dict(s["item_owners"]), "inventory": deepcopy(s["inventory"]),
        "facts": list(s["facts"]), "world_changes": deepcopy(s["world_changes"]),
        "allowed_objects": objects, "hidden_texts": hidden,
    }


def _targets(s, seat):
    if s["stage"] != "scene":
        return []
    targets = []
    moving = any(p["target_id"].startswith("move:") for p in s["pending"].values())
    working_main = any(p["target_id"].startswith("main:") for p in s["pending"].values())
    main = _main_current(s)
    if main and not moving:
        targets.append({"id": "main:" + main["id"], "kind": "main", "label": main["title"], "intent": "advance", "attribute": main["attribute"], "target": main["target"]})
    for q in s["side_quests"]:
        if q["status"] == "resolved" or q["owner"] not in (seat, "npc"):
            continue
        npc_here = s["npc"]["available"] and s["npc"]["location_id"] == s["location_id"]
        if len(q["found_clues"]) < 2 and (q["owner"] != "npc" or npc_here):
            targets.append({"id": "clue:" + q["id"], "kind": "clue", "label": q["question"], "intent": q["intent"], "attribute": q["attribute"], "target": q["target"]})
        if q["found_clues"]:
            targets.append({"id": "deduce:" + q["id"], "kind": "deduce", "label": "推断：" + q["question"], "intent": "explore"})
    for event in s["world"]["events"]:
        if not s["events"][event["id"]]["done"] and event["location_id"] == s["location_id"]:
            targets.append({"id": "event:" + event["id"], "kind": "event", "label": event["title"], "attribute": event["attribute"], "target": event["target"]})
    for loc in s["world"]["locations"]:
        if loc["id"] != s["location_id"] and not moving and not working_main:
            targets.append({"id": "move:" + loc["id"], "kind": "move", "label": "前往" + loc["name"], "intent": "advance", "attribute": "stamina", "target": 6})
    targets.append({"id": "free", "kind": "free", "label": "自由行动：帮助、开店、种田或修行", "target": 6})
    return targets




def observe(s, seat):
    if seat not in s["seats"]:
        raise ValueError("未知席位")
    public = {
        "ruleset": 2, "phase": s["phase"], "stage": s["stage"], "axes": s["axes"],
        "world": {k: s["world"][k] for k in ("world_name", "premise", "lore", "public_goal")} if s["world"] else None,
        "scene_index": s["scene_index"], "scene": deepcopy(s["current_scene"]) if s["stage"] == "scene" else None,
        "narration_pending": s["narration_request"]["kind"] if s["narration_request"] else None,
        "main_complete": _main_complete(s), "main_nodes": [dict(n, **s["nodes"][n["id"]]) for n in (s["world"] or {}).get("main_nodes", [])],
        "tracks": {"progress": sum(n["done"] for n in s["nodes"].values()), "progress_total": len(s["nodes"]), "danger": s["danger"], "vitality": dict(s["vitality"])},
        "location_id": s["location_id"], "npc": deepcopy(s["npc"]), "inventory": deepcopy(s["inventory"]), "item_owners": dict(s["item_owners"]),
        "facts": list(s["facts"]), "world_changes": deepcopy(s["world_changes"]), "old_stories": [_story_view(q) for q in s["side_quests"]],
        "history": deepcopy(s["history"]), "ending": deepcopy(s["ending"]), "submitted": {x: x in s["pending"] for x in s["seats"]},
        "reserved_targets": {x: p["target_id"] for x, p in s["pending"].items() if not p["target_id"].startswith(("clue:", "deduce:")) or ":npc:" in p["target_id"]},
        "identities": {x: {"name": _identity(s, x)["name"], "specialty": _identity(s, x)["specialty"], "attrs": dict(s["attrs"][x])} if s["identities"][x] else None for x in s["seats"]},
    }
    if s["npc"]:
        public["npc"]["location_name"] = next(p["name"] for p in s["world"]["locations"] if p["id"] == s["npc"]["location_id"])
    if s["phase"] == "finished":
        public["chronicle_reveal"] = {"chapters": deepcopy(s["world"]["original_story"]), "original_ending": s["world"]["original_ending"]}
    offers = []
    for iid in s["identity_offers"].get(seat, []):
        card = deepcopy(next(c for c in s["identity_pool"] if c["id"] == iid))
        card.pop("old_stories")
        offers.append(card)
    private = {"identity_offers": offers, "old_stories": [_story_view(q, own=True) for q in s["side_quests"] if q["owner"] in (seat, "npc")],
               "my_pending": deepcopy(s["pending"].get(seat)), "targets": _targets(s, seat)}
    waiting, legal = [], []
    if s["narration_request"]:
        waiting = ["narrator"]
    elif s["stage"] == "identity":
        waiting = [x for x in s["seats"] if not s["identities"][x]]
        if seat in waiting:
            legal = [{"action_id": "choose_identity", "params": {"identity_id": s["identity_offers"][seat]}}]
    elif s["stage"] == "scene":
        waiting = [x for x in s["seats"] if x not in s["pending"]]
        if seat in waiting:
            legal = [{"action_id": "commit", "params": {"intent": INTENTS + ["end"], "target_id": private["targets"],
                      "action": "用自己的方法实现选择的目标，4到240字；推断须写结论和证据",
                      "item_id": [i["id"] for i in s["inventory"][seat] + s["inventory"]["shared"]], "line": "桌边话≤60字，不交给荷官"}}]
    return {"public_state": public, "private_state": private, "legal_actions": legal, "waiting_for": waiting}


def apply(state, seat, action_id, params):
    s = deepcopy(state)
    if seat not in s["seats"] or s["phase"] != "playing" or s["narration_request"]:
        raise IllegalAction("当前不能行动")
    if action_id == "choose_identity" and s["stage"] == "identity":
        iid = params.get("identity_id")
        if s["identities"][seat] or iid not in s["identity_offers"][seat]:
            raise IllegalAction("请选择自己的未选身份")
        s["identities"][seat] = iid
        s["attrs"][seat] = {a: _number(s["seed"], f"{iid}:{a}", 6) + 1 for a in ATTR_NAMES}
        item = deepcopy(_identity(s, seat)["starting_item"])
        s["inventory"][seat].append(item)
        s["item_owners"][item["id"]] = seat
        for original in _identity(s, seat)["old_stories"]:
            q = deepcopy(original)
            q.update(id=f"{seat}:{q['id']}", owner=seat, status="open", found_clues=[])
            s["side_quests"].append(q)
        if all(s["identities"].values()):
            s["scene_index"] = 1
            _request(s, "tt_scene", {"snapshot": _snapshot(s)})
        return s
    if action_id != "commit" or s["stage"] != "scene" or seat in s["pending"]:
        raise IllegalAction("本幕只能提交一次行动")
    intent = params.get("intent")
    if intent not in INTENTS + ["end"]:
        raise IllegalAction("意图非法")
    action = params.get("action", "").strip() if isinstance(params.get("action", ""), str) else ""
    if intent != "end" and not 4 <= len(action) <= 240:
        raise IllegalAction("行动须4到240字")
    target_id = "free" if intent == "end" else params.get("target_id", "free")
    target = next((t for t in _targets(s, seat) if t["id"] == target_id), None)
    if intent != "end" and (not target or target.get("intent", intent) != intent):
        raise IllegalAction("目标不在本席可选清单内，或意图不匹配")
    item = params.get("item_id")
    if item is not None and item not in [i["id"] for i in s["inventory"][seat] + s["inventory"]["shared"]]:
        raise IllegalAction("不能使用不属于自己或队伍的物品")
    line = params.get("line", "")
    if not isinstance(line, str) or len(line.strip()) > 60:
        raise IllegalAction("留言须≤60字")
    s["pending"][seat] = {"intent": intent, "action": action, "target_id": target_id, "item_id": item, "line": line.strip()}
    if len(s["pending"]) == 2:
        _resolve(s)
    return s


def _request(s, kind, context):
    s["narration_request"] = {"kind": kind, "context": context}
    s["stage"] = {"tt_world": "worldgen", "tt_identities": "identities_gen", "tt_scene": "scenegen", "tt_turn": "turngen"}[kind]


def _resolve(s):
    outcomes, approved, candidates, report = [], [], [], []
    first_new_fact = len(s["facts"])
    stop = all(p["intent"] == "end" for p in s["pending"].values())
    if not _main_complete(s) and not stop:
        s["danger"] += 1
    for seat in s["seats"]:
        p = s["pending"][seat]
        if p["intent"] == "end":
            outcomes.append({"seat": seat, "target_id": p["target_id"], "result": "closing_decision", "action": p["action"]})
            report.append(f"{_identity(s, seat)['name']}收尾决定：{p['action']}" if p["action"] else f"{_identity(s, seat)['name']}选择收尾。")
            continue
        prefix, _, key = p["target_id"].partition(":")
        if prefix == "deduce":
            q = next(q for q in s["side_quests"] if q["id"] == key)
            candidates.append({"seat": seat, "story_id": q["id"], "truth": q["truth"],
                               "action": p["action"], "evidence": [deepcopy(q["clues"][i]) for i in q["found_clues"]]})
            outcomes.append({"seat": seat, "target_id": p["target_id"], "result": "awaiting_deduction"})
            report.append(f"{_identity(s, seat)['name']}提出旧事推断，等待按证据核对。")
            continue
        spec = {"attribute": "stamina" if p["intent"] in ("confront", "recover") else "wisdom", "target": 6}
        node, q = None, None
        if prefix in ("main", "event"):
            node = next(n for n in s["world"]["main_nodes" if prefix == "main" else "events"] if n["id"] == key)
            spec = node
        elif prefix == "clue":
            q = next(q for q in s["side_quests"] if q["id"] == key)
            spec = q
        elif prefix == "move":
            spec = {"attribute": "stamina", "target": 6}
        check = _check(s, seat, spec, p)
        outcomes.append(dict(check, seat=seat, target_id=p["target_id"], action=p["action"]))
        report.append(f"{_identity(s, seat)['name']}【{INTENT_NAMES[p['intent']]}】{ATTR_NAMES[check['attribute']]}{check['base']}+骰{check['die']}+修正{check['bonus']}={check['total']} / 目标{check['target']}：{RESULT_NAMES[check['result']]}")
        if check["result"] == "failure":
            s["danger"] += 1
            if p["intent"] == "confront":
                s["vitality"][seat] = max(0, s["vitality"][seat] - 1)
            continue
        achieved = check["result"] == "success"
        if prefix in ("main", "event"):
            record = s["nodes"][key] if prefix == "main" else s["events"][key]
            if record["done"]:
                report.append("同伴已完成该节点，协作不重复发放奖励。")
            else:
                record["effort"] = min(2, record["effort"] + (2 if check["result"] == "success" else 1))
                if record["effort"] == 2:
                    achieved = True
                    outcomes[-1]["node_completed"] = True
                    record["done"] = True
                    s["facts"].append(node["success_fact"])
                    report.append("节点完成：" + node["title"])
                    if prefix == "main":
                        s["location_id"] = node["location_id"]
                        for iid in node["item_ids"]:
                            _give(s, iid)
                        if node["npc_destination"]:
                            s["npc"]["location_id"] = node["npc_destination"]
                    else:
                        s["danger"] -= 2
                else:
                    report.append("阶段推进1/2，尚未获得完整成果或奖励。")
        elif prefix == "clue":
            for i in range(2):
                if i not in q["found_clues"]:
                    q["found_clues"].append(i)
                    if q["owner"] == "npc":
                        report.append("线索入手：" + q["clues"][i]["source"] + "——" + q["clues"][i]["text"])
                    else:
                        report.append(f"{_identity(s, seat)['name']}获得第{i + 1}条身份旧事线索（仅本人可见）。")
                    if check["result"] == "partial":
                        break
            if s["scene_index"] == 10 and achieved and len(q["found_clues"]) == 2:
                candidates.append({"seat": seat, "story_id": q["id"], "truth": q["truth"],
                                   "action": p["action"], "evidence": [deepcopy(q["clues"][i]) for i in q["found_clues"]]})
                report.append("末幕证据已齐，行动中的明确推断将在本幕按证据核对。")
        elif prefix == "move" and check["result"] == "success":
            s["location_id"] = key
        elif p["intent"] == "confront" and check["result"] == "success":
            s["danger"] -= 2
        elif p["intent"] == "recover" and check["result"] == "success":
            s["vitality"][seat] = min(3, s["vitality"][seat] + 1)
        if achieved:
            approved.append({"seat": seat, "target_id": p["target_id"], "action": p["action"]})
    s["danger"] = max(0, min(10, s["danger"]))
    s["history"].append({"scene_index": s["scene_index"], "title": s["current_scene"]["title"], "story_text": s["current_scene"]["text"],
                         "story_responses": list(s["facts"][first_new_fact:]),
                         "commits": deepcopy(s["pending"]), "outcomes": outcomes, "report": report})
    s["npc"]["available"] = s["scene_index"] < 8
    snapshot = _snapshot(s, stop)
    snapshot["next_scene_index"] = s["scene_index"] + 1
    context = {"snapshot": snapshot, "outcomes": outcomes, "approved_actions": approved, "candidates": candidates,
               "closing_decisions": [{"scene_index": h["scene_index"], "seat": o["seat"], "action": o["action"]}
                                     for h in s["history"] for o in h["outcomes"] if o["result"] == "closing_decision"],
               "known_clues": [deepcopy(q["clues"][i]) for q in s["side_quests"] for i in q["found_clues"]], "known_facts": list(s["facts"])}
    if ending_kind(snapshot) or (snapshot["main_complete"] and set(snapshot["open_story_ids"]) <= {q["story_id"] for q in candidates}):
        context["original_ending"] = s["world"]["original_ending"]
    s["pending"] = {}
    _request(s, "tt_turn", context)


def apply_system(state, action_id, payload):
    s = deepcopy(state)
    req = s.get("narration_request")
    if s.get("ruleset") != 2 or action_id != "narration_result" or not req or payload.get("kind") != req["kind"]:
        raise IllegalAction("荷官请求不匹配")
    d, kind = deepcopy(payload["data"]), req["kind"]
    if kind == "tt_world":
        s["world"] = d
        s["location_id"] = d["starting_location"]
        s["npc"] = dict(d["npc"], available=True)
        s["nodes"] = {n["id"]: {"done": False, "effort": 0} for n in d["main_nodes"]}
        s["events"] = {n["id"]: {"done": False, "effort": 0} for n in d["events"]}
        for original in d["npc_old_stories"]:
            q = deepcopy(original)
            q.update(id="npc:" + q["id"], owner="npc", status="open", found_clues=[])
            s["side_quests"].append(q)
        _request(s, "tt_identities", {"world": d, "task_item_ids": [i["id"] for i in d["items"]]})
    elif kind == "tt_identities":
        s["identity_pool"] = d["identities"]
        order = sorted([c["id"] for c in s["identity_pool"]], key=lambda iid: _number(s["seed"], iid, 2**32))
        s["identity_offers"] = {s["seats"][0]: order[:2], s["seats"][1]: order[2:4]}
        s["stage"], s["narration_request"] = "identity", None
    elif kind == "tt_scene":
        s["current_scene"], s["stage"], s["narration_request"] = d, "scene", None
    elif kind == "tt_turn":
        report = s["history"][-1]["report"]
        for match in d["deductions"]:
            q = next(q for q in s["side_quests"] if q["id"] == match["story_id"])
            if q["status"] != "resolved":
                q["status"] = "resolved"
                s["facts"].append(q["truth"])
                s["history"][-1]["story_responses"].append(q["truth"])
                report.append("旧事揭示：" + q["truth"])
        for change in d["world_changes"]:
            s["world_changes"].append(dict(change, scene_index=s["scene_index"]))
            report.append("世界已改变：" + change["text"])
        s["history"][-1]["story_responses"].extend(change["text"] for change in d["world_changes"])
        if req["context"]["candidates"] and not d["deductions"]:
            report.append("推断与证据及答案尚未吻合；已有线索保留，可以继续推理。")
        end = ending_kind(_snapshot(s, req["context"]["snapshot"]["stop_requested"]))
        if end:
            s["ending"] = dict(d["ending"], world_name=s["world"]["world_name"], seed=s["seed"],
                               secret_drives={seat: {"identity": _identity(s, seat)["name"], "text": "解开两条身份旧事",
                               "achieved": all(q["status"] == "resolved" for q in s["side_quests"] if q["owner"] == seat)} for seat in s["seats"]})
            s["phase"] = s["stage"] = "finished"
            s["narration_request"] = None
        else:
            s["scene_index"] += 1
            s["current_scene"], s["stage"], s["narration_request"] = d["scene"], "scene", None
    return s


def sample_actions(state, seat):
    observation = observe(state, seat)
    legal = observation["legal_actions"]
    if not legal:
        return []
    if legal[0]["action_id"] == "choose_identity":
        return [("choose_identity", {"identity_id": iid}) for iid in legal[0]["params"]["identity_id"]]
    return [("commit", {"intent": t.get("intent", "explore"), "target_id": t["id"],
                        "action": "我使用现有工具和经验尝试完成这个目标。"}) for t in observation["private_state"]["targets"]]
