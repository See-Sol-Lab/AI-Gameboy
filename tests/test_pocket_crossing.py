"""《口袋穿越》v0.2 测试:荷官回填、身份暗抽、确定性骰、法则、隐藏线与三类结局。

测试用固定фикс具扮演假荷官,经 apply_system 喂入——同时覆盖了回填路径本身。
"""

import importlib.util
import json
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pocket_crossing_rules",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "pocket-crossing" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SEATS = ["seat_a", "seat_b"]

FIX_WORLD = {
    "world_name": "测试之城",
    "premise": "你们醒在一座用于测试的城里。",
    "lore": "这座城为验收而生。它的每条街都通向断言。",
    "power_level": "低武",
    "world_thread": "测试总署正在远方逐区复核整座城市。",
    "public_goal": "在时钟走完前通过全部断言。",  # 经典跑团测试共用此固定样本
    "goal_menu": [
        {"id": "clear_assertions", "text": "通过本街区的全部断言"},
        {"id": "help_patrol", "text": "查明巡检不眨眼的原因"},
    ],
    "laws": [
        {"id": "law_confront", "text": "对抗会惊动巡检(危险+1)。",
         "trigger_kind": "intent:confront", "cost_kind": "danger"},
        {"id": "law_night", "text": "时钟过5后每幕危险+1。",
         "trigger_kind": "clock>=5", "cost_kind": "danger"},
    ],
    "opening_facts": ["城门上写着 78 passed。", "巡检从不眨眼。"],
    "milestones": [
        {"id": "m1", "text": "通过第一道断言闸机"},
        {"id": "m2", "text": "抵达城心的绿色对勾"},
    ],
    "chronicle": [
        {"chapter": i, "title": f"第{i}章", "event": f"原典密文第{i}节:巡检照常巡逻。"}
        for i in range(1, 7)
    ],
    "original_ending": "原典密文终章:没有人来,测试之城在第八天悄然归档。",
    "hidden_threads": [
        {"id": "h-truth", "required": {"flag": "found_the_key_truth"},
         "effect_kind": "truth", "brief": "这座城是有人测出来的。"},
        {"id": "h-syn", "required": {"synergy>=": 4},
         "effect_kind": "ending_modifier", "brief": "断言也记住了你们。"},
    ],
    "side_quests": [
        {"id": "sq_npc", "question": "档案馆为什么整夜亮灯?",
         "truth": "馆长在誊抄将被归档的城,一页一页救下它的记忆。",
         "unlock_kind": "npc",
         "npc": {"name": "档案馆长", "desc": "抱着一摞誊本,袖口沾着墨。"}},
        {"id": "sq_stat", "question": "巡检为什么从不眨眼?",
         "truth": "巡检是断言化成的人形,眨眼即失效,所以永远睁着。",
         "unlock_kind": "stat", "stat": {"explore_wins>=": 3}},
    ],
}

FIX_IDENTITIES = [
    {"id": "retriever", "name": "失物招领员", "origin": "没丢过东西。",
     "specialty": "explore",
     "gift": {"kind": "explore_crit_item", "text": "探索8+多捡一件"},
     "flaw": {"kind": "confront_minus_danger5", "text": "危险5+对抗-1"},
     "secret_drive": {"kind": "shared_items>=3", "text": "攒满共享行囊"},
     "starting_item": {"id": "lamp", "name": "检索灯", "use": ["explore"]}},
    {"id": "nightwatch", "name": "守夜人", "origin": "守着一条街。",
     "specialty": "support",
     "gift": {"kind": "support_synergy", "text": "支援成功默契+1"},
     "flaw": {"kind": "advance_minus", "text": "推进-1"},
     "secret_drive": {"kind": "partner_full_vitality", "text": "同伴满血到结局"},
     "starting_item": {"id": "flask", "name": "暖壶", "use": ["recover", "support"]}},
    {"id": "courier", "name": "信使", "origin": "记得每条巷子。",
     "specialty": "advance",
     "gift": {"kind": "advance_crit_clock", "text": "推进8+时钟不走"},
     "flaw": {"kind": "explore_minus", "text": "探索-1"},
     "secret_drive": {"kind": "clock<=6", "text": "赶在7点前"},
     "starting_item": {"id": "map", "name": "地图", "use": ["advance", "explore"]}},
    {"id": "locksmith", "name": "拆锁匠", "origin": "认识巡检。",
     "specialty": "confront",
     "gift": {"kind": "confront_no_law", "text": "对抗不触发法则"},
     "flaw": {"kind": "support_minus", "text": "支援-1"},
     "secret_drive": {"kind": "hooks_resolved>=2", "text": "了结两桩悬事"},
     "starting_item": {"id": "hook", "name": "万能钩", "use": ["confront"]}},
    {"id": "medic", "name": "医士", "origin": "药箱上锁。",
     "specialty": "recover",
     "gift": {"kind": "recover_heals_both", "text": "休整治两人"},
     "flaw": {"kind": "confront_minus", "text": "对抗-1"},
     "secret_drive": {"kind": "both_alive", "text": "一个都不能少"},
     "starting_item": {"id": "kit", "name": "药箱", "use": ["recover"]}},
    {"id": "gambler", "name": "赌徒", "origin": "跟城打赌。",
     "specialty": "advance",
     "gift": {"kind": "ones_are_fours", "text": "1当4"},
     "flaw": {"kind": "six_feeds_danger", "text": "6喂危险"},
     "secret_drive": {"kind": "hidden_triggered", "text": "亲见暗线"},
     "starting_item": {"id": "dice", "name": "骰子", "use": ["advance", "confront"]}},
]

