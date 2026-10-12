"""Regression fixtures for the updated night-shop rules; never uses player saves."""
import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_night_rules", ROOT / "cartridges/pocket-night-shop/rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)


class TestNightAudit(unittest.TestCase):
    def state(self):
        s = rules.new_game(["seat_a"], 17)
        s["start_funds_pending"] = False
        s["coins"] = 100
        return s

    def light(self, s, code):
        s["collection"].setdefault(code, {})["revealed"] = "synthetic repaired secret"
        cid = rules.BOND_BY_CODE[code]
        s["customer_book"].setdefault(cid, {})["bond"] = True

    def test_witch_gift_never_overflows_a_full_shelf(self):
        s = self.state()
        s["shop_level"] = 3
        s["unlocked_locations"] = list(rules.LOCATIONS)[:4]
        while len(s["inventory"]) < rules._capacity(s):
            rules._collect(s, rules._make_item(s, "lane", "synthetic fill"))
        rules._witch_book(s)["apple_until"] = s["shift_count"] + 2
        with patch.object(rules, "_number", return_value=0):
            text = rules._witch_meet(s, rules._witch_spot(s))
        self.assertEqual(len(s["inventory"]), rules._capacity(s))
        self.assertNotIn("塞进", text)
        self.assertTrue(rules._apple_held(s))

    def test_exhausted_pool_does_not_resurrect_lit_items(self):
        s = self.state()
        s["shop_level"] = 3
        for code in rules.LOCATIONS["lane"]["pool"]:
            self.light(s, code)
        with self.assertRaises(rules.IllegalAction):
            rules._make_item(s, "lane", "fully exhausted")

    def test_simultaneous_lighthouse_conditions_play_all_three_dreams(self):
        s = self.state()
        s["day"] = rules.SECRET_DAY
        s["reputation"] = rules.SECRET_REPUTATION
        s["collection"] = {f"synthetic_{i}": {} for i in range(rules.SECRET_DISCOVERIES)}
        self.assertEqual([rules._lighthouse_dream(s) for _ in range(3)], list(rules.LIGHTHOUSE_DREAMS))
        self.assertIsNone(rules._lighthouse_dream(s))

    def test_opening_evening_records_arriving_customer(self):
        s = self.state()
        s["shift_index"] = rules.OPEN_SHIFT - 1
        self.assertIsNone(rules._public_customer(s))
        with patch.object(rules, "_maybe_event", return_value=""):
            t = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertEqual(t["history"][-1]["customer_arrived"]["id"], t["customer"]["id"])
        self.assertEqual(rules.observe(t, "seat_a")["public_state"]["shift_number"], rules.OPEN_SHIFT + 1)

    def test_invalid_inputs_leave_state_unchanged(self):
        s = self.state()
        before = deepcopy(s)
        for action, params in [("work_shift", {"focus":"sell", "item_id":s["inventory"][0]["id"], "asking_price":True}),
                               ("run_shifts", {"focus":"tidy", "count":True}),
                               ("merge", {"item_id":[], "from_id":{}}),
                               ("witch_sell", {"item_ids":[{}]})]:
            with self.subTest(action=action), self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", action, params)
            self.assertEqual(s, before)

    def test_bankrupt_shop_waits_for_no_further_player_action(self):
        s = self.state()
        s["bankrupt"] = True
        view = rules.observe(s, "seat_a")
        self.assertEqual(view["legal_actions"], [])
        self.assertEqual(view["waiting_for"], [])

    def test_bankruptcy_is_terminal_and_catalogue_stays_readable(self):
        s = self.state()
        s.update(coins=0, rescues=rules.RESCUE_LIMIT, unpaid_streak=rules.RESCUE_STREAK - 1,
                 shift_index=rules.LAST_SHIFT)
        with patch.object(rules, "_maybe_event", return_value=""):
            t = rules.apply(s, "seat_a", "work_shift", {"focus":"curate", "item_id":s["inventory"][0]["id"]})
        self.assertEqual(t["phase"], "finished")
        self.assertEqual(t["endings"][-1]["id"], "closed")
        view = rules.observe(t, "seat_a")
        self.assertTrue(view["public_state"]["collection"]["entries"])
        self.assertEqual(view["waiting_for"], [])
        with self.assertRaisesRegex(rules.IllegalAction, "破产"):
            rules.apply(t, "seat_a", "work_shift", {"focus":"tidy"})

    def test_cartridge_host_records_bankruptcy_as_finished(self):
        from console import store
        from console.game_host import GameHost
        with tempfile.TemporaryDirectory() as folder:
            host = GameHost(Path(folder) / "test.db", ROOT / "cartridges")
            game = host.create_session("pocket-night-shop", "solo_ai")
            sid, token = game["session_id"], game["seats"][0]["seat_token"]
            view = host.act(sid, token, 0, "introduce", {"display_name":"Synthetic", "surface":"Test"})
            s = self.state()
            s.update(coins=0, rescues=rules.RESCUE_LIMIT, unpaid_streak=rules.RESCUE_STREAK - 1,
                     shift_index=rules.LAST_SHIFT)
            conn = store.connect(host.db_path)
            try:
                engine = json.loads(store.get_session(conn, sid)["engine_state_json"])
                engine["cartridge_state"] = s
                conn.execute("UPDATE session SET engine_state_json=? WHERE id=?", (json.dumps(engine), sid))
            finally:
                conn.close()
            _, host_rules = host._load_cartridge("pocket-night-shop", game["cartridge"]["version"])
            with patch.object(host_rules, "_maybe_event", return_value=""):
                ended = host.act(sid, token, view["revision"], "work_shift", {"focus":"curate", "item_id":s["inventory"][0]["id"]})
            self.assertEqual(ended["status"], "finished")
            self.assertEqual(host.observe(sid, token)["public_state"]["endings"][-1]["id"], "closed")
