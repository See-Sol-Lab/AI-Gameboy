"""Current human/AI seats and night-shop persistence; retired prototypes removed."""
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from console.game_host import GameHost, CartridgeVersionMissing

ROOT = Path(__file__).resolve().parents[1]


class TestHumanSeat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = GameHost(Path(self.tmp.name) / "t.db", ROOT / "cartridges")

    def test_mode_validation(self):
        r = self.host.create_session("pocket-circuit", "human_ai")
        self.assertEqual(r["result"], "ok")         # v0.2 起支持人类先锁牌
        r = self.host.create_session("pocket-circuit", "solo")
        self.assertEqual(r["result"], "rejected")

    def test_pocket_circuit_human_locks_before_ai(self):
        c = self.host.create_session("pocket-circuit", "human_ai")
        sid = c["session_id"]
        t_ai = c["seats"][0]["seat_token"]
        t_hu = c["seats"][1]["seat_token"]
        self.assertEqual(self.host.act(
            sid, t_ai, 0, "introduce",
            {"display_name": "AI 玩家", "surface": "Codex Desktop"})["result"], "ok")
        self.assertEqual(self.host.act(
            sid, t_hu, 1, "introduce",
            {"display_name": "人类玩家", "surface": "掌机 UI"})["result"], "ok")
        self.assertEqual(self.host.start_game(sid)["result"], "ok")

        ai_before = self.host.observe(sid, t_ai)
        human = self.host.observe(sid, t_hu)
        self.assertEqual(ai_before["legal_actions"], [])
        self.assertEqual(human["waiting_for"], ["seat_b"])
        human_card = human["private_state"]["hand"][0]
        locked = self.host.act(sid, t_hu, human["revision"], "play_card",
                               {"card": human_card})
        self.assertEqual(locked["result"], "ok")
        self.assertEqual(locked["private_state"]["my_pending"], human_card)

        ai = self.host.observe(sid, t_ai)
        self.assertTrue(ai["public_state"]["submitted"]["seat_b"])
        self.assertEqual(ai["public_state"]["revealed"], [])
        self.assertIsNone(ai["private_state"]["my_pending"])
        self.assertEqual(ai["legal_actions"][0]["action_id"], "play_card")
        ai_card = ai["private_state"]["hand"][-1]
        resolved = self.host.act(sid, t_ai, ai["revision"], "play_card",
                                 {"card": ai_card})
        self.assertEqual(resolved["result"], "ok")
        self.assertEqual(len(resolved["public_state"]["revealed"]), 1)
        self.assertEqual(resolved["public_state"]["revealed"][0]["cards"],
                         {"seat_a": ai_card, "seat_b": human_card})

    def test_night_shop_solo_starts_without_human_and_resumes_from_disk(self):
        c = self.host.create_session("pocket-night-shop", "solo_ai")
        self.assertEqual(c["result"], "ok")
        self.assertEqual(len(c["seats"]), 1)
        sid, token = c["session_id"], c["seats"][0]["seat_token"]
        with patch("console.game_host.secrets.randbits", return_value=5):
            r = self.host.act(sid, token, 0, "introduce",
                              {"display_name": "Test Keeper", "surface": "Test"})
        self.assertEqual(r["status"], "playing")
        self.assertEqual(r["waiting_for"], ["seat_a"])
        self.assertEqual(self.host.act(sid, token, r["revision"], "roll_start_funds",
                                       {"human_words": "掷"})["result"], "rejected")
        self.assertTrue(r["public_state"]["start_funds_pending"])
        self.assertEqual(self.host.roll_start_funds(sid)["result"], "ok")
        self.assertEqual(self.host.roll_start_funds(sid)["result"], "rejected")
        r = self.host.observe(sid, token)
        r = self.host.act(sid, token, r["revision"], "run_shifts",
                          {"focus": "tidy", "count": 6, "stop_on": []})
        self.assertEqual(r["result"], "ok")
        viewer = self.host.public_view(sid, after_seq=0)
        self.assertIn("customer_book", viewer["public_state"])            # 网页给人类看客人簿
        self.assertNotIn("customer_book", self.host.observe(sid, token)["public_state"])   # AI 看不到
        self.assertNotIn("customer_book", r["public_state"])
        self.assertNotIn("private_state", viewer)
        self.assertNotIn("seat_token", json.dumps(viewer))
        self.assertEqual(len(viewer["public_state"]["playback_entries"]),
                         r["public_state"]["journal_total"])
        self.assertEqual(self.host.act(sid, "viewer", r["revision"], "work_shift",
                                      {"focus": "tidy"})["result"], "forbidden")
        restarted = GameHost(self.host.db_path, ROOT / "cartridges")
        self.assertEqual(restarted.observe(sid, token), self.host.observe(sid, token))
        before = restarted.observe(sid, token)
        rejected = restarted.act(sid, token, before["revision"], "run_shifts",
                                  {"focus": "tidy", "count": 99})
        self.assertEqual(rejected["result"], "rejected")
        self.assertEqual(restarted.observe(sid, token), before)

    def test_night_shop_calls_capped_until_human_said(self):
        from console import game_host
        c = self.host.create_session("pocket-night-shop", "solo_ai")
        sid, token = c["session_id"], c["seats"][0]["seat_token"]
        r = self.host.act(sid, token, 0, "introduce", {"display_name": "K", "surface": "T"})
        self.assertEqual(self.host.act(sid, token, r["revision"], "roll_start_funds",
                                       {"human_words": "掷"})["result"], "rejected")
        self.assertTrue(r["public_state"]["start_funds_pending"])
        self.assertEqual(self.host.roll_start_funds(sid)["result"], "ok")
        self.assertEqual(self.host.roll_start_funds(sid)["result"], "rejected")
        r = self.host.observe(sid, token)
        self.host._calls[sid] = game_host.CALL_LIMIT
        blocked = self.host.act(sid, token, r["revision"], "work_shift", {"focus": "tidy"})
        self.assertEqual(blocked["result"], "rejected")
        self.assertIn("token", blocked["reason"])
        self.assertEqual(self.host.act(sid, token, r["revision"], "human_said",
                                       {"human_words": ""})["result"], "rejected")
        ok = self.host.act(sid, token, r["revision"], "human_said", {"human_words": "继续"})
        self.assertEqual(ok["result"], "ok")
        self.assertEqual(ok["revision"], r["revision"])
        self.assertEqual(self.host.act(sid, token, r["revision"], "work_shift",
                                       {"focus": "tidy"})["result"], "ok")

    def test_night_shop_string_stop_on_survives_host_and_save(self):
        c = self.host.create_session("pocket-night-shop", "solo_ai")
        sid, token = c["session_id"], c["seats"][0]["seat_token"]
        with patch("console.game_host.secrets.randbits", return_value=13):
            before = self.host.act(sid, token, 0, "introduce",
                                   {"display_name": "Test Keeper", "surface": "Test"})
        self.host.roll_start_funds(sid)
        before = self.host.observe(sid, token)
        rejected = self.host.act(sid, token, before["revision"], "run_shifts",
                                 {"focus": "scavenge", "count": 6, "stop_on": "unknown"})
        self.assertEqual(rejected["result"], "rejected")
        self.assertEqual(self.host.observe(sid, token), before)
        result = self.host.act(sid, token, before["revision"], "run_shifts",
                               {"focus": "scavenge", "count": 6, "stop_on": "new"})
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["revision"], before["revision"] + 1)
        restarted = GameHost(self.host.db_path, ROOT / "cartridges")
        self.assertEqual(restarted.observe(sid, token), self.host.observe(sid, token))


    def test_retired_cards_and_old_versions_are_unavailable(self):
        for cid in ("blind-companions", "four-things-in-my-pocket"):
            self.assertEqual(self.host.create_session(cid)["result"], "rejected")
        for cid, version in (("pocket-circuit", "0.1.0"), ("pocket-night-shop", "0.2.0"),
                             ("pocket-crossing", "0.5.0"), ("pocket-tabletop", "1.0.1")):
            with self.subTest(cid=cid):
                with self.assertRaises(CartridgeVersionMissing):
                    self.host._load_cartridge(cid, version)


if __name__ == "__main__":
    unittest.main()
