"""跑团2.0的虚拟剧本与实际规则流程，绝不调用真实荷官。"""
import importlib.util
import unittest
import json
import tempfile
from copy import deepcopy
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from console import tabletop_contract as contract
from console import narrator,store
from console.game_host import GameHost

spec = importlib.util.spec_from_file_location("tabletop", Path(__file__).resolve().parents[1] / "cartridges/pocket-tabletop/rules.py")
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)
SEATS = ["seat_a", "seat_b"]


def story(sid):
    return {"id": sid, "question": "旧照片上的人为何留下这把钥匙？", "intent": "explore", "attribute": "wisdom", "target": 7,
            "clues": [{"source": "旧照片", "text": "照片背面写着：我与见证人甲曾一同守门。"},
                      {"source": "旧信", "text": "见证人甲说：我留下钥匙，是为让后来的旅人进入避风港。"}],
            "truth": "见证人甲曾共同守门，留下钥匙是为了让旅人进入避风港。"}


def world():
    return {"world_name": "验收港", "premise": "两位旅人来到受灾海港。", "lore": "旧堤正在漏水。", "public_goal": "修好海堤，营救居民。",
            "original_ending": "没有旅人时海堤崩塌。", "original_story": [{"chapter": i, "title": "旧海港", "event": "旧堤继续漏水。"} for i in range(1,7)],
            "locations": [{"id": i, "name": name} for i,name in [("harbor","海港"),("tower","灯塔"),("field","田地")]], "starting_location": "harbor",
            "npc": {"id": "npc", "name": "守门人", "desc": "站在门边", "location_id": "harbor"},
            "items": [{"id": "key"+str(i), "name": "钥匙"+str(i), "use": ["advance"]} for i in range(1,4)],
            "main_nodes": [{"id": "m"+str(i), "title": "修复阶段"+str(i), "location_id": loc, "attribute": "wisdom", "target": 7,
                            "item_ids": ["key"+str(i)], "npc_destination": None, "success_fact": "阶段"+str(i)+"已完成。" if i<3 else "海堤已修好，共同危机解除。"}
                           for i,loc in [(1,"harbor"),(2,"tower"),(3,"field")]],
            "events": [{"id": "e"+str(i), "title": "营救居民"+str(i), "location_id": "harbor", "attribute": "stamina", "target": 6, "success_fact": "居民"+str(i)+"已获救。"} for i in range(1,4)],
            "npc_old_stories": [story("n1"),story("n2")]}


def identities():
    return {"identities": [{"id": "role"+str(i), "name": "旅人"+str(i), "origin": "来自邻镇", "specialty": "explore",
                            "starting_item": {"id": "tool"+str(i), "name": "工具"+str(i), "use": ["explore","support"]},
                            "old_stories": [story("p1"),story("p2")]} for i in range(6)]}


def scene(snapshot):
    return {"title": "海港现场", "text": "旅人们面前是仍然运转的海港。", "crisis": "选择本幕行动。", "location_id": snapshot["location_id"],
            "objects": [dict(o, hint="当前可观察的对象") for o in snapshot["allowed_objects"][:3]]}


def feed(s, matches=None, change_text=None):
    req = s["narration_request"]
    if not req:
        return s
    kind, ctx = req["kind"], req["context"]
    if kind == "tt_world":
        data = world()
    elif kind == "tt_identities":
        data = identities()
    elif kind == "tt_scene":
        data = scene(ctx["snapshot"])
    else:
        matches = matches or []
        end = contract.ending_kind(ctx["snapshot"], [m["story_id"] for m in matches])
        data = {"deductions": matches, "world_changes": [{"seat": a["seat"], "quote": a["action"], "text": change_text or "旅人用自己的方法完成了本幕行动。"} for a in ctx["approved_actions"]],
                "scene": None if end else scene(ctx["snapshot"]), "ending": {"kind": end,"text": "海港承接玩家真实做成的事情，留下了新的故事。"} if end else None}
    contract.validate(kind,data,ctx)
    return rules.apply_system(s,"narration_result",{"kind":kind,"data":data})


