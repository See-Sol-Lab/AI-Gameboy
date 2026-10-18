"""成功获得预写证据，推断命中后才完成；含不泄密与荷官越权回归。"""
import unittest
import json
from copy import deepcopy
from console import tabletop_contract as contract
from test_pocket_tabletop import rules,setup,round_,feed,advance,world,scene


def investigate(s,owner="npc"):
    q = next(q for q in s["side_quests"] if q["owner"] == owner and q["status"] == "open")
    return q,{"intent":"explore","action":"我检查旧照片背面的署名，并向守门人询问钥匙用途。","target_id":"clue:"+q["id"]}


def match(c):
    return {"seat":c["seat"],"story_id":c["story_id"],"quote":c["action"]}


class TestStoryEvidence(unittest.TestCase):
    def test_final_input_preserves_prior_and_current_closing_decisions(self):
        s = setup()
        s["scene_index"] = 9
        earlier = "巨鲸只做最后备份，不替居民决定哪些记忆值得保存。"
        latest = "哑贝保持封存，开启前征得当事人同意。"
        s = feed(round_(s, {"intent":"end", "action":earlier}, advance("m1")))
        self.assertEqual(s["scene_index"], 10)
        s = round_(s, {"intent":"end", "action":"由居民共同维护记忆。"},
                   {"intent":"end", "action":latest})
        ctx = s["narration_request"]["context"]
        self.assertEqual([d["scene_index"] for d in ctx["closing_decisions"]], [9, 10, 10])
        self.assertEqual(ctx["closing_decisions"][0]["action"], earlier)
        prompt = contract.prompt("tt_turn", ctx)
        for value in (earlier, latest, "尚未决定的去留保持开放", "关键道具如何被使用、合成或安置"):
            self.assertIn(value, prompt)
        self.assertEqual(feed(s)["ending"]["kind"], "TE")

    def test_closing_decision_reaches_ending_input_without_unearned_rewards(self):
        s = setup()
        s["scene_index"] = 10
        decision = "将记忆彻底隔离于系统权限；唤醒后本人保留自主选择权。"
        s = round_(s, {"intent":"end", "target_id":"free", "action":decision},
                   {"intent":"end", "target_id":"free", "action":""})
        ctx = s["narration_request"]["context"]
        self.assertEqual(ctx["outcomes"][0]["result"], "closing_decision")
        self.assertIn(decision, contract.prompt("tt_turn", ctx))
        self.assertIn(decision, str(s["history"][-1]["report"]))
        self.assertEqual(ctx["approved_actions"], [])
        self.assertEqual(ctx["candidates"], [])
        self.assertEqual(feed(s)["ending"]["kind"], "TE")

    def test_retired_npc_is_removed_from_turn_scene_input(self):
        s = setup()
        s["scene_index"] = 8
        s["npc"]["desc"] = "现场专属描述不应进入后续荷官输入"
        s = round_(s, advance("m1"))
        prompt = contract.prompt("tt_turn", s["narration_request"]["context"])
        self.assertNotIn(s["npc"]["desc"], prompt)
        self.assertIn('"npc": null', prompt)
        self.assertNotIn('"key_facts"', contract.prompt("tt_world", {"axes":{}}))
        self.assertNotIn('"matched_facts"', prompt)

    def test_final_investigation_can_resolve_before_he_settlement(self):
        s = setup()
        s["scene_index"] = 10
        for node in s["nodes"].values():
            node["done"] = True
        q = next(q for q in s["side_quests"] if q["owner"] == "seat_a")
        for other in s["side_quests"]:
            if other is not q:
                other["status"] = "resolved"
        action = {"intent":"explore", "target_id":"clue:"+q["id"], "action":q["truth"]}
        s = round_(s, action, {"intent":"end", "target_id":"free", "action":""})
        c, = s["narration_request"]["context"]["candidates"]
        self.assertEqual(c["evidence"], q["clues"])
        s = feed(s, [match(c)])
        self.assertEqual(s["ending"]["kind"], "HE")

    def test_final_investigation_without_correct_conclusion_remains_te(self):
        for action_text, die in (("是谁留下钥匙，为什么留下？", 6), ("海神留下钥匙统治海港。", 6),
                                 ("见证人甲曾共同守门，钥匙用于让旅人进入避风港。", 1)):
            s = setup()
            s["scene_index"] = 10
            q, action = investigate(s, "seat_a")
            action["action"] = action_text
            if die == 1:
                s["attrs"]["seat_a"]["wisdom"] = 1
            s = round_(s, action, {"intent":"end", "target_id":"free", "action":""}, die=die)
            if die == 1:
                self.assertEqual(s["narration_request"]["context"]["candidates"], [])
            s = feed(s)
            self.assertEqual(s["ending"]["kind"], "TE")
            self.assertEqual(next(x for x in s["side_quests"] if x["id"] == q["id"])["status"], "open")

    def test_turn_template_has_exact_changes_even_when_actions_are_deductions(self):
        states = []
        states.append(round_(setup(), advance("m1")))
        states.append(round_(setup(), advance("m1"), {"intent":"end","action":"","target_id":"free"}))
        s = setup()
        for q in s["side_quests"][:2]:
            q["found_clues"] = [0, 1]
        actions = [{"intent":"explore", "target_id":"deduce:" + q["id"], "action":q["truth"]}
                   for q in s["side_quests"][:2]]
        states.append(round_(s, actions[0], actions[1]))
        for state, expected in zip(states, (2, 1, 0)):
            ctx = state["narration_request"]["context"]
            prompt = contract.prompt("tt_turn", ctx)
            output = json.loads(prompt.split("【输出模板】\n")[1])
            self.assertEqual(len(output["world_changes"]), expected)
            self.assertEqual(output["deductions"], [])
            for result, approved in zip(output["world_changes"], ctx["approved_actions"]):
                self.assertEqual((result["seat"], result["quote"]), (approved["seat"], approved["action"]))
            self.assertEqual(output["scene"]["location_id"], ctx["snapshot"]["location_id"])
            contract.validate("tt_turn", output, ctx)
        output["world_changes"] = [{"seat":"seat_a","quote":actions[0]["action"],"text":"额外编造的变化"}]
        with self.assertRaisesRegex(ValueError, "world_changes必须恰好0条"):
            contract.validate("tt_turn", output, ctx)

    def test_turn_prompt_is_self_contained_and_scene_length_errors_are_reported_together(self):
        s = round_(setup(), advance("m1"))
        ctx = s["narration_request"]["context"]
        prompt = contract.prompt("tt_turn", ctx)
        for expected in ("1到30字符", "1到700字符", "1到160字符", "1到180字符", "1到5个对象", "snapshot.location_id"):
            self.assertIn(expected, prompt)
        bad = scene(ctx["snapshot"])
        bad.update(title="题" * 31, text="文" * 701, crisis="事" * 161)
        with self.assertRaises(ValueError) as caught:
            contract.validate_scene(bad, ctx["snapshot"])
        for expected in ("title", "text", "crisis", "实际31字符", "实际701字符", "实际161字符"):
            self.assertIn(expected, str(caught.exception))
        bad.update(title="题" * 30, text="文" * 700, crisis="事" * 160)
        contract.validate_scene(bad, ctx["snapshot"])

    def test_npc_field_errors_are_distinct_and_contract_has_matching_example(self):
        cases = [("id", "gatekeeper", "npc.id"), ("location_id", None, "缺少location_id"),
                 ("location_id", "海港", "引用locations的id")]
        for field, value, expected in cases:
            data = world()
            if value is None:
                data["npc"].pop(field)
            else:
                data["npc"][field] = value
            with self.assertRaisesRegex(ValueError, expected):
                contract.validate_world(data)
        prompt = contract.prompt("tt_world", {"axes": {}})
        self.assertIn('"location_id":"harbor"', prompt)
        self.assertIn('必须逐字写"npc"', prompt)

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
