from contextlib import redirect_stdout
import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from console import server

ROOT = Path(__file__).resolve().parents[1]


class TestFixedPort(unittest.TestCase):
    def setUp(self):
        self.loader = patch.object(server, "load_fixed_bridge", return_value=None)
        self.loader.start()
        self.addCleanup(self.loader.stop)
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

    def test_configured_fixed_bridge_starts_with_normal_console_and_cleans_up(self):
        config = {"mcp_url":"https://example.invalid/mcp", "tunnel_id":"00000000-0000-0000-0000-000000000001", "wrangler_profile":"example"}
        with patch.object(server, "load_fixed_bridge", return_value=config), \
             patch.object(server, "open_fixed_tunnel") as opening, \
             patch.object(server, "stop_fixed_tunnel") as stop, \
             patch.object(server.mcp, "streamable_http_app", return_value=Mock()), \
             patch("uvicorn.run"), patch.dict(server.BRIDGE), redirect_stdout(io.StringIO()):
            server.serve(False)
            self.assertEqual(server.BRIDGE["mcp_url"], config["mcp_url"])
            self.assertEqual(server.BRIDGE["kind"], "fixed")
            opening.assert_called_once_with(config)
            stop.assert_called_once_with(opening.return_value)

    def test_fixed_and_temporary_bridges_cannot_be_started_together(self):
        with patch.object(server, "load_fixed_bridge", return_value={"mcp_url":"https://example.invalid/mcp"}), \
             patch.object(server, "open_tunnel") as temporary:
            with self.assertRaises(ValueError):
                server.serve(True)
            temporary.assert_not_called()


class TestBridgeConfig(unittest.TestCase):
    def test_config_validation_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(server, "BASE", Path(folder)):
            self.assertIsNone(server.load_fixed_bridge())
            path = Path(folder) / "data/bridge.json"
            path.parent.mkdir()
            good = {"mcp_url":"https://example.invalid/mcp", "tunnel_id":"00000000-0000-0000-0000-000000000001", "wrangler_profile":"example"}
            path.write_text(json.dumps(good), encoding="utf-8")
            self.assertEqual(server.load_fixed_bridge(), good)
            for key, value in (("mcp_url","http://example.invalid/mcp"), ("mcp_url","https://example.invalid/mcp?player=secret"),
                               ("tunnel_id","not-a-uuid"), ("wrangler_profile","unsafe & profile")):
                with self.subTest(key=key,value=value):
                    path.write_text(json.dumps({**good,key:value}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        server.load_fixed_bridge()

    def test_fixed_tunnel_requires_real_registration_marker(self):
        config = {"mcp_url":"https://example.invalid/mcp", "tunnel_id":"00000000-0000-0000-0000-000000000001", "wrangler_profile":"example"}
        proc = Mock()
        proc.stdout = io.StringIO("Registered tunnel connection\n")
        proc.poll.return_value = None
        with patch.object(server.shutil, "which", return_value="npx"), \
             patch.object(server, "find_cloudflared", return_value="cloudflared"), \
             patch.object(server.subprocess, "Popen", return_value=proc) as opening:
            self.assertIs(server.open_fixed_tunnel(config), proc)
            command = opening.call_args.args[0]
            self.assertIn(config["tunnel_id"], command)
            self.assertIn(config["wrangler_profile"], command)

    def test_failed_registration_cleans_owned_tunnel_and_does_not_switch_address(self):
        proc = Mock()
        config = {"tunnel_id":"00000000-0000-0000-0000-000000000001", "wrangler_profile":"example"}
        with patch.object(server.shutil, "which", return_value="npx"), \
             patch.object(server, "find_cloudflared", return_value="cloudflared"), \
             patch.object(server.subprocess, "Popen", return_value=proc), \
             patch.object(server.threading, "Thread"), \
             patch.object(server.threading, "Event") as event, \
             patch.object(server, "stop_fixed_tunnel") as stop:
            event.return_value.wait.return_value = False
            with self.assertRaises(RuntimeError):
                server.open_fixed_tunnel(config)
            stop.assert_called_once_with(proc)

    def test_fixed_cleanup_targets_only_owned_process_tree(self):
        proc = Mock(pid=12345)
        proc.poll.return_value = None
        with patch.object(server.sys, "platform", "win32"), patch.object(server.subprocess, "run") as run:
            server.stop_fixed_tunnel(proc)
            self.assertEqual(run.call_args.args[0], ["taskkill","/PID","12345","/T","/F"])
