"""夜铺0.3内容规模、等级门槛、有限来客与旧局边界。"""
import importlib.util
import json
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_rules(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = load_rules(ROOT / "cartridges/pocket-night-shop/rules.py", "night_expansion")
_raw_new_game = rules.new_game


def _funded_new_game(seats, seed):
    """旧测试按开局 12 枚古币写的:人类发令掷完后把钱定成 12。"""
    s = rules.apply(_raw_new_game(seats, seed), seats[0], "roll_start_funds", {"human_words": "掷"})
    s["coins"] = 12
    return s


rules.new_game = _funded_new_game


def free_event(state):
    if state["pending_event"]:
        event = rules.EVENTS[state["pending_event"]["kind"]]
        choice = next(key for key, option in event["choices"].items() if option["cost"] == 0)
        return rules.apply(state, "seat_a", "choose_event",
                           {"event_id": state["pending_event"]["id"], "choice": choice})
    return state


class TestNightExpansion(unittest.TestCase):
    def test_catalogue_sizes_and_cross_references(self):
        self.assertEqual(len(rules.ITEMS), 72)
        self.assertEqual(len({row[0] for row in rules.ITEMS}), 72)
        self.assertEqual(len({row[1] for row in rules.ITEMS}), 72)
        self.assertEqual(len({row[5] for row in rules.ITEMS}), 72)
        self.assertEqual(len(rules.CUSTOMERS), 86)
        self.assertEqual(len({row[0] for row in rules.CUSTOMERS}), 86)
        self.assertEqual(len({row[1] for row in rules.CUSTOMERS}), 86)
        self.assertEqual(len(rules.LOCATIONS), 6)
        self.assertEqual(len(rules.EVENTS), 18)
        self.assertEqual(len(rules.AMBIENT), 24)
        self.assertEqual(Counter(rules.ITEM_RARITY.values()),
                         {"common": 24, "uncommon": 20, "rare": 14, "ancient": 9, "heirloom": 5})
        codes = {row[0] for row in rules.ITEMS}
        self.assertEqual(set(rules.ITEM_KINDS), codes)
        self.assertEqual(set(rules.ITEM_RARITY), codes)
        self.assertEqual({code for loc in rules.LOCATIONS.values() for code in loc["pool"]}, codes)
        linked = {row[1] for row in rules.SPECIAL_CUSTOMERS.values()}
        self.assertEqual(linked, {code for code, rarity in rules.ITEM_RARITY.items()
                                 if rarity in ("ancient", "heirloom")})
        for customer in rules.CUSTOMERS:
            self.assertTrue(set(customer[4]) <= set(rules.ITEM_KINDS.values()))

    def test_tier_three_item_gate_applies_to_all_sources(self):
        s = rules.new_game(["seat_a"], 42)
        for level in (1, 2):
            s["shop_level"] = level
            for location in rules.LOCATIONS:
                for attempt in range(100):
                    item = rules._make_item(s, location, attempt)
                    self.assertNotIn(item["rarity"], ("ancient", "heirloom"))
        s["shop_level"] = 3
        found = {rules._make_item(s, "archive", attempt)["rarity"] for attempt in range(1000)}
        self.assertIn("ancient", found)
        self.assertIn("heirloom", found)
        s["pending_event"] = {"kind": "star_courier", "id": "delivery", "_location": "archive"}
        s["shop_level"] = 2
        s["coins"] = 100
        s = rules.apply(s, "seat_a", "choose_event", {"event_id": "delivery", "choice": "accept"})
        self.assertNotIn(s["inventory"][-1]["rarity"], ("ancient", "heirloom"))

    def test_every_customer_has_eight_lifetime_visits_and_pool_can_exhaust(self):
        s = rules.new_game(["seat_a"], 88)
        s["shop_level"] = 5
        s["unlocked_locations"] = list(rules.LOCATIONS)
        while s["customer"] is not None:
            self.assertLessEqual(s["customer"]["visits"], 8)
            rules._spawn_customer(s)
        self.assertEqual(s["customer_count"], 86 * 8)
        self.assertEqual(len(s["customer_book"]), 86)
        self.assertTrue(all(row["visits"] == 8 for row in s["customer_book"].values()))
        before = deepcopy(s)
        rules._spawn_customer(s)
        self.assertEqual(s, before)
        view = rules.observe(s, "seat_a")
        self.assertIsNone(view["public_state"]["customer"])
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertEqual(s["shift_count"], 1)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "work_shift", {"focus": "dismiss"})

    def test_special_customers_unlock_without_resetting_normal_visits(self):
        s = rules.new_game(["seat_a"], 15)
        s["unlocked_locations"] = list(rules.LOCATIONS)
        while s["customer"] is not None:
            self.assertNotIn(s["customer"]["id"], rules.SPECIAL_CUSTOMERS)
            rules._spawn_customer(s)
        self.assertEqual(s["customer_count"], 72 * 8)
        s["shop_level"], s["coins"] = 2, 100
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "upgrade"})
        self.assertEqual(s["shop_level"], 3)
        self.assertIn(s["customer"]["id"], rules.SPECIAL_CUSTOMERS)
        self.assertTrue(all(row["visits"] == 8 for key, row in s["customer_book"].items()
                            if key not in rules.SPECIAL_CUSTOMERS))

    def test_special_customer_rejects_same_kind_substitute(self):
        s = rules.new_game(["seat_a"], 30)
        s["shop_level"] = 3
        while not s["customer"]["special"]:
            rules._spawn_customer(s)
        wanted = s["customer"]["_item_code"]
        substitute = next(row for row in rules.ITEMS if row[0] != wanted
                          and rules.ITEM_KINDS[row[0]] == rules.ITEM_KINDS[wanted])
        s["inventory"][0].update(code=substitute[0], kind=rules.ITEM_KINDS[wanted])
        before = s["customer"]["id"]
        s = rules.apply(s, "seat_a", "work_shift",
                        {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 1})
        self.assertEqual(s["customer"]["id"], before)
        self.assertIn("不合需要", s["history"][-1]["text"])
        s = free_event(s)
        s["inventory"][0]["code"] = wanted
        s = rules.apply(s, "seat_a", "work_shift",
                        {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 1})
        self.assertEqual(s["customer_book"][before]["deals"], 1)

    def test_five_shop_levels_have_affordable_idle_maintenance(self):
        s = rules.new_game(["seat_a"], 20)
        s["coins"] = 1000
        for level in range(2, 6):
            s = free_event(s)
            s = rules.apply(s, "seat_a", "work_shift", {"focus": "upgrade"})
            self.assertEqual(s["shop_level"], level)
        s = free_event(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "work_shift", {"focus": "upgrade"})
        s["coins"], s["shift_index"] = 0, 1
        s = rules.apply(s, "seat_a", "run_shifts", {"focus": "tidy", "count": 1, "reserve": 0})
        self.assertEqual(s["last_run"]["completed"], 1)
        self.assertEqual(s["diary"][-1]["upkeep"], 5)

    def test_witch_lilith_trades_after_fourth_place(self):
        self.assertTrue(any(rules.ITEM_RARITY.get(r[0]) in ("ancient", "heirloom") for r in rules.ITEMS))
        s = rules.new_game(["seat_a"], 3)
        s["coins"], s["shop_level"] = 500, 5
        s["unlocked_locations"] = ["lane", "station", "dock"]
        spot = rules._witch_spot(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": spot})
        self.assertIsNone(rules.observe(s, "seat_a")["public_state"]["witch"])    # 三张图时没有魔女
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [s["inventory"][0]["id"]]})
        s["unlocked_locations"] = ["lane", "station", "dock", "arcade"]
        while s["pending_event"]:
            s = rules.apply(s, "seat_a", "choose_event", {"event_id": s["pending_event"]["id"], "choice": next(
                k for k, o in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items() if o["cost"] == 0)})
        spot = rules._witch_spot(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": spot})
        view = rules.observe(s, "seat_a")["public_state"]["witch"]
        self.assertIsNotNone(view)
        self.assertIn("魔女莉莉丝", s["history"][-1]["text"])
        a, b, c = (x["id"] for x in s["inventory"][:3])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [a, b, c]})       # 一次最多2件
        item = s["inventory"][0]
        before = s["coins"]
        s = rules.apply(s, "seat_a", "witch_sell", {"item_ids": [a]})
        expect = max(1, int(item["value"] * (0.8 if view["discount"] else 0.2)))
        self.assertEqual(s["coins"] - before, expect)
        s = rules.apply(s, "seat_a", "witch_sell", {"item_ids": [b]})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [c]})
        # 每10班进一件3级以上宝物,买下后进库存
        while not s["witch"]["stock"]:
            s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
            while s["pending_event"]:
                s = rules.apply(s, "seat_a", "choose_event", {"event_id": s["pending_event"]["id"], "choice": next(
                    k for k, o in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items() if o["cost"] == 0)})
        treasure = s["witch"]["stock"][0]
        self.assertIn(treasure["rarity"], ("ancient", "heirloom"))
        self.assertIsNone(rules.observe(s, "seat_a")["public_state"]["witch"])    # 下一班她就走了
        s["day"] += 0
        spot = rules._witch_spot(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": spot})
        if s["witch"]["visit"]:
            s = rules.apply(s, "seat_a", "witch_buy", {"item_id": treasure["id"]})
            self.assertIn(treasure["id"], [x["id"] for x in s["inventory"]])
        # 金苹果:每20班一半机会出现,持有2班
        apples = sum(rules._number(seed, "witch_apple", 20) % 2 == 0 for seed in range(200))
        self.assertTrue(60 < apples < 140)

    def test_neighbors_are_whoever_came_before_third_place(self):
        s = rules.new_game(["seat_a"], 7)
        for _ in range(30):
            rules._spawn_customer(s)
            self.assertIsNotNone(s["customer"]["request"])
        met = set(s["customer_book"])
        self.assertTrue(all(row["neighbor"] for row in s["customer_book"].values()))
        s["unlocked_locations"].append("dock")
        seen = {}
        while not any(len(v) >= 6 for v in seen.values()):
            rules._spawn_customer(s)
            c = s["customer"]
            if c["id"] in met:
                self.assertIsNotNone(c["request"])          # 老街坊到哪都直说
            elif c["id"] not in rules.SPECIAL_CUSTOMERS:
                seen.setdefault(c["id"], []).append(c["request"])
        stranger = next(v for v in seen.values() if len(v) >= 6)
        self.assertTrue(all(r is None for r in stranger[:4]) and all(stranger[4:]))
        self.assertFalse(s["customer_book"][next(k for k, v in seen.items() if len(v) >= 6)]["neighbor"])
        fresh = rules.new_game(["seat_a"], 7)                # 下一局清零重来
        self.assertEqual(len(fresh["customer_book"]), 1)
        self.assertIn("clue", rules.observe(s, "seat_a")["public_state"]["customer"]["hint"])

    def test_all_event_choices_have_a_free_exit_and_public_outcome(self):
        for kind, event in rules.EVENTS.items():
            if "choices" not in event:
                continue
            self.assertTrue(any(option["cost"] == 0 for option in event["choices"].values()))
            for choice in event["choices"]:
                s = rules.new_game(["seat_a"], 2)
                s["shop_level"], s["coins"] = 5, 100
                s["pending_event"] = {"kind": kind, "id": "fixture", "_location": "lane"}
                s = rules.apply(s, "seat_a", "choose_event", {"event_id": "fixture", "choice": choice})
                self.assertIsNone(s["pending_event"])
                self.assertIn(choice, s["encounters"][kind]["outcomes"])
                self.assertTrue(s["history"][-1]["text"])


    def test_spending_days_does_not_count_as_customer_arrivals(self):
        s = rules.new_game(["seat_a"], 6)
        customer = deepcopy(s["customer"])
        visits = s["customer_count"]
        for _ in range(24):
            s = free_event(s)
            s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertEqual(s["customer"], customer)
        self.assertEqual(s["customer_count"], visits)



if __name__ == "__main__":
    unittest.main()
