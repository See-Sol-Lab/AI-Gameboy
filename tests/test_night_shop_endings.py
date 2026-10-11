"""Synthetic milestone fixtures: no real saves or hidden plot in client commands."""
import importlib.util
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("night_endings", ROOT / "cartridges/pocket-night-shop/rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class TestEndings(unittest.TestCase):
    def setUp(self):
        self.state = rules.new_game(["seat_a"], 23)
        self.state["start_funds_pending"] = False

    def fill(self, secrets=False, guests=False):
        self.state["collection"] = {code: {"revealed": "a repaired secret" if secrets else None}
                                    for code, *_ in rules.ITEMS}
        if guests:
            self.state["customer_book"] = {c[0]: {"name": c[1], "visits": 1} for c in rules.CUSTOMERS}

    def test_collection_reward_is_once_and_does_not_change_economy(self):
        self.fill()
        before = deepcopy(self.state)
        self.assertTrue(rules._check_endings(self.state))
        scene = self.state["endings"][0]
        self.assertEqual(scene["id"], "collection")
        self.assertEqual(scene["reward"], "没有背面的店主铭牌")
        self.assertGreater(len(scene["paragraphs"]), 3)
        for key in ("coins", "reputation", "inventory", "customer_book", "phase"):
            self.assertEqual(self.state[key], before[key])
        self.assertFalse(rules._check_endings(self.state))
        self.assertEqual(len(self.state["endings"]), 1)

    def test_true_ending_requires_every_secret_and_guest_not_inventory(self):
        self.fill(secrets=True, guests=True)
        missing = self.state["customer_book"].pop(rules.CUSTOMERS[-1][0])
        rules._check_endings(self.state)
        self.assertEqual(len(self.state["endings"]), 1)
        self.state["customer_book"][rules.CUSTOMERS[-1][0]] = missing
        self.state["collection"][rules.ITEMS[0][0]]["revealed"] = None
        self.assertFalse(rules._check_endings(self.state))
        self.state["collection"][rules.ITEMS[0][0]]["revealed"] = "repaired"
        self.state["inventory"] = []
        self.assertTrue(rules._check_endings(self.state))
        self.assertEqual(self.state["endings"][-1]["id"], "true_ending")
        self.assertEqual(self.state["phase"], "playing")
        self.assertFalse(rules._check_endings(self.state))

    def test_old_save_catches_up_on_reopen_and_persists(self):
        self.fill(secrets=True, guests=True)
        self.state.pop("endings")
        self.state["resting"] = True
        restored = rules.apply(self.state, "seat_a", "reopen_shop", {})
        self.assertEqual([x["id"] for x in restored["endings"]], ["collection", "true_ending"])
        closed = rules.apply(restored, "seat_a", "close_for_now", {})
        self.assertEqual(closed["endings"], restored["endings"])

    def test_unearned_endings_are_not_exposed(self):
        view = rules.observe(self.state, "seat_a")["public_state"]
        self.assertEqual(view["endings"], [])
        self.assertFalse(view["completion"]["true_ending"])

    def test_congratulations_use_only_known_guests(self):
        self.fill()
        known = [row["name"] for row in self.state["customer_book"].values()]
        rules._check_endings(self.state)
        self.assertTrue(all(name in self.state["endings"][0]["paragraphs"][2] for name in known))

    def test_batch_stops_at_ending_even_with_no_optional_stops(self):
        self.fill()
        self.state["coins"] = 100
        with patch.object(rules, "_maybe_event", return_value=""):
            result = rules.apply(self.state, "seat_a", "run_shifts",
                                 {"focus": "tidy", "count": 6, "stop_on": []})
        self.assertEqual(result["last_run"]["completed"], 1)
        self.assertEqual(result["last_run"]["stop_reason"], "ending")
        self.assertEqual(result["endings"][0]["id"], "collection")

    def test_stock_tutorial_is_logged_once_at_opening(self):
        state = rules.new_game(["seat_a"], 23)
        state = rules.apply(state, "seat_a", "roll_start_funds", {"human_words": "掷"})
        self.assertIn("scavenge", state["history"][0]["text"])
        state = rules.apply(state, "seat_a", "work_shift", {"focus": "tidy"})
        state = rules.apply(state, "seat_a", "close_for_now", {})
        state = rules.apply(state, "seat_a", "reopen_shop", {})
        self.assertEqual(sum(rules.STARTER_STOCK_HINT in row["text"] for row in state["history"]), 1)
