from contextlib import closing
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("story_export", ROOT / "tools/export_story.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def story():
    return {"phase": "finished", "seed": 12345,
            "world": {"world_name": "测试灯城", "premise": "城门在雨中关闭。", "hidden_threads": "UNSEEN_TRUTH"},
            "identity_pool": [{"id": "one", "name": "行者甲", "origin": "来自河岸。", "secret_drive": "PRIVATE_DRIVE"},
                              {"id": "two", "name": "行者乙", "origin": "来自山城。"}],
            "identities": {"seat_a": "one", "seat_b": "two"},
            "history": [{"scene_index": 1, "title": "雨中的门", "story_text": "巡检在门下等候。",
                         "story_responses": ["巡检答道，桥还没有断。"],
                         "commits": {"seat_a": {"action": "检查桥索", "line": "我先过去看看。", "item_id": "PRIVATE_ITEM"},
                                     "seat_b": {"action": "向巡检问路", "line": "我们要找渡口。"}},
                         "slip": {"die": 6}, "report": ["骰6+2=8", "TECHNICAL_REPORT"]}],
            "ending": {"text": "天亮时，城门重新打开。", "secret_drives": "PRIVATE_DRIVE"}}


class TestStoryExport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.db = self.folder / "test.db"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TABLE session (id TEXT, cartridge_id TEXT, status TEXT, engine_state_json TEXT)")
            conn.execute("INSERT INTO session VALUES(?,?,?,?)", ("selected", "pocket-crossing", "finished",
                         json.dumps({"cartridge_state": story(), "events": [{"seat_token": "PRIVATE_TOKEN"}]})))

    def test_both_formats_keep_story_and_exclude_system_and_private_fields(self):
        for cid in exporter.ADVENTURES:
            for fmt in ("md", "txt"):
                with self.subTest(cid=cid, fmt=fmt):
                    text, warnings = exporter.render(cid, story(), fmt)
                    self.assertEqual(warnings, [])
                    for public in ("测试灯城", "巡检在门下等候", "桥还没有断", "检查桥索", "我先过去看看", "城门重新打开"):
                        self.assertIn(public, text)
                    for private in ("PRIVATE_DRIVE", "PRIVATE_ITEM", "UNSEEN_TRUTH", "TECHNICAL_REPORT", "骰6", "12345", "seat_a"):
                        self.assertNotIn(private, text)
                    self.assertEqual(text.startswith("# "), fmt == "md")

    def test_selected_export_is_read_only_and_does_not_overwrite(self):
        original = self.db.read_bytes()
        output = self.folder / "collection.md"
        self.assertEqual(exporter.export(self.db, "selected", "md", output), [])
        self.assertEqual(self.db.read_bytes(), original)
        self.assertNotIn("PRIVATE_TOKEN", output.read_text("utf-8"))
        with self.assertRaises(FileExistsError):
            exporter.export(self.db, "selected", "md", output)
        self.assertTrue(output.read_text("utf-8").startswith("# 测试灯城"))

    def test_incomplete_unsupported_and_repository_destinations_are_rejected(self):
        incomplete = story()
        incomplete["phase"] = "playing"
        with self.assertRaises(ValueError):
            exporter.render("pocket-crossing", incomplete, "md")
        with self.assertRaises(ValueError):
            exporter.render("pocket-night-shop", story(), "md")
        with self.assertRaises(ValueError):
            exporter.export(self.db, "selected", "md", ROOT / "exports/private-story.md")
        with self.assertRaises(ValueError):
            exporter.export(self.db, "missing", "txt", self.folder / "missing.txt")
        self.assertFalse((self.folder / "missing.txt").exists())

    def test_missing_earlier_prose_is_reported_not_invented(self):
        state = story()
        del state["history"][0]["story_text"]
        text, warnings = exporter.render("pocket-crossing", state, "txt")
        self.assertEqual(len(warnings), 1)
        self.assertNotIn("巡检在门下等候", text)
        self.assertIn("检查桥索", text)

    def test_crossing_saves_public_scene_prose_and_responses(self):
        for cid in ("pocket-crossing",):
            spec = importlib.util.spec_from_file_location(cid.replace("-", "_"), ROOT / "cartridges" / cid / "rules.py")
            rules = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(rules)
            state = rules.new_game(["seat_a", "seat_b"], 1)
            scene = {"title": "测试场景", "text": "雨停了。", "npc_responses": [{"detail": "桥可以通行。", "private": "PRIVATE"}]}
            rules._log(state, scene, {}, {}, [])
            entry = state["history"][-1]
            self.assertEqual(entry["story_text"], "雨停了。")
            self.assertEqual(entry["story_responses"], ["桥可以通行。"])
            self.assertNotIn("PRIVATE", json.dumps(entry))

    def test_tabletop_actual_rounds_export_canonical_changes_and_ending(self):
        from test_pocket_tabletop import setup, round_, feed, advance
        state = feed(round_(setup(), advance("m1")), change_text="海堤修复后，旅人为居民搭起避雨棚。")
        state["scene_index"] = 10
        state = feed(round_(state, {"intent": "support", "target_id": "free", "action": "我帮助居民加固避雨棚，安置工具。"}))
        text, warnings = exporter.render("pocket-tabletop", state, "md")
        self.assertEqual(warnings, [])
        self.assertIn(state["history"][0]["story_text"], text)
        self.assertIn("阶段1已完成。", text)
        self.assertIn("旅人为居民搭起避雨棚", text)
        self.assertIn(state["ending"]["text"], text)
        for identity in state["identity_pool"]:
            if identity["id"] in state["identities"].values():
                self.assertIn(identity["name"], text)
        self.assertNotIn("骰", text)
        self.assertNotIn("target_id", text)

    def test_real_rule_ending_exports_saved_prose(self):
        from test_pocket_crossing import setup_playing, feed, rules
        state = setup_playing(4)
        for seat in state["seats"]:
            state = rules.apply(state, seat, "commit", {"intent": "end", "action": ""})
        state = feed(state)
        text, warnings = exporter.render("pocket-crossing", state, "md")
        self.assertEqual(warnings, [])
        self.assertIn(state["history"][0]["story_text"], text)
        self.assertIn(state["ending"]["text"], text)

    def test_public_event_result_has_no_dice_or_numeric_counters(self):
        state = story()
        state["events"] = {"log": [{"scene": 1, "text": "落石封住了山路。", "won": True,
                                    "target": 24, "total": 29}]}
        text, warnings = exporter.render("pocket-tabletop", state, "txt")
        self.assertIn("落石封住了山路", text)
        self.assertIn("化解了这场变故", text)
        self.assertNotIn("24", text)
        self.assertNotIn("29", text)
