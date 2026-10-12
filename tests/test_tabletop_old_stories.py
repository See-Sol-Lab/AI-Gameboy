"""六条旧事、数值调查与终幕推断；全部使用虚拟资料，无API调用。"""
import copy
import unittest
from unittest.mock import patch

from console import narrator
from test_pocket_tabletop import rules, setup_scene, old_story_world, old_story_identities, feed


class TestOldStories(unittest.TestCase):
    def round(self, s, params_a, params_b=None, die=6):
        params_b = params_b or {"intent": "recover", "action": "歇脚"}
        with patch.object(rules, "_die", return_value=die):
            s = rules.apply(s, "seat_a", "commit", params_a)
            return rules.apply(s, "seat_b", "commit", params_b)

    def test_contract_and_hidden_answers(self):
        ctx = {"axes": rules.new_game(["seat_a", "seat_b"], 1)["axes"], "old_story_mode": True}
        narrator.VALIDATORS["gen_world"](old_story_world(), ctx)
        narrator.VALIDATORS["gen_identities"](old_story_identities(), {"old_story_mode": True})
        bad = old_story_world()
        bad["side_quests"][1]["npc"]["name"] = "另一个人"
        with self.assertRaises(narrator.NarratorError):
            narrator.VALIDATORS["gen_world"](bad, ctx)
        s = setup_scene(41)
        ob = rules.observe(s, "seat_a")
        self.assertEqual(len(ob["public_state"]["old_stories"]), 6)
        self.assertTrue(all(q["truth"] is None for q in ob["public_state"]["old_stories"]))
        self.assertNotIn("key_facts", str(ob))
        partner = next(q for q in s["side_quests"] if q["owner"] == "seat_b")
        self.assertNotIn(partner["question"], str(ob))
        self.assertTrue(any(q["owner"] == "seat_a" for q in ob["private_state"]["old_story_choices"]))

    def test_success_reveals_original_without_advancing_main_goal(self):
        s = setup_scene(42)
        q = next(q for q in s["side_quests"] if q["owner"] == "seat_a")
        truth = q["truth"]
        s = self.round(s, {"intent": "explore", "action": "翻阅遗物", "old_story_id": q["id"]})
        self.assertEqual(next(x for x in s["side_quests"] if x["id"] == q["id"])["status"], "resolved")
        self.assertIn(f"真相大白:{truth}", s["facts"])
        self.assertEqual(s["milestones_done"], [])
        s = feed(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit", {"intent": "explore", "action": "重复查", "old_story_id": q["id"]})

    def test_failure_does_not_destroy_opportunity_and_cannot_take_partners_story(self):
        s = setup_scene(43)
        q = next(q for q in s["side_quests"] if q["owner"] == "seat_b")
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit", {"intent": "explore", "action": "查看", "old_story_id": q["id"]})
        q = next(q for q in s["side_quests"] if q["owner"] == "seat_a")
        s = self.round(s, {"intent": "explore", "action": "翻阅", "old_story_id": q["id"]}, die=1)
        self.assertEqual(next(x for x in s["side_quests"] if x["id"] == q["id"])["status"], "open")
        self.assertNotIn(q["truth"], str(s["history"][-1]["report"]))

    def late(self, scene):
        s = setup_scene(44)
        s["scene_index"] = scene
        s["danger"] = 0
        s["world"]["laws"] = []
        s["main_goal_locked"] = True
        s["milestones_done"] = [m["id"] for m in s["world"]["milestones"]]
        s["facts"].append("已知：渡口的名字属于本人，第四枚令牌一直在本人手里。")
        return s

    def test_npc_disappears_after_eight_and_no_late_numeric_investigation(self):
        s = self.late(8)
        self.assertIsNotNone(rules._npc_due(s, 8))
        self.assertIsNone(rules._npc_due(s, 9))
        ctx = rules._scene_context(s, [])
        self.assertIsNone(ctx["npc_onstage"])
        self.assertNotIn("npc", [q["owner"] for q in ctx["old_story_opportunities"]])
        self.assertIn("严禁再次安排", narrator.PROMPTS["gen_scene"](ctx))
        from test_pocket_crossing import fix_scene
        bad_scene = fix_scene(9)
        bad_scene["objects"][0] = {"id": "npc", "name": "守夜人", "hint": "回来了"}
        with self.assertRaises(narrator.NarratorError):
            narrator.VALIDATORS["gen_scene"](bad_scene, ctx)
        s["scene_index"] = 9
        q = s["side_quests"][0]
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "commit", {"intent": "explore", "action": "追NPC", "old_story_id": q["id"]})

    def test_final_turn_checks_inference_before_te_and_only_own_stories(self):
        s = self.late(10)
        s = self.round(s, {"intent": "explore", "action": "我在渡口刻回了姓名，并保管着第四枚令牌。"}, die=1)
        req = s["narration_request"]
        self.assertEqual(req["kind"], "check_old_stories")
        self.assertNotIn("npc", [q["seat"] for q in req["context"]["candidates"]])
        c = next(q for q in req["context"]["candidates"] if q["seat"] == "seat_a")
        match = {"seat": c["seat"], "id": c["id"], "quote": req["context"]["actions"]["seat_a"], "matched_facts": c["key_facts"]}
        narrator.VALIDATORS["check_old_stories"]({"matches": [match]}, req["context"])
        s = rules.apply_system(s, "narration_result", {"kind": "check_old_stories", "data": {"matches": [match]}})
        self.assertEqual(s["ending"]["kind"], "TE")
        self.assertEqual(next(q for q in s["side_quests"] if q["id"] == c["id"])["status"], "resolved")

    def test_inference_rejects_fabricated_quote_and_incomplete_or_foreign_match(self):
        s = self.round(self.late(9), {"intent": "explore", "action": "我在渡口刻回了姓名，并保管着第四枚令牌。"})
        ctx = s["narration_request"]["context"]
        c = next(q for q in ctx["candidates"] if q["seat"] == "seat_a")
        good = {"seat": "seat_a", "id": c["id"], "quote": ctx["actions"]["seat_a"], "matched_facts": c["key_facts"]}
        for key, value in [("quote", "一段不存在的原话"), ("matched_facts", c["key_facts"][:1]), ("id", "npc1")]:
            bad = dict(good, **{key: value})
            with self.assertRaises(narrator.NarratorError):
                narrator.VALIDATORS["check_old_stories"]({"matches": [bad]}, ctx)
        s = rules.apply_system(s, "narration_result", {"kind": "check_old_stories", "data": {"matches": []}})
        self.assertEqual(s["narration_request"]["kind"], "gen_scene")
        self.assertTrue(all(q["status"] == "open" for q in s["side_quests"]))

    def test_all_six_revealed_finishes_early_and_be_has_priority(self):
        s = self.late(4)
        for q in s["side_quests"]:
            q["status"] = "resolved"
        rules._continue_after_round(s)
        self.assertEqual(s["ending"]["kind"], "HE")
        s = self.late(4)
        for q in s["side_quests"]:
            q["status"] = "resolved"
        s["danger"] = 10
        rules._continue_after_round(s)
        self.assertEqual(s["ending"]["kind"], "BE")

    def test_four_round_numeric_playthrough_finishes_he(self):
        s = setup_scene(46)
        s["world"]["laws"] = []
        s["inventory"]["seat_b"].append({"id": "goal_tool", "name": "过闸凭证", "use": ["advance"]})
        quests = {owner: [q["id"] for q in s["side_quests"] if q["owner"] == owner]
                  for owner in ("npc", "seat_a", "seat_b")}
        def investigate(qid):
            return {"intent": "explore", "action": "沿线索查看遗物", "old_story_id": qid}
        rounds = [(quests["npc"][0], quests["seat_b"][0]),
                  (quests["npc"][1], quests["seat_b"][1]),
                  (quests["seat_a"][0], None), (quests["seat_a"][1], None)]
        for qa, qb in rounds:
            s = self.round(s, investigate(qa), investigate(qb) if qb else {"intent": "advance", "action": "完成当前主线阶段", "item_id": "goal_tool"})
            self.assertEqual(next(q for q in s["side_quests"] if q["id"] == qa)["status"], "resolved", s["history"][-1]["report"])
            if s["stage"] != "endinggen":
                s = feed(s)
        self.assertEqual(s["ending"]["kind"], "HE")
        self.assertEqual(s["scene_index"], 4)
        self.assertEqual(sum(q["status"] == "resolved" for q in s["side_quests"]), 6)

    def test_tenth_turn_inference_can_complete_he_without_successful_die(self):
        s = self.late(10)
        own = next(q for q in s["side_quests"] if q["owner"] == "seat_a")
        for q in s["side_quests"]:
            if q is not own:
                q["status"] = "resolved"
        s = self.round(s, {"intent": "explore", "action": "我在渡口刻回了姓名，并保管着第四枚令牌。"}, die=1)
        self.assertFalse(any("已做到:我在渡口" in fact for fact in s["facts"]))
        req = s["narration_request"]
        c, = req["context"]["candidates"]
        match = {"seat": c["seat"], "id": c["id"], "quote": req["context"]["actions"]["seat_a"], "matched_facts": c["key_facts"]}
        s = rules.apply_system(s, "narration_result", {"kind": "check_old_stories", "data": {"matches": [match]}})
        self.assertEqual(s["ending"]["kind"], "HE")

    def test_legacy_save_still_uses_original_contract(self):
        s = rules.new_game(["seat_a", "seat_b"], 12)
        s.pop("old_story_mode")
        s["narration_request"]["context"].pop("old_story_mode")
        s = feed(s)
        self.assertEqual(len(s["side_quests"]), 2)
        self.assertNotIn("old_story_mode", s)


if __name__ == "__main__":
    unittest.main()
