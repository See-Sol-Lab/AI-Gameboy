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


def work(s, focus="tidy", item_id=None, line="今晚先把手边的事做好。", **extra):
    params = {"focus": focus, "mood": "专注", "public_line": line, **extra}
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
        self.assertIn("mood", public)
        self.assertIn("public_line", public)

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

    def test_shift_updates_public_self_report_and_day_diary(self):
        s = rules.new_game(SEATS, 8)
        s = work(s, line="先攒下第一枚不急着花的钱。", goal="把店铺扩建到二级")
        self.assertEqual(s["shift_index"], 1)
        self.assertEqual(s["current_goal"], "把店铺扩建到二级")
        self.assertEqual(s["public_line"], "先攒下第一枚不急着花的钱。")
        s = work(s, line="今天没有发财,但柜台终于像样了。")
        self.assertEqual(s["day"], 2)
        self.assertEqual(len(s["diary"]), 1)
        self.assertEqual(s["diary"][0]["text"], "今天没有发财,但柜台终于像样了。")

    def test_sell_repair_scavenge_and_curate(self):
        s = rules.new_game(SEATS, 9)
        damaged = next(item for item in s["inventory"] if item["condition"] < 3)
        old_value = damaged["value"]
        s = work(s, "repair", damaged["id"])
        repaired = next(item for item in s["inventory"] if item["id"] == damaged["id"])
        self.assertEqual(repaired["value"], old_value + 2)
        s = work(s, "curate", repaired["id"])
        self.assertTrue(next(x for x in s["inventory"]
                             if x["id"] == repaired["id"])["displayed"])
        count = len(s["inventory"])
        s = work(s, "scavenge")
        self.assertEqual(len(s["inventory"]), count + 1)
        sell_id = next(x["id"] for x in s["inventory"] if not x["displayed"])
        coins = s["coins"]
        s = work(s, "sell", sell_id)
        self.assertGreater(s["coins"], coins)
        self.assertNotIn(sell_id, [x["id"] for x in s["inventory"]])

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
