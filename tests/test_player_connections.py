"""Synthetic private connector credentials: recovery, persistence and seat isolation."""
import asyncio
import json
import logging
from pathlib import Path
import socket
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecuritySettings
import uvicorn

from console import server
from console.game_host import GameHost

ROOT = Path(__file__).resolve().parents[1]


def context(player):
    return SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(scope={"gameboy_player": player})))


class TestPlayerConnections(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.host = GameHost(Path(self.temp.name) / "test.db", ROOT / "cartridges")
        self.addCleanup(patch.stopall)
        patch.object(server, "host", self.host).start()
        self.game = self.host.create_session("pocket-circuit", "ai_ai")
        self.key = self.host.create_connection("Example player")["connection_key"]

    def test_unknown_and_unbound_connections_cannot_resume(self):
        self.assertIsNone(self.host.connection("unknown"))
        self.assertEqual(server.game_resume()["result"], "forbidden")
        self.assertEqual(server.game_resume(context(self.host.connection(self.key)))["result"], "rejected")

    def test_binding_survives_restart_and_rejects_other_seat(self):
        seat = self.game["seats"][0]
        player = self.host.connection(self.key)
        bound = server.game_connect(self.game["session_id"], seat["seat_token"], context(player))
        self.assertEqual(bound["result"], "ok")
        restarted = GameHost(self.host.db_path, ROOT / "cartridges")
        with patch.object(server, "host", restarted):
            ctx = context(restarted.connection(self.key))
            resumed = server.game_resume(ctx)
            self.assertEqual(resumed["seat_id"], seat["seat_id"])
            self.assertNotIn(seat["seat_token"], json.dumps(resumed))
            self.assertNotIn(self.key, json.dumps(resumed))
            self.assertEqual(server.game_observe(ctx=ctx)["revision"], bound["revision"])
            wrong = server.game_observe(self.game["session_id"], self.game["seats"][1]["seat_token"], ctx)
            self.assertEqual(wrong["result"], "forbidden")

    def test_failed_rebind_preserves_old_authorization(self):
        player = self.host.connection(self.key)
        seat = self.game["seats"][0]
        self.host.bind_connection(player["key_hash"], self.game["session_id"], seat["seat_token"])
        before = self.host.connection(self.key)
        self.assertEqual(self.host.bind_connection(player["key_hash"], self.game["session_id"], "wrong")["result"], "forbidden")
        self.assertEqual(self.host.connection(self.key), before)

    def test_valid_rebind_keeps_connection_key_and_resumes_new_game(self):
        player = self.host.connection(self.key)
        for _ in range(2):
            game = self.host.create_session("pocket-night-shop", "solo_ai")
            self.host.bind_connection(player["key_hash"], game["session_id"], game["seats"][0]["seat_token"])
            self.assertEqual(server.game_resume(context(self.host.connection(self.key)))["session_id"], game["session_id"])


class TestPrivateMCPWire(unittest.IsolatedAsyncioTestCase):
    async def test_new_transport_recovers_bound_seat_without_credentials_in_tool_args(self):
        previous_logging = logging.root.manager.disable
        logging.disable(logging.INFO)  # Synthetic access keys must not enter test logs.
        self.addCleanup(logging.disable, previous_logging)
        with tempfile.TemporaryDirectory() as folder:
            host = GameHost(Path(folder) / "wire.db", ROOT / "cartridges")
            game = host.create_session("pocket-circuit", "ai_ai")
            keys = [host.create_connection(f"Synthetic {i}")["connection_key"] for i in range(2)]
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            security = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                allowed_hosts=[f"127.0.0.1:{port}"], allowed_origins=[f"http://127.0.0.1:{port}"])
            app = server.Guard(server.mcp.streamable_http_app(transport_security=security, host="127.0.0.1"))
            runner = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
            with patch.object(server, "host", host):
                task = asyncio.create_task(runner.serve(sockets=[sock]))
                try:
                    async with asyncio.timeout(5):
                        while not runner.started:
                            await asyncio.sleep(.01)
                    base = f"http://127.0.0.1:{port}/mcp"
                    async def call(key, tool, args):
                        async with streamable_http_client(base + "?player=" + key) as (read, write):
                            async with ClientSession(read, write) as client:
                                await client.initialize()
                                tools = await client.list_tools()
                                for item in tools.tools:
                                    self.assertNotIn("ctx", item.model_dump(by_alias=True)["inputSchema"].get("properties", {}))
                                response = await client.call_tool(tool, args)
                                return json.loads(response.content[0].text)
                    for key, seat in zip(keys, game["seats"]):
                        bound = await call(key, "game_connect", {"session_id": game["session_id"], "seat_token": seat["seat_token"]})
                        self.assertEqual(bound["result"], "ok")
                    # Fresh MCP transports and a fresh host instance still recover their own seats.
                    with patch.object(server, "host", GameHost(host.db_path, ROOT / "cartridges")):
                        for key, seat in zip(keys, game["seats"]):
                            resumed = await call(key, "game_resume", {})
                            self.assertEqual(resumed["seat_id"], seat["seat_id"])
                            self.assertNotIn(seat["seat_token"], json.dumps(resumed))
                            acted = await call(key, "game_act", {"expected_revision": resumed["revision"], "action_id": "introduce",
                                "params": {"display_name": seat["seat_id"], "surface": "Synthetic"}})
                            self.assertEqual(acted["result"], "ok")
                    def denied(url, headers=None):
                        try:
                            with urlopen(Request(url, data=b'{}', headers=headers or {}), timeout=5) as response:
                                return response.status
                        except HTTPError as error:
                            code = error.code
                            error.close()
                            return code
                    for query in ("?player=unknown", "?player=", "?player=" + keys[0] + "&player=" + keys[1]):
                        self.assertEqual(await asyncio.to_thread(denied, base + query), 403)
                    self.assertEqual(await asyncio.to_thread(denied,
                        f"http://127.0.0.1:{port}/api/player-connections", {"cf-connecting-ip": "192.0.2.1"}), 403)
                finally:
                    runner.should_exit = True
                    await task
                    sock.close()