FIX_MILESTONES = {"tracks": [
    {"seat": "seat_a", "milestones": [
        {"id": "m1", "text": "通过第一道断言闸机"},
        {"id": "m2", "text": "抵达城心的绿色对勾"},
    ]},
    {"seat": "seat_b", "milestones": [
        {"id": "m1", "text": "问清巡检值守的缘故"},
        {"id": "m2", "text": "替巡检补全值守记录"},
    ]},
]}


def fix_scene(n):
    return {"title": f"第{n}号街", "text": "断言街上一切照旧,巡检在拐角打盹。",
            "crisis": "通过这条街的断言。",
            "objects": [{"id": "gate", "name": "闸机", "hint": "亮着绿灯"},
                        {"id": "patrol", "name": "巡检", "hint": "睡得很浅"}],
            "questions": [f"第{n}号街为什么这么安静?"]}


def feed(s):
    """假荷官:凡有挂起请求就按合同喂固定料。"""
    while s.get("narration_request"):
        kind = s["narration_request"]["kind"]
        if kind == "gen_world":
            data = FIX_WORLD
        elif kind == "gen_identities":
            data = FIX_IDENTITIES
        elif kind == "gen_milestones":
            wanted = {g["seat"] for g in s["narration_request"]["context"]["goals"]}
            data = {"tracks": [t for t in FIX_MILESTONES["tracks"]
                               if t["seat"] in wanted]}
        elif kind == "gen_scene":
            data = fix_scene(s["scene_index"] + 1)
            # NPC响应协议:欠着回应债就按合同清偿
            pend = s.get("pending_interactions") or []
            if pend:
                data["npc_responses"] = [
                    {"object_id": p["object_id"], "kind": "answered",
                     "detail": "断言街的规矩,问了就答。"} for p in pend]
        else:
            data = {"text": "测试之城照常运转,断言全部通过。" * 2}
        s = rules.apply_system(s, "narration_result", {"kind": kind, "data": data})
    return s


def setup_playing(seed=1):
    s = feed(rules.new_game(SEATS, seed))
    for seat in SEATS:
        s = rules.apply(s, seat, "choose_identity",
                        {"identity_id": s["identity_offers"][seat][0]})
    s = rules.apply(s, "seat_a", "choose_goal", {"goal_id": "clear_assertions"})
    s = rules.apply(s, "seat_b", "choose_goal", {"goal_id": "help_patrol"})
    return feed(s)


def commit(s, seat, intent, action="就这么办", item=None, line=""):
    s = rules.apply(s, seat, "commit",
                    {"intent": intent, "action": action,
                     "item_id": item, "line": line})
    return feed(s)


class TestNarrationFlow(unittest.TestCase):
    def test_stage_machine(self):
        s = rules.new_game(SEATS, 1)
        self.assertEqual(s["stage"], "worldgen")
        self.assertEqual(s["narration_request"]["kind"], "gen_world")
        with self.assertRaises(rules.IllegalAction):   # 荷官执笔中不能行动
            rules.apply(s, "seat_a", "commit", {"intent": "advance", "action": "x"})
        s = rules.apply_system(s, "narration_result",
                               {"kind": "gen_world", "data": FIX_WORLD})
        self.assertEqual(s["stage"], "identities_gen")
        with self.assertRaises(rules.IllegalAction):   # 回填必须对上请求
            rules.apply_system(s, "narration_result",
                               {"kind": "gen_world", "data": FIX_WORLD})
        s = rules.apply_system(s, "narration_result",
                               {"kind": "gen_identities", "data": FIX_IDENTITIES})
        self.assertEqual(s["stage"], "identity")
        self.assertIsNone(s["narration_request"])
        for seat in SEATS:
            s = rules.apply(s, seat, "choose_identity",
                            {"identity_id": s["identity_offers"][seat][0]})
        self.assertEqual(s["stage"], "goal")
        s = rules.apply(s, "seat_a", "choose_goal", {"goal_id": "clear_assertions"})
        self.assertEqual(s["stage"], "goal")
        s = rules.apply(s, "seat_b", "choose_goal", {"custom_text": "守完本街夜班"})
        self.assertEqual(s["stage"], "milestonegen")
        self.assertEqual(s["narration_request"]["kind"], "gen_milestones")
        self.assertEqual({g["seat"] for g in s["narration_request"]["context"]["goals"]},
                         set(SEATS))

    def test_goal_choice_validation_and_private_progress(self):
        s = feed(rules.new_game(SEATS, 2))
        for seat in SEATS:
            s = rules.apply(s, seat, "choose_identity",
                            {"identity_id": s["identity_offers"][seat][0]})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_goal", {"custom_text": "长" * 41})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_goal", {"goal_id": "not_on_menu"})
        s = rules.apply(s, "seat_a", "choose_goal", {"goal_id": "clear_assertions"})
        own = rules.observe(s, "seat_a")["private_state"]["player_goals"]
        self.assertEqual(own[-1]["text"], "通过本街区的全部断言")
        self.assertEqual(own[-1]["milestones_done"], [])

    def test_crossing_world_keeps_no_world_milestones(self):
        s = setup_playing(3)
        self.assertNotIn("public_goal", s["world"])
        self.assertNotIn("milestones", s["world"])
        self.assertFalse(s["main_goal_locked"])
        self.assertTrue(all(g["milestones"] for goals in s["player_goals"].values()
                            for g in goals))

    def test_observe_old_state_without_goal_fields(self):
        s = setup_playing(4)
        s.pop("player_goals")
        s["world"]["public_goal"] = s["world"].pop("world_thread")
        s["world"].pop("goal_menu")
        observed = rules.observe(s, "seat_a")
        self.assertEqual(observed["private_state"]["player_goals"], [])
        self.assertTrue(observed["public_state"]["world"]["world_thread"])

    def test_axes_deterministic(self):
        self.assertEqual(rules.new_game(SEATS, 5)["axes"],
                         rules.new_game(SEATS, 5)["axes"])


