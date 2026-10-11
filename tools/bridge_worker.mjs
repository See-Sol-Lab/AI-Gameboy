// Stateless MCP-only forwarder. Keep account configuration outside the repository.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/mcp" && url.pathname !== "/mcp/") {
      return new Response("Not found", {status: 404});
    }
    const headers = new Headers(request.headers);
    headers.delete("host");
    const forwarded = new Request("http://127.0.0.1:7777/mcp" + url.search, {
      method: request.method, headers, body: request.body,
      redirect: "manual", duplex: "half",
    });
    const response = await env.GAMEBOY.fetch(forwarded);
    const resultHeaders = new Headers(response.headers);
    resultHeaders.set("cache-control", "no-store");
    return new Response(response.body, {status: response.status, headers: resultHeaders});
  },
};
