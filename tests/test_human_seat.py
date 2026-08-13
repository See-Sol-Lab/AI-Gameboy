"""人类席测试:同一宿主路径、双向私牌隔离、揭示时序、恢复语义(Stage D)。

人类席与 AI 席都调 GameHost.observe/act —— MCP 工具与 HTTP 路由都是它的薄封装,
本文件在宿主层完成双向断言;活服务器上的 HTTP 双向冒烟在施工尾声另行执行。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_host import GameHost  # noqa: E402


def deep_strings(obj):
    """递归收集结构里的所有字符串(键与值)。"""
    out = []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += deep_strings(k) + deep_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            out += deep_strings(v)
    return out


class TestHumanSeat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.host = GameHost(Path(self.tmp.name) / "t.db", ROOT / "cartridges")
        c = self.host.create_session("four-things-in-my-pocket", "human_ai")
        self.assertEqual(c["result"], "ok")
        self.sid = c["session_id"]
        self.t_ai = c["seats"][0]["seat_token"]      # seat_a = ai_window
        self.t_hu = c["seats"][1]["seat_token"]      # seat_b = human
        self.assertEqual(c["seats"][0]["participant_type"], "ai_window")
        self.assertEqual(c["seats"][1]["participant_type"], "human")
        r = self.host.act(self.sid, self.t_ai, 0, "introduce",
                          {"display_name": "AI 玩家", "surface": "Codex Desktop"})
        self.assertEqual(r["result"], "ok")
        r = self.host.act(self.sid, self.t_hu, 1, "introduce",
                          {"display_name": "项目作者", "surface": "掌机 UI"})
        self.assertEqual(r["result"], "ok")
        self.assertEqual(self.host.start_game(self.sid)["result"], "ok")

    def tearDown(self):
        self.tmp.cleanup()

    def obs(self, token):
        r = self.host.observe(self.sid, token)
        self.assertEqual(r["result"], "ok")
        return r

    def assert_id_absent_everywhere(self, observation, item_id, own_hand_ids):
        """校正 #2:分区递归断言 + 全响应序列化断言。"""
        for section in ("public_state", "private_state", "legal_actions",
                        "recent_public_events"):
            strings = deep_strings(observation[section])
            hits = [x for x in strings if item_id in x]
            self.assertEqual(hits, [],
                             f"{item_id} 泄露进 {section}:{hits}")
        blob = json.dumps(observation, ensure_ascii=False)
        if item_id not in own_hand_ids:
            self.assertNotIn(item_id, blob, f"{item_id} 出现在完整响应里")

    def test_mode_validation(self):
        r = self.host.create_session("pocket-circuit", "human_ai")
        self.assertEqual(r["result"], "rejected")   # 口袋电路不支持人类席
        r = self.host.create_session("four-things-in-my-pocket", "solo")
        self.assertEqual(r["result"], "rejected")

    def test_human_sees_own_hand(self):
        o = self.obs(self.t_hu)
        self.assertEqual(o["you"]["seat_id"], "seat_b")
        self.assertEqual(len(o["private_state"]["hand"]), 4)
        for card in o["private_state"]["hand"]:
            self.assertIn("item_id", card)
            self.assertIn("tags", card)

    def test_pending_isolation_both_directions(self):
        """暗选只对提交者可见;揭示后才进入公共层。双向。"""
        # 方向一:人类暗选,AI 绝不可见
        hu_item = self.obs(self.t_hu)["private_state"]["hand"][0]["item_id"]
        r = self.host.act(self.sid, self.t_hu,
                          self.obs(self.t_hu)["revision"],
                          "choose_item", {"item_id": hu_item})
        self.assertEqual(r["result"], "ok")
        self.assertEqual(self.obs(self.t_hu)["private_state"]["my_pending"], hu_item)
        ai_o = self.obs(self.t_ai)
        self.assertTrue(ai_o["public_state"]["submitted"]["seat_b"])
        self.assertIsNone(ai_o["private_state"]["my_pending"])
        ai_hand_ids = [c["item_id"] for c in ai_o["private_state"]["hand"]]
        self.assert_id_absent_everywhere(ai_o, hu_item, ai_hand_ids)
        # 公共旁观视图同样不可见
        pv = self.host.public_view(self.sid)
        self.assertNotIn(hu_item, json.dumps(pv, ensure_ascii=False))
        # 方向二:AI 暗选,人类在揭示前同样不可见……
        ai_item = ai_hand_ids[0]
        r = self.host.act(self.sid, self.t_ai, ai_o["revision"],
                          "choose_item", {"item_id": ai_item})
        self.assertEqual(r["result"], "ok")   # 两边都交了,本轮当场揭示
        # ……揭示之后,双方选择进入公共 revealed,双向可见
        hu_o = self.obs(self.t_hu)
        revealed = hu_o["public_state"]["revealed"]
        self.assertEqual(len(revealed), 1)
        self.assertEqual(revealed[0]["choices"]["seat_a"]["item_id"], ai_item)
        self.assertEqual(revealed[0]["choices"]["seat_b"]["item_id"], hu_item)
        self.assertIn(ai_item, json.dumps(self.obs(self.t_hu),
                                          ensure_ascii=False))

    def test_ai_pending_hidden_from_human_pre_reveal(self):
        """镜像时序:AI 先暗选、人类未选时,人类看不到 AI 选了什么。"""
        ai_o = self.obs(self.t_ai)
        ai_item = ai_o["private_state"]["hand"][0]["item_id"]
        self.host.act(self.sid, self.t_ai, ai_o["revision"],
                      "choose_item", {"item_id": ai_item})
        hu_o = self.obs(self.t_hu)
        self.assertTrue(hu_o["public_state"]["submitted"]["seat_a"])
        hu_hand_ids = [c["item_id"] for c in hu_o["private_state"]["hand"]]
        self.assert_id_absent_everywhere(hu_o, ai_item, hu_hand_ids)

    def test_human_resume_by_token(self):
        """刷新/重开页面 = 凭原令牌再 observe,原地恢复。"""
        hu_item = self.obs(self.t_hu)["private_state"]["hand"][0]["item_id"]
        self.host.act(self.sid, self.t_hu, self.obs(self.t_hu)["revision"],
                      "choose_item", {"item_id": hu_item})
        again = self.obs(self.t_hu)
        self.assertEqual(again["private_state"]["my_pending"], hu_item)
        self.assertEqual(again["status"], "playing")
        # 错误令牌仍然是 forbidden,不泄露任何局面
        bad = self.host.observe(self.sid, "wrong-token")
        self.assertEqual(bad["result"], "forbidden")
        self.assertNotIn("private_state", bad)

    def test_full_four_rounds_and_memorial_data(self):
        for _ in range(4):
            for tok in (self.t_hu, self.t_ai):
                o = self.obs(tok)
                r = self.host.act(self.sid, tok, o["revision"], "choose_item",
                                  {"item_id": o["private_state"]["hand"][0]["item_id"]},
                                  table_line="就它了")
                self.assertEqual(r["result"], "ok")
        final = self.obs(self.t_hu)
        self.assertEqual(final["status"], "finished")
        ps = final["public_state"]
        self.assertEqual(len(ps["revealed"]), 4)
        self.assertEqual(ps["scores"]["seat_a"] + ps["scores"]["seat_b"],
                         sum(r["points"]["seat_a"] + r["points"]["seat_b"]
                             for r in ps["revealed"]))
        self.assertEqual(ps["stars"],
                         sum(1 for r in ps["revealed"] if r["joint_star"]))
        # 纪念卡字段齐备,且两次派生一致
        v1 = self.host.public_view(self.sid)
        v2 = self.host.public_view(self.sid)
        self.assertEqual(v1, v2)
        self.assertEqual(v1["public_state"]["stars"], ps["stars"])
        self.assertEqual(len(v1["public_events"]), len(v2["public_events"]))
        talks = [e for e in v1["public_events"] if e["kind"] == "table_line"]
        self.assertEqual(len(talks), 8)


if __name__ == "__main__":
    unittest.main()
