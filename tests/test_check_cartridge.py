"""合并检查工具本身的测试:示例卡带必须通过,常见毛病必须被抓到。"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_cartridge  # noqa: E402


class CheckCartridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "cartridges" / "pocket-circuit", self.tmp / "cartridges" / "demo",
                        ignore=shutil.ignore_patterns("__pycache__", "versions"))
        manifest = self.tmp / "cartridges" / "demo" / "manifest.json"
        data = json.loads(manifest.read_text("utf-8"))
        data["id"] = "demo"
        manifest.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        self.rules = self.tmp / "cartridges" / "demo" / "rules.py"
        self._root = check_cartridge.ROOT
        check_cartridge.ROOT = self.tmp

    def tearDown(self):
        check_cartridge.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_example_passes(self):
        self.assertEqual(check_cartridge.check("demo"), [])

    def test_private_hand_in_public_state_is_caught(self):
        src = self.rules.read_text("utf-8").replace(
            '"revealed": deepcopy(s["revealed"]),',
            '"revealed": deepcopy(s["revealed"]), "my_hand": list(s["hands"][seat_id]),')
        self.rules.write_text(src, "utf-8")
        problems = check_cartridge.check("demo")
        self.assertTrue(any("public_state 不一样" in p for p in problems), problems)

    def test_nondeterministic_new_game_is_caught(self):
        src = self.rules.read_text("utf-8").replace("random.Random(seed).shuffle(nodes)", "random.shuffle(nodes)")
        self.rules.write_text(src, "utf-8")
        problems = check_cartridge.check("demo")
        self.assertTrue(any("new_game 结果不一样" in p for p in problems), problems)

    def test_crashing_rules_are_reported_not_raised(self):
        src = self.rules.read_text("utf-8").replace('s["pending"][seat_id] = card', 's["pending"][seat_id] = card; 1 / 0')
        self.rules.write_text(src, "utf-8")
        problems = check_cartridge.check("demo")
        self.assertTrue(any("ZeroDivisionError" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
