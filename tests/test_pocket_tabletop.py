"""《口袋跑团》v1.0 冒烟测试:经典危机词库 + 与口袋穿越同源的引擎机制。"""

import importlib.util
import unittest
from pathlib import Path

from test_pocket_crossing import FIX_WORLD, FIX_IDENTITIES, fix_scene, SEATS

_spec = importlib.util.spec_from_file_location(
    "pocket_tabletop_rules",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "pocket-tabletop" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)


def feed(s):
    while s.get("narration_request"):
        kind = s["narration_request"]["kind"]
        data = {"gen_world": FIX_WORLD, "gen_identities": FIX_IDENTITIES,
                "gen_scene": fix_scene(s["scene_index"] + 1)}.get(
            kind, {"text": "跑团之城照常运转,危机如期解除。" * 2})
        s = rules.apply_system(s, "narration_result", {"kind": kind, "data": data})
    return s


class TestPocketTabletop(unittest.TestCase):
    def test_classic_axes_keys(self):
        s = rules.new_game(SEATS, 7)
        self.assertEqual(set(s["axes"]),
                         {"form", "power", "kind", "mood", "variable"})
        self.assertEqual(s["axes"], rules.new_game(SEATS, 7)["axes"])

    def test_pool_members(self):
        self.assertIn(("修仙世界", 1), rules.POOLS["form"])
        self.assertNotIn("engine", rules.POOLS)   # 新词库不进这张卡

    def test_full_game_smoke(self):
        s = feed(rules.new_game(SEATS, 8))
        for seat in SEATS:
            s = rules.apply(s, seat, "choose_identity",
                            {"identity_id": s["identity_offers"][seat][0]})
        s = feed(s)
        self.assertEqual(s["stage"], "scene")
        # 支线暗典机制同样在场
        self.assertEqual(len(s["side_quests"]), 2)
        self.assertEqual(len(s["hooks"]), 2)
        # 双双停笔可收卷
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = rules.apply(s, "seat_b", "commit", {"intent": "end", "action": ""})
        s = feed(s)
        self.assertEqual(s["phase"], "finished")
        self.assertIn(s["ending"]["kind"], ("HE", "BE", "TE"))


if __name__ == "__main__":
    unittest.main()
