import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("player_setup", ROOT / "tools/setup_player_connection.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class TestPlayerSetup(unittest.TestCase):
    def test_preserves_private_query_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "player.json"
            response = {"result": "ok", "name": "Example", "mcp_url": "http://127.0.0.1:7777/mcp?player=synthetic"}
            with patch.object(setup, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as opening:
                setup.setup("Example", path, "https://example.invalid/mcp")
                self.assertEqual(json.loads(path.read_text("utf-8"))["mcp_url"], "https://example.invalid/mcp?player=synthetic")
                with self.assertRaises(ValueError):
                    setup.setup("Example", path)
                opening.assert_called_once()

    def test_rejects_repository_paths_and_invalid_public_addresses_before_creation(self):
        with patch.object(setup, "urlopen") as opening, tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                setup.setup("Example", ROOT / "data/player.json")
            for url in ("http://example.invalid/mcp", "https://example.invalid/", "https://example.invalid/mcp?player=x"):
                with self.assertRaises(ValueError):
                    setup.setup("Example", Path(folder) / "player.json", url)
            opening.assert_not_called()