class TestIdentity(unittest.TestCase):
    def test_offers_private_and_disjoint(self):
        s = feed(rules.new_game(SEATS, 3))
        oa = s["identity_offers"]["seat_a"]
        ob = s["identity_offers"]["seat_b"]
        self.assertEqual(set(oa) & set(ob), set())
        obs_b = rules.observe(s, "seat_b")
        blob = json.dumps(obs_b, ensure_ascii=False)
        for iid in oa:
            self.assertNotIn(f'"{iid}"', blob)

    def test_secret_drive_private(self):
        s = setup_playing(1)
        oa = rules.observe(s, "seat_a")
        drive_b = rules._identity(s, s["identities"]["seat_b"])["secret_drive"]["text"]
        self.assertNotIn(drive_b, json.dumps(oa, ensure_ascii=False))
        self.assertTrue(oa["private_state"]["secret_drive"])


class TestDiceAndResolution(unittest.TestCase):
    def test_deterministic(self):
        r1 = commit(commit(setup_playing(9), "seat_a", "explore"), "seat_b", "advance")
        r2 = commit(commit(setup_playing(9), "seat_a", "explore"), "seat_b", "advance")
        self.assertEqual(r1["history"], r2["history"])

    def test_validations(self):
        s = setup_playing(4)
        with self.assertRaises(rules.IllegalAction):
            commit(s, "seat_a", "advance", action="")
        with self.assertRaises(rules.IllegalAction):
            commit(s, "seat_a", "dance")
        with self.assertRaises(rules.IllegalAction):
            commit(s, "seat_a", "advance", item="not-mine")

    def test_support_and_law(self):
        s = setup_playing(5)
        s = commit(s, "seat_a", "support", action="我托住他")
        s = commit(s, "seat_b", "confront", action="我抡起家伙")
        rep = "\n".join(s["history"][0]["report"])
        self.assertIn("同伴支援+1", rep)
        lk = rules._identity(s, s["identities"]["seat_b"])["gift"]["kind"]
        if lk != "confront_no_law":
            self.assertIn("法则应验", rep)

    def test_scene_advances_via_narrator(self):
        s = setup_playing(7)
        s = commit(s, "seat_a", "recover")
        s = rules.apply(s, "seat_b", "commit",
                        {"intent": "recover", "action": "喘口气"})
        # 结算后应挂起下一幕请求;喂料前不能行动
        self.assertEqual(s["narration_request"]["kind"], "gen_scene")
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit", {"intent": "advance", "action": "x"})
        s = feed(s)
        self.assertEqual(s["scene_index"], 2)
        self.assertEqual(s["stage"], "scene")

    def test_success_advances_only_that_seats_track(self):
        s = setup_playing(70)
        rolls = iter([8, 1])
        orig = rules._die
        rules._die = lambda st: next(rolls)
        try:
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "advance", "action": "冲过闸机"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "recover", "action": "原地歇脚"})
        finally:
            rules._die = orig
        self.assertEqual(rules._active_goal(s, "seat_a")["milestones_done"], ["m1"])
        self.assertEqual(rules._active_goal(s, "seat_b")["milestones_done"], [])

    def test_all_seats_must_lock_before_main_goal(self):
        s = setup_playing(71)
        for seat in SEATS:
            goal = rules._active_goal(s, seat)
            goal["milestones"] = goal["milestones"][:1]
        orig = rules._die
        try:
            rolls = iter([8, 1])
            rules._die = lambda st: next(rolls)
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "advance", "action": "先过关"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "recover", "action": "暂时歇脚"})
            self.assertTrue(rules._active_goal(s, "seat_a")["goal_locked"])
            self.assertFalse(rules._active_goal(s, "seat_b")["goal_locked"])
            self.assertFalse(s["main_goal_locked"])
            s = feed(s)
            rolls = iter([1, 8])
            rules._die = lambda st: next(rolls)
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "recover", "action": "等同伴"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "advance", "action": "随后过关"})
        finally:
            rules._die = orig
        self.assertTrue(rules._active_goal(s, "seat_b")["goal_locked"])
        self.assertTrue(s["main_goal_locked"])

    def test_switch_goal_costs_clock_and_preserves_old_track(self):
        s = setup_playing(72)
        old = rules._active_goal(s, "seat_a")
        old_milestones = list(old["milestones"])
        clock = s["clock"]
        other = rules._active_goal(s, "seat_b")
        s = rules.apply(s, "seat_a", "switch_goal",
                        {"custom_text": "替闸机找回遗失的铰链"})
        self.assertEqual(s["clock"], clock + 1)
        self.assertTrue(old["abandoned"] is False)  # apply() 保持输入 state 不变
        abandoned = s["player_goals"]["seat_a"][0]
        self.assertTrue(abandoned["abandoned"])
        self.assertEqual(abandoned["milestones"], old_milestones)
        self.assertEqual(s["stage"], "milestonegen")
        goals = s["narration_request"]["context"]["goals"]
        self.assertEqual([g["seat"] for g in goals], ["seat_a"])
        s = feed(s)
        self.assertEqual(s["stage"], "scene")
        self.assertEqual(rules._active_goal(s, "seat_a")["text"],
                         "替闸机找回遗失的铰链")
        self.assertEqual(rules._active_goal(s, "seat_b"), other)

    def test_switch_goal_rejected_after_lock(self):
        s = setup_playing(73)
        s["main_goal_locked"] = True
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "switch_goal", {"goal_id": "help_patrol"})


