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
SOURCE = ROOT / "standalone/pocket_night_shop.py"


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

    def call(self, line):
        return json.loads(self.shop.cmd(line))

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
        self.assertIn("legal_actions", self.shop.cmd("help"))
        self.assertFalse(self.shop.SAVE_PATH.exists())
        view = self.call("observe")
        self.assertEqual(view["result"], "ok")
        self.assertEqual(view["public_state"]["collection"]["total"], 72)
        self.assertEqual(view["public_state"]["customer_collection"]["total"], 86)
        blob = json.dumps(view, ensure_ascii=False)
        for name in ("_secret", "_budget", "_wants", "_item_code", "末站遗下的站名牌"):
            self.assertNotIn(name, blob)
        self.assertTrue(self.shop.SAVE_PATH.exists())

    def test_same_rules_and_seed_give_identical_gameplay(self):
        canonical = load(ROOT / "cartridges/pocket-night-shop/rules.py", "standalone_canonical")
        state = canonical.new_game(["seat_a"], 17)
        self.assertEqual(self.call('new_game {"seed":17}')["public_state"], canonical.observe(state, "seat_a")["public_state"])
        state = canonical.apply(state, "seat_a", "set_start_funds", {"amount": 23})
        self.assertEqual(self.call('set_start_funds {"amount":23}')["public_state"]["coins"], 23)
        params = {"focus": "scavenge", "count": 6, "stop_on": "new"}
        state = canonical.apply(state, "seat_a", "run_shifts", params)
        result = self.call("run_shifts " + json.dumps(params))
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["public_state"], canonical.observe(state, "seat_a")["public_state"])

    def test_close_reopen_and_fresh_module_resume_disk_state(self):
        self.call('new_game {"seed":17}')
        self.call('set_start_funds {"amount":12}')
        self.call('work_shift {"focus":"tidy"}')
        closed = self.call("close_for_now")
        fresh = load(self.path, "standalone_resumed")
        self.assertEqual(json.loads(fresh.cmd("observe")), closed)
        self.shop = fresh
        opened = self.call("reopen_shop")
        self.assertFalse(opened["public_state"]["resting"])
        for key in ("inventory", "day", "coins", "collection", "customer_book", "pending_event"):
            self.assertEqual(opened["public_state"][key], closed["public_state"][key])

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
        self.call('set_start_funds {"amount":12}')
        for _ in range(110):
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
        for command in ("collection", "encounters", "customers"):
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
        self.assertEqual(json.loads(run.stdout)["result"], "ok")
        self.assertTrue((Path(self.temp.name) / "pocket_night_shop.save.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
