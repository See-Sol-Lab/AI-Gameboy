"""《口袋穿越》规则测试:身份暗抽、确定性骰、修正项、法则、隐藏线与三类结局。"""

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


def setup_playing(seed=1):
    s = rules.new_game(SEATS, seed)
    for seat in SEATS:
        s = rules.apply(s, seat, "choose_identity",
                        {"identity_id": s["identity_offers"][seat][0]})
    return s


def commit(s, seat, intent, action="就这么办", item=None, line=""):
    return rules.apply(s, seat, "commit",
                       {"intent": intent, "action": action,
                        "item_id": item, "line": line})


class TestSetup(unittest.TestCase):
    def test_offers_disjoint_and_private(self):
        s = rules.new_game(SEATS, 3)
        oa, ob = s["identity_offers"]["seat_a"], s["identity_offers"]["seat_b"]
        self.assertEqual(len(oa), 2)
        self.assertEqual(set(oa) & set(ob), set())
        ob_b = rules.observe(s, "seat_b")
        blob = json.dumps(ob_b, ensure_ascii=False)
        for iid in oa:  # 对面的候选身份不可见
            self.assertNotIn(f'"{iid}"', blob)
        # 自己的两张齐全
        self.assertEqual(len(ob_b["private_state"]["identity_offers"]), 2)

    def test_choose_identity_and_secret_drive_private(self):
        s = setup_playing(1)
        self.assertEqual(s["stage"], "scene")
        self.assertEqual(s["scene_index"], 1)
        oa = rules.observe(s, "seat_a")
        self.assertTrue(oa["private_state"]["secret_drive"])
        # 对面的私密动机绝不出现在我这
        drive_b = rules._identity(s["identities"]["seat_b"])["secret_drive"]["text"]
        self.assertNotIn(drive_b, json.dumps(oa, ensure_ascii=False))
        # 身份公开面有名字/擅长,无 secret
        self.assertTrue(oa["public_state"]["identities"]["seat_b"]["name"])
        self.assertNotIn("secret",
                         json.dumps(oa["public_state"]["identities"]))

    def test_wrong_identity_rejected(self):
        s = rules.new_game(SEATS, 2)
        bad = s["identity_offers"]["seat_b"][0]
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_identity", {"identity_id": bad})


class TestDice(unittest.TestCase):
    def test_deterministic(self):
        s1 = setup_playing(9)
        s2 = setup_playing(9)
        r1 = commit(commit(s1, "seat_a", "explore"), "seat_b", "advance")
        r2 = commit(commit(s2, "seat_a", "explore"), "seat_b", "advance")
        self.assertEqual(r1["history"], r2["history"])   # 同局面同骰同判词

    def test_action_text_required(self):
        s = setup_playing(4)
        with self.assertRaises(rules.IllegalAction):
            commit(s, "seat_a", "advance", action="")
        with self.assertRaises(rules.IllegalAction):
            commit(s, "seat_a", "dance")
        with self.assertRaises(rules.IllegalAction):
            commit(s, "seat_a", "advance", item="not-mine")


class TestResolution(unittest.TestCase):
    def test_support_gives_partner_plus(self):
        s = setup_playing(5)
        s = commit(s, "seat_a", "support", action="我托住他")
        s = commit(s, "seat_b", "advance", action="我往前冲")
        rep = "\n".join(s["history"][0]["report"])
        self.assertIn("同伴支援+1", rep)

    def test_specialty_and_item(self):
        s = setup_playing(5)
        ident_a = rules._identity(s["identities"]["seat_a"])
        spec = ident_a["specialty"]
        item = s["inventory"]["seat_a"][0]
        use_ok = spec in item["use"]
        s = commit(s, "seat_a", spec, item=item["id"])
        s = commit(s, "seat_b", "recover")
        rep = "\n".join(s["history"][0]["report"])
        self.assertIn("身份擅长+1", rep)
        if use_ok:
            self.assertIn(f"{item['name']}+1", rep)

    def test_confront_law_feeds_danger(self):
        s = setup_playing(6)
        # 找一个非拆锁匠的席位来对抗
        seat = next(x for x in SEATS
                    if s["identities"][x] != "locksmith")
        other = [x for x in SEATS if x != seat][0]
        d0 = s["danger"]
        s = commit(s, seat, "confront", action="我抡起家伙")
        s = commit(s, other, "recover")
        rep = "\n".join(s["history"][0]["report"])
        self.assertTrue("法则应验" in rep or s["danger"] > d0)

    def test_clock_always_advances(self):
        s = setup_playing(7)
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "recover")
        self.assertGreaterEqual(s["clock"], 1)
        self.assertEqual(s["scene_index"], 2)


class TestHiddenAndEndings(unittest.TestCase):
    def test_hidden_thread_ledger(self):
        s = setup_playing(1)
        s["flags"].append("found_the_ledger")
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "recover")
        self.assertIn("h-ledger", s["hidden_fired"])
        self.assertIn("truth_known", s["flags"])

    def test_he_goal(self):
        s = setup_playing(2)
        s["progress"] = 9
        s = commit(s, "seat_a", "advance", action="最后一步")
        s = commit(s, "seat_b", "advance", action="一起")
        if s["phase"] == "finished":                  # 进度到 10 即 HE
            self.assertEqual(s["ending"]["kind"], "HE")
            self.assertIn("secret_drives", s["ending"])
        else:                                          # 双失败时进度可能没到
            self.assertLess(s["progress"], 10)

    def test_be_world_lost(self):
        s = setup_playing(3)
        s["danger"] = 9
        s["progress"] = 0
        # 找非拆锁匠去对抗喂雾;失败也 +1,必到 10
        seat = next(x for x in SEATS if s["identities"][x] != "locksmith")
        other = [x for x in SEATS if x != seat][0]
        s = commit(s, seat, "confront", action="硬闯")
        s = commit(s, other, "confront", action="我也上")
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["ending"]["kind"], "BE")

    def test_te_mutual_end(self):
        s = setup_playing(4)
        s = commit(s, "seat_a", "end", action="")
        s = commit(s, "seat_b", "end", action="")
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["ending"]["kind"], "TE")
        self.assertEqual(s["ending"]["reason"], "mutual_end")

    def test_te_out_of_time(self):
        s = setup_playing(8)
        s["clock"] = 7
        s["progress"] = 0
        s = commit(s, "seat_a", "recover")
        s = commit(s, "seat_b", "recover")
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["ending"]["kind"], "TE")
        self.assertEqual(s["ending"]["reason"], "out_of_time")

    def test_one_end_proposal_is_public_not_final(self):
        s = setup_playing(5)
        s = commit(s, "seat_a", "end", action="")
        s = commit(s, "seat_b", "advance", action="再走一程")
        self.assertEqual(s["phase"], "playing")
        self.assertEqual(s["end_proposed_by"], "seat_a")

    def test_full_random_game_terminates(self):
        """随机策略连打:任何一局都必须在 8 幕内落入三类结局之一。"""
        import itertools
        intents = ["advance", "explore", "support", "confront", "recover"]
        for seed in range(6):
            s = setup_playing(seed + 20)
            picker = itertools.cycle(intents)
            guard = 0
            while s["phase"] == "playing":
                guard += 1
                self.assertLess(guard, 20)
                for seat in SEATS:
                    if s["phase"] != "playing":
                        break
                    s = commit(s, seat, next(picker))
            self.assertIn(s["ending"]["kind"], ("HE", "BE", "TE"))
            self.assertTrue(s["ending"]["text"])
            self.assertEqual(len(s["ending"]["secret_drives"]), 2)


if __name__ == "__main__":
    unittest.main()
