"""荷官校验器测试:合格样稿放行,越权/缺字段/超模一律打回(不联网)。"""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import narrator  # noqa: E402
from test_pocket_crossing import FIX_WORLD, FIX_IDENTITIES, fix_scene  # noqa: E402


class TestValidators(unittest.TestCase):
    def test_good_samples_pass(self):
        narrator.VALIDATORS["gen_world"](copy.deepcopy(FIX_WORLD))
        narrator.VALIDATORS["gen_identities"](copy.deepcopy(FIX_IDENTITIES))
        narrator.VALIDATORS["gen_scene"](fix_scene(1))
        narrator.VALIDATORS["render_ending"]({"text": "结局" * 20})

    def bad(self, kind, data):
        with self.assertRaises(narrator.NarratorError):
            narrator.VALIDATORS[kind](data)

    def test_world_rejects(self):
        w = copy.deepcopy(FIX_WORLD)
        del w["laws"]
        self.bad("gen_world", w)                       # 缺字段
        w = copy.deepcopy(FIX_WORLD)
        w["laws"][0]["trigger_kind"] = "whenever_i_want"
        self.bad("gen_world", w)                       # 法则触发不可判
        w = copy.deepcopy(FIX_WORLD)
        w["hidden_threads"][0]["required"] = {"vibes": "good"}
        self.bad("gen_world", w)                       # 暗线条件不结构化
        # power_level 已改为引擎按种子注入,荷官不写不算错

    def test_identities_reject_off_menu(self):
        ids = copy.deepcopy(FIX_IDENTITIES)
        ids[0]["gift"]["kind"] = "instant_win"
        self.bad("gen_identities", ids)                # 超模天赋出局
        ids = copy.deepcopy(FIX_IDENTITIES)
        ids[1]["starting_item"]["use"] = ["fly"]
        self.bad("gen_identities", ids)
        self.bad("gen_identities", FIX_IDENTITIES[:5])  # 数量不对

    def test_scene_rejects(self):
        sc = fix_scene(1)
        sc["text"] = "长" * 451
        self.bad("gen_scene", sc)
        sc = fix_scene(1)
        del sc["objects"]
        self.bad("gen_scene", sc)

    def test_ending_rejects(self):
        self.bad("render_ending", {"text": "太短"})
        self.bad("render_ending", {})


if __name__ == "__main__":
    unittest.main()
