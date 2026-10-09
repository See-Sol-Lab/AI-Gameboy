import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("private_files_check", ROOT / "tools/check_private_files.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TestPrivateFiles(unittest.TestCase):
    def test_local_runtime_files_are_rejected_even_under_cartridges(self):
        for path in ("data/gameboy.db", "data/narrator.json", "data/stage_a_calls.log",
                     "cartridges/demo/my_save.json", "cartridges/demo/save.json",
                     "cartridges/demo/store.sqlite3-wal", "screenshots/test.png", ".env",
                     "cartridges/demo/package.zip"):
            with self.subTest(path=path):
                self.assertIsNotNone(checker.check(path, b"{}"))

    def test_disguised_database_and_save_are_rejected(self):
        self.assertIsNotNone(checker.check("cartridges/demo/readme.txt", b"SQLite format 3\x00payload"))
        for value in ({"seat_token": "example"}, {"nested": {"token_hash": "example"}},
                      {"shopkeeper": "seat_a", "inventory": [], "history": []}):
            self.assertIsNotNone(checker.check("cartridges/demo/payload.json", json.dumps(value).encode()))

    def test_code_manifest_and_empty_config_example_are_allowed(self):
        for path, content in (("cartridges/demo/rules.py", b"def new_game(seats, seed): pass"),
                              ("cartridges/demo/manifest.json", b'{"id":"demo","version":"1.0.0"}'),
                              ("data/narrator.example.json", b'{"api_key":""}')):
            self.assertIsNone(checker.check(path, content))

    def test_credentials_fail_without_echoing_the_value(self):
        credential = b"sk-" + b"a" * 30
        reason = checker.check("cartridges/demo/rules.py", credential)
        self.assertIsNotNone(reason)
        self.assertNotIn(credential.decode(), reason)
        self.assertIsNotNone(checker.check("data/narrator.example.json", b'{"api_key":"real-provider-key"}'))
