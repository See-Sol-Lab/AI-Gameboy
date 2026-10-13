"""夜铺0.3内容规模、等级门槛、有限来客与旧局边界。"""
import importlib.util
import json
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_rules(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = load_rules(ROOT / "cartridges/pocket-night-shop/rules.py", "night_expansion")
_raw_new_game = rules.new_game


def _funded_new_game(seats, seed):
    """旧测试按开局 12 枚古币写的:人类发令掷完后把钱定成 12。"""
    s = rules.apply(_raw_new_game(seats, seed), seats[0], "roll_start_funds", {"human_words": "掷"})
    s["coins"] = 12
    return s


rules.new_game = _funded_new_game


def free_event(state):
    if state["pending_event"]:
        event = rules.EVENTS[state["pending_event"]["kind"]]
        choice = next(key for key, option in event["choices"].items() if option["cost"] == 0)
        return rules.apply(state, "seat_a", "choose_event",
                           {"event_id": state["pending_event"]["id"], "choice": choice})
    return state


class TestNightExpansion(unittest.TestCase):
    def test_catalogue_sizes_and_cross_references(self):
        self.assertEqual(len(rules.ITEMS), 72)
        self.assertEqual(len({row[0] for row in rules.ITEMS}), 72)
        self.assertEqual(len({row[1] for row in rules.ITEMS}), 72)
        self.assertEqual(len({row[5] for row in rules.ITEMS}), 72)
        self.assertEqual(len(rules.CUSTOMERS), 86)
        self.assertEqual(len({row[0] for row in rules.CUSTOMERS}), 86)
        self.assertEqual(len({row[1] for row in rules.CUSTOMERS}), 86)
        self.assertEqual(len(rules.LOCATIONS), 7)   # 含第七张隐藏地图
        self.assertEqual(len(rules.EVENTS), 48)
        self.assertEqual(len(rules.AMBIENT), 24)
        self.assertEqual(Counter(rules.ITEM_RARITY.values()),
                         {"common": 24, "uncommon": 20, "rare": 14, "ancient": 9, "heirloom": 5})
        codes = {row[0] for row in rules.ITEMS}
        self.assertEqual(set(rules.ITEM_KINDS), codes)
        self.assertEqual(set(rules.ITEM_RARITY), codes)
        self.assertEqual({code for loc in rules.LOCATIONS.values() for code in loc["pool"]}, codes)
        linked = {row[1] for row in rules.SPECIAL_CUSTOMERS.values()}
        self.assertTrue({code for code, rarity in rules.ITEM_RARITY.items()
                         if rarity in ("ancient", "heirloom")} <= linked)
        self.assertEqual(len(rules.SPECIAL_CUSTOMERS), 24)
        normal = [c[5] for c in rules.CUSTOMERS if c[0] not in rules.SPECIAL_CUSTOMERS]
        self.assertEqual((len(normal), min(normal), max(normal)), (62, 10, 28))
        for customer in rules.CUSTOMERS:
            self.assertTrue(set(customer[4]) <= set(rules.ITEM_KINDS.values()))

    def test_ordinary_clues_match_paired_items_and_unpaired_have_none(self):
        ordinary = [c for c in rules.CUSTOMERS if c[0] not in rules.SPECIAL_CUSTOMERS]
        self.assertEqual(sum(c[0] in rules.BOND_LINES for c in ordinary), 48)
        self.assertEqual(sum(c[3] is None for c in ordinary), 14)
        for cid, name, request, clue, wants, budget in ordinary:
            self.assertEqual(bool(clue), cid in rules.BOND_LINES, name)
            if cid in rules.BOND_LINES:
                self.assertIn(rules.ITEM_KINDS[rules.BOND_LINES[cid][0]], wants)
        self.assertIn("皮鞋", next(c[3] for c in ordinary if c[0] == "roadkeeper"))
        self.assertNotIn("钥匙", next(c[3] for c in ordinary if c[0] == "roadkeeper"))
        self.assertIn("玻璃罐", next(c[3] for c in ordinary if c[0] == "father"))
        draft = (ROOT / "docs/night-shop-customer-lines-draft.md").read_text("utf-8")
        table = draft.split("## 二、")[1].split("## 三、")[0]
        pairs = {cells[0]: cells[2] for line in table.splitlines() if line.startswith("| ")
                 for cells in [[cell.strip() for cell in line.split("|")[1:-1]]] if len(cells) == 5 and cells[0] != "客人"}
        self.assertEqual(len(pairs), 48)
        for cid, name, *_ in ordinary:
            if cid in rules.BOND_LINES:
                item_name = next(i[1] for i in rules.ITEMS if i[0] == rules.BOND_LINES[cid][0])
                self.assertEqual(pairs[name], item_name, name)

    def test_old_saved_customer_clues_use_current_text_without_mutating_save(self):
        s = rules.new_game(["seat_a"], 42)
        s["shift_index"] = rules.OPEN_SHIFT
        s["customer"] = {"id": "roadkeeper", "name": "旅店主", "clue": "旧钥匙提示"}
        s["customer_book"]["roadkeeper"] = {"id": "roadkeeper", "name": "旅店主", "clue": "旧钥匙提示", "visits": 1}
        s["customer_book"]["cook"] = {"id": "cook", "name": "厨师", "clue": "应删除的旧线索", "visits": 1}
        before = deepcopy(s)
        view = rules.observe(s, "seat_a")["public_state"]
        self.assertIn("皮鞋", view["customer"]["clue"])
        self.assertIn("皮鞋", next(c for c in view["customer_book"] if c["id"] == "roadkeeper")["clue"])
        self.assertNotIn("clue", next(c for c in view["customer_book"] if c["id"] == "cook"))
        self.assertTrue(next(c for c in view["customer_book"] if c["id"] == "cook")["request"])
        s["customer"] = {"id": "cook", "name": "厨师", "clue": "应删除的旧线索"}
        self.assertNotIn("clue", rules._public_customer(s))
        self.assertTrue(rules._public_customer(s)["request"])
        s["customer"] = before["customer"]
        self.assertEqual(s, before)

    def test_event_frequency_falls_as_shop_grows_all_levels(self):
        for level, interval in ((1, 4), (2, 6), (3, 8), (5, 8)):
            count = 0
            for n in range(96):
                s = rules.new_game(["seat_a"], 42)
                s["shop_level"] = level
                with mock.patch.object(rules, "_number", return_value=n):
                    count += bool(rules._maybe_event(s))
            self.assertEqual(count, 96 // interval)

    def test_event_never_repeats_previous_encounter(self):
        s = rules.new_game(["seat_a"], 42)
        s["shop_level"] = 5
        with mock.patch.object(rules, "_number", return_value=0):
            rules._maybe_event(s)
            previous = s["last_event"]
            rules._maybe_event(s)
        self.assertNotEqual(previous, s["last_event"])
        self.assertEqual(s["event_count"], 2)

    def test_negative_events_have_small_costs_and_no_negative_balances(self):
        keys = ["leaking_roof", "broken_sign", "spilled_oil", "damp_paper", "loose_window", "wrong_delivery",
                "misread_hours", "dusty_step", "empty_footsteps", "cold_bus", "erased_address", "unanswered_knock"]
        self.assertEqual(len(keys), 12)
        for key in keys:
            event = rules.EVENTS[key]
            self.assertIn(event.get("coins", 0), (-2, -1, 0))
            self.assertIn(event.get("reputation", 0), (-1, 0))
            self.assertNotIn("choices", event)
            s = rules.new_game(["seat_a"], 42)
            s["coins"] = s["reputation"] = 0
            with mock.patch.object(rules, "EVENTS", {key: event}), mock.patch.object(rules, "_number", return_value=0):
                self.assertIn(event["name"], rules._maybe_event(s))
            self.assertEqual((s["coins"], s["reputation"]), (0, 0))

    def test_tier_three_item_gate_applies_to_all_sources(self):
        s = rules.new_game(["seat_a"], 42)
        for level in (1, 2):
            s["shop_level"] = level
            for location in rules.LOCATIONS:
                if location == rules.SECRET:      # 灯塔只有宝物,本就要5级
                    continue
                for attempt in range(100):
                    item = rules._make_item(s, location, attempt)
                    self.assertNotIn(item["rarity"], ("ancient", "heirloom"))
        s["shop_level"] = 3
        found = {rules._make_item(s, "archive", attempt)["rarity"] for attempt in range(1000)}
        self.assertIn("ancient", found)
        self.assertIn("heirloom", found)
        s["pending_event"] = {"kind": "star_courier", "id": "delivery", "_location": "archive"}
        s["shop_level"] = 2
        s["coins"] = 100
        s = rules.apply(s, "seat_a", "choose_event", {"event_id": "delivery", "choice": "accept"})
        self.assertNotIn(s["inventory"][-1]["rarity"], ("ancient", "heirloom"))

    def test_every_customer_has_eight_lifetime_visits_and_pool_can_exhaust(self):
        s = rules.new_game(["seat_a"], 88)
        s["shop_level"] = 5
        s["unlocked_locations"] = list(rules.LOCATIONS)
        while s["customer"] is not None:
            self.assertLessEqual(s["customer"]["visits"], 8)
            rules._spawn_customer(s)
        self.assertEqual(s["customer_count"], 86 * 8)
        self.assertEqual(len(s["customer_book"]), 86)
        self.assertTrue(all(row["visits"] == 8 for row in s["customer_book"].values()))
        before = deepcopy(s)
        rules._spawn_customer(s)
        self.assertEqual(s, before)
        view = rules.observe(s, "seat_a")
        self.assertIsNone(view["public_state"]["customer"])
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertEqual(s["shift_count"], 1)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "work_shift", {"focus": "dismiss"})

    def test_special_customers_unlock_without_resetting_normal_visits(self):
        s = rules.new_game(["seat_a"], 15)
        s["unlocked_locations"] = list(rules.LOCATIONS)
        while s["customer"] is not None:
            self.assertNotIn(s["customer"]["id"], rules.SPECIAL_CUSTOMERS)
            rules._spawn_customer(s)
        self.assertEqual(s["customer_count"], 62 * 8)
        s["shop_level"], s["coins"] = 2, 100
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "upgrade"})
        self.assertEqual(s["shop_level"], 3)
        self.assertIn(s["customer"]["id"], rules.SPECIAL_CUSTOMERS)
        self.assertTrue(all(row["visits"] == 8 for key, row in s["customer_book"].items()
                            if key not in rules.SPECIAL_CUSTOMERS))

    def test_special_customer_rejects_same_kind_substitute(self):
        s = rules.new_game(["seat_a"], 30)
        s["shop_level"] = 3
        while not s["customer"]["special"]:
            rules._spawn_customer(s)
        wanted = s["customer"]["_item_code"]
        substitute = next(row for row in rules.ITEMS if row[0] != wanted
                          and rules.ITEM_KINDS[row[0]] == rules.ITEM_KINDS[wanted])
        s["inventory"][0].update(code=substitute[0], kind=rules.ITEM_KINDS[wanted])
        before = s["customer"]["id"]
        s = rules.apply(s, "seat_a", "work_shift",
                        {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 1})
        self.assertEqual(s["customer"]["id"], before)
        self.assertIn("不合需要", s["history"][-1]["text"])
        s = free_event(s)
        s["inventory"][0]["code"] = wanted
        s = rules.apply(s, "seat_a", "work_shift",
                        {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 1})
        self.assertEqual(s["customer_book"][before]["deals"], 1)

    def test_five_shop_levels_have_affordable_idle_maintenance(self):
        s = rules.new_game(["seat_a"], 20)
        s["coins"] = 1000
        for level in range(2, 6):
            s = free_event(s)
            s = rules.apply(s, "seat_a", "work_shift", {"focus": "upgrade"})
            self.assertEqual(s["shop_level"], level)
        s = free_event(s)
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "work_shift", {"focus": "upgrade"})
        s["coins"], s["shift_index"] = 0, rules.LAST_SHIFT
        s = rules.apply(s, "seat_a", "run_shifts", {"focus": "tidy", "count": 1, "reserve": 0})
        self.assertEqual(s["last_run"]["completed"], 1)
        self.assertEqual(s["diary"][-1]["upkeep"], 5)

    def test_reputation_gates_and_hidden_lighthouse(self):
        self.assertEqual(len(rules.SECRET_ITEMS), 5)
        for key, loc in rules.LOCATIONS.items():
            if key != rules.SECRET:
                self.assertFalse(set(loc["pool"]) & set(rules.SECRET_ITEMS))
        s = rules.new_game(["seat_a"], 9)
        s.update(coins=500, shop_level=5, reputation=9)
        for c, name, story, *_ in rules.ITEMS[:60]:
            s["collection"].setdefault(c, {"code": c, "name": name, "story": story,
                                           "kind": rules.ITEM_KINDS[c], "rarity": rules.ITEM_RARITY[c],
                                           "first_day": 1, "first_location": "lane", "count": 1,
                                           "revealed": None})
        with self.assertRaisesRegex(rules.IllegalAction, "声望"):
            rules.apply(s, "seat_a", "unlock_location", {"location": "dock"})
        s["reputation"] = 10
        s = rules.apply(s, "seat_a", "unlock_location", {"location": "dock"})
        # 隐藏图:条件没满足时完全看不见,也开不了
        s["day"], s["reputation"] = 179, 166
        ids = [r["id"] for r in rules.observe(s, "seat_a")["public_state"]["locations"]]
        self.assertNotIn(rules.SECRET, ids)
        with self.assertRaisesRegex(rules.IllegalAction, "未知地点"):
            rules.apply(s, "seat_a", "unlock_location", {"location": rules.SECRET})
        s["day"], s["dreams"] = 180, 2
        # 三个条件都满足,也要等当晚打烊做完第三个梦,灯塔才出现
        self.assertNotIn(rules.SECRET, [r["id"] for r in rules.observe(s, "seat_a")["public_state"]["locations"]])
        while s["day"] == 180:
            s = free_event(rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"}))
        self.assertTrue(any("雾尽灯塔" in h["text"] for h in s["history"]))
        self.assertIn(rules.SECRET, [r["id"] for r in rules.observe(s, "seat_a")["public_state"]["locations"]])
        s = rules.apply(s, "seat_a", "unlock_location", {"location": rules.SECRET})
        self.assertEqual(s["secret_opened_day"], 181)
        self.assertTrue(rules._apple_held(s))                    # 7天内魔女必持金苹果
        s["day"] = 188
        self.assertFalse(rules._apple_window(s))
        # 7天内碰面,约一半机会送金苹果,只送一次
        gifts = 0
        for seed in range(200):
            t = deepcopy(s)
            t.update(seed=seed, day=181, unlocked_locations=list(rules.LOCATIONS))
            rules._witch_meet(t, rules._witch_spot(t))
            got = t.get("apple_pending", 0) > 0
            gifts += got
            if got:
                self.assertFalse(rules._apple_window(t))
        self.assertTrue(60 < gifts < 140)

    def test_teleport_scroll_is_free_same_day_and_expires(self):
        self.assertEqual(sum(bool(e.get("scroll")) for e in rules.EVENTS.values()), 6)
        s = rules.new_game(["seat_a"], 9)
        s.update(coins=20, unlocked_locations=["lane", "station"])
        s["inventory"] = s["inventory"][:2]
        with self.assertRaisesRegex(rules.IllegalAction, "没有传送卷轴"):
            rules.apply(s, "seat_a", "teleport", {})
        # 白天拿到:当天打烊就失效
        s["shift_index"], s["scroll"] = 0, {"until_day": s["day"]}
        self.assertIn("teleport", [a["action_id"] for a in rules.observe(s, "seat_a")["legal_actions"]])
        before = deepcopy(s)
        t = rules.apply(s, "seat_a", "teleport", {})
        self.assertEqual((t["coins"] - before["coins"]) in (0, 2), True)   # 只可能多出新发现的2枚
        self.assertEqual((t["shift_count"], t["day"]), (before["shift_count"], before["day"]))
        self.assertEqual(len(t["inventory"]), 3)
        self.assertIsNone(t["scroll"])
        self.assertIn(t["inventory"][-1]["origin"], ("lane", "station"))
        # 不用的话打烊化成灰
        u = deepcopy(before)
        with mock.patch.object(rules, "_maybe_event", return_value=""):   # 别让新卷轴顶掉旧的
            while u["day"] == before["day"]:
                u = rules.apply(u, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertTrue(any("化成了灰" in h["text"] for h in u["history"]))
        self.assertNotIn("scroll", rules.observe(u, "seat_a")["public_state"])
        # 深夜见闻给的卷轴留到第二天
        v = deepcopy(before)
        v.update(shift_index=rules.LAST_SHIFT, scroll=None)
        for n in range(500):
            v["shift_count"] = n
            text = rules._maybe_event(v)
            if v.get("scroll"):
                break
        self.assertEqual(v["scroll"]["until_day"], v["day"] + 1)
        self.assertIn("明天", text)
        # 货架满时拒绝,卷轴保留
        w = deepcopy(before)
        w["inventory"] = [dict(w["inventory"][0], id=f"x{i}") for i in range(rules._capacity(w))]
        with self.assertRaisesRegex(rules.IllegalAction, "货架满了"):
            rules.apply(w, "seat_a", "teleport", {})

    def test_afternoon_closed_half_price_and_map_complete_reputation(self):
        s = rules.new_game(["seat_a"], 4)
        s.update(coins=30, shift_index=0, unlocked_locations=["lane", "station", "dock"])
        view = rules.observe(s, "seat_a")["public_state"]
        self.assertIsNone(view["customer"])
        self.assertIn("door", view)
        for focus in ("sell", "dismiss"):
            with self.assertRaisesRegex(rules.IllegalAction, "下午还没开门"):
                rules.apply(s, "seat_a", "work_shift",
                            {"focus": focus, "item_id": s["inventory"][0]["id"], "asking_price": 1})
        self.assertEqual([rules.LOCATIONS[k]["cost"] for k in rules.LOCATIONS], [2, 2, 2, 2, 4, 4, 4])
        self.assertEqual(rules._work_cost(s, {"focus": "scavenge", "location": "observatory"}), 2)   # 下午半价
        self.assertEqual(rules._work_cost(s, {"focus": "scavenge", "location": "lane"}), 1)
        s["shift_index"] = rules.OPEN_SHIFT
        self.assertEqual(rules._work_cost(s, {"focus": "scavenge", "location": "observatory"}), 4)
        self.assertIsNotNone(rules.observe(s, "seat_a")["public_state"]["customer"])
        # 收齐一张图的旧物,声望+5,只给一次
        pool = rules.LOCATIONS["station"]["pool"]
        s["collection"] = {c: {"count": 1} for c in pool[:-1]}
        rep = s["reputation"]
        item = rules._make_item(s, "lane", "x")
        item.update(code=pool[-1])
        rules._collect(s, item)
        self.assertEqual(s["reputation"], rep + rules.MAP_COMPLETE_REPUTATION)
        self.assertEqual(s["maps_done"], ["station"])
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertIn("全部收进图鉴", s["history"][-1]["text"])

    def test_witch_stall_has_two_slots_with_set_odds(self):
        s = rules.new_game(["seat_a"], 4)
        s.update(unlocked_locations=list(rules.LOCATIONS)[:4], shop_level=5)
        seen = {0: Counter(), 1: Counter()}
        for k in range(1, 2001):
            s["shift_count"] = rules.WITCH_TREASURE_EVERY * k
            rules._witch_tick(s)
            stock = rules._witch_book(s)["stock"]
            self.assertLessEqual(len(stock), 2)
            fresh = stock[-1]
            seen[fresh["_slot"]][fresh["rarity"]] += 1
        self.assertEqual(set(seen[0]), {"heirloom", "rare"})        # 一号位:遗世30%、奇珍70%
        self.assertEqual(set(seen[1]), {"ancient", "rare"})         # 二号位:上古40%、奇珍60%
        self.assertAlmostEqual(seen[0]["heirloom"] / 1000, 0.30, delta=0.05)
        self.assertAlmostEqual(seen[1]["ancient"] / 1000, 0.40, delta=0.05)

    def test_witch_stock_of_revealed_species_is_already_repaired(self):
        s = rules.new_game(["seat_a"], 4)
        s.update(unlocked_locations=list(rules.LOCATIONS)[:4], shop_level=3)
        codes = [c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] in ("rare", "ancient", "heirloom")]
        s["collection"] = {c: {"code": c, "count": 1, "revealed": "x"} for c in codes}
        s["shift_count"] = rules.WITCH_TREASURE_EVERY
        rules._witch_tick(s)
        item = rules._witch_book(s)["stock"][-1]
        self.assertEqual((item["condition"], item.get("pre_repaired")), (3, True))
        self.assertIsNotNone(item["secret"])

    def test_fully_lit_items_vanish_and_finished_market_closes(self):
        s = rules.new_game(["seat_a"], 4)
        s.update(coins=50, unlocked_locations=["lane", "station"])
        s["inventory"] = []

        def light(code):
            s["collection"][code] = {"code": code, "count": 1, "revealed": "x",
                                     "rarity": rules.ITEM_RARITY[code]}
            cid = rules.BOND_BY_CODE[code]
            s["customer_book"].setdefault(cid, {"id": cid, "name": cid, "request": None, "clue": "",
                                                "special": False, "first_day": 1, "visits": 0,
                                                "deals": 1, "trust": 0, "neighbor": True})["bond"] = True

        lane = rules.LOCATIONS["lane"]["pool"]
        for code in lane[:-1]:
            light(code)
        self.assertEqual({rules._make_item(s, "lane", i)["code"] for i in range(50)}, {lane[-1]})
        self.assertFalse(rules._closed(s, "lane"))
        light(lane[-1])
        self.assertTrue(rules._closed(s, "lane"))
        self.assertEqual(rules._open_locations(s), ["station"])
        with self.assertRaisesRegex(rules.IllegalAction, "不再开放"):
            rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": "lane"})
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertIn("旧货巷的旧物都讲完了", s["history"][-1]["text"])
        s = rules.apply(free_event(s), "seat_a", "work_shift", {"focus": "tidy"})
        self.assertNotIn("旧货巷", s["history"][-1]["text"])           # 只宣布一次
        lane_row = next(r for r in rules.observe(s, "seat_a")["public_state"]["locations"] if r["id"] == "lane")
        self.assertTrue(lane_row["closed"])
        s["scroll"] = {"until_day": s["day"]}
        s = rules.apply(s, "seat_a", "teleport", {})
        self.assertEqual(s["inventory"][-1]["origin"], "station")
        # 魔女也不再进点亮的宝物
        treasures = [c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] in ("ancient", "heirloom")
                     and c not in rules.SECRET_ITEMS]
        for code in treasures[:-1] + [c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] == "rare"]:
            light(code)
        s.update(unlocked_locations=list(rules.LOCATIONS)[:4], shop_level=5)
        for k in range(1, 6):
            s["shift_count"] = rules.WITCH_TREASURE_EVERY * k
            rules._witch_tick(s)
        self.assertEqual({x["code"] for x in rules._witch_book(s)["stock"]}, {treasures[-1]})

    def test_unlock_refusal_names_what_is_missing_and_upgrade_cost(self):
        s = rules.new_game(["seat_a"], 4)
        s.update(coins=100, reputation=50)
        s["collection"] = {c: {"rarity": rules.ITEM_RARITY[c]} for c, *_ in rules.ITEMS[:20]}
        with self.assertRaises(rules.IllegalAction) as caught:
            rules.apply(s, "seat_a", "unlock_location", {"location": "arcade"})
        message = str(caught.exception)
        self.assertIn("店铺要2级(现在1级", message)
        self.assertIn("扩建到2级要10枚古币", message)
        self.assertNotIn("声望要", message)
        s["shop_level"] = rules.MAX_SHOP_LEVEL
        self.assertEqual(rules._upgrade_hint(s), "")

    def test_map_glows_on_every_outing_until_lighthouse_opens(self):
        s = rules.new_game(["seat_a"], 9)
        s.update(coins=200, inventory=[])
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge"})
        self.assertNotIn("雾尽灯塔", s["history"][-1]["text"])
        s["dreams"] = 3
        s = free_event(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge"})
        self.assertIn("边缘有一处在发光:雾尽灯塔", s["history"][-1]["text"])
        s["unlocked_locations"].append(rules.SECRET)
        s = free_event(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge"})
        self.assertNotIn("在发光", s["history"][-1]["text"])

    def test_golden_apple_is_cash_or_one_keepsake_off_the_shelf(self):
        s = rules.new_game(["seat_a"], 4)
        s.update(coins=0, apple_pending=2)
        legal = [a["action_id"] for a in rules.observe(s, "seat_a")["legal_actions"]]
        self.assertIn("golden_apple", legal)
        self.assertIn("2个金苹果", rules.observe(s, "seat_a")["public_state"]["apple"])
        s = rules.apply(s, "seat_a", "golden_apple", {"choice": "keep"})
        self.assertTrue(s["apple_kept"])
        with self.assertRaisesRegex(rules.IllegalAction, "只能换钱"):
            rules.apply(s, "seat_a", "golden_apple", {"choice": "keep"})
        s = rules.apply(s, "seat_a", "golden_apple", {"choice": "cash"})
        self.assertEqual((s["coins"], s["apple_pending"]), (77, 0))
        with self.assertRaisesRegex(rules.IllegalAction, "没有待处理"):
            rules.apply(s, "seat_a", "golden_apple", {"choice": "cash"})
        # 收藏后回收多5粒星沙,打烊小结挂[金苹果]
        item = s["inventory"][0]
        base = rules.SAND_DROP.get(item["rarity"], 0)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "recycle", "item_id": item["id"]})
        self.assertEqual(s["stardust"], base + rules.APPLE_SAND)
        self.assertTrue(rules._day_summary(s, s["day"]).endswith("[金苹果]"))

    def test_grand_slam_closes_the_shop_with_a_keepsake_record(self):
        s = rules.new_game(["seat_a"], 4)
        for code, name, story, *_ in rules.ITEMS:
            s["collection"][code] = {"code": code, "name": name, "story": story, "kind": rules.ITEM_KINDS[code],
                                     "rarity": rules.ITEM_RARITY[code], "first_day": 1, "first_location": "lane",
                                     "count": 1, "revealed": "x"}
        for c in rules.CUSTOMERS:
            s["customer_book"][c[0]] = {"id": c[0], "name": c[1], "request": None, "clue": c[3],
                                        "special": c[0] in rules.SPECIAL_CUSTOMERS, "first_day": 1, "visits": 1,
                                        "deals": 1, "trust": 0, "neighbor": True}
        bonded = list(rules.BOND_LINES)
        for cid in bonded[:-1]:
            s["customer_book"][cid]["bond"] = True
        self.assertTrue(rules._check_endings(s))
        self.assertEqual([e["id"] for e in s["endings"]], ["collection", "true_ending"])   # 还差一句话
        self.assertEqual(s["phase"], "playing")
        s["customer_book"][bonded[-1]]["bond"] = True
        s["last_bond"] = {"name": "最后的客人", "line": "最后一句。", "item": "某件旧物", "day": s["day"]}
        s["apple_kept"] = True
        rules._check_endings(s)
        self.assertEqual(s["phase"], "finished")
        record = rules.observe(s, "seat_a")["public_state"]["closing_record"]
        self.assertEqual([t["title"] for t in record["trophies"]], ["第七面墙", "夜铺之外", "万灯送行"])
        self.assertEqual(record["trophies"][-1]["reward"], rules.GRAND_SLAM_REWARD)
        self.assertEqual(record["notes"]["lines"], 72)
        self.assertEqual(record["last_words"]["line"], "最后一句。")
        names = [k["name"] for k in record["keepsakes"]]
        self.assertEqual(names, [x["name"] for x in s["inventory"]] + ["魔女的金苹果"])
        self.assertIn("今夜照常营业。", s["history"][-1]["text"])
        with self.assertRaisesRegex(rules.IllegalAction, "夜铺已经收起"):
            rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})

    def test_coins_buy_stardust_after_full_collection_with_daily_cap(self):
        s = rules.new_game(["seat_a"], 4)
        s["coins"] = 200
        with self.assertRaisesRegex(rules.IllegalAction, "第七面墙"):
            rules.apply(s, "seat_a", "buy_sand", {"amount": 1})
        self.assertNotIn("buy_sand", [a["action_id"] for a in rules._legal_actions(s)])
        s["endings"] = [{"id": "collection", "title": "第七面墙", "day": 1, "reward": None, "paragraphs": []}]
        sand = s.get("stardust", 0)
        s = rules.apply(s, "seat_a", "buy_sand", {"amount": 20})
        self.assertEqual((s["coins"], s["stardust"]), (140, sand + 20))
        with self.assertRaisesRegex(rules.IllegalAction, "只能再买10粒"):
            rules.apply(s, "seat_a", "buy_sand", {"amount": 11})
        s = rules.apply(s, "seat_a", "buy_sand", {"amount": 10})
        self.assertNotIn("buy_sand", [a["action_id"] for a in rules._legal_actions(s)])
        s["day"] += 1                                       # 第二天额度回满
        self.assertEqual(rules._sand_left(s), 30)
        s["coins"] = 5
        with self.assertRaisesRegex(rules.IllegalAction, "古币不够"):
            rules.apply(s, "seat_a", "buy_sand", {"amount": 2})

    def test_lighthouse_dreams_one_per_condition(self):
        s = rules.new_game(["seat_a"], 9)
        s["day"] = 180
        self.assertEqual(rules._lighthouse_dream(s), rules.LIGHTHOUSE_DREAMS[0])
        self.assertIsNone(rules._lighthouse_dream(s))             # 同一个条件不重复做梦
        s["reputation"] = rules.SECRET_REPUTATION
        self.assertEqual(rules._lighthouse_dream(s), rules.LIGHTHOUSE_DREAMS[1])
        self.assertNotIn(rules.SECRET, rules._visible_locations(s))
        s["collection"] = {c: {} for c, *_ in rules.ITEMS[:rules.SECRET_DISCOVERIES]}
        self.assertEqual(rules._lighthouse_dream(s), rules.LIGHTHOUSE_DREAMS[2])
        self.assertIn(rules.SECRET, rules._visible_locations(s))
        # 连续经营遇到梦会停下来
        t = rules.new_game(["seat_a"], 9)
        t.update(day=180, coins=100)
        t = rules.apply(t, "seat_a", "run_shifts", {"focus": "tidy", "count": 6, "stop_on": []})
        self.assertEqual(t["last_run"]["stop_reason"], "dream")
        self.assertIn("梦", t["last_run"]["stop_text"])

    def test_unseen_items_weighted_up_after_fifth_and_sixth_place(self):
        def fresh_rate(opened):
            s = rules.new_game(["seat_a"], 11)
            s["unlocked_locations"] = list(rules.LOCATIONS)[:opened]
            pool = rules.LOCATIONS["lane"]["pool"]
            seen = pool[:-2]                       # 只剩两件没见过
            s["collection"] = {c: {"count": 1} for c in seen}
            hits = sum(rules._make_item(s, "lane", i)["code"] not in seen for i in range(3000))
            return hits / 3000
        r4, r5, r6 = fresh_rate(4), fresh_rate(5), fresh_rate(6)
        self.assertLess(r4 * 1.5, r5)
        self.assertLess(r5 * 1.2, r6)
        self.assertLess(r6 * 1.2, fresh_rate(7))      # 灯塔开通后×5

    def test_lighthouse_doubles_special_customers(self):
        def special_rate(locations):
            s = rules.new_game(["seat_a"], 3)
            s["shop_level"], s["unlocked_locations"] = 5, locations
            hits = 0
            for _ in range(400):
                s["customer_book"] = {}
                rules._spawn_customer(s)
                hits += s["customer"]["special"]
            return hits / 400
        six = list(rules.LOCATIONS)[:6]
        self.assertLess(special_rate(six) * 1.25, special_rate(six + [rules.SECRET]))

    def test_full_shelf_can_still_meet_witch_and_sell(self):
        s = rules.new_game(["seat_a"], 21)
        s.update(coins=100, shop_level=5, unlocked_locations=["lane", "station", "dock", "arcade"])
        while len(s["inventory"]) < rules._capacity(s):
            s["inventory"].append(dict(s["inventory"][0], id=f"x{len(s['inventory'])}"))
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": rules._witch_spot(s)})
        self.assertIsNotNone(s["witch"]["visit"])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [{}]})
        s = rules.apply(s, "seat_a", "witch_sell", {"item_ids": [s["inventory"][-1]["id"], s["inventory"][-2]["id"]]})
        self.assertEqual(len(s["inventory"]), rules._capacity(s) - 2)

    def test_reputation_buys_shelf_slots_after_lighthouse(self):
        s = rules.new_game(["seat_a"], 5)
        s["reputation"] = 100
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "buy_slot", {})
        s["unlocked_locations"].append(rules.SECRET)
        cap = rules._capacity(s)
        s = rules.apply(s, "seat_a", "buy_slot", {})
        self.assertEqual((rules._capacity(s), s["reputation"], s["shift_count"]), (cap + 1, 60, 0))
        s["reputation"] = 39
        with self.assertRaisesRegex(rules.IllegalAction, "声望不够"):
            rules.apply(s, "seat_a", "buy_slot", {})

    def test_repair_steps_value_and_reveal_rewards_by_rarity(self):
        for rarity, steps, gain, reward in (("common", 1, 1, 2), ("uncommon", 2, 2, 3), ("rare", 3, 3, 5),
                                            ("ancient", 3, 5, 10), ("heirloom", 3, 7, 25)):
            with self.subTest(rarity=rarity):
                s = rules.new_game(["seat_a"], 4)
                s["coins"] = 50
                code = next(c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] == rarity)
                item = rules._make_item(s, "lane", 0)
                row = next(r for r in rules.ITEMS if r[0] == code)
                item.update(code=code, rarity=rarity, value=row[4], name=row[1], _secret=row[5],
                            condition=rules._start_condition(rarity))
                s["inventory"].append(item)
                s["collection"].setdefault(code, {"code": code, "revealed": None, "count": 1, "rarity": rarity})
                coins, value = s["coins"], item["value"]
                for _ in range(steps):
                    s = rules.apply(s, "seat_a", "work_shift", {"focus": "repair", "item_id": item["id"]})
                    while s["pending_event"]:
                        s = rules.apply(s, "seat_a", "choose_event", {"event_id": s["pending_event"]["id"], "choice": next(
                            k for k, o in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items() if o["cost"] == 0)})
                done = next(x for x in s["inventory"] if x["id"] == item["id"])
                self.assertEqual(done["condition"], 3)
                self.assertEqual(done["value"] - value, gain)
                self.assertIn(f"获得{reward}枚古币", s["history"][-1]["text"] + s["history"][-2]["text"]
                              if len(s["history"]) > 1 else s["history"][-1]["text"])

    def test_every_eighth_reveal_pays_twenty(self):
        s = rules.new_game(["seat_a"], 4)
        s["coins"] = 50
        others = [c for c, *_ in rules.ITEMS][10:17]
        for c in others:                                    # 已揭开7种
            s["collection"][c] = {"code": c, "revealed": "x", "count": 1}
        item = next(x for x in s["inventory"] if x["condition"] < 3)
        item["condition"] = 2
        before = s["coins"]
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "repair", "item_id": item["id"]})
        text = " ".join(h["text"] for h in s["history"][-2:])
        self.assertIn("每揭开8种秘密", text)
        self.assertGreaterEqual(s["coins"] - before, 20)

    def test_price_feedback_tells_how_far_off(self):
        s = rules.new_game(["seat_a"], 5)
        s["coins"] = 50
        c = s["customer"]
        item = s["inventory"][0]
        item["kind"] = c["_wants"][0]
        ceiling = min(c["_budget"], item["value"] + item["condition"] + s["shop_level"])
        near = rules.apply(deepcopy(s), "seat_a", "work_shift",
                           {"focus": "sell", "item_id": item["id"], "asking_price": ceiling + 1})
        self.assertIn("差一点", near["history"][-1]["text"])
        far = rules.apply(deepcopy(s), "seat_a", "work_shift",
                          {"focus": "sell", "item_id": item["id"], "asking_price": ceiling * 2 + 5})
        self.assertIn("差得远", far["history"][-1]["text"])
        ok = rules.apply(deepcopy(s), "seat_a", "work_shift",
                         {"focus": "sell", "item_id": item["id"], "asking_price": ceiling})
        self.assertIn("满意", ok["history"][-1]["text"])

    def test_bond_lines_cover_every_item_once_and_fit_wants(self):
        self.assertEqual(len(rules.BOND_LINES), 72)
        self.assertEqual({code for code, _ in rules.BOND_LINES.values()}, {row[0] for row in rules.ITEMS})
        wants = {c[0]: c[4] for c in rules.CUSTOMERS}
        for cid, (code, line) in rules.BOND_LINES.items():
            self.assertIn(rules.ITEM_KINDS[code], wants[cid], cid)
            if cid in rules.SPECIAL_CUSTOMERS:
                self.assertEqual(rules.SPECIAL_CUSTOMERS[cid][1], code)
            self.assertTrue(line)

    def test_bond_line_only_on_first_fully_repaired_match(self):
        s = rules.new_game(["seat_a"], 9)
        while s["customer"]["id"] not in rules.BOND_LINES or s["customer"]["special"]:
            rules._spawn_customer(s)
        guest = deepcopy(s["customer"])
        code, line = rules.BOND_LINES[guest["id"]]
        s["inventory"][0].update(code=code, kind=rules.ITEM_KINDS[code], condition=3)
        broken = deepcopy(s)
        broken["inventory"][0]["condition"] = 2

        def sell(state):
            return rules.apply(state, "seat_a", "work_shift",
                               {"focus": "sell", "item_id": state["inventory"][0]["id"], "asking_price": 1})

        plain = sell(broken)
        self.assertNotIn(line, plain["history"][-1]["text"])
        s = sell(s)
        self.assertIn(line, s["history"][-1]["text"])
        self.assertEqual(s["coins"] - plain["coins"], rules.BOND_COINS)
        self.assertTrue(s["customer_book"][guest["id"]]["bond"])
        s = free_event(s)
        s["customer"] = guest
        s["inventory"].insert(0, dict(broken["inventory"][0], id="again", condition=3))
        s = sell(s)
        self.assertIn("满意", s["history"][-1]["text"])
        self.assertNotIn(line, s["history"][-1]["text"])

    def test_special_customer_says_farewell_after_bond_and_never_returns(self):
        s = rules.new_game(["seat_a"], 30)
        s["shop_level"] = 3
        while not s["customer"]["special"]:
            rules._spawn_customer(s)
        sid = s["customer"]["id"]
        code = s["customer"]["_item_code"]
        s["inventory"][0].update(code=code, kind=rules.ITEM_KINDS[code], condition=3)
        s = rules.apply(s, "seat_a", "work_shift",
                        {"focus": "sell", "item_id": s["inventory"][0]["id"], "asking_price": 1})
        text = s["history"][-1]["text"]
        self.assertIn(rules.BOND_LINES[sid][1], text)
        self.assertIn("同你告别", text)
        self.assertTrue(s["customer_book"][sid]["farewell"])
        for _ in range(2000):
            rules._spawn_customer(s)
            if s["customer"] is None:
                break
            self.assertNotEqual(s["customer"]["id"], sid)

    def test_merge_duplicate_repairs_without_shift_or_coins(self):
        s = rules.new_game(["seat_a"], 6)
        s["coins"] = 20
        code = next(c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] == "common")
        a = rules._make_item(s, "lane", 1); b = rules._make_item(s, "lane", 2)
        row = next(r for r in rules.ITEMS if r[0] == code)
        for x in (a, b):
            x.update(code=code, name=row[1], rarity="common", condition=2, value=row[4], _secret=row[5])
        s["inventory"] += [a, b]
        s["collection"].setdefault(code, {"code": code, "revealed": None, "count": 2})
        self.assertIn("merge", [x["action_id"] for x in rules._legal_actions(s)])
        coins, shifts, n = s["coins"], s["shift_count"], len(s["inventory"])
        s = rules.apply(s, "seat_a", "merge", {"item_id": a["id"], "from_id": b["id"]})
        fixed = next(x for x in s["inventory"] if x["id"] == a["id"])
        self.assertEqual((fixed["condition"], len(s["inventory"]), s["shift_count"]), (3, n - 1, shifts))
        self.assertEqual(s["coins"] - coins, 2)                  # 不花钱,只拿寻常揭秘奖励
        self.assertIn("拆下一件", s["history"][-1]["text"])
        # 上古不能拆件修理
        anc = next(c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] == "ancient")
        c1, c2 = dict(a, id="x1", code=anc, rarity="ancient", condition=1), dict(a, id="x2", code=anc, rarity="ancient", condition=1)
        s["inventory"] += [c1, c2]
        with self.assertRaisesRegex(rules.IllegalAction, "上古"):
            rules.apply(s, "seat_a", "merge", {"item_id": "x1", "from_id": "x2"})

    def test_recycle_drops_stardust_and_sand_repairs_to_full(self):
        s = rules.new_game(["seat_a"], 6)
        s["coins"] = 20
        item = s["inventory"][0]
        item["rarity"] = "uncommon"
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "recycle", "item_id": item["id"]})
        self.assertEqual(s["stardust"], 2)
        self.assertIn("2粒星沙", s["history"][-1]["text"])
        code = next(c for c, *_ in rules.ITEMS if rules.ITEM_RARITY[c] == "heirloom")
        row = next(r for r in rules.ITEMS if r[0] == code)
        treasure = dict(s["inventory"][0], id="t1", code=code, name=row[1], rarity="heirloom",
                        condition=0, value=row[4], _secret=row[5])
        s["inventory"].append(treasure)
        s["collection"].setdefault(code, {"code": code, "revealed": None, "count": 1})
        with self.assertRaisesRegex(rules.IllegalAction, "星沙不够"):
            rules.apply(s, "seat_a", "sand_repair", {"item_id": "t1"})
        s["stardust"], coins, shifts, rep = 60, s["coins"], s["shift_count"], s["reputation"]
        s = rules.apply(s, "seat_a", "sand_repair", {"item_id": "t1"})
        t = next(x for x in s["inventory"] if x["id"] == "t1")
        self.assertEqual((t["condition"], t["value"], s["stardust"], s["shift_count"]), (3, row[4] + 7, 5, shifts))
        self.assertEqual((s["coins"] - coins, s["reputation"] - rep), (25, 10))   # 遗世揭秘25、声望+10
        with self.assertRaisesRegex(rules.IllegalAction, "寻常和少见"):
            rules.apply(s, "seat_a", "sand_repair", {"item_id": s["inventory"][0]["id"]})

    def test_rescue_after_three_unpaid_days_then_bankrupt(self):
        def broke_days(s, days):
            for _ in range(days):
                s["coins"], s["shift_index"] = 0, rules.LAST_SHIFT
                s = rules.apply(s, "seat_a", "work_shift", {"focus": "dismiss"})
                while s["pending_event"]:
                    s = rules.apply(s, "seat_a", "choose_event", {"event_id": s["pending_event"]["id"], "choice": next(
                        k for k, o in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items() if o["cost"] == 0)})
            return s
        s = rules.new_game(["seat_a"], 8)
        s = broke_days(s, 2)
        self.assertNotIn("rescues_left", rules.observe(s, "seat_a")["public_state"])   # 平时不显示
        with self.assertRaisesRegex(rules.IllegalAction, "还不能"):
            rules.apply(s, "seat_a", "call_human", {"human_words": "救"})
        self.assertIn("tidy", s["history"][-1]["text"])
        for n in range(1, 4):
            s = broke_days(s, 3)
            self.assertIn("call_human", [x["action_id"] for x in rules._legal_actions(s)])
            with self.assertRaises(rules.IllegalAction):
                rules.apply(s, "seat_a", "call_human", {"human_words": ""})
            s = rules.apply(s, "seat_a", "call_human", {"human_words": "救救夜铺"})
            self.assertTrue(11 <= s["coins"] <= 66)
            self.assertIn(f"第{n}次救店", s["history"][-1]["text"])
        s = broke_days(s, 3)
        self.assertTrue(s["bankrupt"])
        self.assertEqual(rules._legal_actions(s), [])
        self.assertEqual(s["endings"][-1]["id"], "closed")
        self.assertIn("落叶封门", s["history"][-1]["text"])
        self.assertNotIn("_close_pending", s)
        with self.assertRaisesRegex(rules.IllegalAction, "破产"):
            rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})

    def test_special_customer_leaves_next_morning(self):
        s = rules.new_game(["seat_a"], 30)
        s["shop_level"] = 3
        while not s["customer"]["special"]:
            rules._spawn_customer(s)
        sid = s["customer"]["id"]
        self.assertNotIn("stay", rules.observe(s, "seat_a")["public_state"]["customer"])   # 不提前预告
        s["shift_index"] = rules.LAST_SHIFT - 1
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})        # 傍晚:还在
        self.assertEqual(s["customer"]["id"], sid)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})        # 深夜打烊,天亮就走
        self.assertNotEqual((s["customer"] or {}).get("id"), sid)
        self.assertIn("天亮前悄悄走了", s["history"][-1]["text"] + " ".join(h["text"] for h in s["history"][-3:]))

    def test_revealed_species_arrive_already_repaired(self):
        s = rules.new_game(["seat_a"], 6)
        first = rules._make_item(s, "lane", 1)
        self.assertLess(first["condition"], 3)                   # 还没揭秘:照常是破的
        code = first["code"]
        s["collection"].setdefault(code, {"code": code, "count": 1})
        s["collection"][code]["revealed"] = "已揭开"
        again = None
        for salt in range(400):
            x = rules._make_item(s, "lane", salt)
            if x["code"] == code:
                again = x
                break
        self.assertIsNotNone(again)
        row = next(r for r in rules.ITEMS if r[0] == code)
        self.assertEqual(again["condition"], 3)
        self.assertTrue(again["pre_repaired"])
        self.assertEqual(again["secret"], row[5])
        steps = rules.REPAIR_STEPS[again["rarity"]]
        self.assertEqual(again["value"], row[4] + steps + rules.REPAIR_EXTRA.get(again["rarity"], 0))

    def test_witch_buys_ancient_and_heirloom_at_eighty_percent(self):
        s = rules.new_game(["seat_a"], 21)
        s.update(coins=100, shop_level=5, unlocked_locations=["lane", "station", "dock", "arcade"])
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": rules._witch_spot(s)})
        item = dict(s["inventory"][0], id="old_seal", rarity="ancient", value=40)
        s["inventory"].append(item)
        if not s["witch"]["visit"]["discount"]:
            self.assertEqual(rules._witch_price(s, item, True), 32)
            self.assertEqual(rules._witch_price(s, dict(item, rarity="common", value=10), True), 2)

    def test_ancient_and_heirloom_repairs_add_reputation(self):
        s = rules.new_game(["seat_a"], 4)
        s["coins"] = 50
        item = s["inventory"][0]
        item.update(rarity="heirloom", condition=2)
        before = s["reputation"]
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "repair", "item_id": item["id"]})
        self.assertEqual(s["reputation"] - before, 10)
        dup = deepcopy(s["inventory"][-1] if s["inventory"][-1]["code"] == item["code"] else item)
        dup.update(id="dup_1", condition=2, secret=None, _secret="秘密")
        s["inventory"].append(dup)
        before = s["reputation"]
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "repair", "item_id": "dup_1"})
        self.assertEqual(s["reputation"] - before, 0)      # 重复货修满不再加声望

    def test_witch_lilith_trades_after_fourth_place(self):
        self.assertTrue(any(rules.ITEM_RARITY.get(r[0]) in ("ancient", "heirloom") for r in rules.ITEMS))
        s = rules.new_game(["seat_a"], 3)
        s["coins"], s["shop_level"] = 500, 5
        s["unlocked_locations"] = ["lane", "station", "dock"]
        spot = rules._witch_spot(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": spot})
        self.assertIsNone(rules.observe(s, "seat_a")["public_state"]["witch"])    # 三张图时没有魔女
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [s["inventory"][0]["id"]]})
        s["unlocked_locations"] = ["lane", "station", "dock", "arcade"]
        while s["pending_event"]:
            s = rules.apply(s, "seat_a", "choose_event", {"event_id": s["pending_event"]["id"], "choice": next(
                k for k, o in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items() if o["cost"] == 0)})
        spot = rules._witch_spot(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": spot})
        view = rules.observe(s, "seat_a")["public_state"]["witch"]
        self.assertIsNotNone(view)
        self.assertIn("魔女莉莉丝", s["history"][-1]["text"])
        a, b, c = (x["id"] for x in s["inventory"][:3])
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [a, b, c]})       # 一次最多2件
        item = s["inventory"][0]
        before = s["coins"]
        s = rules.apply(s, "seat_a", "witch_sell", {"item_ids": [a]})
        expect = max(1, int(item["value"] * (0.8 if view["discount"] else 0.2)))
        self.assertEqual(s["coins"] - before, expect)
        s = rules.apply(s, "seat_a", "witch_sell", {"item_ids": [b]})
        with self.assertRaises(rules.IllegalAction):
            rules.apply(s, "seat_a", "witch_sell", {"item_ids": [c]})
        # 每10班轮流刷新一个摊位(遗世/上古或奇珍),买下后进库存
        while not s["witch"]["stock"]:
            s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
            while s["pending_event"]:
                s = rules.apply(s, "seat_a", "choose_event", {"event_id": s["pending_event"]["id"], "choice": next(
                    k for k, o in rules.EVENTS[s["pending_event"]["kind"]]["choices"].items() if o["cost"] == 0)})
        treasure = s["witch"]["stock"][0]
        self.assertIn(treasure["rarity"], ("rare", "ancient", "heirloom"))
        self.assertIsNone(rules.observe(s, "seat_a")["public_state"]["witch"])    # 下一班她就走了
        s["day"] += 0
        spot = rules._witch_spot(s)
        s = rules.apply(s, "seat_a", "work_shift", {"focus": "scavenge", "location": spot})
        if s["witch"]["visit"]:
            s = rules.apply(s, "seat_a", "witch_buy", {"item_id": treasure["id"]})
            self.assertIn(treasure["id"], [x["id"] for x in s["inventory"]])
        # 金苹果:每20班一半机会出现,持有2班
        apples = sum(rules._number(seed, "witch_apple", 20) % 2 == 0 for seed in range(200))
        self.assertTrue(60 < apples < 140)

    def test_neighbors_are_whoever_came_before_third_place(self):
        s = rules.new_game(["seat_a"], 7)
        for _ in range(30):
            rules._spawn_customer(s)
            self.assertIsNotNone(s["customer"]["request"])
        met = set(s["customer_book"])
        self.assertTrue(all(row["neighbor"] for row in s["customer_book"].values()))
        s["unlocked_locations"].append("dock")
        seen = {}
        while not any(len(v) >= 6 for v in seen.values()):
            rules._spawn_customer(s)
            c = s["customer"]
            if c["id"] in met:
                self.assertIsNotNone(c["request"])          # 老街坊到哪都直说
            elif c["id"] not in rules.SPECIAL_CUSTOMERS:
                if c["id"] in rules.BOND_LINES:
                    seen.setdefault(c["id"], []).append(c["request"])
                else:
                    self.assertIsNotNone(c["request"])   # 没有物品线索的来客直接报类别
        stranger = next(v for v in seen.values() if len(v) >= 6)
        self.assertTrue(all(r is None for r in stranger[:4]) and all(stranger[4:]))
        self.assertFalse(s["customer_book"][next(k for k, v in seen.items() if len(v) >= 6)]["neighbor"])
        fresh = rules.new_game(["seat_a"], 7)                # 下一局清零重来
        self.assertEqual(len(fresh["customer_book"]), 1)
        self.assertIn("线索", rules.observe(s, "seat_a")["public_state"]["customer"]["hint"])

    def test_all_event_choices_have_a_free_exit_and_public_outcome(self):
        for kind, event in rules.EVENTS.items():
            if "choices" not in event:
                continue
            self.assertTrue(any(option["cost"] == 0 for option in event["choices"].values()))
            for choice in event["choices"]:
                s = rules.new_game(["seat_a"], 2)
                s["shop_level"], s["coins"] = 5, 100
                s["pending_event"] = {"kind": kind, "id": "fixture", "_location": "lane"}
                s = rules.apply(s, "seat_a", "choose_event", {"event_id": "fixture", "choice": choice})
                self.assertIsNone(s["pending_event"])
                self.assertIn(choice, s["encounters"][kind]["outcomes"])
                self.assertTrue(s["history"][-1]["text"])


    def test_spending_days_does_not_count_as_customer_arrivals(self):
        s = rules.new_game(["seat_a"], 6)
        customer = deepcopy(s["customer"])
        visits = s["customer_count"]
        # 开张那天傍晚起算:第1天3班、第2天5班、第3天前4班,客人一直等着
        for _ in range(12):
            s = free_event(s)
            s = rules.apply(s, "seat_a", "work_shift", {"focus": "tidy"})
        self.assertEqual(s["day"], 3)
        self.assertEqual(s["customer"], customer)
        self.assertEqual(s["customer_count"], visits)
        # 第三天打烊:没买到想要的,自己走
        s = rules.apply(free_event(s), "seat_a", "work_shift", {"focus": "tidy"})
        self.assertNotEqual(s["customer"]["id"], customer["id"])
        self.assertIn("等了三天", s["history"][-1]["text"])



if __name__ == "__main__":
    unittest.main()
