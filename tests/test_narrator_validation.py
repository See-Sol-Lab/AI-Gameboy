"""荷官校验器测试:合格样稿放行,越权/缺字段/超模一律打回(不联网)。"""

import copy
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from console import narrator  # noqa: E402
from test_pocket_crossing import (FIX_WORLD, FIX_IDENTITIES,
                                  FIX_MILESTONES, fix_scene)  # noqa: E402


class TestValidators(unittest.TestCase):
    def test_resummon_feedback_is_in_crossing_prompt_without_mutating_context(self):
        ctx = {"world": {"world_name": "测试世界", "premise": "背景", "lore": "传说"},
               "last_narrator_error": "gift.kind只能使用菜单中的代码"}
        before = copy.deepcopy(ctx)
        with patch.object(narrator, "_chat", return_value={"identities": copy.deepcopy(FIX_IDENTITIES)}) as chat:
            self.assertEqual(narrator.call("gen_identities", ctx), FIX_IDENTITIES)
            self.assertIn(ctx["last_narrator_error"], chat.call_args.args[0])
        self.assertEqual(ctx, before)

    def test_identity_object_is_unwrapped_and_validated(self):
        ctx = {"world": {"world_name": "测试世界", "premise": "背景", "lore": "传说"}}
        prompt = narrator.PROMPTS["gen_identities"](ctx)
        self.assertIn('"identities"', prompt)
        self.assertIn("禁止翻译、缩写或自创代码", prompt)
        with patch.object(narrator, "_chat", return_value={"identities": copy.deepcopy(FIX_IDENTITIES)}) as chat:
            self.assertEqual(narrator.call("gen_identities", ctx), FIX_IDENTITIES)
            chat.assert_called_once()
        for data in [copy.deepcopy(FIX_IDENTITIES), {}, {"identities": FIX_IDENTITIES[:5]}]:
            with patch.object(narrator, "_chat", return_value=data):
                with self.assertRaises(narrator.NarratorError):
                    narrator.call("gen_identities", ctx)
        bad = copy.deepcopy(FIX_IDENTITIES)
        bad[0]["gift"]["kind"] = "instant_win"
        with patch.object(narrator, "_chat", return_value={"identities": bad}):
            with self.assertRaisesRegex(narrator.NarratorError, "instant_win"):
                narrator.call("gen_identities", ctx)

    def test_good_samples_pass(self):
        world = copy.deepcopy(FIX_WORLD)
        world.pop("public_goal")
        world.pop("milestones")
        narrator.VALIDATORS["gen_world"](
            world, {"axes": {"engine": "误入秘境"}})
        tabletop_world = copy.deepcopy(FIX_WORLD)
        tabletop_world.pop("world_thread")
        tabletop_world.pop("goal_menu")
        narrator.VALIDATORS["gen_world"](
            tabletop_world, {"axes": {"form": "古典跑团"}})
        narrator.VALIDATORS["gen_identities"](copy.deepcopy(FIX_IDENTITIES))
        narrator.VALIDATORS["gen_milestones"](
            copy.deepcopy(FIX_MILESTONES),
            {"goals": [{"seat": "seat_a"}, {"seat": "seat_b"}]})
        narrator.VALIDATORS["gen_scene"](fix_scene(1))
        narrator.VALIDATORS["render_ending"]({"text": "结局" * 20})

    def bad(self, kind, data, ctx=None):
        with self.assertRaises(narrator.NarratorError):
            narrator.VALIDATORS[kind](data, ctx)

    def test_world_rejects(self):
        w = copy.deepcopy(FIX_WORLD)
        del w["laws"]
        self.bad("gen_world", w, {"axes": {"engine": "误入秘境"}})  # 缺字段
        w = copy.deepcopy(FIX_WORLD)
        w["laws"][0]["trigger_kind"] = "whenever_i_want"
        self.bad("gen_world", w, {"axes": {"engine": "误入秘境"}})  # 法则触发不可判
        w = copy.deepcopy(FIX_WORLD)
        w["hidden_threads"][0]["required"] = {"vibes": "good"}
        self.bad("gen_world", w, {"axes": {"engine": "误入秘境"}})  # 暗线条件不结构化
        w = copy.deepcopy(FIX_WORLD)
        w["goal_menu"][0]["text"] = "长" * 41
        self.bad("gen_world", w, {"axes": {"engine": "误入秘境"}})  # 目标菜单过长
        # power_level 已改为引擎按种子注入,荷官不写不算错

    def test_identities_reject_off_menu(self):
        ids = copy.deepcopy(FIX_IDENTITIES)
        ids[0]["gift"]["kind"] = "instant_win"
        self.bad("gen_identities", ids)                # 超模天赋出局
        ids = copy.deepcopy(FIX_IDENTITIES)
        ids[1]["starting_item"]["use"] = ["fly"]
        self.bad("gen_identities", ids)
        self.bad("gen_identities", FIX_IDENTITIES[:5])  # 数量不对

    def test_milestones_reject_disjunction_and_wrong_seats(self):
        ctx = {"goals": [{"seat": "seat_a"}, {"seat": "seat_b"}]}
        data = copy.deepcopy(FIX_MILESTONES)
        data["tracks"][0]["milestones"][0]["text"] = "找到遗稿或信物"
        self.bad("gen_milestones", data, ctx)
        data = copy.deepcopy(FIX_MILESTONES)
        data["tracks"].pop()
        self.bad("gen_milestones", data, ctx)

    def test_scene_rejects(self):
        sc = fix_scene(1)
        sc["text"] = "长" * 451
        self.bad("gen_scene", sc)
        sc = fix_scene(1)
        del sc["objects"]
        self.bad("gen_scene", sc)

    def badc(self, kind, data, ctx):
        with self.assertRaises(narrator.NarratorError):
            narrator.VALIDATORS[kind](data, ctx)

    def test_scene_response_debt_enforced(self):
        """NPC响应协议:欠债不还/枚举非法/内容太空,一律废稿。"""
        ctx = {"pending_interactions": [
            {"object_id": "patrol", "object_name": "巡检",
             "by": "失物招领员", "action": "盘问", "tier": "success"}]}
        good = fix_scene(2)
        good["npc_responses"] = [{"object_id": "patrol", "kind": "refused",
                                  "detail": "巡检说职责所限,不能透露布防。"}]
        narrator.VALIDATORS["gen_scene"](good, ctx)          # 合格样稿放行
        self.badc("gen_scene", fix_scene(2), ctx)            # 没交 npc_responses
        sc = fix_scene(2)
        sc["npc_responses"] = [{"object_id": "patrol", "kind": "ignored",
                                "detail": "他没理会。"}]
        self.badc("gen_scene", sc, ctx)                      # 枚举外的 kind
        sc = fix_scene(2)
        sc["npc_responses"] = [{"object_id": "patrol", "kind": "answered",
                                "detail": "嗯"}]
        self.badc("gen_scene", sc, ctx)                      # 回应没有实质内容
        sc = fix_scene(2)
        sc["npc_responses"] = [{"object_id": "gate", "kind": "answered",
                                "detail": "闸机嗡嗡作响地回答了。"}]
        self.badc("gen_scene", sc, ctx)                      # 债主没对上,装聋

    def test_scene_recurring_npc_needs_change(self):
        """刷脸铁律:登场过的对象再出现必须带 change,否则废稿。"""
        ctx = {"recurring_npcs": [{"name": "巡检", "appearances": 2,
                                   "last_scene": 2, "last_note": None}]}
        self.badc("gen_scene", fix_scene(3), ctx)            # 巡检再登场却无 change
        sc = fix_scene(3)
        for o in sc["objects"]:
            if o["name"] == "巡检":
                o["change"] = "巡检换了岗,眼神比昨天更疲惫。"
        narrator.VALIDATORS["gen_scene"](sc, ctx)            # 带变化即放行

    def test_ending_rejects(self):
        self.bad("render_ending", {"text": "太短"})
        self.bad("render_ending", {})


if __name__ == "__main__":
    unittest.main()
