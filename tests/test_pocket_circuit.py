"""《口袋电路》v0.2:对称手牌、节点竞标、人类先锁与平局蓄能。"""

import importlib.util
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pocket_circuit_rules",
    Path(__file__).resolve().parents[1] / "cartridges" / "pocket-circuit" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SEATS = ["seat_a", "seat_b"]


class TestDeal(unittest.TestCase):
    def test_deterministic_by_seed(self):
        self.assertEqual(rules.new_game(SEATS, 42), rules.new_game(SEATS, 42))

    def test_both_players_get_same_complete_voltage_hand(self):
        s = rules.new_game(SEATS, 4)
        self.assertEqual(s["hands"]["seat_a"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(s["hands"]["seat_b"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(sorted(s["node_order"]), [1, 2, 3, 4, 5, 6])

    def test_two_players_only(self):
        with self.assertRaises(ValueError):
            rules.new_game(["x"], 1)


class TestPlay(unittest.TestCase):
    def setUp(self):
        self.s = rules.new_game(SEATS, 7)

    @staticmethod
    def play_round(s, human_card, ai_card):
        s = rules.apply(s, "seat_b", "play_card", {"card": human_card})
        return rules.apply(s, "seat_a", "play_card", {"card": ai_card})

    def test_human_seat_locks_first_then_ai_reveals_atomically(self):
        with self.assertRaises(rules.IllegalAction):
            rules.apply(self.s, "seat_a", "play_card", {"card": 6})
        s = rules.apply(self.s, "seat_b", "play_card", {"card": 2})
        self.assertEqual(s["pending"], {"seat_b": 2})
        self.assertEqual(s["revealed"], [])
        ai_ob = rules.observe(s, "seat_a")
        self.assertTrue(ai_ob["public_state"]["submitted"]["seat_b"])
        self.assertIsNone(ai_ob["private_state"]["my_pending"])
        self.assertEqual(ai_ob["public_state"]["revealed"], [])
        self.assertEqual(ai_ob["waiting_for"], ["seat_a"])
        s = rules.apply(s, "seat_a", "play_card", {"card": 5})
        self.assertEqual(s["pending"], {})
        self.assertEqual(s["revealed"][0]["cards"], {"seat_a": 5, "seat_b": 2})

    def test_tie_carries_stake_into_next_node(self):
        first_node = self.s["current_node"]
        s = self.play_round(self.s, 3, 3)
        self.assertIsNone(s["revealed"][0]["winner"])
        self.assertEqual(s["revealed"][0]["points"], 0)
        self.assertEqual(s["stake"], first_node + s["current_node"])
        carried = s["stake"]
        s = self.play_round(s, 1, 6)
        self.assertEqual(s["revealed"][1]["points"], carried)
        self.assertEqual(s["scores"]["seat_a"], carried)

    def test_six_rounds_finish_and_use_every_card(self):
        s = self.s
        for card in [1, 2, 3, 4, 5, 6]:
            s = self.play_round(s, card, 7 - card)
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(s["round"], 6)
        self.assertEqual(s["hands"], {"seat_a": [], "seat_b": []})
        self.assertEqual(len(s["revealed"]), 6)
        self.assertLessEqual(sum(s["scores"].values()), sum(rules.NODE_VALUES))

    def test_original_state_not_mutated(self):
        before = rules.new_game(SEATS, 7)
        rules.apply(before, "seat_b", "play_card", {"card": 1})
        self.assertEqual(before, rules.new_game(SEATS, 7))

    def test_illegal_actions(self):
        with self.assertRaises(rules.IllegalAction):
            rules.apply(self.s, "seat_b", "dance", {})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(self.s, "seat_b", "play_card", {"card": 7})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(self.s, "seat_b", "play_card", {"card": "3"})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(self.s, "seat_b", "play_card", {"card": True})
        done = self.s
        for card in [1, 2, 3, 4, 5, 6]:
            done = self.play_round(done, card, 7 - card)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(done, "seat_b", "play_card", {"card": 1})


class TestObserve(unittest.TestCase):
    def test_only_expected_seat_has_legal_action(self):
        s = rules.new_game(SEATS, 3)
        human = rules.observe(s, "seat_b")
        ai = rules.observe(s, "seat_a")
        self.assertEqual(human["legal_actions"][0]["action_id"], "play_card")
        self.assertEqual(ai["legal_actions"], [])
        self.assertEqual(human["waiting_for"], ["seat_b"])

    def test_draw_has_no_winner(self):
        s = rules.new_game(SEATS, 3)
        for card in [1, 2, 3, 4, 5, 6]:
            s = TestPlay.play_round(s, card, card)
        ob = rules.observe(s, "seat_a")
        self.assertIsNone(ob["public_state"]["winner"])
        self.assertEqual(ob["legal_actions"], [])


if __name__ == "__main__":
    unittest.main()