def setup(seed=7):
    s = feed(feed(rules.new_game(SEATS,seed)))
    for seat in SEATS:
        s = rules.apply(s,seat,"choose_identity",{"identity_id":s["identity_offers"][seat][0]})
    s = feed(s)
    s["attrs"] = {seat:{"wisdom":4,"stamina":4,"luck":4} for seat in SEATS}
    return s


def round_(s, a, b=None, die=6):
    b = b or {"intent":"support","action":"我帮助同伴处理眼前的事情。","target_id":"free"}
    with patch.object(rules,"_die",return_value=die):
        s = rules.apply(s,"seat_a","commit",a)
        return rules.apply(s,"seat_b","commit",b)


def advance(mid):
    return {"intent":"advance","target_id":"main:"+mid,"action":"我利用现有工具，完成当前海堤修复阶段。"}


class TestTabletop(unittest.TestCase):
    def test_world_and_cards_contract(self):
        s = setup()
        self.assertEqual(len(s["side_quests"]),6)
        self.assertEqual(rules.new_game(SEATS,7),rules.new_game(SEATS,7))
        self.assertNotIn("clock",s)
        self.assertEqual(s["ruleset"],2)

    def test_main_progress_only_counts_completed_nodes_and_awards_inventory(self):
        s = round_(setup(),advance("m1"))
        self.assertEqual(rules.observe(s,"seat_a")["public_state"]["tracks"]["progress"],1)
        self.assertEqual(s["item_owners"]["key1"],"shared")
        self.assertEqual([i["id"] for i in s["inventory"]["shared"]],["key1"])
        s = feed(s)
        self.assertNotIn("main:m1",[t["id"] for t in rules.observe(s,"seat_a")["private_state"]["targets"]])
        self.assertNotIn("key1",[o["id"] for o in s["narration_request"]["context"]["snapshot"]["allowed_objects"]] if s["narration_request"] else [o["id"] for o in s["current_scene"]["objects"]])
        s = round_(s,{"intent":"explore","target_id":"free","action":"我调查附近海堤的渗水痕迹。"})
        self.assertEqual(sum(n["done"] for n in s["nodes"].values()),1)

    def test_partial_main_progress_accumulates_without_premature_item(self):
        s = setup()
        s["attrs"]["seat_a"]["wisdom"] = 2
        wait = {"intent":"end","action":"","target_id":"free"}
        s = round_(s,advance("m1"),wait,die=3)
        self.assertEqual(s["nodes"]["m1"],{"done":False,"effort":1})
        self.assertNotIn("key1",s["item_owners"])
        s = round_(feed(s),advance("m1"),wait,die=3)
        self.assertTrue(s["nodes"]["m1"]["done"])
        self.assertIn("key1",s["item_owners"])

    def test_success_moves_party_but_not_npc(self):
        s = feed(round_(setup(),advance("m1")))
        s = round_(s,advance("m2"))
        self.assertEqual(s["location_id"],"tower")
        self.assertEqual(s["npc"]["location_id"],"harbor")
        self.assertNotIn("npc",[o["id"] for o in s["narration_request"]["context"]["snapshot"]["allowed_objects"]])

    def test_attributes_affect_checks_and_source_is_immutable(self):
        original = setup()
        low = deepcopy(original)
        low["attrs"]["seat_a"]["wisdom"] = 1
        high = deepcopy(original)
        high["attrs"]["seat_a"]["wisdom"] = 6
        wait = {"intent":"end","action":"","target_id":"free"}
        self.assertFalse(round_(low,advance("m1"),wait,die=1)["nodes"]["m1"]["done"])
        self.assertTrue(round_(high,advance("m1"),wait,die=1)["nodes"]["m1"]["done"])
        self.assertFalse(original["nodes"]["m1"]["done"])

    def test_main_complete_allows_farming_without_restarting_crisis(self):
        s = setup()
        for mid in ("m1","m2","m3"):
            s = feed(round_(s,advance(mid)))
        danger = s["danger"]
        action = "我把修好的海堤改造成灌溉渠，开设一间教人种田的铺子。"
        s = round_(s,{"intent":"advance","target_id":"free","action":action})
        self.assertEqual(s["danger"],danger)
        ctx = s["narration_request"]["context"]
        self.assertNotIn("original_ending",ctx)
        s = feed(s,change_text="海堤旁开起农具铺，灌溉渠让居民学会种田。")
        s = round_(s,{"intent":"support","target_id":"free","action":"我帮居民经营现有的农具铺，教孩子辨认种子。"})
        self.assertIn("农具铺",str(s["narration_request"]["context"]["snapshot"]["world_changes"]))
        self.assertTrue(all(n["done"] for n in s["nodes"].values()))

    def test_invalid_target_or_item_and_duplicate_commit(self):
        s = setup()
        for params in [dict(advance("m3")),dict(advance("m1"),item_id="foreign-tool")]:
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s,"seat_a","commit",params)
        s = rules.apply(s,"seat_a","commit",advance("m1"))
        self.assertEqual(rules.observe(s,"seat_b")["public_state"]["reserved_targets"],{"seat_a":"main:m1"})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s,"seat_a","commit",advance("m1"))

    def test_be_priority_and_tenth_turn_te(self):
        s = setup()
        s["danger"] = 9
        s = feed(round_(s,{"intent":"recover","target_id":"free","action":"我停下来休整，为同伴包扎伤口。"}))
        self.assertEqual(s["ending"]["kind"],"BE")
        s = setup()
        s["scene_index"] = 10
        s = feed(round_(s,{"intent":"recover","target_id":"free","action":"我为留在海港的人准备明天的食物。"}))
        self.assertEqual(s["ending"]["kind"],"TE")

    def test_arrival_order_does_not_change_seeded_rolls_or_results(self):
        original = setup(16)
        s = deepcopy(original)
        a,b = advance("m1"), {"intent":"support","action":"我帮同伴布置修复海堤的工具。","target_id":"free"}
        first = rules.apply(rules.apply(s,"seat_a","commit",a),"seat_b","commit",b)
        second = rules.apply(rules.apply(original,"seat_b","commit",b),"seat_a","commit",a)
        self.assertEqual(first,second)

    def test_public_target_reservation_prevents_conflicting_travel(self):
        s = rules.apply(setup(),"seat_a","commit",advance("m1"))
        self.assertFalse(any(t["kind"] == "move" for t in rules.observe(s,"seat_b")["private_state"]["targets"]))


