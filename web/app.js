/* AI-Gameboy Stage C:掌机壳主板。
   三屏:卡带架 / 开局席位 / 正在游戏(+ 纪念卡)。
   实体键 A/B/START/SELECT/方向键真实可用;屏内保留中文按钮。
   令牌边界不变:只在建局标签页的 sessionStorage 里,服务器只存哈希。 */

const app = document.getElementById("app");
const bezelTitle = document.getElementById("bezel-title");
const powerLed = document.getElementById("power-led");
const startBtn = document.getElementById("btn-start");
const cartOverlay = document.getElementById("cart-overlay");

/* 唯一内置卡带的架面信息(展示用;牌局真相始终来自服务端) */
const CART = {
  id: "pocket-circuit",
  name: "口袋电路",
  author: "See Sol Lab · 自研",
  players: "2 人",
  minutes: "约 5 分钟",
  license: "private-prototype",
  rules: "数字牌 1–6 随机分成两手,各三张互不重复。每轮双方各暗投一张,同时揭示,大者得分;三轮定胜负。你知道对方拿哪三张,但不知道这一轮他出哪张。",
};

const S = {
  view: "shelf",   // shelf | seats | game | memorial
  sid: null,
  timer: null,
  focusIdx: 0,
  infoOpen: false,
  lastSnap: "",
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, method = "GET") => (await fetch(path, { method })).json();
const tokensKey = (sid) => `gb-tokens-${sid}`;
const hhmm = (t) => (t || "").slice(11, 16);

/* ---------------- 路由 ---------------- */

