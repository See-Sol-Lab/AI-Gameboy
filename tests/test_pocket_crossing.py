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
    "public_goal": "在时钟走完前通过全部断言。",
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
        elif kind == "gen_scene":
            data = fix_scene(s["scene_index"] + 1)
        else:
            data = {"text": "测试之城照常运转,断言全部通过。" * 2}
        s = rules.apply_system(s, "narration_result", {"kind": kind, "data": data})
    return s


def setup_playing(seed=1):
    s = feed(rules.new_game(SEATS, seed))
    for seat in SEATS:
        s = rules.apply(s, seat, "choose_identity",
                        {"identity_id": s["identity_offers"][seat][0]})
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
        while not s.get("main_goal_locked") and guard < 20:
            guard += 1
            for seat in SEATS:
                if s.get("narration_request"):
                    break
                s = rules.apply(s, seat, "commit",
                                {"intent": "advance", "action": "冲阵"})
            s = feed(s)
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