class TestHiddenAndEndings(unittest.TestCase):
    def test_hidden_thread(self):
        s = setup_playing(1)
        s["flags"].append("found_the_key_truth")
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "recover")
        self.assertIn("h-truth", s["hidden_fired"])
        self.assertIn("truth_known", s["flags"])

    def test_be_world_lost_and_ending_via_narrator(self):
        s = setup_playing(3)
        s["danger"] = 9
        s["progress"] = 0
        seat = next(x for x in SEATS if s["identities"][x] != "locksmith")
        other = [x for x in SEATS if x != seat][0]
        s = commit(s, seat, "confront", action="硬闯")
        s = rules.apply(s, other, "commit",
                        {"intent": "confront", "action": "我也上"})
        # 结局判定后应挂起 render_ending;成文前 phase 仍 playing
        self.assertEqual(s["stage"], "endinggen")
        self.assertEqual(s["narration_request"]["kind"], "render_ending")
        self.assertEqual(s["phase"], "playing")
        s = feed(s)
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["ending"]["kind"], "BE")
        self.assertTrue(s["ending"]["text"])

    def test_te_mutual_end(self):
        s = setup_playing(4)
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = rules.apply(s, "seat_b", "commit", {"intent": "end", "action": ""})
        s = feed(s)
        self.assertEqual(s["ending"]["kind"], "TE")
        self.assertEqual(s["ending"]["reason"], "mutual_end")

    def test_ending_context_has_goal_world_matrix_fields(self):
        import narrator
        s = setup_playing(75)
        s = rules.apply(s, "seat_a", "switch_goal",
                        {"custom_text": "替巡检补好旧制服"})
        s = feed(s)
        rules._active_goal(s, "seat_a")["goal_locked"] = True
        rules._finish(s, "HE", "goal")
        ctx = s["narration_request"]["context"]
        self.assertEqual(s["ending"]["kind"], "HE")
        self.assertEqual(set(ctx["world_thread"]), {"text", "outcome"})
        self.assertEqual(ctx["world_thread"]["text"], FIX_WORLD["world_thread"])
        self.assertEqual(ctx["world_thread"]["outcome"], FIX_WORLD["original_ending"])
        self.assertTrue(any(g["abandoned"] for g in ctx["player_goals"]))
        for goal in ctx["player_goals"]:
            self.assertEqual(set(goal),
                             {"seat", "identity", "text", "achieved", "abandoned"})
        prompt = narrator._p_ending(ctx)
        for wording in ("做成了自己的事,世界照旧转", "做成了,且留下了痕迹",
                        "没做成,世界也没在意", "没做成,但世界因你们歪了一点"):
            self.assertIn(wording, prompt)
        self.assertIn("正文禁止提及、惩罚或评价", prompt)

    def test_chronicle_secret_until_finished(self):
        """原典对局中零可见;终局才揭晓。先知撕页只给撕到的人看。"""
        s = setup_playing(6)
        for seat in SEATS:
            blob = json.dumps(rules.observe(s, seat), ensure_ascii=False)
            self.assertNotIn("原典密文", blob)          # 底本小说滴水不漏
        # 先知情报:私密单向
        s["prophecies"]["seat_a"].append("原典第3章《第3章》:原典密文第3节")
        oa = rules.observe(s, "seat_a")
        ob = rules.observe(s, "seat_b")
        self.assertIn("原典密文第3节",
                      json.dumps(oa["private_state"]["prophecies"], ensure_ascii=False))
        self.assertNotIn("原典密文第3节", json.dumps(ob, ensure_ascii=False))
        # 终局揭晓
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = rules.apply(s, "seat_b", "commit", {"intent": "end", "action": ""})
        s = feed(s)
        o = rules.observe(s, "seat_b")
        cr = o["public_state"]["chronicle_reveal"]
        self.assertEqual(len(cr["chapters"]), 6)
        self.assertIn("悄然归档", cr["original_ending"])

    def test_milestones_lock_goal_and_leave_sidequest_turns(self):
        """主线达成后继续到第10幕,余下回合可探索支线。"""
        s = setup_playing(42)
        guard = 0
        orig = rules._die
        rules._die = lambda st: 8
        try:
            while not s.get("main_goal_locked") and guard < 20:
                guard += 1
                for seat in SEATS:
                    if s.get("narration_request"):
                        break
                    s = rules.apply(s, seat, "commit",
                                    {"intent": "advance", "action": "冲阵"})
                s = feed(s)
        finally:
            rules._die = orig
        self.assertTrue(s["main_goal_locked"])
        self.assertEqual(s["progress"], 10)
        self.assertEqual(s["phase"], "playing")
        self.assertIsNone(s["ending"])
        self.assertLess(s["goal_locked_at_scene"], rules.MAX_SCENES)
        self.assertIn("余波幕", rules._scene_context(s, None)["pacing"])

        s["scene_index"] = rules.MAX_SCENES
        s["danger"] = 10
        s["clock"] = 8
        s = commit(s, "seat_a", "explore", action="把遗留的岔路走完")
        s = rules.apply(s, "seat_b", "commit",
                        {"intent": "support", "action": "替她照亮支路"})
        self.assertEqual(s["stage"], "endinggen")
        self.assertEqual(s["ending"]["kind"], "HE")

    def test_target_object_creates_response_debt_and_fact(self):
        """点名在场对象且没骰砸→挂回应债;荷官清偿→入既成事实(NPC响应协议)。"""
        hit = None
        for seed in range(60, 90):
            s = setup_playing(seed)
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "explore", "action": "上前盘问闸机边的巡检",
                             "target": "patrol"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "support", "action": "在旁帮腔"})
            if s.get("pending_interactions"):
                hit = s
                break
        self.assertIsNotNone(hit, "30个种子里竟无一次交涉判定过关")
        p = hit["pending_interactions"][0]
        self.assertEqual(p["object_id"], "patrol")
        self.assertEqual(p["object_name"], "巡检")
        self.assertIn("正面交涉", json.dumps(hit["history"][-1]["report"],
                                         ensure_ascii=False))
        ctx = hit["narration_request"]["context"]
        self.assertTrue(ctx["pending_interactions"])
        s2 = feed(hit)   # 假荷官按合同清偿
        self.assertIsNone(s2["pending_interactions"])
        self.assertIn("巡检对", json.dumps(s2["facts"], ensure_ascii=False))
        self.assertIn("如实作答", json.dumps(s2["facts"], ensure_ascii=False))

    def test_target_must_be_scene_object(self):
        s = setup_playing(46)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit",
                        {"intent": "explore", "action": "问路",
                         "target": "nobody_here"})

    def test_about_requires_target_and_open_hook(self):
        s = setup_playing(48)
        hook = s["hooks"][0]
        with self.assertRaises(rules.IllegalAction):   # 没点名问谁
            rules.apply(s, "seat_a", "commit",
                        {"intent": "explore", "action": "追问", "about": hook})
        with self.assertRaises(rules.IllegalAction):   # 悬事没对上原句
            rules.apply(s, "seat_a", "commit",
                        {"intent": "explore", "action": "追问",
                         "target": "gate", "about": "自创的谜题?"})

    def test_pressing_hook_twice_reveals_truth(self):
        """追问机制:点对悬事逼问,两次(卓越算两次)谜底必出——不许守门到终局。"""
        hook = FIX_WORLD["side_quests"][1]["question"]   # 数值考验型支线
        truth = FIX_WORLD["side_quests"][1]["truth"]
        done = False
        for seed in range(90, 140):
            s = setup_playing(seed)
            presses = 0
            guard = 0
            while presses < 2 and s["phase"] == "playing" and guard < 8:
                guard += 1
                if hook not in s["hooks"]:
                    break   # 数值考验先解开了,换个种子重试
                s = rules.apply(s, "seat_a", "commit",
                                {"intent": "explore", "action": "揪住巡检追问到底",
                                 "target": "patrol", "about": hook})
                s = rules.apply(s, "seat_b", "commit",
                                {"intent": "support", "action": "帮腔施压"})
                q = next(x for x in s["side_quests"] if x["question"] == hook)
                presses = q.get("pressed", 0)
                if q["status"] == "resolved":
                    done = True
                    break
                s = feed(s)
            if done:
                break
        self.assertTrue(done, "50个种子里追问竟从未成功两次")
        self.assertIn(truth, json.dumps(s["facts"], ensure_ascii=False))
        self.assertNotIn(hook, s["hooks"])
        self.assertIn("追问到底", json.dumps(s["history"], ensure_ascii=False))

    def test_npc_book_tracks_appearances(self):
        """同名对象反复登场,台帐计数;change 入台帐(刷脸铁律的账本侧)。"""
        s = setup_playing(47)
        s = commit(s, "seat_a", "explore", action="看看闸机")
        s = commit(s, "seat_b", "recover", action="歇脚")
        self.assertGreaterEqual(s["npc_book"]["闸机"]["count"], 2)
        ctx_names = [n["name"] for n in
                     rules._scene_context(s, None)["recurring_npcs"]]
        self.assertIn("巡检", ctx_names)

    def test_cornered_npc_requires_confront(self):
        """墙角摊牌:硬茬NPC被逼入墙角后,追查只能【对抗】(项目作者设计,治反派瞬移)。"""
        s = setup_playing(50)
        q = next(x for x in s["side_quests"] if x["unlock_kind"] == "npc")
        q["npc"]["persona"] = "铁血寡言"
        q["cornered"] = True
        q["windows"] = [s["scene_index"]]
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit",
                        {"intent": "explore", "action": "再问一次",
                         "target": "npc"})

    def test_hard_npc_corners_instead_of_vanishing(self):
        """硬茬NPC:追查失败不消失,入墙角且窗口顺延。"""
        found = False
        for seed in range(150, 200):
            s = setup_playing(seed)
            q = next(x for x in s["side_quests"] if x["unlock_kind"] == "npc")
            q["npc"]["persona"] = "傲慢毒舌"
            q["windows"] = [s["scene_index"]]
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "explore", "action": "上去堵人盘问",
                             "target": "npc"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "recover", "action": "在旁歇脚"})
            q2 = next(x for x in s["side_quests"] if x["unlock_kind"] == "npc")
            if q2.get("cornered"):
                found = True
                self.assertEqual(q2["status"], "open")   # 没有"永久埋没"
                self.assertIn(s["scene_index"] + 1, q2["windows"])
                self.assertIn("逼到了墙角",
                              json.dumps(s["history"][-1]["report"],
                                         ensure_ascii=False))
                break
        self.assertTrue(found, "50个种子里追查竟从未失败过")

    def test_showdown_win_resolves_and_boosts_progress(self):
        """摊牌得胜:真相到手+势力瓦解+进度大涨。"""
        won = False
        for seed in range(200, 260):
            s = setup_playing(seed)
            q = next(x for x in s["side_quests"] if x["unlock_kind"] == "npc")
            q["npc"]["persona"] = "腹黑藏锋"
            q["cornered"] = True
            q["windows"] = [s["scene_index"]]
            p0 = s["progress"]
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "confront", "action": "拔刀摊牌",
                             "target": "npc"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "support", "action": "压阵助势"})
            q2 = next(x for x in s["side_quests"] if x["unlock_kind"] == "npc")
            if q2["status"] == "resolved":
                won = True
                rep = json.dumps(s["history"][-1]["report"], ensure_ascii=False)
                self.assertIn("刀口之下", rep)
                self.assertIn("势力被打散", rep)
                self.assertGreaterEqual(s["progress"], p0 + 2)
                break
        self.assertTrue(won, "60个种子里摊牌竟从未打赢")

    def test_lock_with_no_open_sidequests_settles_immediately(self):
        """主线锁定且支线全清:当场收卷,不再发空转的余波幕。"""
        s = setup_playing(44)
        for q in s["side_quests"]:
            q["status"] = "resolved"
        s["main_goal_locked"] = True
        s["goal_locked_at_scene"] = s["scene_index"]
        s["progress"] = 10
        s = rules.apply(s, "seat_a", "commit",
                        {"intent": "explore", "action": "再看一眼"})
        s = rules.apply(s, "seat_b", "commit",
                        {"intent": "support", "action": "陪着"})
        self.assertIsNotNone(s["ending"])
        self.assertEqual(s["ending"]["kind"], "HE")
        self.assertEqual(s["ending"]["reason"], "goal")

    def test_lock_message_mentions_sidequests_only_if_open(self):
        """锁定瞬间支线已全清时,不再喊'可自由探索支线'。"""
        s = setup_playing(45)
        for q in s["side_quests"]:
            q["status"] = "lost"
        guard = 0
        while not s.get("main_goal_locked") and s["phase"] == "playing" \
                and guard < 20:
            guard += 1
            for seat in SEATS:
                if s.get("narration_request") or s["phase"] != "playing":
                    break
                s = rules.apply(s, seat, "commit",
                                {"intent": "advance", "action": "冲阵"})
            s = feed(s)
        if s.get("main_goal_locked"):
            text = json.dumps(s["history"], ensure_ascii=False)
            self.assertNotIn("可自由探索支线", text)

    def test_mutual_end_after_goal_keeps_locked_ending(self):
        s = setup_playing(43)
        s["main_goal_locked"] = True
        s["goal_locked_at_scene"] = s["scene_index"]
        s["progress"] = 10
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = rules.apply(s, "seat_b", "commit", {"intent": "end", "action": ""})
        self.assertEqual(s["ending"]["kind"], "HE")
        self.assertEqual(s["ending"]["reason"], "goal")

    def test_one_end_proposal_not_final(self):
        s = setup_playing(5)
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = commit(s, "seat_b", "advance", action="再走一程")
        self.assertEqual(s["phase"], "playing")
        self.assertEqual(s["end_proposed_by"], "seat_a")

    def test_random_games_terminate(self):
        import itertools
        intents = ["advance", "explore", "support", "confront", "recover"]
        for seed in range(5):
            s = setup_playing(seed + 20)
            picker = itertools.cycle(intents)
            guard = 0
            while s["phase"] == "playing":
                guard += 1
                self.assertLess(guard, 25)
                if s.get("narration_request"):
                    s = feed(s)
                    continue
                for seat in SEATS:
                    if s["phase"] != "playing" or s.get("narration_request"):
                        break
                    s = rules.apply(s, seat, "commit",
                                    {"intent": next(picker), "action": "试试"})
                s = feed(s)
            self.assertIn(s["ending"]["kind"], ("HE", "BE", "TE"))
            self.assertTrue(s["ending"]["text"])
            self.assertEqual(len(s["ending"]["secret_drives"]), 2)


