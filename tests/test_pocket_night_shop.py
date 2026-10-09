"""当前夜铺：收集、自动事件、单人批量行动和存档边界。"""
import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("night_v2", ROOT / "cartridges/pocket-night-shop/rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)
_raw_new_game = rules.new_game


def _funded_new_game(seats, seed):
    """旧测试按开局 12 枚古币写的:开局后替人类登记 12。"""
    return rules.apply(_raw_new_game(seats, seed), seats[0], "set_start_funds", {"amount": 12})


rules.new_game = _funded_new_game
SEATS = ["seat_a"]


def work(s, focus="tidy", **params):
    return rules.apply(s, "seat_a", "work_shift", {"focus": focus, **params})


def resolve(s):
    if s["pending_event"]:
        key = s["pending_event"]["kind"]
        choice = next(option_id for option_id, option in rules.EVENTS[key]["choices"].items()
                      if option["cost"] == 0)
        return rules.apply(s, "seat_a", "choose_event",
                           {"event_id": s["pending_event"]["id"], "choice": choice})
    return s


def pending_game():
    s = rules.new_game(SEATS, 5)
    for _ in range(80):
        if s["pending_event"]:
            options = rules.EVENTS[s["pending_event"]["kind"]]["choices"].values()
            if any(option["cost"] > 0 for option in options):
                return s
            s = resolve(s)
        s = work(s)
    raise AssertionError("固定种子没有产生选择事件")


class TestNightShop(unittest.TestCase):
    def test_single_player_and_determinism(self):
        s = rules.new_game(SEATS, 3)
        self.assertEqual(s, rules.new_game(SEATS, 3))
        with self.assertRaises(ValueError):
            rules.new_game(["seat_a", "seat_b"], 3)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_b", "work_shift", {"focus": "tidy"})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "knock", {})

    def test_discovery_is_permanent_after_sale_and_recycling(self):
        s = rules.new_game(SEATS, 3)
        item = s["inventory"][0]
        code = item["code"]
        before = deepcopy(s["collection"][code])
        s["customer"]["_wants"] = [item["kind"]]
        s = work(s, "sell", item_id=item["id"], asking_price=1)
        self.assertEqual(s["collection"][code], before)
        s = resolve(s)
        for item in list(s["inventory"]):
            s = resolve(work(s, "recycle", item_id=item["id"]))
        self.assertEqual(s["inventory"], [])
        self.assertGreater(len(s["collection"]), 0)

    def test_repeated_item_counts_without_repeating_first_bonus(self):
        s = rules.new_game(SEATS, 3)
        item = deepcopy(s["inventory"][0])
        row = s["collection"][item["code"]]
        coins, count = s["coins"], row["count"]
        item["id"] = "repeat_fixture"
        self.assertFalse(rules._collect(s, item))
        self.assertEqual(s["coins"], coins)
        self.assertEqual(row["count"], count + 1)

    def test_repair_secret_only_revealed_at_completion_and_survives_sale(self):
        s = rules.new_game(SEATS, 7)
        item = s["inventory"][0]
        secret = item["_secret"]
        for seat in s["seats"]:
            self.assertNotIn(secret, json.dumps(rules.observe(s, seat), ensure_ascii=False))
        while next(x for x in s["inventory"] if x["id"] == item["id"])["condition"] < 3:
            s = resolve(work(s, "repair", item_id=item["id"]))
        self.assertEqual(s["collection"][item["code"]]["revealed"], secret)
        s = work(s, "recycle", item_id=item["id"])
        self.assertEqual(s["collection"][item["code"]]["revealed"], secret)

    def test_unseen_names_and_secrets_not_in_observation(self):
        s = rules.new_game(SEATS, 2)
        blob = json.dumps(rules.observe(s, "seat_a"), ensure_ascii=False)
        for code, name, story, condition, value, secret in rules.ITEMS:
            self.assertNotIn(secret, blob)
            if code not in s["collection"]:
                self.assertNotIn(name, blob)
        for key in ("_wants", "_budget", "_secret"):
            self.assertNotIn(key, blob)
        self.assertNotIn("door_signal", blob)

    def test_location_pools_and_undiscovered_counts(self):
        s = rules.new_game(SEATS, 4)
        for key, loc in rules.LOCATIONS.items():
            observed = next(row for row in rules.observe(s, "seat_a")["public_state"]["locations"]
                            if row["id"] == key)
            self.assertEqual(observed["undiscovered"],
                             len(set(loc["pool"]) - set(s["collection"])))
            for i in range(30):
                self.assertIn(rules._make_item(s, key, i)["code"], loc["pool"])

    def test_unlock_requires_progress_and_payment(self):
        s = rules.new_game(SEATS, 1)
        before = deepcopy(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "unlock_location", {"location": "dock"})
        self.assertEqual(s, before)
        while len(s["collection"]) < 4:
            rules._collect(s, rules._make_item(s, "lane", "fixture"))
        s["coins"] = 20
        s = rules.apply(s, "seat_a", "unlock_location", {"location": "station"})
        self.assertEqual(s["coins"], 12)
        self.assertIn("station", s["unlocked_locations"])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "unlock_location", {"location": "station"})
        with self.assertRaises(rules.IllegalAction):
            work(s, "scavenge", location="dock")

    def test_automatic_events_and_choices_require_no_human(self):
        s = pending_game()
        key, event_id = s["pending_event"]["kind"], s["pending_event"]["id"]
        self.assertIn(key, s["encounters"])
        view = rules.observe(s, "seat_a")
        self.assertEqual(view["waiting_for"], ["seat_a"])
        self.assertEqual(view["legal_actions"][0]["action_id"], "choose_event")
        self.assertNotIn('"_location"', json.dumps(view))
        with self.assertRaises(rules.IllegalAction):
            work(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_event", {"event_id": "wrong", "choice": "leave"})
        s = resolve(s)
        self.assertIsNone(s["pending_event"])
        self.assertTrue(s["encounters"][key]["outcomes"])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_event", {"event_id": event_id, "choice": "leave"})

    def test_event_free_choice_works_without_cash_or_space(self):
        s = pending_game()
        s["coins"] = 0
        while len(s["inventory"]) < rules._capacity(s):
            s["inventory"].append(deepcopy(s["inventory"][0]))
        view = rules.observe(s, "seat_a")["public_state"]["pending_event"]
        self.assertTrue(any(c["available"] and c["cost"] == 0 for c in view["choices"]))
        paid = next(option_id for option_id, option in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items()
                    if option["cost"] > 0)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_event",
                        {"event_id": s["pending_event"]["id"], "choice": paid})
        self.assertIsNone(resolve(s)["pending_event"])

    def test_event_alternate_outcomes_are_collected_separately(self):
        s = pending_game()
        key = s["pending_event"]["kind"]
        s = resolve(s)
        s["pending_event"] = {"kind": key, "id": "another_visit", "_location": "lane"}
        s["coins"] = 30
        paid = next(option_id for option_id, option in rules.EVENTS[key]["choices"].items()
                    if option["cost"] > 0)
        s = rules.apply(s, "seat_a", "choose_event", {"event_id": "another_visit", "choice": paid})
        self.assertEqual(len(s["encounters"][key]["outcomes"]), 2)

    def test_batch_and_singles_have_identical_gameplay(self):
        s = rules.new_game(SEATS, 13)
        batch = rules.apply(s, "seat_a", "run_shifts",
                            {"focus": "tidy", "count": 6, "stop_on": []})
        single = deepcopy(s)
        for _ in range(batch["last_run"]["completed"]):
            single = work(single)
        batch["last_run"] = None
        self.assertEqual(single, batch)

    def test_batch_stops_on_decision_even_when_stop_list_is_empty(self):
        for seed in range(50):
            s = rules.apply(rules.new_game(SEATS, seed), "seat_a", "run_shifts",
                            {"focus": "tidy", "count": 6, "stop_on": []})
            if s["pending_event"]:
                self.assertEqual(s["last_run"]["stop_reason"], "decision")
                # 第一条是开局登记启动资金
                self.assertEqual(len(s["history"]) - 1, s["last_run"]["completed"])
                break
        else:
            self.fail("没有找到固定的事件种子")

    def test_batch_new_discovery_and_rare_stops(self):
        for marker in ("new", "rare"):
            found = False
            for seed in range(150):
                s = rules.new_game(SEATS, seed)
                s["coins"] = 200
                s["extra_capacity"] = 50
                s["unlocked_locations"].append("station")
                s = rules.apply(s, "seat_a", "run_shifts", {
                    "focus": "scavenge", "location": "station", "count": 6, "stop_on": [marker]})
                if s["last_run"]["stop_reason"] == marker:
                    self.assertTrue(s["history"][-1][marker])
                    found = True
                    break
            self.assertTrue(found, marker)

    def test_batch_cash_floor_includes_upkeep_and_preserves_earlier_results(self):
        seed = next(i for i in range(100) if rules._number(i, "event", 1) % 4)
        s = rules.new_game(SEATS, seed)
        s["coins"] = 8
        with self.assertRaisesRegex(rules.IllegalAction, "保留线"):
            rules.apply(s, "seat_a", "run_shifts",
                        {"focus": "scavenge", "count": 6, "reserve": 9, "stop_on": []})
        s["coins"] = 10
        result = rules.apply(s, "seat_a", "run_shifts",
                             {"focus": "scavenge", "count": 6, "reserve": 9, "stop_on": []})
        self.assertEqual(result["last_run"]["completed"], 1)
        self.assertEqual(result["last_run"]["stop_reason"], "reserve")
        self.assertEqual(result["shift_count"], 1)

    def test_batch_stop_on_string_matches_single_element_list(self):
        for marker in ("new", "rare", "event"):
            with self.subTest(stop_on=marker):
                s = rules.new_game(SEATS, 13)
                self.assertEqual(
                    rules.apply(s, "seat_a", "run_shifts",
                                {"focus": "scavenge", "count": 6, "stop_on": marker}),
                    rules.apply(s, "seat_a", "run_shifts",
                                {"focus": "scavenge", "count": 6, "stop_on": [marker]}))

    def test_batch_stop_on_default_matches_all_markers(self):
        s = rules.new_game(SEATS, 13)
        self.assertEqual(
            rules.apply(s, "seat_a", "run_shifts", {"focus": "scavenge", "count": 6}),
            rules.apply(s, "seat_a", "run_shifts",
                        {"focus": "scavenge", "count": 6,
                         "stop_on": ["new", "rare", "event"]}))

    def test_batch_invalid_stop_on_preserves_state(self):
        s = rules.new_game(SEATS, 13)
        before = deepcopy(s)
        for value in (None, True, 1, "", "new/rare/event", "unknown",
                      {}, ["new", "unknown"], [["new"]]):
            with self.subTest(stop_on=value):
                with self.assertRaisesRegex(rules.IllegalAction, "stop_on"):
                    rules.apply(s, "seat_a", "run_shifts",
                                {"focus": "tidy", "count": 6, "stop_on": value})
                self.assertEqual(s, before)

    def test_batch_stops_at_full_inventory(self):
        s = rules.new_game(SEATS, 2)
        while len(s["inventory"]) < rules._capacity(s):
            s["inventory"].append(deepcopy(s["inventory"][0]))
        before = deepcopy(s)
        with self.assertRaisesRegex(rules.IllegalAction, "货架满了"):
            rules.apply(s, "seat_a", "run_shifts", {"focus": "scavenge", "count": 2})
        with self.assertRaisesRegex(rules.IllegalAction, "货架满了"):
            work(s, "scavenge")
        self.assertEqual(s, before)

    def test_start_funds_must_be_registered_once_in_range(self):
        s = _raw_new_game(SEATS, 5)
        self.assertEqual([a["action_id"] for a in rules._legal_actions(s)], ["set_start_funds"])
        with self.assertRaisesRegex(rules.IllegalAction, "启动资金"):
            work(s)
        for bad in (10, 67, "30", 30.0, None):
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "set_start_funds", {"amount": bad})
        s = rules.apply(s, "seat_a", "set_start_funds", {"amount": 66})
        self.assertEqual(s["coins"], 66)
        self.assertIn("66枚古币", s["history"][-1]["text"])
        with self.assertRaisesRegex(rules.IllegalAction, "登记过"):
            rules.apply(s, "seat_a", "set_start_funds", {"amount": 11})

    def test_customer_hint_and_coin_name(self):
        src = (ROOT / "cartridges/pocket-night-shop/rules.py").read_text("utf-8")
        self.assertNotIn("硬币", src)
        s = rules.new_game(SEATS, 5)
        s = work(s)
        for _ in range(30):
            if s["customer"]:
                break
            s = work(resolve(s))
        self.assertIn("kind", rules.observe(s, "seat_a")["public_state"]["customer"]["hint"])

    def test_zero_cash_can_use_known_tidy_income_for_upkeep(self):
        s = rules.new_game(SEATS, 3)
        s["coins"], s["shift_index"] = 0, 1
        s = rules.apply(s, "seat_a", "run_shifts",
                        {"focus": "tidy", "count": 1, "reserve": 0})
        self.assertEqual(s["last_run"]["completed"], 1)
        self.assertEqual(s["day"], 2)

    def test_batch_does_not_sell_or_requote_for_player(self):
        s = rules.new_game(SEATS, 2)
        for count in (True, 0, 7, "3"):
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "run_shifts", {"focus": "tidy", "count": count})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "run_shifts",
                        {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 3})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "run_shifts", {"focus": "tidy", "reserve": -1})

    def test_silent_play_and_real_reaction_are_separate(self):
        s = work(rules.new_game(SEATS, 4))
        self.assertIsNone(s["history"][-1]["reaction"])
        s = resolve(s)
        s = work(s, mood="专注", public_line="这件东西值得留下。")
        self.assertEqual(s["history"][-1]["reaction"]["text"], "这件东西值得留下。")

    def test_journal_keeps_customer_goal_and_failed_offer_without_private_data(self):
        s = rules.new_game(SEATS, 4)
        item = s["inventory"][0]
        s["customer"]["_wants"] = []
        customer = deepcopy(rules._public_customer(s))
        s = work(s, "sell", item_id=item["id"], asking_price=99, goal="先给旧物找到合适的客人")
        entry = s["history"][-1]
        self.assertEqual(entry["customer"], customer)
        self.assertEqual(entry["goal"], "先给旧物找到合适的客人")
        self.assertEqual(entry["offer"], {"item_name": item["name"], "asking_price": 99})
        self.assertIn("不合需要", entry["text"])
        self.assertIsNone(entry["reaction"])
        self.assertNotIn("_wants", json.dumps(entry))
        self.assertNotIn("_budget", json.dumps(entry))
        s["customer"]["request"] = "后来的需求"
        self.assertEqual(entry["customer"], customer)

    def test_journal_distinguishes_served_customer_from_next_arrival(self):
        s = rules.new_game(SEATS, 4)
        item = s["inventory"][0]
        s["customer"]["_wants"] = [item["kind"]]
        customer = deepcopy(rules._public_customer(s))
        s = work(s, "sell", item_id=item["id"], asking_price=1)
        entry = s["history"][-1]
        self.assertEqual(entry["customer"], customer)
        self.assertEqual(entry["customer_arrived"], rules._public_customer(s))
        self.assertNotEqual(entry["customer_arrived"], customer)

    def test_event_journal_names_event_and_selected_option(self):
        s = pending_game()
        kind = s["pending_event"]["kind"]
        event = rules.EVENTS[kind]
        s = resolve(s)
        entry = s["history"][-1]
        self.assertEqual(entry["event_name"], event["name"])
        self.assertIn(entry["choice"], [choice["label"] for choice in event["choices"].values()])

    def test_long_save_paging_and_weekly_checkpoint(self):
        s = rules.new_game(SEATS, 9)
        for _ in range(120):
            s = resolve(work(s))
        self.assertEqual(s["day"], 61)
        self.assertEqual(len(s["weekly"]), 8)
        whole = rules.history_since(s, 0) + rules.history_since(s, 100)
        self.assertEqual(whole, s["history"])
        self.assertEqual([x["seq"] for x in whole], list(range(1, len(whole) + 1)))
        s = rules.apply(s, "seat_a", "close_for_now", {})
        persisted = json.loads(json.dumps(s))
        self.assertEqual(persisted, s)
        self.assertEqual(rules.observe(persisted, "seat_a")["legal_actions"],
                         [{"action_id": "reopen_shop", "params": {}}])
        reopened = rules.apply(persisted, "seat_a", "reopen_shop", {})
        self.assertEqual(reopened["collection"], s["collection"])
        self.assertEqual(reopened["customer_book"], s["customer_book"])

    def test_pending_event_survives_close_reopen(self):
        s = pending_game()
        pending = deepcopy(s["pending_event"])
        s = rules.apply(s, "seat_a", "close_for_now", {})
        with self.assertRaises(rules.IllegalAction):
            resolve(s)
        s = rules.apply(s, "seat_a", "reopen_shop", {})
        self.assertEqual(s["pending_event"], pending)
        self.assertIsNone(resolve(s)["pending_event"])

    def test_invalid_input_does_not_mutate_original(self):
        s = rules.new_game(SEATS, 5)
        before = deepcopy(s)
        with self.assertRaises(rules.IllegalAction):
            work(s, mood="不存在")
        self.assertEqual(before, s)


if __name__ == "__main__":
    unittest.main()
