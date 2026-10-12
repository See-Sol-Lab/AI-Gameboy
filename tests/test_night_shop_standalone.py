"""Standalone blind edition: no repository/runtime dependency after download."""
import importlib.util
from contextlib import closing
import json
import re
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "口袋夜铺_单机盲玩版/pocket_night_shop.py"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNightStandalone(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "pocket_night_shop.py"
        shutil.copyfile(SOURCE, self.path)
        self.shop = load(self.path, "standalone_test")
        self.limit, self.shop.CALL_LIMIT = self.shop.CALL_LIMIT, 10 ** 6   # 其他测试不管轮次;轮次另有专门测试

    def call(self, line):
        """测数据层;给 AI 看的是 cmd() 渲染出的中文文本,另有专门测试。"""
        out = self.shop._call(line)
        out.pop("calls_left", None)
        out.pop("round", None)
        return out

    def test_every_rules_action_is_a_known_command(self):
        self.call("observe")
        src = (ROOT / "cartridges/pocket-night-shop/rules.py").read_text("utf-8")
        for action in set(re.findall(r'action_id (?:==|in) \(?"([a-z_]+)"', src)) | {"witch_buy"}:
            with self.subTest(action=action):
                self.assertNotIn("未知指令", self.call(action + " {}").get("message", ""))

    def test_rounds_lock_after_limit_and_only_real_time_unlocks(self):
        self.shop.CALL_LIMIT = self.limit
        clock = [1000.0]
        self.shop._clock = lambda: clock[0]
        self.assertEqual((self.shop.CALL_LIMIT, self.shop.ROUND_WAIT), (30, 90))
        self.assertIn("30", self.shop.cmd("help"))
        for _ in range(self.shop.CALL_LIMIT - 1):
            self.assertEqual(self.call("status")["result"], "ok")
        last = self.shop._call("status")                        # 第30次照常执行,同时上锁
        self.assertEqual((last["result"], last["calls_left"]), ("ok", 0))
        self.assertIn("最后一次", last["round"])
        clock[0] += 60
        blocked = self.call("status")
        self.assertEqual(blocked["result"], "rejected")
        self.assertIn("还差31秒", blocked["message"])
        # 编一句人类原话也没用:human_said 已取消
        self.assertEqual(self.call('human_said {"human_words":"继续吧"}')["result"], "rejected")
        self.assertEqual(self.call("status")["result"], "rejected")
        clock[0] += 31
        fresh = self.shop._call("status")
        self.assertEqual((fresh["result"], fresh["calls_left"]), ("ok", self.shop.CALL_LIMIT - 1))
        self.assertIn("新一轮", fresh["round"])
        # 没用满,但两次调用本来就隔了1分30秒以上,也算新一轮
        for _ in range(5):
            self.shop.cmd("status")
        clock[0] += 95
        self.assertEqual(self.shop._call("status")["calls_left"], self.shop.CALL_LIMIT - 1)

    def test_round_lock_survives_module_reload(self):
        self.shop.CALL_LIMIT = self.limit
        clock = [1000.0]
        self.shop._clock = lambda: clock[0]
        for _ in range(self.limit):
            self.shop._call("status")
        fresh = load(self.path, "standalone_audit_round_reload")
        fresh._clock = lambda: clock[0]
        self.assertEqual(fresh._call("status")["result"], "rejected")
        clock[0] += self.shop.ROUND_WAIT
        self.assertEqual(fresh._call("status")["calls_left"], self.limit - 1)

    def test_generated_file_matches_rules_template_and_license(self):
        builder = load(ROOT / "tools/build_night_shop.py", "standalone_builder")
        # 压缩块按字节因 zlib 版本而异(CI 与本机不同),内容由下一条断言解压后逐字比对
        strip = lambda text: re.sub(r'(?ms)^_RULES_B64 = \(.*?^\)$', "_RULES_B64 = ...", text)
        self.assertEqual(strip(SOURCE.read_text("utf-8")), strip(builder.render()))
        rules = (ROOT / "cartridges/pocket-night-shop/rules.py").read_text("utf-8")
        self.assertEqual(self.shop._zlib.decompress(self.shop._base64.b64decode(self.shop._RULES_B64)).decode(), rules)
        self.assertIn((ROOT / "LICENSE").read_text("utf-8").strip(), SOURCE.read_text("utf-8"))
        self.assertNotIn("末站遗下的站名牌", SOURCE.read_text("utf-8"))

    def test_help_does_not_create_save_and_observe_initializes(self):
        self.assertIn("代码执行", self.shop.__doc__)
        self.assertIn("能做的", self.shop.cmd("help"))
        self.assertFalse(self.shop.SAVE_PATH.exists())
        view = self.call("observe")
        self.assertEqual(view["result"], "ok")
        self.assertEqual(view["public_state"]["collection"]["total"], 72)
        self.assertNotIn("customer_book", view["public_state"])        # 盲玩版没有客人图鉴
        self.assertNotIn("customer_collection", view["public_state"])
        self.assertEqual(self.call("customers")["result"], "rejected")
        blob = json.dumps(view, ensure_ascii=False)
        for name in ("_secret", "_budget", "_wants", "_item_code", "末站遗下的站名牌"):
            self.assertNotIn(name, blob)
        self.assertTrue(self.shop.SAVE_PATH.exists())

    def test_same_rules_and_seed_give_identical_gameplay(self):
        canonical = load(ROOT / "cartridges/pocket-night-shop/rules.py", "standalone_canonical")
        blind = lambda p: {k: v for k, v in p.items() if k not in self.shop.BLIND_HIDDEN}
        state = canonical.new_game(["seat_a"], 17)
        self.call('new_game {"seed":17}')
        full = lambda: self.call("detail")["public_state"]
        self.assertEqual(full(), blind(canonical.observe(state, "seat_a")["public_state"]))
        state = canonical.apply(state, "seat_a", "roll_start_funds", {"human_words": "掷"})
        self.call('roll_start_funds {"human_words":"掷"}')
        self.assertEqual(full(), blind(canonical.observe(state, "seat_a")["public_state"]))
        params = {"focus": "scavenge", "count": 6, "stop_on": "new"}
        state = canonical.apply(state, "seat_a", "run_shifts", params)
        result = self.call("run_shifts " + json.dumps(params))
        self.assertEqual(result["result"], "ok")
        self.assertEqual(full(), blind(canonical.observe(state, "seat_a")["public_state"]))
        # 日常返回是精简版:不带图鉴和整份货架,但带这一步的新记录
        self.assertNotIn("collection", result["public_state"])
        self.assertTrue(result["public_state"]["new_log"])
        self.assertLess(len(json.dumps(result, ensure_ascii=False)), 6000)

    def test_routine_replies_skip_unchanged_shelf_and_fold_repeats(self):
        self.call('new_game {"seed":17}')
        self.call('roll_start_funds {"human_words":"掷"}')
        tidy = self.call('work_shift {"focus":"tidy"}')["public_state"]
        self.assertNotIn("inventory", tidy)
        self.assertNotIn("shelf_change", tidy)                    # 货架没变就不提
        self.assertRegex(tidy["shelf"], r"^\d+/\d+件$")
        for key in ("reputation", "shop_level", "current_goal", "location"):
            self.assertNotIn(key, tidy)                            # 打烊小结里才写
        self.assertNotIn("pending_event", tidy)
        self.assertNotIn("hint", json.dumps(tidy, ensure_ascii=False))
        batch = self.call('run_shifts {"focus":"tidy","count":6,"stop_on":[]}')["public_state"]
        self.assertLess(len(batch["new_log"]), batch["last_run"]["completed"])
        self.assertNotIn("highlights", batch["last_run"])
        self.assertTrue(any("打烊小结" in line for line in batch["new_log"]))
        found = self.call('work_shift {"focus":"scavenge"}')["public_state"]
        self.assertTrue(found["shelf_change"][0].startswith("+ "))
        self.assertRegex(found["shelf_change"][0], r"\[\w+\] \S+·(寻常|少见|奇珍|上古|遗世)·完好\d/3·值\d+古币$")
        full = self.call("observe")["public_state"]
        self.assertIsInstance(full["inventory"], list)
        self.assertIn("pending_event", full)

    def test_everything_the_ai_reads_is_chinese_text(self):
        self.call('new_game {"seed":17}')
        outputs = [self.shop.cmd(line) for line in (
            "observe", 'roll_start_funds {"human_words":"掷"}', 'work_shift {"focus":"tidy"}',
            'run_shifts {"focus":"scavenge","count":6,"stop_on":[]}', "map", "collection", "encounters",
            "endings", "history 0", "detail", 'work_shift {"focus":"sell","item_id":"nope","asking_price":3}')]
        for text in outputs:
            with self.subTest(text=text[:40]):
                self.assertFalse(text.lstrip().startswith("{"))
                for word in ("public_state", "legal_actions", "calls_left", "patience", "visits", "request",
                             "clue", "rarity", "condition", "new_log", "stop_reason", "shelf_change",
                             "uncommon", "heirloom", "ancient", '"result"'):
                    self.assertNotIn(word, text)
        for text in outputs:
            self.assertNotRegex(text, r"\b[a-z][a-z_]*_\d+\b")      # 旧物编号只露数字,不露英文代号
        self.assertIn("本轮还能调用", outputs[0])
        self.assertIn("没办成:", outputs[-1])

    def test_numeric_ids_and_chinese_place_names_work_in_commands(self):
        self.call('new_game {"seed":17}')
        self.call('roll_start_funds {"human_words":"掷"}')
        shelf = self.call("observe")["public_state"]["inventory"]
        real = shelf[0].split(" [")[1].split("]")[0]
        number = real.rsplit("_", 1)[-1]
        self.assertIn(f"[{number}]", self.shop.cmd("observe"))
        done = self.call('work_shift {"focus":"recycle","item_id":"%s"}' % number)
        self.assertEqual(done["result"], "ok")
        self.assertTrue(done["public_state"]["shelf_change"][0].startswith("- "))
        refused = self.call('unlock_location {"location":"废弃车站"}')   # 图鉴还不够:认得地名,只是条件没到
        self.assertEqual(refused["result"], "rejected")
        self.assertIn("还开不了废弃车站", refused["message"])

    def test_grand_slam_reads_as_a_closed_shop(self):
        record = {"title": "万灯送行", "day": 300, "coins": 1, "reputation": 2,
                  "trophies": [{"title": "第七面墙", "day": 200, "reward": "没有背面的店主铭牌"},
                               {"title": "夜铺之外", "day": 280, "reward": "通往亚空间的钥匙"},
                               {"title": "万灯送行", "day": 300, "reward": "装着整间夜铺的一盏小灯"}],
                  "keepsakes": [{"name": "停在四点的怀表", "kind": "时间", "rarity": "寻常", "condition": 3}],
                  "notes": {"days": 300, "guests": 86, "revealed": 72, "farewells": 24, "lines": 72},
                  "last_words": {"name": "钟表匠", "line": "都是一种钟。", "item": "扁瓶", "day": 300},
                  "epilogue": "此间夜铺已经结业。店主带着所有故事，去往下一盏灯下。"}
        text = self.shop._state_text({"closing_record": record, "new_log": []}, [], True)
        for piece in ("【店铺已收起 · 游戏结束】", "🏆 万灯送行(第300天,纪念:装着整间夜铺的一盏小灯)",
                      "说出口的话72句", "钟表匠捧着「扁瓶」说:「都是一种钟。」", "停在四点的怀表(寻常)",
                      "今夜照常营业。"):
            self.assertIn(piece, text)

    def test_close_reopen_and_fresh_module_resume_disk_state(self):
        self.call('new_game {"seed":17}')
        self.call('roll_start_funds {"human_words":"掷"}')
        self.call('work_shift {"focus":"tidy"}')
        self.call("close_for_now")
        closed = self.call("observe")
        fresh = load(self.path, "standalone_resumed")
        self.assertEqual({k: v for k, v in fresh._call("observe").items() if k != "calls_left"}, closed)
        self.shop = fresh
        opened = self.call("reopen_shop")
        self.assertFalse(opened["public_state"].get("resting"))       # 日常返回省掉空字段
        self.assertNotIn("shelf_change", opened["public_state"])
        reopened = self.call("observe")["public_state"]
        for key in ("inventory", "day", "coins", "collection", "pending_event"):
            self.assertEqual(reopened[key], closed["public_state"][key])

    def test_invalid_actions_and_new_game_do_not_overwrite_save(self):
        before = self.call('new_game {"seed":17}')
        for command in ('new_game {"seed":18}', 'work_shift {"focus":"unknown"}',
                        'work_shift {oops', 'work_shift []', 'run_shifts {"focus":"tidy","count":99}',
                        'history -1', 'secret', 'observe null'):
            with self.subTest(command=command):
                self.assertEqual(self.call(command)["result"], "rejected")
                self.assertEqual(self.call("observe"), before)

    def test_all_history_pages_and_known_catalogues_are_available(self):
        self.call('new_game {"seed":17}')
        self.call('roll_start_funds {"human_words":"掷"}')
        for i in range(110):
            view = self.call("observe")["public_state"]
            if view["pending_event"]:
                pending = view["pending_event"]
                option = next(row["id"] for row in pending["choices"] if row["cost"] == 0)
                self.call("choose_event " + json.dumps({"event_id": pending["id"], "choice": option}))
            self.assertEqual(self.call('work_shift {"focus":"tidy"}')["result"], "ok")
        first, second = self.call("history 0"), self.call("history 100")
        self.assertEqual(len(first["entries"]), 100)
        self.assertEqual(len(first["entries"]) + len(second["entries"]), first["total"])
        self.assertEqual(second["entries"][0]["seq"], 101)
        for command in ("collection", "encounters"):
            self.assertEqual(self.call(command)["result"], "ok")

    def test_incompatible_or_corrupt_save_fails_without_reset(self):
        self.call("observe")
        with closing(sqlite3.connect(self.shop.SAVE_PATH)) as conn, conn:
            conn.execute("UPDATE shop SET version='future-version'")
        self.assertEqual(self.call("observe")["result"], "rejected")
        with closing(sqlite3.connect(self.shop.SAVE_PATH)) as conn, conn:
            self.assertEqual(conn.execute("SELECT version FROM shop").fetchone()[0], "future-version")
            conn.execute("UPDATE shop SET version=?,state='broken json'", (self.shop.VERSION,))
        self.assertEqual(self.call("observe")["result"], "rejected")
        with closing(sqlite3.connect(self.shop.SAVE_PATH)) as conn, conn:
            self.assertEqual(conn.execute("SELECT state FROM shop").fetchone()[0], "broken json")

    def test_only_downloaded_file_runs_in_isolated_python(self):
        run = subprocess.run([sys.executable, "-I", str(self.path), "observe"],
                             cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(run.stdout.startswith("【第1天"), run.stdout[:200])
        self.assertTrue((Path(self.temp.name) / "pocket_night_shop.save.sqlite3").exists())

    def test_earned_endings_can_be_read_after_reload_without_spoilers(self):
        self.assertEqual(self.call("endings")["endings"], [])
        with closing(sqlite3.connect(self.shop.SAVE_PATH)) as conn, conn:
            state = json.loads(conn.execute("SELECT state FROM shop").fetchone()[0])
            scene = {"id": "collection", "title": "第七面墙", "day": 291,
                     "reward": "没有背面的店主铭牌", "paragraphs": ["货架后面亮起一盏灯。"]}
            state["endings"] = [scene]
            conn.execute("UPDATE shop SET state=?", (json.dumps(state),))
        reloaded = load(self.path, "standalone_ending_reload")
        result = reloaded._call("endings")
        self.assertEqual(result["endings"], [scene])
        text = reloaded.cmd("endings")
        self.assertIn("【第七面墙】第291天", text)
        self.assertIn("纪念:没有背面的店主铭牌", text)
        self.assertNotIn("夜铺之外", text)
        self.assertIn("endings", reloaded.cmd("help"))


if __name__ == "__main__":
    unittest.main()
