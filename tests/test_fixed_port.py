from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from console import server

ROOT = Path(__file__).resolve().parents[1]


class TestFixedPort(unittest.TestCase):
    def test_local_client_config_matches_fixed_server_address(self):
        self.assertEqual((server.HOST, server.PORT), ("127.0.0.1", 7777))
        config = json.loads((ROOT / ".mcp.json").read_text("utf-8"))
        self.assertEqual(config["mcpServers"]["gameboy"]["url"], "http://127.0.0.1:7777/mcp")

    def test_local_and_bridge_start_on_same_port(self):
        for bridge in (False, True):
            with self.subTest(bridge=bridge):
                tunnel = Mock()
                with patch("console.server.open_tunnel", return_value=(tunnel, "test.example")) as opening, \
                     patch.object(server.mcp, "streamable_http_app", return_value=Mock()) as app, \
                     patch("uvicorn.run") as run, patch.dict(server.BRIDGE), redirect_stdout(io.StringIO()):
                    server.serve(bridge)
                self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
                self.assertEqual(run.call_args.kwargs["port"], 7777)
                security = app.call_args.kwargs["transport_security"]
                self.assertIn("127.0.0.1:7777", security.allowed_hosts)
                if bridge:
                    opening.assert_called_once()
                    tunnel.terminate.assert_called_once()
                else:
                    opening.assert_not_called()

    def test_start_failure_does_not_retry_on_another_port(self):
        with patch("uvicorn.run", side_effect=SystemExit(1)) as run, \
             patch.object(server.mcp, "streamable_http_app", return_value=Mock()), \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                server.serve(False)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["port"], 7777)
