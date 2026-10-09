"""Installation, shelf visibility, archive reading and save-protected removal."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from console import cartridges, narrator, server
from console.game_host import GameHost

ROOT = Path(__file__).resolve().parents[1]


class TestCartridgeManagement(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "cartridges").mkdir()
        self.source = self.root / "download" / "demo"
        self.source.parent.mkdir()
        shutil.copytree(ROOT / "examples/pocket-circuit", self.source,
                        ignore=shutil.ignore_patterns("__pycache__"))
        manifest = json.loads((self.source / "manifest.json").read_text("utf-8"))
        manifest["id"] = "demo"
        (self.source / "manifest.json").write_text(json.dumps(manifest), "utf-8")
        self.host = GameHost(self.root / "data/gameboy.db", self.root / "cartridges")

    def test_default_shelf_is_three_games_and_old_cards_still_load(self):
        host = GameHost(self.root / "unused.db", ROOT / "cartridges")
        ids = {m["id"] for m in host.list_cartridges()["cartridges"]}
        self.assertEqual(ids, {"pocket-crossing", "pocket-tabletop", "pocket-night-shop"})
        for cid in ("pocket-circuit",):
            manifest = host._load_manifest(cid)
            _, rules = host._load_cartridge(cid, manifest["version"])
            self.assertTrue(callable(rules.observe))
        for cid in ("blind-companions", "four-things-in-my-pocket"):
            self.assertEqual(host.create_session(cid)["result"], "rejected")

    def test_install_hide_and_show_preserve_existing_session(self):
        self.assertEqual(cartridges.install(self.source, self.root), "demo")
        created = self.host.create_session("demo", "human_ai")
        self.assertEqual(created["result"], "ok")
        sid, token = created["session_id"], created["seats"][0]["seat_token"]
        before = self.host.observe(sid, token)
        cartridges.set_hidden("demo", True, self.root)
        self.assertEqual(self.host.list_cartridges()["cartridges"], [])
        self.assertEqual(self.host.observe(sid, token), before)
        self.assertTrue(cartridges.installed(self.root)[0]["hidden"])
        cartridges.set_hidden("demo", False, self.root)
        self.assertEqual(self.host.list_cartridges()["cartridges"][0]["id"], "demo")

    def test_uninstall_requires_confirmation_and_leaves_other_files_alone(self):
        cartridges.install(self.source, self.root)
        sentinel = self.root / "keep.txt"
        sentinel.write_text("keep", "utf-8")
        with self.assertRaisesRegex(ValueError, "确认"):
            cartridges.uninstall("demo", self.root)
        self.assertTrue((self.root / "cartridges/demo/rules.py").exists())
        cartridges.uninstall("demo", self.root, confirmed=True)
        self.assertFalse((self.root / "cartridges/demo").exists())
        self.assertEqual(sentinel.read_text("utf-8"), "keep")
        self.assertEqual(self.host.create_session("demo")["result"], "rejected")

    def test_any_saved_session_blocks_uninstall_including_finished(self):
        cartridges.install(self.source, self.root)
        created = self.host.create_session("demo", "human_ai")
        with closing(sqlite3.connect(self.host.db_path)) as conn, conn:
            conn.execute("UPDATE session SET status='finished'")
        with self.assertRaisesRegex(ValueError, "存档"):
            cartridges.uninstall("demo", self.root, confirmed=True)
        self.assertTrue((self.root / "cartridges/demo/rules.py").exists())
        self.assertEqual(len(self.host.list_sessions()["sessions"]), 1)

    def test_duplicate_install_and_traversal_are_rejected(self):
        cartridges.install(self.source, self.root)
        with self.assertRaisesRegex(ValueError, "覆盖"):
            cartridges.install(self.source, self.root)
        for cid in ("../data", "..", "x/y", "C:\\data", ""):
            with self.subTest(cid=cid):
                with self.assertRaises(ValueError):
                    cartridges.uninstall(cid, self.root, confirmed=True)
                self.assertEqual(self.host.create_session(cid)["result"], "rejected")

    def test_reinstall_returns_previously_hidden_card_to_shelf(self):
        cartridges.install(self.source, self.root)
        cartridges.set_hidden("demo", True, self.root)
        cartridges.uninstall("demo", self.root, confirmed=True)
        cartridges.install(self.source, self.root)
        self.assertFalse(cartridges.installed(self.root)[0]["hidden"])
        self.assertEqual(self.host.list_cartridges()["cartridges"][0]["id"], "demo")

    def test_console_move_keeps_runtime_data_and_web_paths(self):
        self.assertEqual(server.BASE, ROOT)
        self.assertEqual(server.host.db_path, str(ROOT / "data/gameboy.db"))
        self.assertEqual(narrator.CONFIG_PATH, ROOT / "data/narrator.json")
        self.assertEqual(server.WEB, ROOT / "console/web")
        self.assertTrue((server.WEB / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
