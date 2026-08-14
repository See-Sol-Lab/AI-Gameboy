"""《口袋里的四样东西》V2 规则测试:目录可达性、配方、背书、补牌、桌面、判词与隐私。"""

import importlib.util
import json
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "four_things_rules_v2",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "four-things-in-my-pocket" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

SEATS = ["seat_a", "seat_b"]


def force(state, **kw):
    """测试用:直接改牌面构造场景(纯值操作,不经宿主)。"""
    state = json.loads(json.dumps(state))
    state.update(kw)
    return state


class TestCatalog(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(len(rules.ITEMS), 16)
        self.assertEqual(len(rules.SITUATIONS), 12)
        self.assertGreaterEqual(len(rules.RECIPES), 12)

    def test_every_need_reachable_in_full_catalog(self):
        all_tags = {t for it in rules.ITEMS.values() for t in it["tags"]}
        grant_tags = {g for r in rules.RECIPES for g in r["grants"]}
        for sid, sit in rules.SITUATIONS.items():
            self.assertEqual(len(sit["needs"]), 2, sid)
            for need in sit["needs"]:
                self.assertIn(need, all_tags | grant_tags,
                              f"{sid} 的需求 {need} 无人可达")
            self.assertIn(sit["risk"], all_tags, f"{sid} 的风险 {sit['risk']} 不会被踩中")

    def test_prop_ids_unique_and_disjoint_from_items(self):
        seen = set()
        for sit in rules.SITUATIONS.values():
            for p in sit["props"]:
                self.assertNotIn(p["id"], rules.ITEMS)
                self.assertNotIn(p["id"], seen)
                seen.add(p["id"])

    def test_deal_guarantee(self):
        for seed in range(16):
            s = rules.new_game(SEATS, seed)
            self.assertTrue(rules._deal_reachable(s), f"seed {seed} 保底失败")
            self.assertEqual(len(s["hands"]["seat_a"]), 4)
            self.assertEqual(len(s["hands"]["seat_b"]), 4)
            self.assertEqual(len(s["pool"]), 8)
            self.assertEqual(s["chips"], {"seat_a": 2, "seat_b": 2})


class TestRecipes(unittest.TestCase):
    def bead_sunlight_state(self):
        """一线天:玻璃珠 + 缝外日光(公共物)——首局冤案的回归样板。"""
        s = rules.new_game(SEATS, 1)
        s["situations"][0] = "narrow-slit"
        s["field"] = []
        rules._add_props(s, "narrow-slit")
        s["hands"]["seat_a"] = ["thread", "coin"]
        s["hands"]["seat_b"] = ["glass-bead", "chalk"]
        return s

    def test_bead_borrows_sunlight(self):
        s = self.bead_sunlight_state()
        s = rules.apply(s, "seat_a", "choose_item",
                        {"item_id": "thread", "usage": "把细线穿过缝递东西",
                         "combo_target": "partner"})
        s = rules.apply(s, "seat_b", "choose_item",
                        {"item_id": "glass-bead", "usage": "借日光聚束把光信号送过缝",
                         "combo_target": "field:sunlight"})
        r = s["revealed"][0]
        names = [c["name"] for c in r["combos"]]
        self.assertIn("借光聚束", names)   # 玻璃珠 × 日光,引擎直接认
        self.assertIn("系与投", names)     # 线 × 对面的玻璃珠(细小)
        # B:送达(借光)+细小(自带)+妙 = +3;A:送达+细小(线自带)+妙 = +3
        self.assertEqual(r["points"], {"seat_a": 3, "seat_b": 3})
        self.assertTrue(r["joint_star"])
        self.assertTrue(any("借光聚束" in line for line in r["report"]))

    def test_spent_target_rejected(self):
        s = rules.new_game(SEATS, 2)
        s["field"].append({"field_id": "match", "name": "火柴",
                           "tags": ["火", "照明", "燃料", "一次性"],
                           "owner": "seat_b", "spent": True, "source": "play"})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "choose_item",
                        {"item_id": s["hands"]["seat_a"][0], "usage": "借桌上火柴",
                         "combo_target": "field:match"})

    def test_usage_required(self):
        s = rules.new_game(SEATS, 3)
        iid = s["hands"]["seat_a"][0]
        for bad in ({}, {"item_id": iid}, {"item_id": iid, "usage": "  "},
                    {"item_id": iid, "usage": "长" * 81}):
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "choose_item", bad)


