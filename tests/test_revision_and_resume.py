"""revision 冲突、非法动作、断线恢复与完整对局测试(蓝图 §16 / §20)。"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_host import GameHost  # noqa: E402
from test_seat_privacy import make_host, setup_playing  # noqa: E402


class TestLobby(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = make_host(self.tmp.name)
        c = self.host.create_session()
        self.sid = c["session_id"]
        self.ta = c["seats"][0]["seat_token"]
        self.tb = c["seats"][1]["seat_token"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_lobby_flow_and_introduce_validation(self):
        a = self.host.observe(self.sid, self.ta)
        self.assertEqual(a["status"], "lobby")
        self.assertEqual(a["legal_actions"][0]["action_id"], "introduce")
        # 开局前不能出牌
        r = self.host.act(self.sid, self.ta, 0, "play_card", {"card": 1})
        self.assertEqual(r["result"], "rejected")
        # 两席未就座不能 START
        self.assertEqual(self.host.start_game(self.sid)["result"], "rejected")
        # 参数校验
        bad = [
            {},  # 缺 display_name
            {"display_name": "甲"},  # 缺 surface
            {"display_name": "x" * 41, "surface": "s"},
            {"display_name": "甲", "surface": "s", "public_anchors": ["1", "2", "3"]},
            {"display_name": "甲", "surface": "s", "secret": "?"},
        ]
        for params in bad:
            r = self.host.act(self.sid, self.ta, 0, "introduce", params)
            self.assertEqual(r["result"], "rejected", params)
        # 正常入座(带锚点与桌边话)
        r = self.host.act(self.sid, self.ta, 0, "introduce",
                          {"display_name": "甲", "surface": "TestA",
                           "now": "先看看你们怎么选",
                           "public_anchors": ["锚点一", "锚点二"]},
                          table_line="各位好")
        self.assertEqual(r["result"], "ok")
        self.assertEqual(r["you"]["display_name"], "甲")
        kinds = [e["kind"] for e in r["recent_public_events"]]
        self.assertIn("introduce", kinds)
        self.assertIn("table_line", kinds)
        # 重复入座被拒
        r = self.host.act(self.sid, self.ta, r["revision"], "introduce",
                          {"display_name": "甲2", "surface": "TestA"})
        self.assertEqual(r["result"], "rejected")

    def test_table_line_too_long_rejected_whole(self):
        before = self.host.observe(self.sid, self.ta)["revision"]
        r = self.host.act(self.sid, self.ta, before, "introduce",
                          {"display_name": "甲", "surface": "TestA"},
                          table_line="长" * 121)
        self.assertEqual(r["result"], "rejected")
        after = self.host.observe(self.sid, self.ta)
        self.assertEqual(after["revision"], before)      # 局面不变
        self.assertIsNone(after["you"]["display_name"])  # 入座也没发生


class TestRevisionAndResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = make_host(self.tmp.name)
        self.sid, self.ta, self.tb = setup_playing(self.host)

    def tearDown(self):
        self.tmp.cleanup()

    def obs(self, token):
        return self.host.observe(self.sid, token)

    def test_stale_revision_second_writer_loses(self):
        rev = self.obs(self.tb)["revision"]
        ca = self.obs(self.ta)["private_state"]["hand"][0]
        cb = self.obs(self.tb)["private_state"]["hand"][0]
        r1 = self.host.act(self.sid, self.tb, rev, "play_card", {"card": cb})
        self.assertEqual(r1["result"], "ok")
        # 后手基于同一 revision 提交:得到 stale_revision 与新观察
        r2 = self.host.act(self.sid, self.ta, rev, "play_card", {"card": ca})
        self.assertEqual(r2["result"], "stale_revision")
        self.assertEqual(r2["revision"], r1["revision"])
        self.assertIn("legal_actions", r2)
        # 按新 revision 重交成功,两牌同时揭示
        r3 = self.host.act(self.sid, self.ta, r2["revision"], "play_card",
                           {"card": ca})
        self.assertEqual(r3["result"], "ok")
        self.assertEqual(len(r3["public_state"]["revealed"]), 1)

    def test_rejected_keeps_state(self):
        rev = self.obs(self.tb)["revision"]
        r = self.host.act(self.sid, self.tb, rev, "play_card", {"card": 7})
        self.assertEqual(r["result"], "rejected")
        self.assertEqual(self.obs(self.tb)["revision"], rev)
        cb = self.obs(self.tb)["private_state"]["hand"][0]
        self.assertEqual(self.host.act(self.sid, self.tb, rev, "play_card",
                                       {"card": cb})["result"], "ok")
        # 同轮重复暗投被拒
        r = self.host.act(self.sid, self.tb, rev + 1, "play_card",
                          {"card": self.obs(self.tb)["private_state"]["hand"][0]})
        self.assertEqual(r["result"], "rejected")

    def test_resume_after_disconnect(self):
        """断开没有持久连接状态:凭原令牌再 observe 就回到原局(§16)。"""
        cb = self.obs(self.tb)["private_state"]["hand"][0]
        self.host.act(self.sid, self.tb, self.obs(self.tb)["revision"],
                      "play_card", {"card": cb})
        again = self.obs(self.tb)  # 模拟窗口关闭后重来
        self.assertEqual(again["result"], "ok")
        self.assertEqual(again["private_state"]["my_pending"], cb)
        self.assertEqual(again["status"], "playing")
        self.assertEqual(again["waiting_for"], ["seat_a"])

    def test_full_game_to_finish(self):
        for _ in range(6):
            for tok in (self.tb, self.ta):
                o = self.obs(tok)
                self.host.act(self.sid, tok, o["revision"], "play_card",
                              {"card": o["private_state"]["hand"][0]},
                              table_line="出了")
        final = self.obs(self.ta)
        self.assertEqual(final["status"], "finished")
        self.assertEqual(len(final["public_state"]["revealed"]), 6)
        scores = final["public_state"]["scores"]
        self.assertLessEqual(scores["seat_a"] + scores["seat_b"], 21)
        self.assertIn(final["public_state"]["winner"], ("seat_a", "seat_b", None))
        self.assertEqual(final["legal_actions"], [])
        # 结束后动作被拒
        r = self.host.act(self.sid, self.ta, final["revision"], "play_card",
                          {"card": 1})
        self.assertEqual(r["result"], "rejected")
        # 结算写在唯一事实源里,人类公开视图一致
        v = self.host.public_view(self.sid)
        self.assertEqual(v["public_state"]["scores"], scores)

    def test_human_end_mid_game(self):
        self.assertEqual(self.host.end_session(self.sid)["result"], "ok")
        o = self.obs(self.ta)
        self.assertEqual(o["status"], "finished")
        r = self.host.act(self.sid, self.ta, o["revision"], "play_card",
                          {"card": o["private_state"]["hand"][0]})
        self.assertEqual(r["result"], "rejected")
        self.assertEqual(self.host.end_session(self.sid)["result"], "rejected")


if __name__ == "__main__":
    unittest.main()
