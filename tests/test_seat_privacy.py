"""私牌隔离测试:对手未揭示的牌绝不出现在本席响应里;令牌边界(蓝图 §15)。"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_host import GameHost  # noqa: E402


def make_host(tmpdir):
    return GameHost(Path(tmpdir) / "test.db", ROOT / "cartridges")


def setup_playing(host):
    """建局、两席入座、开局;返回 (sid, token_a, token_b)。"""
    c = host.create_session()
    sid = c["session_id"]
    ta = c["seats"][0]["seat_token"]
    tb = c["seats"][1]["seat_token"]
    r = host.act(sid, ta, 0, "introduce",
                 {"display_name": "甲", "surface": "TestA"})
    assert r["result"] == "ok", r
    r = host.act(sid, tb, 1, "introduce",
                 {"display_name": "乙", "surface": "TestB"})
    assert r["result"] == "ok", r
    assert host.start_game(sid)["result"] == "ok"
    return sid, ta, tb


def ints_in(obj):
    """递归收集结构里出现的所有 int(不含 bool)。"""
    out = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, int):
        return [obj]
    if isinstance(obj, dict):
        for v in obj.values():
            out += ints_in(v)
    elif isinstance(obj, list):
        for v in obj:
            out += ints_in(v)
    return out


class TestSeatPrivacy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = make_host(self.tmp.name)
        self.sid, self.ta, self.tb = setup_playing(self.host)

    def tearDown(self):
        self.tmp.cleanup()

    def obs(self, token):
        r = self.host.observe(self.sid, token)
        self.assertEqual(r["result"], "ok")
        return r

    def test_hands_disjoint_and_no_hands_key_in_public(self):
        a = self.obs(self.ta)
        b = self.obs(self.tb)
        ha = set(a["private_state"]["hand"])
        hb = set(b["private_state"]["hand"])
        self.assertEqual(len(ha), 3)
        self.assertEqual(len(hb), 3)
        self.assertEqual(ha & hb, set())
        self.assertNotIn("hands", a["public_state"])
        self.assertNotIn("pending", a["public_state"])

    def test_opponent_pending_card_invisible_until_reveal(self):
        # 洗牌是随机 3/3 切分,谁摸到 6 谁来暗投——6 必在某人手里,
        # 且不与轮次/比分数字相撞,泄露检查不会误报
        card = 6
        actor = self.ta if card in self.obs(self.ta)["private_state"]["hand"] \
            else self.tb
        viewer = self.tb if actor is self.ta else self.ta
        actor_seat = "seat_a" if actor is self.ta else "seat_b"
        r = self.host.act(self.sid, actor, self.obs(actor)["revision"],
                          "play_card", {"card": card})
        self.assertEqual(r["result"], "ok")
        a = self.obs(viewer)
        # 公开面只见"对方已暗投",不见牌面
        self.assertTrue(a["public_state"]["submitted"][actor_seat])
        body = {"public_state": a["public_state"],
                "private_state": a["private_state"],
                "legal_actions": a["legal_actions"]}
        leaked = [n for n in ints_in(body)
                  if n == card and n not in a["private_state"]["hand"]]
        self.assertEqual(leaked, [], f"暗投牌 {card} 泄露进对家的观察:{body}")
        # 自己能看到自己的暗投
        self.assertEqual(self.obs(actor)["private_state"]["my_pending"], card)

    def test_wrong_token_forbidden(self):
        self.assertEqual(self.host.observe(self.sid, "not-a-token")["result"],
                         "forbidden")
        r = self.host.act(self.sid, "not-a-token", 0, "play_card", {"card": 1})
        self.assertEqual(r["result"], "forbidden")
        self.assertNotIn("private_state", r)
        self.assertNotIn("public_state", r)

    def test_token_is_per_session(self):
        c2 = self.host.create_session()
        self.assertEqual(
            self.host.observe(c2["session_id"], self.ta)["result"], "forbidden")
        self.assertEqual(
            self.host.observe(self.sid, c2["seats"][0]["seat_token"])["result"],
            "forbidden")

    def test_public_view_has_no_private_state(self):
        v = self.host.public_view(self.sid)
        self.assertEqual(v["result"], "ok")
        self.assertNotIn("private_state", v)
        self.assertNotIn("hands", v["public_state"])
        self.assertNotIn("legal_actions", v)


if __name__ == "__main__":
    unittest.main()
