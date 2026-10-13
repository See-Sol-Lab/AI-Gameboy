"""Synthetic postgame economy and last-shift arrival regression tests."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("night_postgame", Path(__file__).resolve().parents[1] / "cartridges/pocket-night-shop/rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


def shop():
    s = rules.new_game(["seat_a"], 23)
    s["start_funds_pending"] = False
    s["coins"] = 500
    s["shop_level"] = 3
    return s


class TestPostgame(unittest.TestCase):
    def test_exchange_requires_second_ending(self):
        for endings in ([], [{"id": "collection"}]):
            s = shop()
            s["endings"] = endings
            s["stardust"] = 50
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "exchange_resources", {"resource": "stardust", "amount": 50})
            self.assertNotIn("exchange_resources", rules.observe(s, "seat_a")["public_state"])

    def test_exchange_does_not_advance_time_or_customers(self):
        for resource, amount, payout in (("stardust", 50, 100), ("reputation", 99, 99)):
            s = shop()
            s["endings"] = [{"id": "true_ending"}]
            s[resource] = amount + 1
            before = deepcopy(s)
            out = rules.apply(s, "seat_a", "exchange_resources", {"resource": resource, "amount": amount})
            self.assertEqual(out[resource], 1)
            self.assertEqual(out["coins"], s["coins"] + payout)
            for key in ("day", "shift_index", "shift_count", "customer", "customer_book"):
                self.assertEqual(out[key], s[key])
            self.assertEqual(s, before)
            self.assertTrue(any(a["action_id"] == "exchange_resources" for a in rules._legal_actions(out)))

    def test_invalid_or_insufficient_exchange_is_rejected(self):
        s = shop()
        s["endings"] = [{"id": "true_ending"}]
        s["stardust"] = 5
        before = deepcopy(s)
        for resource, amount in (([], 1), ("coins", 1), ("stardust", True), ("stardust", 0), ("stardust", -1), ("stardust", 6)):
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "exchange_resources", {"resource": resource, "amount": amount})
            self.assertEqual(s, before)

    def test_special_arrival_after_last_shift_has_a_real_service_window(self):
        for focus in ("dismiss", "sell", "rejected_sale"):
            with self.subTest(focus=focus):
                s = shop()
                s["day"], s["shift_index"] = 141, rules.LAST_SHIFT
                old = next(c for c in rules.CUSTOMERS if c[0] == s["customer"]["id"])
                special = next(c for c in rules.CUSTOMERS if c[0] == "firstrain")
                params = {"focus": "dismiss"}
                if focus != "dismiss":
                    s["customer"]["_wants"] = [s["inventory"][0]["kind"]]
                    s["customer"]["patience"] = 1
                    params = {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 1 if focus == "sell" else 99999}
                number = rules._number
                def draw(seed, *parts):
                    return 1 if parts[0] == "customer" else number(seed, *parts)
                with patch.object(rules, "CUSTOMERS", [old, special]), patch.object(rules, "_number", side_effect=draw), patch.object(rules, "_maybe_event", return_value=""):
                    out = rules.apply(s, "seat_a", "work_shift", params)
                    self.assertEqual((out["day"], out["shift_index"]), (142, 0))
                    self.assertEqual(out["customer"]["id"], "firstrain")
                    self.assertEqual(out["customer"]["_arrived_day"], 142)
                    self.assertEqual(out["customer_book"]["firstrain"]["visits"], 1)
                    self.assertEqual(out["customer_count"], s["customer_count"] + 1)
                    self.assertNotIn("天亮前悄悄走了", out["history"][-1]["text"])
                    for _ in range(rules.OPEN_SHIFT):
                        out = rules.apply(out, "seat_a", "work_shift", {"focus": "tidy"})
                    self.assertEqual(rules._public_customer(out)["id"], "firstrain")
                    self.assertEqual(out["customer_book"]["firstrain"]["visits"], 1)