class TestSideQuests(unittest.TestCase):
    """v0.3 支线暗典:谜底预写、NPC 窗口、数值考验、悬事生命周期。"""

    @staticmethod
    def _npc_quest(s):
        return next(q for q in s["side_quests"] if q["unlock_kind"] == "npc")

    def test_hooks_seeded_from_quests_and_never_proliferate(self):
        s = setup_playing(11)
        qs = [q["question"] for q in s["side_quests"]]
        self.assertEqual(s["hooks"], qs)
        s = commit(commit(s, "seat_a", "explore"), "seat_b", "advance")
        self.assertTrue(set(s["hooks"]) <= set(qs))     # 只减不增
        self.assertEqual(len(s["hooks"]), len(set(s["hooks"])))  # 永不重复

    def test_truth_hidden_during_play(self):
        s = setup_playing(15)
        for seat in SEATS:
            blob = json.dumps(rules.observe(s, seat), ensure_ascii=False)
            for q in s["side_quests"]:
                self.assertNotIn(q["truth"], blob)

    def test_npc_windows_deterministic(self):
        self.assertEqual(rules._npc_windows(123), rules._npc_windows(123))
        for seed in range(30):
            ws = rules._npc_windows(seed)
            self.assertEqual(len(set(ws)), 2)
            for w in ws:
                self.assertTrue(1 <= w <= rules.MAX_SCENES)

    def test_npc_pursuit_success_resolves(self):
        s = setup_playing(12)
        self._npc_quest(s)["windows"] = [s["scene_index"]]
        orig = rules._die
        rules._die = lambda st: 8   # 保证成功档
        try:
            s = rules.apply(s, "seat_a", "commit",
                            {"intent": "explore", "action": "追上那个人",
                             "target": "npc"})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "support", "action": "掩护"})
        finally:
            rules._die = orig
        q = self._npc_quest(s)
        self.assertEqual(q["status"], "resolved")
        self.assertNotIn(q["question"], s["hooks"])
        self.assertEqual(s["hooks_resolved"], 1)
        self.assertTrue(any(q["truth"] in f for f in s["facts"]))

    def test_npc_final_window_missed_locks_forever(self):
        s = setup_playing(13)
        self._npc_quest(s)["windows"] = [s["scene_index"]]
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "recover")
        self.assertEqual(self._npc_quest(s)["status"], "lost")

    def test_target_rejected_without_npc(self):
        s = setup_playing(13)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit",
                        {"intent": "explore", "action": "追", "target": "npc"})

    def test_stat_quest_auto_resolves(self):
        s = setup_playing(16)
        s["wins"]["explore"] = 3
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "recover")
        sq = next(q for q in s["side_quests"] if q["unlock_kind"] == "stat")
        self.assertEqual(sq["status"], "resolved")
        self.assertNotIn(sq["question"], s["hooks"])

    def test_reveal_includes_side_quests(self):
        s = setup_playing(14)
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = rules.apply(s, "seat_b", "commit", {"intent": "end", "action": ""})
        s = feed(s)
        cr = rules.observe(s, "seat_a")["public_state"]["chronicle_reveal"]
        self.assertEqual(len(cr["side_quests"]), 2)
        for q in cr["side_quests"]:
            self.assertTrue(q["truth"])
            self.assertIn("status", q)