function route() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; }
  S.lastSnap = "";
  S.focusIdx = 0;
  const mem = location.hash.match(/^#\/m\/(.+)$/);
  const ses = location.hash.match(/^#\/s\/(.+)$/);
  if (mem) showMemorial(mem[1]);
  else if (ses) showSession(ses[1]);
  else showShelf();
}

function setScreen(view, title) {
  S.view = view;
  bezelTitle.textContent = title;
  startBtn.classList.remove("armed");
}

/* ---------------- 卡带架 ---------------- */

async function showShelf() {
  setScreen("shelf", "卡带架");
  const data = await api("/api/sessions");
  const sessions = data.sessions || [];
  const played = sessions.filter((s) => s.status === "finished").length;
  const saves = sessions.map((s) => `
    <div class="save-item focusable" data-act="open-save" data-sid="${esc(s.session_id)}">
      <span class="sid">${esc(s.session_id)}</span>
      <span class="save-badge ${esc(s.status)}">${esc(statusText(s.status))}</span>
      <span class="when">${esc((s.updated_at || "").slice(5, 16).replace("T", " "))}</span>
    </div>`).join("");
  app.innerHTML = `
    <h2>· 卡 带 架 ·</h2>
    ${infoPanel()}
    <div class="shelf-row">
      <div class="cart focusable" data-act="insert">
        <div class="cart-face">
          <div class="t">${esc(CART.name)}</div>
          <div class="a">${esc(CART.author)}</div>
          <div class="m">${esc(CART.players)} · ${esc(CART.minutes)}</div>
        </div>
        <div class="cart-plays">已玩 ${played} 局</div>
      </div>
    </div>
    <p class="dim center">对准卡带按 A 插入,开一张新桌 · SELECT 看卡带说明</p>
    <div class="saves">
      <p class="dim">存档</p>
      ${saves || '<p class="dim center">这张卡带还没有存档</p>'}
    </div>`;
  afterRender();
}

const statusText = (s) =>
  ({ lobby: "大厅", playing: "进行中", finished: "已收桌" }[s] || s);

function infoPanel() {
  if (!S.infoOpen) return "";
  return `<div class="info-panel"><dl>
    <dt>${esc(CART.name)} · v0.1.0</dt><dd>${esc(CART.author)} · ${esc(CART.license)}</dd>
    <dt>玩法</dt><dd>${esc(CART.rules)}</dd>
    <dt>授权</dt><dd>内置测试卡,随掌机宿主发布,已通过 20 项协议测试。</dd>
  </dl></div>`;
}

async function insertCartridge() {
  cartOverlay.hidden = false;
  cartOverlay.querySelector(".cart-kacha").hidden = false;
  await new Promise((r) => setTimeout(r, 750));
  cartOverlay.hidden = true;
  const r = await api("/api/sessions", "POST");
  if (r.result === "ok") {
    sessionStorage.setItem(tokensKey(r.session_id), JSON.stringify(r.seats));
    location.hash = `#/s/${r.session_id}`;
  } else {
    alert("插卡失败:" + JSON.stringify(r));
  }
}

/* ---------------- 牌局(席位 / 游戏) ---------------- */

async function showSession(sid) {
  S.sid = sid;
  const draw = async () => {
    const v = await api(`/api/sessions/${sid}`);
    if (v.result !== "ok") {
      setScreen("seats", "开局席位");
      app.innerHTML = `<p class="center">读不到这局(${esc(v.result)})。按 B 回卡带架。</p>`;
      return;
    }
    if (v.status === "finished") {
      location.replace(`#/m/${sid}`);
      return;
    }
    const snap = JSON.stringify(v) + S.infoOpen;
    if (snap === S.lastSnap) return;
    S.lastSnap = snap;
    if (v.status === "lobby") renderSeats(v);
    else renderGame(v);
  };
  await draw();
  S.timer = setInterval(draw, 3000); // 人类视图自刷新,不触碰任何 AI 窗口
}

function renderSeats(v) {
  setScreen("seats", "开局席位");
  powerLed.classList.add("busy");
  const tokens = JSON.parse(sessionStorage.getItem(tokensKey(v.session_id)) || "null");
  const slots = v.seats.map((s) => {
    const turn = (v.waiting_for || []).includes(s.seat_id);
    const tok = tokens && tokens.find((t) => t.seat_id === s.seat_id);
    let body;
    if (s.seated) {
      body = `<div class="who">${esc(s.display_name)}</div>
        <div class="surf">${esc(s.surface)}</div>
        ${s.now ? `<div class="now-line">"${esc(s.now)}"</div>` : ""}
        ${(s.public_anchors || []).map((a) => `<div class="anchor">⚓ ${esc(a)}</div>`).join("")}`;
    } else {
      body = `<div class="empty-hint">等待照面</div>
        <div class="conn-box center">${tok
          ? `<button class="soft focusable" data-act="copy" data-seat="${esc(s.seat_id)}">复制 ${esc(s.seat_id)} 连接信息</button>
             <div class="conn-note">整段只交给一个真实窗口</div>`
          : `<div class="conn-note">令牌只在建局的标签页显示一次</div>`}</div>`;
    }
    return `<div class="slot ${s.seated ? "seated" : ""} ${turn ? "turn" : ""}">
      <span class="lamp"></span>
      <div class="dim">${esc(s.seat_id)}</div>${body}</div>`;
  }).join("");
  const ready = v.public_state && v.public_state.waiting_human_start;
  if (ready) startBtn.classList.add("armed");
  app.innerHTML = `
    <h2>· 开 局 席 位 ·</h2>
    ${infoPanel()}
    <div class="slots">${slots}</div>
    <div class="start-hint ${ready ? "ready" : ""}">${ready
      ? "两席已就座 —— 按 START 开局"
      : "把连接信息分别交给两个真实窗口,等它们自己入座"}</div>
    <p class="center"><button class="soft warn focusable" data-act="end">收起这局</button></p>
    <p class="dim center">局号 ${esc(v.session_id)}</p>`;
  afterRender();
}

function renderGame(v) {
  setScreen("game", "正在游戏");
  powerLed.classList.add("busy");
  const ps = v.public_state || {};
  const [a, b] = v.seats;
  const nameOf = (id) => {
    const s = v.seats.find((x) => x.seat_id === id);
    return (s && s.display_name) || id;
  };
  const seatBox = (s) => {
    const turn = (v.waiting_for || []).includes(s.seat_id);
    const sub = ps.submitted && ps.submitted[s.seat_id];
    return `<div class="side-seat ${turn ? "turn" : ""}">
      <div class="lamp"></div>
      <div class="who">${esc(s.display_name)}</div>
      <div class="surf">${esc(s.surface)}</div>
      <div class="stat">${sub ? "已暗投 ▮" : turn ? "考虑中…" : ""}</div>
    </div>`;
  };
  const revealedRows = (ps.revealed || []).map((r) => {
    const ca = r.cards[a.seat_id], cb = r.cards[b.seat_id];
    return `<div class="mem-round">
      <span class="dim">第${r.round}轮</span>
      <span class="pcard ${r.winner === a.seat_id ? "win" : ""}">${ca}</span>
      <span class="dim">vs</span>
      <span class="pcard ${r.winner === b.seat_id ? "win" : ""}">${cb}</span>
      <span class="w">${esc(nameOf(r.winner))} 得分</span>
    </div>`;
  }).join("");
  const talk = (v.public_events || v.recent_public_events || [])
    .map(eventLine).filter(Boolean).join("");
  app.innerHTML = `
    ${infoPanel()}
    <div class="table-top">
      ${seatBox(a)}
      <div class="felt">
        <div class="score">${esc(nameOf(a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
          <span class="colon">:</span>${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(b.seat_id))}</div>
        <div class="round-line">第 ${ps.round} / ${ps.total_rounds} 轮</div>
        <div class="cards-row">
          ${(ps.revealed || []).length ? "" : '<span class="pcard back">?</span><span class="pcard back">?</span>'}
        </div>
        <div class="rounds-mini">${revealedRows}</div>
      </div>
      ${seatBox(b)}
    </div>
    <div class="table-talk">${talk}</div>
    <p class="center"><button class="soft warn focusable" data-act="end">结束本局</button></p>
    <p class="dim center">局号 ${esc(v.session_id)}</p>`;
  afterRender();
}

function eventLine(e) {
  if (e.kind === "table_line")
    return `<div class="talk-line"><span class="tt">${esc(hhmm(e.t))}</span>
      <span class="who">${esc(e.display_name)}</span>
      <span class="txt">${esc(e.text)}</span></div>`;
  if (e.kind === "introduce")
    return `<div class="sys-line">· ${esc(e.display_name)}(${esc(e.surface)})入座 ·</div>`;
  if (e.kind === "start") return `<div class="sys-line">· 牌局开始 ·</div>`;
  if (e.kind === "finish") return `<div class="sys-line">· 三轮打完,结算 ·</div>`;
  if (e.kind === "human_end") return `<div class="sys-line">· 人类收起了这局 ·</div>`;
  return "";
}

async function endSession() {
  if (!confirm("确定收起这局吗?局面会停在这里。")) return;
  await api(`/api/sessions/${S.sid}/end`, "POST");
  S.lastSnap = "";
}

/* ---------------- 纪念卡 ---------------- */

async function showMemorial(sid) {
  S.sid = sid;
  setScreen("memorial", "纪念卡");
  powerLed.classList.remove("busy");
  const v = await api(`/api/sessions/${sid}`);
  if (v.result !== "ok") {
    app.innerHTML = `<p class="center">读不到这局(${esc(v.result)})。按 B 回卡带架。</p>`;
    return;
  }
  const ps = v.public_state || {};
  const [a, b] = v.seats;
  const nameOf = (id) => {
    const s = v.seats.find((x) => x.seat_id === id);
    return (s && s.display_name) || id;
  };
  const events = v.public_events || v.recent_public_events || [];
  const rounds = (ps.revealed || []).map((r) => `
    <div class="mem-round">
      <span class="dim">第${r.round}轮</span>
      <span class="pcard ${r.winner === a.seat_id ? "win" : ""}">${r.cards[a.seat_id]}</span>
      <span class="dim">vs</span>
      <span class="pcard ${r.winner === b.seat_id ? "win" : ""}">${r.cards[b.seat_id]}</span>
      <span class="w">${esc(nameOf(r.winner))}</span>
    </div>`).join("");
  const seatSec = v.seats.map((s) => `
    <div class="mem-seat">
      <span class="who">${esc(s.display_name || s.seat_id)}</span>
      <span class="surf">@ ${esc(s.surface || "未就座")}</span>
      ${s.now ? `<div>"${esc(s.now)}"</div>` : ""}
      ${(s.public_anchors || []).map((x) => `<div class="mem-anchor">⚓ ${esc(x)}</div>`).join("")}
    </div>`).join("");
  const talks = events.filter((e) => e.kind === "table_line").map((e) => `
    <div class="mem-talk"><span class="tt">${esc(hhmm(e.t))}</span>
      <span class="who">${esc(e.display_name)}</span>:"${esc(e.text)}"</div>`).join("");
  const ended = ps.phase === "finished";
  app.innerHTML = `
    <div class="memcard">
      <h3>· ${esc(v.cartridge.name)} · 纪 念 卡 ·</h3>
      <div class="meta">局号 ${esc(v.session_id)} · ${esc((v.updated_at || "").replace("T", " ").slice(0, 16))}</div>
      <div class="big-score">${esc(nameOf(a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
        : ${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(b.seat_id))}</div>
      <div class="champ">${ended && ps.winner
        ? `胜者 · ${esc(nameOf(ps.winner))} 🏆` : "本局由人类提前收起"}</div>
      ${rounds ? `<div class="mem-sec"><div class="sec-t">三 轮 揭 牌</div>${rounds}</div>` : ""}
      <div class="mem-sec"><div class="sec-t">座 签</div>${seatSec}</div>
      ${talks ? `<div class="mem-sec"><div class="sec-t">桌 边 话</div>${talks}</div>` : ""}
      <div class="mem-sec meta">此卡由 SQLite 里的原局面当场派生,可随时重新打开。</div>
    </div>
    <p class="center" style="margin-top:.8rem">
      <button class="soft focusable" data-act="back">回卡带架</button></p>`;
  afterRender();
}

/* ---------------- 焦点与实体键 ---------------- */

function focusables() {
  return [...app.querySelectorAll("[data-act]")];
}

function afterRender() {
  const els = focusables();
  els.forEach((el, i) => {
    el.classList.add("focusable");
    el.addEventListener("click", () => act(el));
    if (i === Math.min(S.focusIdx, els.length - 1)) el.classList.add("focused");
  });
}

function moveFocus(delta) {
  const els = focusables();
  if (!els.length) return;
  els.forEach((el) => el.classList.remove("focused"));
  S.focusIdx = (Math.min(S.focusIdx, els.length - 1) + delta + els.length) % els.length;
  const el = els[S.focusIdx];
  el.classList.add("focused");
  el.scrollIntoView({ block: "nearest" });
}

function act(el) {
  const a = el.dataset.act;
  if (a === "insert") insertCartridge();
  else if (a === "open-save") location.hash = `#/s/${el.dataset.sid}`;
  else if (a === "copy") copyConn(el.dataset.seat, el);
  else if (a === "end") endSession();
  else if (a === "back") location.hash = "#/";
}

async function copyConn(seatId, btn) {
  const tokens = JSON.parse(sessionStorage.getItem(tokensKey(S.sid)) || "[]");
  const t = tokens.find((x) => x.seat_id === seatId);
  if (!t) return;
  const text = `你在 AI-Gameboy 牌桌上有一个席位(MCP 服务名 gameboy,入口 http://127.0.0.1:7777/mcp)。
session_id: ${S.sid}
seat_id: ${t.seat_id}
seat_token: ${t.seat_token}
请先调用 game_observe(session_id, seat_token) 看你的桌面,
然后按 legal_actions 用 game_act 行动;第一步是 introduce 自我介绍。
桌上是谁、怎么玩、说什么,都由你自己决定。`;
  await navigator.clipboard.writeText(text);
  btn.textContent = "已复制,只发一个窗口";
  setTimeout(() => { S.lastSnap = ""; }, 1800);
}

function handleKey(key) {
  if (key === "up" || key === "left") moveFocus(-1);
  else if (key === "down" || key === "right") moveFocus(1);
  else if (key === "a") {
    const el = focusables()[Math.min(S.focusIdx, focusables().length - 1)];
    if (el) act(el);
  } else if (key === "b") {
    if (S.view !== "shelf") location.hash = "#/";
  } else if (key === "start") {
    if (S.view === "seats" && startBtn.classList.contains("armed")) {
      api(`/api/sessions/${S.sid}/start`, "POST").then((r) => {
        if (r.result !== "ok") alert("开局失败:" + (r.reason || r.result));
        S.lastSnap = "";
      });
    }
  } else if (key === "select") {
    S.infoOpen = !S.infoOpen;
    S.lastSnap = "";
    if (S.view === "shelf") showShelf();
  }
}

document.querySelectorAll("[data-key]").forEach((btn) => {
  btn.addEventListener("click", () => handleKey(btn.dataset.key));
  btn.addEventListener("pointerdown", () => btn.classList.add("pressed"));
  btn.addEventListener("pointerup", () => btn.classList.remove("pressed"));
  btn.addEventListener("pointerleave", () => btn.classList.remove("pressed"));
});

window.addEventListener("keydown", (e) => {
  const map = {
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
    KeyA: "a", Enter: "a", KeyB: "b", Escape: "b", KeyS: "start", KeyQ: "select",
  };
  const byKey = {
    a: "a", b: "b", s: "start", q: "select", Enter: "a", Escape: "b",
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
  };
  const k = map[e.code] || byKey[e.key];
  if (!k) return;
  e.preventDefault();
  const phys = document.querySelector(`[data-key="${k}"]`);
  if (phys) {
    phys.classList.add("pressed");
    setTimeout(() => phys.classList.remove("pressed"), 130);
  }
  handleKey(k);
});

window.addEventListener("hashchange", route);
route();
