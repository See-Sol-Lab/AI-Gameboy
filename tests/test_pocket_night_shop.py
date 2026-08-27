"""《口袋夜铺》:自主经营、公开心情、持久续玩与盲点门铃。"""

import importlib.util
import json
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pocket_night_shop_rules",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "pocket-night-shop" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SEATS = ["seat_a", "seat_b"]


def work(s, focus="tidy", item_id=None, line=None, mood=None, **extra):
    params = {"focus": focus, **extra}
    if line is not None:
        params["public_line"] = line
    if mood is not None:
        params["mood"] = mood
    if item_id:
        params["item_id"] = item_id
    return rules.apply(s, "seat_a", "work_shift", params)


class TestNightShop(unittest.TestCase):
    def test_new_game_is_deterministic_and_visible(self):
        s = rules.new_game(SEATS, 12)
        self.assertEqual(s, rules.new_game(SEATS, 12))
        self.assertEqual(len(s["inventory"]), 3)
        self.assertEqual(s["shopkeeper"], "seat_a")
        public = rules.observe(s, "seat_b")["public_state"]
        self.assertEqual(public["coins"], 12)
        self.assertEqual(len(public["inventory"]), 3)
        self.assertNotIn("mood", public)
        self.assertNotIn("public_line", public)
        self.assertNotIn("_secret", json.dumps(public, ensure_ascii=False))
        self.assertTrue(public["customer"]["request"])
        self.assertNotIn("_budget", json.dumps(public, ensure_ascii=False))
        self.assertNotIn("_wants", json.dumps(public, ensure_ascii=False))

    def test_only_ai_operates_and_human_only_knocks(self):
        s = rules.new_game(SEATS, 5)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_b", "work_shift",
                        {"focus": "tidy", "mood": "专注", "public_line": "越权"})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "knock", {})
        self.assertEqual(rules.observe(s, "seat_a")["legal_actions"][0]["action_id"],
                         "work_shift")
        self.assertEqual(rules.observe(s, "seat_b")["legal_actions"], [])

    def test_shift_allows_optional_reaction_and_engine_day_diary(self):
        s = rules.new_game(SEATS, 8)
        s = work(s, line="先攒下第一枚不急着花的钱。", mood="专注",
                 goal="把店铺扩建到二级")
        self.assertEqual(s["shift_index"], 1)
        self.assertEqual(s["history"][-1]["seq"], 1)
        self.assertEqual(s["current_goal"], "把店铺扩建到二级")
        self.assertEqual(s["public_line"], "先攒下第一枚不急着花的钱。")
        self.assertEqual(s["history"][-1]["reaction"],
                         {"mood": "专注", "text": "先攒下第一枚不急着花的钱。"})
        s = work(s)
        self.assertEqual(s["day"], 2)
        self.assertEqual(len(s["diary"]), 1)
        self.assertIn("打烊时硬币", s["diary"][0]["text"])
        self.assertIsNone(s["history"][-1]["reaction"])
        self.assertEqual(s["history"][-1]["seq"], 2)
        self.assertIn("打烊维护应付3枚", s["history"][-1]["text"])
        self.assertEqual(s["history"][-1]["coins_delta"], -2)

    def test_repair_scavenge_and_curate(self):
        s = rules.new_game(SEATS, 9)
        damaged = next(item for item in s["inventory"] if item["condition"] < 3)
        old_value = damaged["value"]
        s = work(s, "repair", damaged["id"])
        repaired = next(item for item in s["inventory"] if item["id"] == damaged["id"])
        self.assertGreaterEqual(repaired["value"], old_value + 2)
        s = work(s, "curate", repaired["id"])
        self.assertTrue(next(x for x in s["inventory"]
                             if x["id"] == repaired["id"])["displayed"])
        count = len(s["inventory"])
        s = work(s, "scavenge")
        self.assertEqual(len(s["inventory"]), count + 1)

    @staticmethod
    def _state_with_matching_item():
        for seed in range(100):
            s = rules.new_game(SEATS, seed)
            match = next((item for item in s["inventory"]
                          if item["kind"] in s["customer"]["_wants"]), None)
            if match:
                return s, match
        raise AssertionError("100个种子里没有顾客与初始旧物匹配")

    def test_customer_hidden_budget_accepts_fair_offer_and_builds_trust(self):
        s, item = self._state_with_matching_item()
        customer_id = s["customer"]["id"]
        coins = s["coins"]
        s = work(s, "sell", item["id"], asking_price=1)
        self.assertEqual(s["coins"], coins + 1)
        self.assertNotIn(item["id"], [x["id"] for x in s["inventory"]])
        self.assertEqual(s["customer_book"][customer_id]["deals"], 1)
        self.assertEqual(s["customer_book"][customer_id]["trust"], 1)
        self.assertIn("接受了1枚硬币的报价", s["history"][-1]["text"])

    def test_customer_rejects_high_offer_without_revealing_budget(self):
        s, item = self._state_with_matching_item()
        customer_id = s["customer"]["id"]
        hidden_budget = s["customer"]["_budget"]
        s = work(s, "sell", item["id"], asking_price=hidden_budget + 10)
        self.assertEqual(s["customer"]["id"], customer_id)
        self.assertEqual(s["customer"]["patience"], 1)
        self.assertIn(item["id"], [x["id"] for x in s["inventory"]])
        public = json.dumps(rules.observe(s, "seat_a"), ensure_ascii=False)
        self.assertNotIn('"_budget"', public)
        self.assertIn("还有一次重新报价", s["history"][-1]["text"])

    def test_completed_repair_reveals_engine_secret_only_after_completion(self):
        s = rules.new_game(SEATS, 14)
        item = s["inventory"][0]
        hidden_text = item["_secret"]
        before = json.dumps(rules.observe(s, "seat_a"), ensure_ascii=False)
        self.assertNotIn(hidden_text, before)
        while next(x for x in s["inventory"] if x["id"] == item["id"])["condition"] < 3:
            s = work(s, "repair", item["id"])
        public_item = next(x for x in rules.observe(s, "seat_a")["public_state"]["inventory"]
                           if x["id"] == item["id"])
        self.assertEqual(public_item["secret"], hidden_text)
        self.assertIn("完全修复后才发现", s["history"][-1]["text"])

    def test_door_event_hidden_until_blind_click(self):
        hit = None
        for seed in range(100):
            s = work(rules.new_game(SEATS, seed))
            if s["door_signal"]:
                hit = s
                break
        self.assertIsNotNone(hit)
        hidden = hit["door_signal"]["event"]
        human = rules.observe(hit, "seat_b")
        ai = rules.observe(hit, "seat_a")
        self.assertTrue(human["public_state"]["door_waiting"])
        self.assertEqual(human["legal_actions"], [{"action_id": "knock", "params": {}}])
        self.assertNotIn('"event"', json.dumps(human, ensure_ascii=False))
        self.assertNotIn('"event"', json.dumps(ai, ensure_ascii=False))
        self.assertNotIn(hidden, json.dumps(human["public_state"]["door_history"],
                                             ensure_ascii=False))

        after = rules.apply(hit, "seat_b", "knock", {})
        self.assertIsNone(after["door_signal"])
        self.assertEqual(len(after["door_history"]), 1)
        self.assertTrue(after["door_history"][0]["text"])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(after, "seat_b", "knock", {})

    def test_ai_can_keep_playing_while_door_waits_and_resume_later(self):
        s = rules.new_game(SEATS, 19)
        guard = 0
        while not s["door_signal"] and guard < 20:
            s = work(s)
            guard += 1
        self.assertIsNotNone(s["door_signal"])
        signal = dict(s["door_signal"])
        day = s["day"]
        for _ in range(8):
            s = work(s)
        self.assertEqual(s["door_signal"], signal)
        self.assertGreater(s["day"], day)
        resume = rules.observe(s, "seat_a")["private_state"]["resume_summary"]
        self.assertEqual(resume["day"], s["day"])
        self.assertTrue(resume["last_events"])

    def test_sixty_shifts_remain_playable_and_persisted(self):
        s = rules.new_game(SEATS, 23)
        for _ in range(60):
            s = work(s)
        self.assertEqual(s["phase"], "playing")
        self.assertEqual(s["day"], 31)
        self.assertEqual(len(s["diary"]), 30)
        self.assertEqual(len(s["history"]), 60)
        self.assertEqual(len(s["weekly"]), 4)
        self.assertEqual(s["weekly"][0]["through_day"], 7)
        self.assertEqual(rules.observe(s, "seat_a")["legal_actions"][0]["action_id"],
                         "work_shift")

    def test_week_checkpoint_can_close_and_reopen_without_ending_save(self):
        s = rules.new_game(SEATS, 31)
        for _ in range(14):
            s = work(s)
        self.assertEqual(s["day"], 8)
        s = rules.apply(s, "seat_a", "close_for_now", {})
        self.assertTrue(s["resting"])
        self.assertEqual(s["phase"], "playing")
        self.assertEqual(s["last_checkpoint"]["week"], 1)
        ob = rules.observe(s, "seat_a")
        self.assertEqual(ob["legal_actions"], [{"action_id": "reopen_shop", "params": {}}])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        s = rules.apply(s, "seat_a", "reopen_shop", {})
        self.assertFalse(s["resting"])
        self.assertEqual(rules.observe(s, "seat_a")["legal_actions"][0]["action_id"],
                         "work_shift")

    def test_invalid_public_self_report_rejected_without_mutation(self):
        s = rules.new_game(SEATS, 4)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "work_shift",
                        {"focus": "tidy", "mood": "秘密", "public_line": "x"})
        self.assertEqual(s, rules.new_game(SEATS, 4))


if __name__ == "__main__":
    unittest.main()