class TestEndorse(unittest.TestCase):
    def wood_state(self):
        """无向之林:玻璃珠看坡向——配方不认,走背书门。"""
        s = rules.new_game(SEATS, 1)
        s["situations"][0] = "pathless-wood"
        s["field"] = []
        s["hands"]["seat_a"] = ["glass-bead", "coin"]
        s["hands"]["seat_b"] = ["chalk", "thread"]
        s = rules.apply(s, "seat_a", "choose_item",
                        {"item_id": "glass-bead",
                         "usage": "珠子放叶面看滚向判断坡度,下坡出山",
                         "combo_target": "partner"})   # 与粉笔无配方
        s = rules.apply(s, "seat_b", "choose_item",
                        {"item_id": "chalk", "usage": "沿路画箭头"})
        self.assertEqual(s["step"], "judge")
        return s

    def test_endorse_flow(self):
        s = self.wood_state()
        # 只有 seat_b 有裁决权;非法 needs 被拒
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "judge", {"verdict": "doubt"})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_b", "judge",
                        {"verdict": "endorse", "needs": ["送达"]})  # 不是本轮需求
        s2 = rules.apply(s, "seat_b", "judge",
                         {"verdict": "endorse", "needs": ["方向"]})
        r = s2["revealed"][0]
        self.assertEqual(s2["chips"]["seat_b"], 1)          # 章 −1
        # A:方向(背书授予)+妙 = +2;B:标记+消耗风险−1+识解+1 = +1
        self.assertEqual(r["points"], {"seat_a": 2, "seat_b": 1})
        self.assertEqual(r["combos"][0]["kind"], "endorsed")

    def test_doubt_recorded_and_zero(self):
        s = self.wood_state()
        s2 = rules.apply(s, "seat_b", "judge", {"verdict": "doubt"})
        r = s2["revealed"][0]
        self.assertEqual(r["points"]["seat_a"], 0)          # 珠子生的分全无
        self.assertEqual(s2["chips"]["seat_b"], 2)          # 存疑不花章
        self.assertEqual(len(r["doubts"]), 1)
        self.assertIn("滚向", r["doubts"][0]["usage"])       # 原文在案

    def test_endorse_needs_chip(self):
        s = self.wood_state()
        s["chips"]["seat_b"] = 0
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_b", "judge",
                        {"verdict": "endorse", "needs": ["方向"]})


class TestFlow(unittest.TestCase):
    def play_round(self, s, usage="就它了"):
        for seat in SEATS:
            if seat not in s["pending"]:
                s = rules.apply(s, seat, "choose_item",
                                {"item_id": s["hands"][seat][0], "usage": usage})
        return s

    def test_full_game_with_draw_and_field(self):
        s = rules.new_game(SEATS, 7)
        s = self.play_round(s)                     # R1
        self.assertEqual(len(s["field"]) >= 2, True)
        played_r1 = [f for f in s["field"] if f["source"] == "play"]
        self.assertEqual(len(played_r1), 2)
        for f in played_r1:                        # 一次性入桌即耗尽
            self.assertEqual(f["spent"], "一次性" in f["tags"])
        s = self.play_round(s)                     # R2 → 补牌阶段
        self.assertEqual(s["step"], "draw")
        with self.assertRaises(rules.IllegalAction):   # 补牌阶段不能出牌
            rules.apply(s, "seat_a", "choose_item",
                        {"item_id": s["hands"]["seat_a"][0], "usage": "x"})
        for seat in SEATS:
            offer = s["draw"]["offers"][seat]
            self.assertEqual(len(offer), 2)
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, seat, "draw_pick", {"item_id": "not-offered"})
            s = rules.apply(s, seat, "draw_pick", {"item_id": offer[0]})
        self.assertEqual(s["round"], 3)
        self.assertEqual(len(s["hands"]["seat_a"]), 3)
        s = self.play_round(s)                     # R3
        s = self.play_round(s)                     # R4
        self.assertEqual(s["phase"], "finished")
        self.assertEqual(len(s["revealed"]), 4)
        # 分数 = 各轮 points 之和;星 = 各轮 joint_star 之和
        for seat in SEATS:
            self.assertEqual(s["scores"][seat],
                             sum(r["points"][seat] for r in s["revealed"]))
        self.assertEqual(s["stars"],
                         sum(1 for r in s["revealed"] if r["joint_star"]))
        for r in s["revealed"]:                    # 判词逐轮存在且是人话
            self.assertTrue(all(isinstance(x, str) and x for x in r["report"]))
        # 终局手牌:4−4+1=1,加上未选完……两人共 2 件在手,选择空间未塌
        self.assertEqual(len(s["hands"]["seat_a"]) + len(s["hands"]["seat_b"]), 2)

    def test_usage_private_before_reveal(self):
        s = rules.new_game(SEATS, 5)
        secret = "这句宣言在揭示前绝不能给对面看到"
        s = rules.apply(s, "seat_a", "choose_item",
                        {"item_id": s["hands"]["seat_a"][0], "usage": secret})
        ob_b = rules.observe(s, "seat_b")
        self.assertNotIn(secret, json.dumps(ob_b, ensure_ascii=False))
        self.assertTrue(ob_b["public_state"]["submitted"]["seat_a"])
        ob_a = rules.observe(s, "seat_a")
        self.assertEqual(ob_a["private_state"]["my_pending"]["usage"], secret)

    def test_draw_offers_private(self):
        s = rules.new_game(SEATS, 7)
        s = self.play_round(s)
        s = self.play_round(s)
        self.assertEqual(s["step"], "draw")
        ob_a = rules.observe(s, "seat_a")
        # 我的补牌候选只在我的 private_state 里
        self.assertEqual([c["item_id"] for c in ob_a["private_state"]["draw_offers"]],
                         s["draw"]["offers"]["seat_a"])
        # 任何人的候选都不进公开面与 legal_actions 之外的区域
        public_blob = json.dumps({"public_state": ob_a["public_state"]},
                                 ensure_ascii=False)
        for iid in s["draw"]["offers"]["seat_a"] + s["draw"]["offers"]["seat_b"]:
            on_field = any(f["field_id"] == iid for f in s["field"])
            if not on_field:
                self.assertNotIn(f'"{iid}"', public_blob)

    def test_field_is_public(self):
        s = rules.new_game(SEATS, 7)
        s = self.play_round(s)
        ob = rules.observe(s, "seat_b")
        self.assertEqual(len(ob["public_state"]["field"]),
                         len(s["field"]))


if __name__ == "__main__":
    unittest.main()
