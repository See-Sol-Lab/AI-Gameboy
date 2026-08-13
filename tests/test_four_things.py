"""《口袋里的四样东西》纯规则测试:目录完整性、发牌、标签计分、共同星、四轮与非法动作。"""

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "four_things_rules",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "four-things-in-my-pocket" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SEATS = ["seat_a", "seat_b"]


class TestCatalog(unittest.TestCase):
    def test_twelve_items_three_tags_each(self):
        self.assertEqual(len(rules.ITEMS), 12)
        for it in rules.ITEMS.values():
            self.assertEqual(len(it["tags"]), 3)

    def test_at_least_eight_situations_and_coverage(self):
        self.assertGreaterEqual(len(rules.SITUATIONS), 8)
        all_tags = {t for it in rules.ITEMS.values() for t in it["tags"]}
        for sit in rules.SITUATIONS.values():
            self.assertEqual(len(sit["needs"]), 2)
            for need in sit["needs"]:
                self.assertIn(need, all_tags, f"需求 {need} 没有任何物件能满足")
            self.assertIn(sit["risk"], all_tags, f"风险 {sit['risk']} 不会被任何物件踩中")


class TestDeal(unittest.TestCase):
    def test_deterministic_by_seed(self):
        self.assertEqual(rules.new_game(SEATS, 9), rules.new_game(SEATS, 9))

    def test_hands_and_situations(self):
        for seed in range(20):
            s = rules.new_game(SEATS, seed)
            a, b = s["hands"]["seat_a"], s["hands"]["seat_b"]
            self.assertEqual(len(a), 4)
            self.assertEqual(len(b), 4)
            self.assertEqual(set(a) & set(b), set())
            self.assertTrue(set(a + b) <= set(rules.ITEMS))
            self.assertEqual(len(s["situations"]), 4)
            self.assertEqual(len(set(s["situations"])), 4)
            self.assertTrue(set(s["situations"]) <= set(rules.SITUATIONS))


class TestScoring(unittest.TestCase):
    def full_game(self, seed):
        """双方每轮都出手牌第一件,返回终局状态。"""
        s = rules.new_game(SEATS, seed)
        while s["phase"] == "playing":
            for seat in SEATS:
                s = rules.apply(s, seat, "choose_item",
                                {"item_id": s["hands"][seat][0]})
        return s

    def test_points_and_stars_recomputable(self):
        """独立按目录重算每轮得分与共同星,必须与引擎一致。"""
        for seed in range(12):
            s = self.full_game(seed)
            self.assertEqual(s["phase"], "finished")
            self.assertEqual(len(s["revealed"]), 4)
            expect_scores = {x: 0 for x in SEATS}
            expect_stars = 0
            for r in s["revealed"]:
                sit = rules.SITUATIONS[r["situation"]["situation_id"]]
                needs, risk = set(sit["needs"]), sit["risk"]
                union = set()
                for seat in SEATS:
                    tags = set(rules.ITEMS[r["choices"][seat]["item_id"]]["tags"])
                    union |= tags
                    pts = len(tags & needs) - (1 if risk in tags else 0)
                    self.assertEqual(r["points"][seat], pts)
                    expect_scores[seat] += pts
                self.assertEqual(r["joint_star"], needs <= union)
                expect_stars += 1 if r["joint_star"] else 0
            self.assertEqual(s["scores"], expect_scores)
            self.assertEqual(s["stars"], expect_stars)

    def test_items_leave_hands(self):
        s = rules.new_game(SEATS, 3)
        first = {x: s["hands"][x][0] for x in SEATS}
        for seat in SEATS:
            s = rules.apply(s, seat, "choose_item", {"item_id": first[seat]})
        for seat in SEATS:
            self.assertNotIn(first[seat], s["hands"][seat])
            self.assertEqual(len(s["hands"][seat]), 3)
        self.assertEqual(s["round"], 2)

    def test_joint_star_when_union_covers(self):
        """人工构造一轮:火柴 + 粉笔 覆盖『停电的档案室』全部需求。"""
        s = rules.new_game(SEATS, 1)
        s["situations"][0] = "blackout-archive"
        s["hands"]["seat_a"] = ["match", "coin"]
        s["hands"]["seat_b"] = ["chalk", "thread"]
        s = rules.apply(s, "seat_a", "choose_item", {"item_id": "match"})
        s = rules.apply(s, "seat_b", "choose_item", {"item_id": "chalk"})
        r = s["revealed"][0]
        self.assertTrue(r["joint_star"])
        self.assertEqual(r["points"]["seat_a"], 1)  # 照明+1
        self.assertEqual(r["points"]["seat_b"], 1)  # 标记+1
        self.assertEqual(s["stars"], 1)

    def test_risk_costs_point(self):
        """玻璃珠在档案室:标记+1 但易碎−1 = 0。"""
        s = rules.new_game(SEATS, 1)
        s["situations"][0] = "blackout-archive"
        s["hands"]["seat_a"] = ["glass-bead", "coin"]
        s["hands"]["seat_b"] = ["thread", "wax"]
        s = rules.apply(s, "seat_a", "choose_item", {"item_id": "glass-bead"})
        s = rules.apply(s, "seat_b", "choose_item", {"item_id": "thread"})
        self.assertEqual(s["revealed"][0]["points"]["seat_a"], 0)
        self.assertFalse(s["revealed"][0]["joint_star"])


class TestIllegal(unittest.TestCase):
    def setUp(self):
        self.s = rules.new_game(SEATS, 5)

    def test_illegal_actions(self):
        s = self.s
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "play_card", {"card": 1})  # 别的卡的动作
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_item",
                        {"item_id": s["hands"]["seat_b"][0]})  # 对方的东西
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_item", {"item_id": 3})  # 类型不对
        s2 = rules.apply(s, "seat_a", "choose_item",
                         {"item_id": s["hands"]["seat_a"][0]})
        with self.assertRaises(rules.IllegalAction):  # 同轮重复暗选
            rules.apply(s2, "seat_a", "choose_item",
                        {"item_id": s2["hands"]["seat_a"][0]})
        done = s
        while done["phase"] == "playing":
            for seat in SEATS:
                done = rules.apply(done, seat, "choose_item",
                                   {"item_id": done["hands"][seat][0]})
        with self.assertRaises(rules.IllegalAction):  # 终局后
            rules.apply(done, "seat_a", "choose_item", {"item_id": "key"})

    def test_observe_privacy_shape(self):
        s = rules.apply(self.s, "seat_b", "choose_item",
                        {"item_id": self.s["hands"]["seat_b"][0]})
        ob_a = rules.observe(s, "seat_a")
        self.assertNotIn("hands", ob_a["public_state"])
        self.assertNotIn("pending", ob_a["public_state"])
        self.assertIsNone(ob_a["private_state"]["my_pending"])
        self.assertTrue(ob_a["public_state"]["submitted"]["seat_b"])
        ob_b = rules.observe(s, "seat_b")
        self.assertEqual(ob_b["private_state"]["my_pending"],
                         s["pending"]["seat_b"])


if __name__ == "__main__":
    unittest.main()