class TestLockAndEndFixes(unittest.TestCase):
    """v0.3 机械修缮:锁定冻结、单方停笔=静候、幕满强制收卷。"""

    def test_lock_freezes_progress_and_clock(self):
        s = setup_playing(17)
        s["main_goal_locked"] = True
        s["goal_locked_at_scene"] = 1
        s["progress"] = 10
        clock0 = s["clock"]
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "advance")
        self.assertEqual(s["progress"], 10)
        self.assertEqual(s["clock"], clock0)

    def test_single_end_is_wait_not_recover(self):
        s = setup_playing(18)
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = commit(s, "seat_b", "recover", action="喘口气")
        h = s["history"][0]
        self.assertEqual(h["slip"]["outcome"]["seat_a"], "wait")
        self.assertIn("静静等着", "\n".join(h["report"]))
        self.assertEqual(s["end_proposed_by"], "seat_a")

    def test_weighted_pick_deterministic_and_in_pool(self):
        for key, pool in rules.POOLS.items():
            values = [v for v, _ in pool]
            for seed in range(40):
                v = rules._pick(seed, key, pool)
                self.assertIn(v, values)
                self.assertEqual(v, rules._pick(seed, key, pool))

    def test_three_end_proposals_force_settlement(self):
        s = setup_playing(21)
        for i in range(3):
            s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
            s = rules.apply(s, "seat_b", "commit",
                            {"intent": "recover", "action": "再撑一幕"})
            if i < 2:
                self.assertIsNone(s["ending"])
                s = feed(s)
        self.assertEqual(s["stage"], "endinggen")
        self.assertEqual(s["ending"]["kind"], "TE")
        self.assertEqual(s["ending"]["reason"], "insist_end")

    def test_end_streak_resets_when_playing_on(self):
        s = setup_playing(22)
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = commit(s, "seat_b", "recover", action="撑住")
        s = commit(s, "seat_a", "recover", action="回心转意")   # 断签
        s = commit(s, "seat_b", "recover", action="继续")
        self.assertEqual(s["end_streaks"]["seat_a"], 0)
        self.assertIsNone(s["ending"])

    def test_scene_limit_forces_ending_even_unlocked(self):
        s = setup_playing(19)
        s["scene_index"] = rules.MAX_SCENES
        s = commit(s, "seat_a", "recover")
        s = rules.apply(s, "seat_b", "commit",
                        {"intent": "recover", "action": "撑住"})
        self.assertEqual(s["stage"], "endinggen")
        self.assertEqual(s["ending"]["kind"], "TE")
        self.assertEqual(s["ending"]["reason"], "out_of_time")


