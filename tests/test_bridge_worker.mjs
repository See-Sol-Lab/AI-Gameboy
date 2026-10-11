import test from "node:test";
import assert from "node:assert/strict";
import worker from "../tools/bridge_worker.mjs";

test("only exact MCP routes reach the local service", async () => {
  let calls = 0;
  const env = {GAMEBOY: {fetch: async () => { calls++; return new Response("ok"); }}};
  for (const path of ["/", "/api/sessions", "/web/app.js", "/mcp/../api/sessions", "/mcp/private", "/mcpx"]) {
    assert.equal((await worker.fetch(new Request("https://example.invalid" + path), env)).status, 404);
  }
  assert.equal(calls, 0);
  for (const path of ["/mcp", "/mcp/"]) {
    assert.equal((await worker.fetch(new Request("https://example.invalid" + path), env)).status, 200);
  }
  assert.equal(calls, 2);
});

test("private query, body and MCP headers survive without caching", async () => {
  let forwarded;
  const env = {GAMEBOY: {fetch: async request => {
    forwarded = request;
    return new Response('{"result":"ok"}', {headers: {"content-type":"application/json", "mcp-session-id":"synthetic-session"}});
  }}};
  const response = await worker.fetch(new Request("https://example.invalid/mcp?player=synthetic", {
    method: "POST", body: '{"method":"tools/list"}',
    headers: {"mcp-protocol-version":"2025-11-25", host:"example.invalid"},
  }), env);
  assert.equal(forwarded.url, "http://127.0.0.1:7777/mcp?player=synthetic");
  assert.equal(forwarded.method, "POST");
  assert.equal(await forwarded.text(), '{"method":"tools/list"}');
  assert.equal(forwarded.headers.get("mcp-protocol-version"), "2025-11-25");
  assert.equal(response.headers.get("mcp-session-id"), "synthetic-session");
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("SSE responses remain streaming", async () => {
  const env = {GAMEBOY:{fetch:async () => new Response("data: example\n\n", {headers:{"content-type":"text/event-stream"}})}};
  const response = await worker.fetch(new Request("https://example.invalid/mcp"), env);
  assert.equal(response.headers.get("content-type"), "text/event-stream");
  assert.equal(await response.text(), "data: example\n\n");
});
