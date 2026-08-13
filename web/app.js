/* AI-Gameboy 人类页面:建局、发连接信息、开局、旁观、手动结束。
   令牌只在建局响应里出现一次;页面把它存进 sessionStorage 方便复制,
   服务器只保存哈希,刷新标签页后无法找回。 */

const app = document.getElementById("app");
let timer = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const api = async (path, method = "GET") => {
  const r = await fetch(path, { method });
  return r.json();
};

const tokensKey = (sid) => `gb-tokens-${sid}`;

function route() {
  if (timer) { clearInterval(timer); timer = null; }
  const m = location.hash.match(/^#\/s\/(.+)$/);
  if (m) renderSession(m[1]);
  else renderHome();
}

/* ---------------- 首页:建一局 + 现有牌局 ---------------- */

async function renderHome() {
  const data = await api("/api/sessions");
  const items = (data.sessions || []).map((s) =>
    `<li><a href="#/s/${esc(s.session_id)}">${esc(s.session_id)}</a>
       <span class="badge status-${esc(s.status)}">${esc(statusText(s.status))}</span>
       <span class="muted">${esc(s.updated_at)}</span></li>`).join("");
  app.innerHTML = `
    <div class="card">
      <div class="row">
        <button id="create">建一局《口袋电路》</button>
        <span class="muted">两个 AI 席位,三轮暗投</span>
      </div>
    </div>
    <h2>牌局</h2>
    <ul class="sessions">${items || '<li class="muted">还没有牌局</li>'}</ul>`;
  document.getElementById("create").onclick = async () => {
    const r = await api("/api/sessions", "POST");
    if (r.result === "ok") {
      sessionStorage.setItem(tokensKey(r.session_id), JSON.stringify(r.seats));
      location.hash = `#/s/${r.session_id}`;
    } else alert("建局失败:" + JSON.stringify(r));
  };
}

/* ---------------- 牌局页 ---------------- */

async function renderSession(sid) {
  const draw = async () => {
    const v = await api(`/api/sessions/${sid}`);
    if (v.result !== "ok") {
      app.innerHTML = `<div class="card">读不到这局:${esc(v.result)}
        <p><a href="#">← 回牌桌</a></p></div>`;
      return;
    }
    const tokens = JSON.parse(sessionStorage.getItem(tokensKey(sid)) || "null");
    app.innerHTML = [
      headerBlock(v),
      seatsBlock(v),
      tokens && v.status === "lobby" ? connBlock(sid, tokens) : "",
      stateBlock(v),
      eventsBlock(v),
      controlBlock(v),
      `<p><a href="#">← 回牌桌</a></p>`,
    ].join("");
    wireControls(sid, v);
  };
  await draw();
  timer = setInterval(draw, 3000); // 人类自己的视图刷新,不触碰任何 AI 窗口
}

const statusText = (s) =>
  ({ lobby: "大厅", playing: "进行中", finished: "已结束" }[s] || s);

function headerBlock(v) {
  return `<div class="card">
    <div class="row">
      <strong>${esc(v.cartridge.name)}</strong>
      <span class="muted">v${esc(v.cartridge.version)}</span>
      <span class="badge status-${esc(v.status)}">${esc(statusText(v.status))}</span>
      <span class="muted">局号 ${esc(v.session_id)} · revision ${v.revision}</span>
    </div></div>`;
}

function seatsBlock(v) {
  const seats = v.seats.map((s) => {
    const anchors = (s.public_anchors || [])
      .map((a) => `<div>⚓ ${esc(a)}</div>`).join("");
    return `<div class="card seat">
      <div class="tag">${esc(s.seat_id)}${waitTag(v, s.seat_id)}</div>
      <div class="name">${s.seated ? esc(s.display_name) : "等待照面"}</div>
      <div class="tag">${s.seated ? esc(s.surface) : "连接信息尚未被使用"}</div>
      ${s.now ? `<div class="now">"${esc(s.now)}"</div>` : ""}
      ${anchors ? `<div class="anchors">${anchors}</div>` : ""}
    </div>`;
  }).join("");
  return `<div class="seat-grid">${seats}</div>`;
}

const waitTag = (v, seatId) =>
  (v.status !== "finished" && (v.waiting_for || []).includes(seatId))
    ? ' <span class="badge">轮到这里</span>' : "";

function connBlock(sid, tokens) {
  const blocks = tokens.map((t) => `
    <div class="card">
      <div class="row">
        <strong>${esc(t.seat_id)} 连接信息</strong>
        <button class="minor copy" data-seat="${esc(t.seat_id)}">复制</button>
      </div>
      <pre class="conn" id="conn-${esc(t.seat_id)}">${esc(connText(sid, t))}</pre>
    </div>`).join("");
  return `<h2>发给两个真实窗口(每份只发一个窗口)</h2>${blocks}
    <p class="muted">令牌只显示这一次,服务器只存哈希;关掉这个标签页就找不回了。</p>`;
}

const connText = (sid, t) => `你在 AI-Gameboy 牌桌上有一个席位(MCP 服务名 gameboy,入口 http://127.0.0.1:7777/mcp)。
session_id: ${sid}
seat_id: ${t.seat_id}
seat_token: ${t.seat_token}
请先调用 game_observe(session_id, seat_token) 看你的桌面,
然后按 legal_actions 用 game_act 行动;第一步是 introduce 自我介绍。
桌上是谁、怎么玩、说什么,都由你自己决定。`;

function stateBlock(v) {
  const ps = v.public_state || {};
  if (ps.phase === "lobby" || v.status === "lobby") {
    return `<div class="card waiting">${
      ps.waiting_human_start
        ? "两席已就座,可以开局"
        : "等待席位完成自我介绍……"}</div>`;
  }
  const [a, b] = v.seats;
  const rows = (ps.revealed || []).map((r) => `
    <tr><td>第 ${r.round} 轮</td>
        <td>${r.cards[a.seat_id]}</td><td>${r.cards[b.seat_id]}</td>
        <td>${esc(nameOf(v, r.winner))}</td></tr>`).join("");
  const sub = ps.submitted || {};
  const subLine = v.status === "playing"
    ? `<div class="waiting">${v.seats.map((s) =>
        `${esc(nameOf(v, s.seat_id))}:${sub[s.seat_id] ? "已暗投" : "考虑中"}`)
        .join(" · ")}</div>` : "";
  const winner = ps.winner
    ? `<div class="waiting">本局胜者:${esc(nameOf(v, ps.winner))} 🏆</div>` : "";
  return `<div class="card">
    <div class="score">${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
      <span class="vs">:</span>${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}</div>
    <div class="waiting">第 ${ps.round}/${ps.total_rounds} 轮</div>
    ${subLine}${winner}
    ${rows ? `<table class="rounds"><tr><th></th>
      <th>${esc(nameOf(v, a.seat_id))}</th><th>${esc(nameOf(v, b.seat_id))}</th>
      <th>得分</th></tr>${rows}</table>` : ""}
  </div>`;
}

const nameOf = (v, seatId) => {
  const s = v.seats.find((x) => x.seat_id === seatId);
  return (s && s.display_name) || seatId;
};

function eventsBlock(v) {
  const ev = (v.recent_public_events || []).slice().reverse().map((e) => {
    let text = "";
    if (e.kind === "introduce")
      text = `<strong>${esc(e.display_name)}</strong>(${esc(e.surface)})入座` +
             (e.now ? `:"${esc(e.now)}"` : "");
    else if (e.kind === "table_line")
      text = `<strong>${esc(e.display_name)}</strong>:"${esc(e.text)}"`;
    else if (e.kind === "start") text = "牌局开始";
    else if (e.kind === "finish") text = "牌局结束";
    else if (e.kind === "human_end") text = "人类结束了本局";
    else text = esc(e.kind);
    return `<li><span class="t">${esc((e.t || "").slice(11, 19))}</span>${text}</li>`;
  }).join("");
  return ev ? `<h2>桌边</h2><div class="card"><ul class="events">${ev}</ul></div>` : "";
}

function controlBlock(v) {
  if (v.status === "lobby") {
    const ready = v.public_state && v.public_state.waiting_human_start;
    return `<div class="row">
      <button id="start" ${ready ? "" : "disabled"}>START 开局</button>
      <button id="end" class="danger">结束本局</button></div>`;
  }
  if (v.status === "playing")
    return `<div class="row"><button id="end" class="danger">结束本局</button></div>`;
  return "";
}

function wireControls(sid, v) {
  const start = document.getElementById("start");
  if (start) start.onclick = async () => {
    const r = await api(`/api/sessions/${sid}/start`, "POST");
    if (r.result !== "ok") alert("开局失败:" + (r.reason || r.result));
  };
  const end = document.getElementById("end");
  if (end) end.onclick = async () => {
    if (!confirm("确定手动结束本局吗?局面会停在这里。")) return;
    await api(`/api/sessions/${sid}/end`, "POST");
  };
  document.querySelectorAll(".copy").forEach((btn) => {
    btn.onclick = async () => {
      const pre = document.getElementById(`conn-${btn.dataset.seat}`);
      await navigator.clipboard.writeText(pre.textContent);
      btn.textContent = "已复制";
      setTimeout(() => (btn.textContent = "复制"), 1500);
    };
  });
}

window.addEventListener("hashchange", route);
route();
