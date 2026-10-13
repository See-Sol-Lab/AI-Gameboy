"""成功获得预写证据，推断命中后才完成；含不泄密与荷官越权回归。"""
import unittest
from copy import deepcopy
from console import tabletop_contract as contract
from test_pocket_tabletop import rules,setup,round_,feed,advance,world,scene


def investigate(s,owner="npc"):
    q = next(q for q in s["side_quests"] if q["owner"] == owner and q["status"] == "open")
    return q,{"intent":"explore","action":"我检查旧照片背面的署名，并向守门人询问钥匙用途。","target_id":"clue:"+q["id"]}


def match(c):
    return {"seat":c["seat"],"story_id":c["story_id"],"quote":c["action"],"matched_facts":c["key_facts"]}


class TestStoryEvidence(unittest.TestCase):
    def test_success_pays_fixed_clues_not_answer(self):
        s = setup()
        q,p = investigate(s)
        s = round_(s,p)
        updated = next(x for x in s["side_quests"] if x["id"] == q["id"])
        self.assertEqual(updated["found_clues"],[0,1])
        self.assertEqual(updated["status"],"open")
        self.assertNotIn(q["truth"],str(s["facts"])+str(s["history"]))
        public = rules.observe(s,"seat_a")["public_state"]
        view = next(x for x in public["old_stories"] if x["id"] == q["id"])
        self.assertEqual(view["clues"],q["clues"])
        self.assertIsNone(view["truth"])

    def test_partial_pays_one_clue_and_retry_keeps_evidence(self):
        s = setup()
        s["attrs"]["seat_a"]["wisdom"] = 2
        q,p = investigate(s)
        s = round_(s,p,{"intent":"end","target_id":"free","action":""},die=2)
        self.assertEqual(s["side_quests"][0]["found_clues"],[0])
        s = round_(feed(s),p,{"intent":"end","target_id":"free","action":""},die=2)
        self.assertEqual(s["side_quests"][0]["found_clues"],[0,1])
        self.assertEqual(s["side_quests"][0]["status"],"open")

    def test_valid_deduction_completes_only_selected_story(self):
        s = setup()
        q,p = investigate(s)
        s = feed(round_(s,p))
        p = {"intent":"explore","target_id":"deduce:"+q["id"],"action":"照片说明见证人甲曾共同守门；旧信说明这把钥匙用于让旅人进入避风港。"}
        s = round_(s,p)
        c, = s["narration_request"]["context"]["candidates"]
        s = feed(s,[match(c)])
        self.assertEqual(sum(q["status"] == "resolved" for q in s["side_quests"]),1)
        self.assertEqual(s["side_quests"][0]["status"],"resolved")

    def test_wrong_guess_preserves_clues_and_no_random_guess_without_evidence(self):
        s = setup()
        q,p = investigate(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s,"seat_a","commit",{"intent":"explore","target_id":"deduce:"+q["id"],"action":"我猜所有秘密都和海神有关。"})
        s = feed(round_(s,p))
        s = feed(round_(s,{"intent":"explore","target_id":"deduce:"+q["id"],"action":"我认为这是海神留下的钥匙，照片中的人就是海神。"}))
        self.assertEqual(s["side_quests"][0]["found_clues"],[0,1])
        self.assertEqual(s["side_quests"][0]["status"],"open")

    def test_npc_leaves_after_eight_but_acquired_evidence_remains_usable(self):
        s = setup()
        s["scene_index"] = 8
        q,p = investigate(s)
        s = feed(round_(s,p))
        self.assertEqual(s["scene_index"],9)
        self.assertFalse(s["npc"]["available"])
        targets = rules.observe(s,"seat_a")["private_state"]["targets"]
        self.assertNotIn("clue:"+q["id"],[t["id"] for t in targets])
        self.assertIn("deduce:"+q["id"],[t["id"] for t in targets])
        self.assertNotIn("npc",[o["id"] for o in s["current_scene"]["objects"]])

    def test_private_clues_and_answers_do_not_leak_to_partner(self):
        s = setup()
        q,p = investigate(s,"seat_a")
        s = round_(s,p)
        ob = rules.observe(s,"seat_b")
        self.assertNotIn(q["clues"][0]["text"],str(ob))
        own = rules.observe(s,"seat_a")["private_state"]
        self.assertIn(q["clues"][0]["text"],str(own))
        self.assertNotIn(q["truth"],str(own))

    def test_scene_input_contains_no_unearned_clues_or_old_tragedy(self):
        s = setup()
        ctx = {"snapshot":rules._snapshot(s)}
        prompt = contract.prompt("tt_scene",ctx)
        for q in s["side_quests"]:
            self.assertNotIn(q["truth"],prompt)
            self.assertNotIn(q["clues"][0]["text"],prompt)
        self.assertNotIn(s["world"]["original_ending"],prompt)

    def test_contract_rejects_reset_item_npc_teleport_and_early_secret(self):
        s = feed(round_(setup(),advance("m1")))
        ctx = {"snapshot":rules._snapshot(s)}
        for obj in [{"id":"key1","name":"钥匙1","hint":"还没取走"},{"id":"invented","name":"新谜题","hint":"新任务"}]:
            d = scene(ctx["snapshot"])
            d["objects"].append(obj)
            with self.assertRaises(ValueError):
                contract.validate("tt_scene",d,ctx)
        ctx["snapshot"]["location_id"] = "tower"
        ctx["snapshot"]["allowed_objects"] = [{"id":"tower","name":"灯塔"}]
        d = scene(ctx["snapshot"])
        d["objects"].append({"id":"npc","name":"守门人","hint":"突然在塔楼出现"})
        with self.assertRaises(ValueError):
            contract.validate("tt_scene",d,ctx)
        d = scene(ctx["snapshot"])
        d["text"] = s["side_quests"][0]["truth"]
        with self.assertRaises(ValueError):
            contract.validate("tt_scene",d,ctx)

    def test_full_completion_can_be_he_and_bad_numbers_still_be(self):
        s = setup()
        for mid in ("m1","m2","m3"):
            s = feed(round_(s,advance(mid)))
        for q in s["side_quests"]:
            q["status"] = "resolved"
        s = feed(round_(s,{"intent":"advance","target_id":"free","action":"我开起一间农具铺，为获救居民准备新的生活。"}))
        self.assertEqual(s["ending"]["kind"],"HE")
        self.assertLess(s["scene_index"],10)
        self.assertEqual(contract.ending_kind(dict(rules._snapshot(s),danger=10)),"BE")

    def test_duplicates_and_foreign_deductions_are_rejected(self):
        s = setup()
        q,p = investigate(s)
        s = feed(round_(s,p))
        s = round_(s,{"intent":"explore","target_id":"deduce:"+q["id"],"action":"见证人甲曾共同守门，钥匙为了让旅人进入避风港。"})
        ctx = s["narration_request"]["context"]
        c, = ctx["candidates"]
        valid = match(c)
        base = {"world_changes":[{"seat":a["seat"],"quote":a["action"],"text":"帮助同伴完成了准备工作。"} for a in ctx["approved_actions"]],"scene":scene(ctx["snapshot"]),"ending":None}
        for guesses in [[valid,valid],[dict(valid,seat="seat_b")],[dict(valid,quote="我从未说过的假原文")]]:
            with self.assertRaises(ValueError):
                contract.validate("tt_turn",dict(base,deductions=guesses),ctx)


if __name__ == "__main__":
    unittest.main()
