"""《口袋电路》纯规则测试:发牌、暗投、揭示、计分、终局与非法动作。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cartridges" / "pocket-circuit"))
import rules  # noqa: E402

SEATS = ["seat_a", "seat_b"]


class TestDeal(unittest.TestCase):
    def test_deterministic_by_seed(self):
        self.assertEqual(rules.new_game(SEATS, 42), rules.new_game(SEATS, 42))

    def test_hands_disjoint_and_complete(self):
        for seed in range(30):
            s = rules.new_game(SEATS, seed)
            a, b = s["hands"]["seat_a"], s["hands"]["seat_b"]
            self.assertEqual(len(a), 3)
            self.assertEqual(len(b), 3)
            self.assertEqual(sorted(a + b), [1, 2, 3, 4, 5, 6])

    def test_two_players_only(self):
        with self.assertRaises(ValueError):
            rules.new_game(["x"], 1)


class TestPlay(unittest.TestCase):
    def setUp(self):
        self.s = rules.new_game(SEATS, 7)

    def play_round(self, s, ca, cb):
        s = rules.apply(s, "seat_a", "play_card", {"card": ca})
        return rules.apply(s, "seat_b", "play_card", {"card": cb})

    def test_pending_then_reveal(self):
        ca = self.s["hands"]["seat_a"][0]
        s = rules.apply(self.s, "seat_a", "play_card", {"card": ca})
        self.assertEqual(s["pending"], {"seat_a": ca})
        self.assertEqual(s["revealed"], [])
        cb = s["hands"]["seat_b"][0]
        s = rules.apply(s, "seat_b", "play_card", {"card": cb})
        self.assertEqual(s["pending"], {})
        self.assertEqual(len(s["revealed"]), 1)
        r = s["revealed"][0]
        self.assertEqual(r["cards"], {"seat_a": ca, "seat_b": cb})
        self.assertEqual(r["winner"], "seat_a" if ca > cb else "seat_b")
        self.assertNotIn(ca, s["hands"]["seat_a"])
        self.assertNotIn(cb, s["hands"]["seat_b"])
        self.assertEqual(s["round"], 2)

    def test_three_rounds_finish_and_scores(self):
        s = self.s
        for _ in range(3):
            s = self.play_round(s, s["hands"]["seat_a"][0], s["hands"]["seat_b"][0])
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["round"], 3)
        self.assertEqual(s["scores"]["seat_a"] + s["scores"]["seat_b"], 3)
        wins = sum(1 for r in s["revealed"] if r["winner"] == "seat_a")
        self.assertEqual(s["scores"]["seat_a"], wins)
        self.assertNotEqual(s["scores"]["seat_a"], s["scores"]["seat_b"])

    def test_original_state_not_mutated(self):
        before = rules.new_game(SEATS, 7)
        rules.apply(before, "seat_a", "play_card", {"card": before["hands"]["seat_a"][0]})
        self.assertEqual(before, rules.new_game(SEATS, 7))

    def test_illegal_actions(self):
        s = self.s
        with self.assertRaises(rules.IllegalAction):  # 不存在的动作
            rules.apply(s, "seat_a", "dance", {})
        with self.assertRaises(rules.IllegalAction):  # 牌不在手里
            rules.apply(s, "seat_a", "play_card",
                        {"card": s["hands"]["seat_b"][0]})
        with self.assertRaises(rules.IllegalAction):  # card 类型不对
            rules.apply(s, "seat_a", "play_card", {"card": "3"})
        with self.assertRaises(rules.IllegalAction):  # bool 不算整数
            rules.apply(s, "seat_a", "play_card", {"card": True})
        s2 = rules.apply(s, "seat_a", "play_card", {"card": s["hands"]["seat_a"][0]})
        with self.assertRaises(rules.IllegalAction):  # 一轮内重复暗投
            rules.apply(s2, "seat_a", "play_card", {"card": s2["hands"]["seat_a"][0]})
        done = s
        for _ in range(3):
            done = self.play_round(done, done["hands"]["seat_a"][0],
                                   done["hands"]["seat_b"][0])
        with self.assertRaises(rules.IllegalAction):  # 终局后不能再出牌
            rules.apply(done, "seat_a", "play_card", {"card": 1})


class TestObserve(unittest.TestCase):
    def test_winner_only_when_finished(self):
        s = rules.new_game(SEATS, 3)
        self.assertNotIn("winner", rules.observe(s, "seat_a")["public_state"])
        for _ in range(3):
            s = rules.apply(s, "seat_a", "play_card", {"card": s["hands"]["seat_a"][0]})
            s = rules.apply(s, "seat_b", "play_card", {"card": s["hands"]["seat_b"][0]})
        ob = rules.observe(s, "seat_a")
        self.assertIn(ob["public_state"]["winner"], SEATS)
        self.assertEqual(ob["legal_actions"], [])


if __name__ == "__main__":
    unittest.main()
