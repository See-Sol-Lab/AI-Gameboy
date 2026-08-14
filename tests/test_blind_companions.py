"""《盲区同行》规则测试:视野分配、钉见闻、姿态一次性、组合、余波、背书与终局。"""

import importlib.util
import json
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "blind_companions_rules",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "blind-companions" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SEATS = ["seat_a", "seat_b"]


def commit(s, seat, fact_id, stance, target, line="", endorse=False):
    return rules.apply(s, seat, "commit",
                       {"fact_id": fact_id, "stance": stance,
                        "target_id": target, "line": line, "endorse": endorse})


def first_fact(s, seat):
    return s["facts"][seat][0]


class TestSetup(unittest.TestCase):
    def test_deal(self):
        s = rules.new_game(SEATS, 1)
        self.assertEqual(rules.new_game(SEATS, 1), s)      # 种子确定性
        packs = set(s["packets"].values())
        self.assertEqual(packs, {"terrain", "echo"})       # 两套视野各一
        for seat in SEATS:
            self.assertEqual(len(s["facts"][seat]), 3)
            self.assertEqual(len(s["stances_left"][seat]), 4)
            self.assertEqual(s["endorse_left"][seat], 1)
        self.assertEqual(sorted(s["omens"]), ["代价", "回声", "顺势"])

    def test_facts_private_pending_private(self):
        s = rules.new_game(SEATS, 2)
        secret_fact = first_fact(s, "seat_a")
        s = commit(s, "seat_a", secret_fact, "推进", "conveyor",
                   line="这句揭示前不能给对面看")
        ob_b = rules.observe(s, "seat_b")
        blob = json.dumps({"public_state": ob_b["public_state"],
                           "private_state": ob_b["private_state"],
                           "legal_actions": ob_b["legal_actions"]},
                          ensure_ascii=False)
        self.assertNotIn("揭示前不能", blob)                # 台词不漏
        self.assertNotIn(secret_fact, blob)                 # 钉出前的见闻不漏
        self.assertTrue(ob_b["public_state"]["submitted"]["seat_a"])
        # 对面自己的三条见闻齐全
        self.assertEqual(len(ob_b["private_state"]["facts"]), 3)


class TestBeatFlow(unittest.TestCase):
    def setUp(self):
        self.s = rules.new_game(SEATS, 3)

    def test_validations(self):
        s = self.s
        other_fact = first_fact(s, "seat_b")
        with self.assertRaises(rules.IllegalAction):   # 别人的见闻
            commit(s, "seat_a", other_fact, "推进", "conveyor")
        with self.assertRaises(rules.IllegalAction):   # 目标不存在
            commit(s, "seat_a", first_fact(s, "seat_a"), "推进", "moon")
        with self.assertRaises(rules.IllegalAction):   # 台词过长
            commit(s, "seat_a", first_fact(s, "seat_a"), "推进", "conveyor",
                   line="长" * 41)
        s2 = commit(s, "seat_a", first_fact(s, "seat_a"), "推进", "conveyor")
        with self.assertRaises(rules.IllegalAction):   # 一拍一交
            commit(s2, "seat_a", first_fact(s2, "seat_a"), "护持", "bell")

    def test_reveal_pins_and_stance_once(self):
        s = self.s
        fa, fb = first_fact(s, "seat_a"), first_fact(s, "seat_b")
        s = commit(s, "seat_a", fa, "推进", "conveyor")
        s = commit(s, "seat_b", fb, "转向", "clerk")
        self.assertEqual(len(s["pinned"]), 2)              # 双方见闻已上桌
        self.assertEqual(s["beat"], 2)
        self.assertNotIn("推进", s["stances_left"]["seat_a"])  # 姿态用掉
        self.assertNotIn("转向", s["stances_left"]["seat_b"])
        with self.assertRaises(rules.IllegalAction):       # 第二拍不能重用姿态
            commit(s, "seat_a", first_fact(s, "seat_a"), "推进", "bell")
        log = s["beats_log"][0]
        self.assertTrue(any("姿态咬合" in l for l in log["report"]))

    def test_pinned_boost_fires(self):
        """钉出的见闻,谁的行动踩中都生效;没钉出就没有效果。"""
        s = self.s
        # 找到地形视野持有者与 t-hatch(推进×conveyor -> progress+1)
        terrain_seat = next(x for x in SEATS if s["packets"][x] == "terrain")
        echo_seat = next(x for x in SEATS if x != terrain_seat)
        s["omens"] = ["顺势", "顺势", "顺势"]  # 排除余波干扰(测试直改牌面)
        s = commit(s, terrain_seat, "t-hatch", "推进", "conveyor")
        s = commit(s, echo_seat, "e-clerk", "转向", "clerk")
        # 推进+转向 = 进度+2 压力+1;t-hatch 与 e-clerk 本拍双双应验 => 进度4
        self.assertEqual(s["progress"], 4)
        self.assertTrue(any("见闻应验" in l for l in s["beats_log"][0]["report"]))

    def test_endorse_blocks_cost(self):
        s = self.s
        s["omens"] = ["代价", "顺势", "回声"]
        terrain_seat = next(x for x in SEATS if s["packets"][x] == "terrain")
        echo_seat = next(x for x in SEATS if x != terrain_seat)
        s = commit(s, terrain_seat, "t-chain", "推进", "hatch", endorse=True)
        s = commit(s, echo_seat, "e-clerk", "转向", "clerk")
        self.assertEqual(s["endorse_left"][terrain_seat], 0)
        log = s["beats_log"][0]
        self.assertTrue(any("被背书的信任挡下" in l for l in log["report"]))
        # 推进+转向:进度+2 压力+1;e-clerk(转向×clerk)应验 +1 进度;代价被挡
        self.assertEqual(s["progress"], 3)
        self.assertEqual(s["pressure"], 1)
        with self.assertRaises(rules.IllegalAction):       # 背书只有一次
            commit(s, terrain_seat, first_fact(s, terrain_seat),
                   "探明", "bell", endorse=True)

    def test_third_path_opens(self):
        s = self.s
        s["omens"] = ["顺势", "顺势", "顺势"]
        s = commit(s, "seat_a", first_fact(s, "seat_a"), "转向", "bell")
        s = commit(s, "seat_b", first_fact(s, "seat_b"), "探明", "clerk")
        self.assertIn("return-chute", s["objects_open"])
        self.assertTrue(any(p["fact"]["id"] == "path-open" for p in s["pinned"]))

    def test_peek_shows_next_omen(self):
        s = self.s
        s["omens"] = ["顺势", "代价", "回声"]
        s = commit(s, "seat_a", first_fact(s, "seat_a"), "护持", "bell")
        s = commit(s, "seat_b", first_fact(s, "seat_b"), "护持", "furnace")
        self.assertTrue(s["peeked"])
        ob = rules.observe(s, "seat_a")
        self.assertEqual(ob["public_state"]["omen_peek"], "代价")