class TestScopeAndAntiEpic(unittest.TestCase):
    """v0.3 规模轴与反史诗纪律:镜头可以很小,世界照样宏大。"""

    def test_scope_axis_present_and_budgeted(self):
        s = rules.new_game(SEATS, 7)
        values = [v for v, _ in rules.POOLS["scope"]]
        self.assertIn(s["axes"]["scope"], values)
        for v in values:   # 每档规模都必须有烈度预算,漏一档就是哑轴
            self.assertIn(v, rules.SCOPE_INTENSITY)

    def test_worldgen_context_carries_intensity(self):
        s = rules.new_game(SEATS, 7)
        ctx = s["narration_request"]["context"]
        self.assertEqual(ctx["scope_intensity"],
                         rules.SCOPE_INTENSITY[s["axes"]["scope"]])

    def test_world_prompt_scale_rules_by_scope(self):
        import narrator
        axes = {k: rules.POOLS[k][0][0] for k in rules.POOLS}
        axes["scope"] = "鸡毛蒜皮"
        p = narrator._p_world({"axes": axes, "scope_intensity": "烈度1-2"})
        self.assertIn("规模纪律", p)
        self.assertIn("烈度1-2", p)
        self.assertIn('"world_thread"', p)
        self.assertIn('"goal_menu"', p)
        self.assertNotIn('"public_goal"', p)
        self.assertNotIn('"milestones"', p)
        axes["scope"] = "天下大势"
        p = narrator._p_world({"axes": axes, "scope_intensity": ""})
        self.assertNotIn("规模纪律", p)

    def test_scene_prompt_forbids_escalation(self):
        import narrator
        ctx = {"world": {"world_name": "测", "public_goal": "goal",
                         "laws": [], "clock_text": ""},
               "scene_index": 1, "tracks": {}, "identities": {},
               "facts": [], "hooks": []}
        self.assertIn("禁止替他们升级", narrator._p_scene(ctx))

    def test_npc_persona_seeded_and_reaches_scene(self):
        s = setup_playing(23)
        values = [v for v, _ in rules.NPC_PERSONAS]
        q = next(q for q in s["side_quests"] if q["unlock_kind"] == "npc")
        self.assertIn(q["npc"]["persona"], values)
        # 同种子复现同人格
        s2 = setup_playing(23)
        q2 = next(q for q in s2["side_quests"] if q["unlock_kind"] == "npc")
        self.assertEqual(q["npc"]["persona"], q2["npc"]["persona"])
        # NPC 窗口幕的场景上下文携带人格,荷官每次登场都得照此写人
        s["scene_index"] = q["windows"][0] - 1
        ctx = rules._scene_context(s, [])
        self.assertEqual(ctx["npc_onstage"]["persona"], q["npc"]["persona"])

    def test_ending_prompt_forbids_invention_and_moralizing(self):
        import narrator
        ctx = {"world": {"world_name": "测", "clock_text": ""},
               "kind": "HE", "reason_name": "目标达成", "tracks": {},
               "identities": {}, "scene_titles": [], "facts": [],
               "hidden_fired": []}
        p = narrator._p_ending(ctx)
        self.assertIn("禁止补写没演出来的新事件", p)
        self.assertIn("不强制升华", p)


if __name__ == "__main__":
    unittest.main()
