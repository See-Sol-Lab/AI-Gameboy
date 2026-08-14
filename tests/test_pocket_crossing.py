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
    "hidden_threads": [
        {"id": "h-truth", "required": {"flag": "found_the_key_truth"},
         "effect_kind": "truth", "brief": "这座城是有人测出来的。"},
        {"id": "h-syn", "required": {"synergy>=": 4},
         "effect_kind": "ending_modifier", "brief": "断言也记住了你们。"},
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


if __name__ == "__main__":
    unittest.main()