class TestEndings(unittest.TestCase):
    def full_game(self, seed, plan):
        """plan: [(stance_a, target_a, stance_b, target_b), ...]"""
        s = rules.new_game(SEATS, seed)
        for sa, ta, sb, tb in plan:
            if s["phase"] != "playing":
                break
            s = commit(s, "seat_a", first_fact(s, "seat_a"), sa, ta)
            s = commit(s, "seat_b", first_fact(s, "seat_b"), sb, tb)
        return s

    def test_incomplete_then_memory(self):
        s = self.full_game(5, [("护持", "bell", "护持", "furnace"),
                               ("转向", "clerk", "转向", "bell")])
        # 护持+护持(压力-1,窥视)后 转向+转向(进度1 压力-1) → 第三拍
        self.assertEqual(s["phase"], "playing")
        s = commit(s, "seat_a", first_fact(s, "seat_a"), "探明", "bell")
        s = commit(s, "seat_b", first_fact(s, "seat_b"), "探明", "clerk")
        self.assertEqual(s["phase"], "finished")
        self.assertIn(s["ending"], ("incomplete", "success"))
        self.assertTrue(s["memory"]["text"])               # 世界记忆生成
        self.assertEqual(len(s["beats_log"]), 3)

    def test_pressure_ending(self):
        s = rules.new_game(SEATS, 7)
        s["pressure"] = 3
        s["omens"] = ["代价", "顺势", "回声"]
        s = commit(s, "seat_a", first_fact(s, "seat_a"), "推进", "conveyor")
        s = commit(s, "seat_b", first_fact(s, "seat_b"), "推进", "bell")
        # 推进+推进:压力+2,加代价 → 顶满 4,世界先行动
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["ending"], "pressure")
        self.assertIn("倾斜", s["memory"]["text"])

    def test_success_ending(self):
        s = rules.new_game(SEATS, 9)
        s["progress"] = 3
        s["omens"] = ["顺势", "回声", "代价"]
        terrain_seat = next(x for x in SEATS if s["packets"][x] == "terrain")
        echo_seat = next(x for x in SEATS if x != terrain_seat)
        s = commit(s, terrain_seat, "t-hatch", "推进", "conveyor",
                   line="停住传送带,门自己会开")
        s = commit(s, echo_seat, "e-clerk", "转向", "clerk",
                   line="我们来办退件")
        # 推进+转向 +2,t-hatch 应验 +1,e-clerk 应验 +1 → 3+4 → 封顶 5
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["ending"], "success")
        self.assertIn("出口", s["memory"]["text"])
        # 终局后不能再提交
        with self.assertRaises(rules.IllegalAction):
            commit(s, terrain_seat, "t-chain", "护持", "bell")


if __name__ == "__main__":
    unittest.main()
