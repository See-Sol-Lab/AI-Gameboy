"""《口袋跑团》v1.0 冒烟测试:经典危机词库 + 与口袋穿越同源的引擎机制。"""

import importlib.util
import copy
import unittest
from pathlib import Path

from test_pocket_crossing import FIX_WORLD, FIX_IDENTITIES, fix_scene, SEATS

_spec = importlib.util.spec_from_file_location(
    "pocket_tabletop_rules",
    Path(__file__).resolve().parents[1]
    / "cartridges" / "pocket-tabletop" / "rules.py")
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)


def story(sid, owner="旅人"):
    return {"id": sid, "question": f"{owner}的{sid}旧事是什么？",
            "truth": f"{owner}在渡口刻回了姓名，并保管着第四枚令牌。",
            "key_facts": ["在渡口刻回了姓名", "保管着第四枚令牌"], "intent": "explore"}


def old_story_world():
    w = copy.deepcopy(FIX_WORLD)
    w.pop("world_thread", None)
    w.pop("goal_menu", None)
    w["side_quests"] = [dict(story(f"npc{i}", "守夜人"), npc={"name": "守夜人", "desc": "守在渡口"}) for i in (1, 2)]
    return w


def old_story_identities():
    ids = copy.deepcopy(FIX_IDENTITIES)
    for card in ids:
        card.pop("secret_drive")
        card["old_stories"] = [story(f"past{i}", card["name"]) for i in (1, 2)]
    return ids


def feed(s):
    while s.get("narration_request"):
        kind = s["narration_request"]["kind"]
        modern = s.get("old_story_mode")
        data = {"gen_world": old_story_world() if modern else FIX_WORLD,
                "gen_identities": old_story_identities() if modern else FIX_IDENTITIES,
                "check_old_stories": {"matches": []},
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
        self.assertEqual(len(s["side_quests"]), 6)
        self.assertEqual(len(s["hooks"]), 2)
        # 双双停笔可收卷
        s = rules.apply(s, "seat_a", "commit", {"intent": "end", "action": ""})
        s = rules.apply(s, "seat_b", "commit", {"intent": "end", "action": ""})
        s = feed(s)
        self.assertEqual(s["phase"], "finished")
        self.assertIn(s["ending"]["kind"], ("HE", "BE", "TE"))


def setup_scene(seed):
    s = feed(rules.new_game(SEATS, seed))
    for seat in SEATS:
        s = rules.apply(s, seat, "choose_identity",
                        {"identity_id": s["identity_offers"][seat][0]})
    return feed(s)


def resolve_with(s, die, event=None):
    if event:
        s["current_scene"]["event"] = event
    orig = rules._die
    rules._die = lambda st: die
    try:
        s = rules.apply(s, "seat_a", "commit", {"intent": "explore", "action": "看"})
        s = rules.apply(s, "seat_b", "commit", {"intent": "explore", "action": "看"})
    finally:
        rules._die = orig
    return s


class TestTabletopV11(unittest.TestCase):
    """v1.1:与口袋穿越 v0.6 同步的三维、随机事件与结局三档。"""

    def test_attrs_and_event(self):
        s = setup_scene(21)
        self.assertTrue(all(1 <= v <= 6 for x in SEATS for v in s["attrs"][x].values()))
        s["attrs"] = {x: {"wisdom": 6, "stamina": 6, "luck": 1} for x in SEATS}
        s["danger"] = 4
        s = resolve_with(s, 6, {"text": "城门塌了半边", "difficulty": "hard"})
        self.assertTrue(s["events"]["log"][-1]["won"])     # 26 + 6 + 6 = 38 ≥ 31

    def test_progress_full_locks_and_danger_full_is_be(self):
        s = setup_scene(22)
        s["progress"] = 9
        s = resolve_with(s, 6)
        self.assertTrue(s["main_goal_locked"])
        s = feed(s)
        s["danger"] = 10
        s = resolve_with(s, 3)
        self.assertEqual(s["ending"]["kind"], "BE")


if __name__ == "__main__":
    unittest.main()
