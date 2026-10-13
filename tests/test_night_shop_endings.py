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

    def test_true_ending_requires_every_secret_not_guests_or_inventory(self):
        self.fill(secrets=True)
        self.state["customer_book"] = {}
        self.state["collection"][rules.ITEMS[0][0]]["revealed"] = None
        rules._check_endings(self.state)
        self.assertEqual(len(self.state["endings"]), 1)
        self.assertFalse(rules._check_endings(self.state))
        self.state["collection"][rules.ITEMS[0][0]]["revealed"] = "repaired"
        self.state["inventory"] = []
        self.assertTrue(rules._check_endings(self.state))
        self.assertEqual(self.state["endings"][-1]["id"], "true_ending")
        self.assertEqual(self.state["phase"], "playing")
        self.assertFalse(rules._check_endings(self.state))

    def test_old_save_catches_up_on_reopen_and_persists(self):
        self.fill(secrets=True)
        self.state["customer_book"] = {}
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

    def test_waiting_item_is_visible_only_after_true_ending(self):
        s = self.state
        s["shift_index"] = rules.OPEN_SHIFT
        cid = next(iter(rules.BOND_LINES))
        code = rules.BOND_LINES[cid][0]
        expected_name = next(row[1] for row in rules.ITEMS if row[0] == code)
        s["customer"] = {"id": cid, "name": "测试来客", "_item_code": code}
        s["customer_book"] = {cid: {"id": cid, "name": "测试来客", "visits": 1}}
        for endings in ([], [{"id": "collection"}]):
            s["endings"] = endings
            view = rules.observe(s, "seat_a")["public_state"]
            self.assertNotIn("waiting_item", view["customer"])
            self.assertNotIn("waiting_item", view["customer_book"][0])
        s["endings"].append({"id": "true_ending"})
        original = deepcopy(s)
        view = rules.observe(s, "seat_a")["public_state"]
        expected = {"code": code, "name": expected_name, "required_condition": 3}
        self.assertEqual(view["customer"]["waiting_item"], expected)
        self.assertEqual(view["customer_book"][0]["waiting_item"], expected)
        self.assertNotIn("_item_code", view["customer"])
        self.assertEqual(s, original)
        self.assertEqual(rules._waiting_item(s, "unmapped_guest"), {})

    def test_congratulations_use_only_known_guests(self):
        self.fill()
        known = [row["name"] for row in self.state["customer_book"].values()]
        rules._check_endings(self.state)
        self.assertTrue(all(name in self.state["endings"][0]["paragraphs"][2] for name in known))

    def test_summon_goods_is_paid_exactly_and_does_not_advance_time(self):
        s = self.state
        s["coins"] = 200
        self.fill()
        rules._check_endings(s)
        for row in s["collection"].values():
            row["count"] = 0
        before = deepcopy(s)
        out = rules.apply(s, "seat_a", "summon_goods", {"code": "buttonjar"})
        self.assertEqual(out["coins"], 101)
        self.assertEqual(out["inventory"][-1]["code"], "buttonjar")
        self.assertEqual(out["item_counter"], s["item_counter"] + 1)
        for key in ("day", "shift_index", "shift_count", "customer_count", "customer_book"):
            self.assertEqual(out[key], s[key])
        self.assertEqual(s, before)
        self.assertTrue(any(a["action_id"] == "summon_goods" for a in rules._legal_actions(out)))

    def test_summon_goods_rejects_without_payment_and_preserves_repair_progress(self):
        s = self.state
        s["coins"] = 200
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "summon_goods", {"code": "buttonjar"})
        self.fill(secrets=True)
        rules._check_endings(s)
        for row in s["collection"].values():
            row["count"] = 0
        out = rules.apply(s, "seat_a", "summon_goods", {"code": "buttonjar"})
        self.assertEqual(out["inventory"][-1]["condition"], 3)
        self.assertTrue(out["inventory"][-1]["pre_repaired"])
        for bad in ("not_an_item", [], None):
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "summon_goods", {"code": bad})
        s["coins"] = 98
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "summon_goods", {"code": "buttonjar"})
        self.assertEqual(s["coins"], 98)
        s["coins"] = 200
        s["inventory"] = s["inventory"] * rules._capacity(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "summon_goods", {"code": "buttonjar"})
        self.assertEqual(s["coins"], 200)

    def test_collection_summon_notice(self):
        self.assertNotIn("summon_goods", rules.observe(self.state, "seat_a")["public_state"])
        self.state["endings"] = [{"id": "collection"}]
        self.assertIn("99", rules.observe(self.state, "seat_a")["public_state"]["summon_goods"])

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