class TestTabletopHost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.host = GameHost(Path(self.tmp.name)/"t.db",Path(__file__).resolve().parents[1]/"cartridges")
        self.created = self.host.create_session("pocket-tabletop","ai_ai")
        self.sid = self.created["session_id"]

    def test_real_host_uses_independent_contract_and_stores_progress(self):
        for rev, seat in enumerate(self.created["seats"]):
            self.assertEqual(self.host.act(self.sid,seat["seat_token"],rev,"introduce",{"display_name":seat["seat_id"],"surface":"test"})["result"],"ok")
        self.assertEqual(self.host.start_game(self.sid)["result"],"ok")
        with patch.object(narrator,"_chat",return_value=world()) as chat:
            self.assertEqual(self.host.narrate(self.sid)["kind"],"tt_world")
            self.assertEqual(chat.call_args.kwargs["kind"],"tt_world")
        with patch.object(narrator,"_chat",return_value=identities()):
            self.assertEqual(self.host.narrate(self.sid)["result"],"ok")
        for seat in self.created["seats"]:
            ob = self.host.observe(self.sid,seat["seat_token"])
            iid = ob["private_state"]["identity_offers"][0]["id"]
            result = self.host.act(self.sid,seat["seat_token"],ob["revision"],"choose_identity",{"identity_id":iid})
            self.assertEqual(result["result"],"ok")
        with closing(store.connect(self.host.db_path)) as conn:
            payload = json.loads(store.get_session(conn,self.sid)["engine_state_json"])
        ctx = payload["cartridge_state"]["narration_request"]["context"]
        with patch.object(narrator,"_chat",return_value=scene(ctx["snapshot"])):
            self.assertEqual(self.host.narrate(self.sid)["result"],"ok")
        self.assertEqual(self.host.public_view(self.sid)["public_state"]["ruleset"],2)

    def test_bad_world_rejected_before_it_enters_saved_state(self):
        for rev,seat in enumerate(self.created["seats"]):
            self.host.act(self.sid,seat["seat_token"],rev,"introduce",{"display_name":seat["seat_id"],"surface":"test"})
        self.host.start_game(self.sid)
        broken = world()
        broken["main_nodes"][0]["item_ids"] = ["invented_key"]
        with patch.object(narrator,"_chat",return_value=broken):
            self.assertEqual(self.host.narrate(self.sid)["result"],"narrator_error")
        ob = self.host.public_view(self.sid)["public_state"]
        self.assertIsNone(ob["world"])
        self.assertEqual(ob["narration_pending"],"tt_world")

    def test_only_current_cartridge_version_is_loaded(self):
        from console.game_host import CartridgeVersionMissing
        with closing(store.connect(self.host.db_path)) as conn:
            payload = json.loads(store.get_session(conn,self.sid)["engine_state_json"])
            payload["cartridge_state"] = rules.new_game(SEATS, 17)
            conn.execute("UPDATE session SET cartridge_version=?,status=?,engine_state_json=? WHERE id=?",
                         ("1.1.0","playing",json.dumps(payload),self.sid))
            conn.commit()
        with self.assertRaises(CartridgeVersionMissing):
            self.host._load_cartridge("pocket-tabletop", "1.1.0")
        self.assertEqual(self.host.public_view(self.sid)["result"], "cartridge_version_missing")
        token = self.created["seats"][0]["seat_token"]
        self.assertEqual(self.host.observe(self.sid,token)["result"], "cartridge_version_missing")
        with patch.object(narrator,"_chat") as chat:
            self.assertEqual(self.host.narrate(self.sid)["result"], "rejected")
            chat.assert_not_called()

    def test_human_resummon_receives_last_validation_error_then_clears_it(self):
        for rev, seat in enumerate(self.created["seats"]):
            self.host.act(self.sid,seat["seat_token"],rev,"introduce",{"display_name":seat["seat_id"],"surface":"test"})
        self.host.start_game(self.sid)
        bad = world()
        bad["npc"]["id"] = "gatekeeper"
        with patch.object(narrator,"_chat",return_value=bad) as chat:
            first = self.host.narrate(self.sid)
            self.assertEqual(chat.call_count, 1)
        self.assertIn("npc.id", first["message"])
        with closing(store.connect(self.host.db_path)) as conn:
            saved = json.loads(store.get_session(conn,self.sid)["engine_state_json"])["cartridge_state"]
        self.assertIsNone(saved["world"])
        self.assertEqual(saved["history"], [])
        self.assertEqual(saved["narration_request"]["last_error"], first["message"])
        bad = world()
        bad["npc"]["location_id"] = "海港"
        with patch.object(narrator,"_chat",return_value=bad) as chat:
            second = self.host.narrate(self.sid)
            self.assertIn(json.dumps({"validation_error": first["message"]}, ensure_ascii=False), chat.call_args.args[0])
            self.assertEqual(chat.call_count, 1)
        self.assertIn("npc.location_id", second["message"])
        with patch.object(narrator,"_chat",return_value=world()) as chat:
            self.assertEqual(self.host.narrate(self.sid)["result"], "ok")
            self.assertIn(json.dumps({"validation_error": second["message"]}, ensure_ascii=False), chat.call_args.args[0])
            self.assertEqual(chat.call_count, 1)
        with closing(store.connect(self.host.db_path)) as conn:
            saved = json.loads(store.get_session(conn,self.sid)["engine_state_json"])["cartridge_state"]
        self.assertEqual(saved["narration_request"]["kind"], "tt_identities")
        self.assertNotIn("last_error", saved["narration_request"])

    def test_transport_failure_does_not_change_game_state(self):
        for rev, seat in enumerate(self.created["seats"]):
            self.host.act(self.sid,seat["seat_token"],rev,"introduce",{"display_name":seat["seat_id"],"surface":"test"})
        self.host.start_game(self.sid)
        before = self.host.public_view(self.sid)
        with patch.object(narrator,"_chat",side_effect=narrator.NarratorError("连接失败")):
            self.assertEqual(self.host.narrate(self.sid)["result"], "narrator_error")
        self.assertEqual(self.host.public_view(self.sid), before)


if __name__ == "__main__":
    unittest.main()
