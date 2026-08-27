/* AI-Gameboy Stage D 主板。
   三屏不变:卡带架 / 开局席位 / 正在游戏(+ 纪念卡)。
   人类席:走与 MCP 同构的 POST observe/act,前端零改局逻辑;
   人类席令牌存 localStorage(只存自己的),身份只凭 observe 成功确认;
   卡带渲染集中在 CART_UI 一张映射表里,不散落分支。 */

const app = document.getElementById("app");
const bezelTitle = document.getElementById("bezel-title");
const powerLed = document.getElementById("power-led");
const startBtn = document.getElementById("btn-start");
const cartOverlay = document.getElementById("cart-overlay");

const S = {
  view: "shelf", sid: null, timer: null, focusIdx: 0, infoOpen: false,
  lastSnap: "",
  carts: [],            // /api/cartridges 真实清单
  currentCartridgeId: null,
  human: null,          // {token, seatId} — 仅在 observe 成功后设置
  picked: null,         // 人类本轮点选中的 item_id(未提交)
  chooseCart: null,     // 插卡后待选模式的卡带
  bc: { fact: null, stance: null, target: null },  // 盲区同行的三步选择
  pc: { intent: null },                            // 口袋穿越的意图选择
  night: { sid: null, known: [], queue: [], active: null, holdUntil: 0 },
};

const isNightShop = (id) => id === "pocket-night-shop";

const targetName = (v, oid) => {
  const o = (v.public_state.objects || []).find((x) => x.id === oid);
  return o ? o.name : oid;
};

/* 盲区同行的人话翻译层:机制词 → 一眼懂 */
const BC_STANCE_GLOSS = { 推进: "莽·直接上手", 护持: "稳·护着别出事",
                          转向: "绕·换个路子", 探明: "看·先弄清楚" };
const BC_EFFECT_GLOSS = { progress: "进度 +1", pressure: "压力 -1",
                          shield: "挡下一次坏签", memory: "被世界长久记住" };
const bcRedeemLine = (v, boost) =>
  `谁用【${boost.stance}】碰「${targetName(v, boost.target)}」→ ${BC_EFFECT_GLOSS[boost.effect] || boost.effect}`;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, method = "GET", body = undefined) => {
  const r = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
};
const aiTokensKey = (sid) => `gb-tokens-${sid}`;
const humanTokenKey = (sid) => `gb-human-token-${sid}`;
const hhmm = (t) => (t || "").slice(11, 16);
const statusText = (s) =>
  ({ lobby: "大厅", playing: "进行中", finished: "已收桌" }[s] || s);

/* ---------------- 路由 ---------------- */

function route() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; }
  S.lastSnap = ""; S.focusIdx = 0; S.human = null;
  powerLed.classList.remove("busy");
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

const nightEntryKey = (entry) => entry
  ? String(entry.seq ?? `${entry.day}|${entry.shift}|${entry.focus}|${entry.text}`)
  : "";

function updateNightPlayback(sid, ps) {
  const history = ps.recent_history || [];
  const now = Date.now();
  if (S.night.sid !== sid) {
    S.night = {
      sid, known: history.map(nightEntryKey), queue: [],
      active: history.length ? history[history.length - 1] : null,
      holdUntil: now + 5000,
    };
    return;
  }
  for (const entry of history) {
    const key = nightEntryKey(entry);
    if (!S.night.known.includes(key)) {
      S.night.known.push(key);
      S.night.queue.push(entry);
    }
  }
  if (S.night.queue.length && (!S.night.active || now >= S.night.holdUntil)) {
    S.night.active = S.night.queue.shift();
    S.night.holdUntil = now + 5000;
  }
}

/* ---------------- 卡带架(真实清单) ---------------- */

async function showShelf() {
  setScreen("shelf", "卡带架");
  S.chooseCart = null;
  const [cartsData, sessData] = await Promise.all([
    api("/api/cartridges"), api("/api/sessions"),
  ]);
  S.carts = cartsData.cartridges || [];
  const sessions = sessData.sessions || [];
  const cartsHtml = S.carts.map((c) => {
    const played = sessions.filter(
      (s) => s.cartridge_id === c.id && s.status === "finished").length;
    const human = (c.modes || []).includes("human_ai");
    const playMode = isNightShop(c.id)
      ? "AI 单机 · 人类观看"
      : `${esc(c.players.min)}–${esc(c.players.max)} 人${human ? " · 可亲自下场" : ""}`;
    return `<div class="cart focusable" data-act="insert" data-cart="${esc(c.id)}">
      <div class="cart-face">
        <div class="t">${esc(c.name)}</div>
        <div class="a">${esc(c.author)} · 自研</div>
        <div class="m">${playMode}${c.minutes ? ` · 约 ${esc(c.minutes)} 分钟` : " · 长期存档"}</div>
      </div>
      <div class="cart-plays">已玩 ${played} 局</div>
    </div>`;
  }).join("");
  const saves = sessions.map((s) => `
    <div class="save-item focusable" data-act="open-save" data-sid="${esc(s.session_id)}">
      <span class="sid">${esc(s.session_id)}</span>
      <span class="dim">${esc(cartName(s.cartridge_id))}</span>
      <span class="save-badge ${esc(s.status)}">${esc(statusText(s.status))}</span>
      <span class="when">${esc((s.updated_at || "").slice(5, 16).replace("T", " "))}</span>
    </div>`).join("");
  app.innerHTML = `
    <h2>· 卡 带 架 ·</h2>
    ${infoPanel()}
    <div class="shelf-row">${cartsHtml}</div>
    <p class="dim center">对准卡带按 A 插入 · SELECT 看卡带说明</p>
    <div class="saves"><p class="dim">存档</p>
      ${saves || '<p class="dim center">还没有存档</p>'}</div>`;
  afterRender();
}

const cartName = (id) => {
  const c = S.carts.find((x) => x.id === id);
  return c ? c.name : id;
};

function infoPanel() {
  if (!S.infoOpen || !S.carts.length) return "";
  const rows = S.carts.map((c) => `
    <dt>${esc(c.name)} · v${esc(c.version)}</dt>
    <dd>${esc(c.author)} · ${esc(c.license)} · ${esc((c.modes || []).join(" / "))}</dd>`).join("");
  return `<div class="info-panel"><dl>${rows}
    <dt>牌桌纪律</dt><dd>私牌只进本席响应;桌边话不参与计分;断线凭原令牌原地恢复。</dd>
  </dl></div>`;
}

/* ---- 插卡:支持人类席的卡带先选模式 ---- */

function askMode(cartId) {
  setScreen("shelf", "选择模式");
  S.chooseCart = cartId;
  if (isNightShop(cartId)) {
    app.innerHTML = `
      <h2>· ${esc(cartName(cartId))} ·</h2>
      <p class="center dim">一位 AI 店主自主经营 · 你在显示器外观看</p>
      <div class="mode-choices">
        <button class="soft focusable" data-act="create" data-mode="human_ai">开一间夜铺</button>
      </div>
      <p class="center dim">经营不会等待观看者;门外一响时,你偶尔能叩一下。</p>`;
    afterRender();
    return;
  }
  app.innerHTML = `
    <h2>· ${esc(cartName(cartId))} ·</h2>
    <p class="center dim">这张卡带支持真人下场。谁来玩?</p>
    <div class="mode-choices">
      <button class="soft focusable" data-act="create" data-mode="human_ai">我 × AI(我坐 B 席)</button>
      <button class="soft focusable" data-act="create" data-mode="ai_ai">AI × AI(我旁观)</button>
    </div>
    <p class="center dim">按 B 放回卡带</p>`;
  afterRender();
}

async function insertCartridge(cartId, mode) {
  cartOverlay.querySelector(".cart-label").textContent = cartName(cartId);
  cartOverlay.hidden = false;
  cartOverlay.querySelector(".cart-kacha").hidden = false;
  await new Promise((r) => setTimeout(r, 750));
  cartOverlay.hidden = true;
  const r = await api("/api/sessions", "POST", { cartridge_id: cartId, mode });
  if (r.result !== "ok") { alert("插卡失败:" + (r.reason || r.result)); return; }
  const aiSeats = r.seats.filter((s) => s.participant_type === "ai_window");
  sessionStorage.setItem(aiTokensKey(r.session_id), JSON.stringify(aiSeats));
  const humanSeat = r.seats.find((s) => s.participant_type === "human");
  if (humanSeat) {
    localStorage.setItem(humanTokenKey(r.session_id), humanSeat.seat_token);
    if (isNightShop(cartId)) {
      const o = await api(`/api/sessions/${r.session_id}/observe`, "POST",
                          { seat_token: humanSeat.seat_token });
      if (o.result === "ok" && (o.legal_actions || []).some(
          (x) => x.action_id === "introduce")) {
        await api(`/api/sessions/${r.session_id}/act`, "POST", {
          seat_token: humanSeat.seat_token,
          expected_revision: o.revision,
          action_id: "introduce",
          params: { display_name: "观看者", surface: "掌机显示器" },
        });
      }
    }
  }
  location.hash = `#/s/${r.session_id}`;
}

/* ---------------- 牌局(席位 / 游戏) ---------------- */

async function showSession(sid) {
  if (S.sid !== sid) {
    S.picked = null;
    S.bc = { fact: null, stance: null, target: null };
    S.pc = { intent: null };
    S.night = { sid: null, known: [], queue: [], active: null, holdUntil: 0 };
  }
  S.sid = sid;
  // 人类身份只凭统一 observe 成功确认,不靠 localStorage 猜(校正 #1)
  const stored = localStorage.getItem(humanTokenKey(sid));
  let tokenLost = false;
  if (stored) {
    const o = await api(`/api/sessions/${sid}/observe`, "POST",
                        { seat_token: stored });
    if (o.result === "ok") S.human = { token: stored, seatId: o.you.seat_id };
    else tokenLost = true;
  }
  const draw = async () => {
    const v = await api(`/api/sessions/${sid}`);
    if (v.result !== "ok") {
      setScreen("seats", "开局席位");
      app.innerHTML = `<p class="center">读不到这局(${esc(v.result)})。按 B 回卡带架。</p>`;
      return;
    }
    S.currentCartridgeId = v.cartridge.id;
    if (v.status === "finished") { location.replace(`#/m/${sid}`); return; }
    let mine = null;
    if (S.human) {
      const o = await api(`/api/sessions/${sid}/observe`, "POST",
                          { seat_token: S.human.token });
      if (o.result === "ok") mine = o;
    }
    const draft = captureDraft();
    if (isNightShop(v.cartridge.id) && v.status === "playing")
      updateNightPlayback(sid, v.public_state);
    const snap = JSON.stringify([v, mine && mine.revision, mine && mine.public_state,
                                 mine && mine.private_state, S.infoOpen, S.picked,
                                 tokenLost, S.night.active && nightEntryKey(S.night.active, 0),
                                 S.night.queue.length]);
    if (snap === S.lastSnap) return;
    S.lastSnap = snap;
    if (v.status === "lobby") renderSeats(v, mine, tokenLost);
    else renderGame(v, mine, tokenLost);
    restoreDraft(draft);
  };
  await draw();
  S.timer = setInterval(draw, 3000); // 人类自己的视图刷新,不触碰任何 AI 窗口
}

const DRAFT_IDS = ["tl-input", "intro-name", "intro-now", "usage-input",
                   "combo-select", "bc-line", "pc-action", "pc-item", "pc-line"];

function captureDraft() {
  const d = {};
  for (const id of DRAFT_IDS) {
    const el = document.getElementById(id);
    if (el) d[id] = el.value;
  }
  d.needs = [...document.querySelectorAll(".need-box:checked")].map((x) => x.value);
  d.bcEndorse = !!document.getElementById("bc-endorse")?.checked;
  return d;
}
function restoreDraft(d) {
  if (!d) return;
  for (const id of DRAFT_IDS) {
    const el = document.getElementById(id);
    if (el && d[id] != null && d[id] !== "") el.value = d[id];
  }
  for (const box of document.querySelectorAll(".need-box"))
    if ((d.needs || []).includes(box.value)) box.checked = true;
  const be = document.getElementById("bc-endorse");
  if (be && d.bcEndorse) be.checked = true;
}

/* ---- 开局席位 ---- */

function renderSeats(v, mine, tokenLost) {
  if (isNightShop(v.cartridge.id)) {
    renderNightShopSeats(v, tokenLost);
    return;
  }
  setScreen("seats", "开局席位");
  powerLed.classList.add("busy");
  const aiTokens = JSON.parse(sessionStorage.getItem(aiTokensKey(v.session_id)) || "null");
  const slots = v.seats.map((s) => {
    const turn = (v.waiting_for || []).includes(s.seat_id);
    const isMe = S.human && S.human.seatId === s.seat_id;
    const tok = aiTokens && aiTokens.find((t) => t.seat_id === s.seat_id);
    let body;
    if (s.seated) {
      body = `<div class="who">${esc(s.display_name)}${isMe ? "(你)" : ""}</div>
        <div class="surf">${esc(s.surface)}</div>
        ${s.now ? `<div class="now-line">"${esc(s.now)}"</div>` : ""}
        ${(s.public_anchors || []).map((a) => `<div class="anchor">⚓ ${esc(a)}</div>`).join("")}`;
    } else if (isMe) {
      body = `<div class="dim center">这是你的席位,报个名入座:</div>
        <div class="intro-form">
          <input id="intro-name" maxlength="40" value="项目作者" aria-label="称呼">
          <input id="intro-now" maxlength="120" placeholder="此刻一句话(可空)" aria-label="此刻">
          <button class="soft focusable" data-act="hu-intro">入座</button>
        </div>`;
    } else {
      body = `<div class="empty-hint">等待照面</div>
        <div class="conn-box center">${tok
          ? `<button class="soft focusable" data-act="copy" data-seat="${esc(s.seat_id)}">复制 ${esc(s.seat_id)} 连接信息</button>
             <div class="conn-note">整段只交给一个真实窗口</div>`
          : `<div class="conn-note">令牌只在建局的标签页显示一次</div>`}</div>`;
    }
    return `<div class="slot ${s.seated ? "seated" : ""} ${turn ? "turn" : ""}">
      <span class="lamp"></span>
      <div class="dim">${esc(s.seat_id)}${s.participant_type === "human" ? " · 人类席" : ""}</div>
      ${body}</div>`;
  }).join("");
  const ready = v.public_state && v.public_state.waiting_human_start;
  if (ready) startBtn.classList.add("armed");
  app.innerHTML = `
    <h2>· 开 局 席 位 · ${esc(v.cartridge.name)}</h2>
    ${tokenLost ? '<p class="center warn-note">人类席令牌无效或已丢失,本局只能旁观。</p>' : ""}
    ${infoPanel()}
    <div class="slots">${slots}</div>
    <div class="start-hint ${ready ? "ready" : ""}">${ready
      ? "两席已就座 —— 按 START 开局"
      : "等待所有席位完成自我介绍"}</div>
    <p class="center"><button class="soft warn focusable" data-act="end">收起这局</button></p>
    <p class="dim center">局号 ${esc(v.session_id)}</p>`;
  afterRender();
}

function renderNightShopSeats(v, tokenLost) {
  setScreen("seats", "夜铺准备");
  powerLed.classList.add("busy");
  const aiTokens = JSON.parse(sessionStorage.getItem(aiTokensKey(v.session_id)) || "null");
  const shopkeeper = v.seats.find((s) => s.seat_id === "seat_a") || v.seats[0];
  const tok = aiTokens && aiTokens.find((t) => t.seat_id === shopkeeper.seat_id);
  const ready = v.public_state && v.public_state.waiting_human_start;
  if (ready) startBtn.classList.add("armed");
  const keeperBody = shopkeeper.seated
    ? `<div class="who">${esc(shopkeeper.display_name)}</div>
       <div class="surf">${esc(shopkeeper.surface)}</div>
       ${shopkeeper.now ? `<div class="now-line">“${esc(shopkeeper.now)}”</div>` : ""}`
    : `<div class="empty-hint">等待 AI 店主接入夜铺</div>
       <div class="conn-box center">${tok
         ? `<button class="soft focusable" data-act="copy" data-seat="${esc(shopkeeper.seat_id)}">复制店主连接信息</button>
            <div class="conn-note">把整段交给一个 AI;它会自己连续经营并保存。</div>`
         : '<div class="conn-note">店主令牌只在建店的标签页显示一次</div>'}</div>`;
  app.innerHTML = `
    <h2>· 开 店 准 备 · ${esc(v.cartridge.name)}</h2>
    ${tokenLost ? '<p class="center warn-note">观看端令牌无效或已丢失,当前只能看公共橱窗。</p>' : ""}
    <div class="night-lobby">
      <div class="slot night-keeper ${shopkeeper.seated ? "seated" : "turn"}">
        <span class="lamp"></span>
        <div class="dim">AI 店主</div>${keeperBody}
      </div>
      <div class="night-observer-note">◉ 观看端已连接<br>
        <span class="dim">你不占玩家席位。门外一响时,显示器会给你一次盲点。</span></div>
    </div>
    <div class="start-hint ${ready ? "ready" : ""}">${ready
      ? "店主已经进门 —— 按 START 开灯营业"
      : "等待 AI 店主完成自我介绍"}</div>
    <p class="center"><button class="soft warn focusable" data-act="end">收起这间夜铺</button></p>
    <p class="dim center">存档 ${esc(v.session_id)}</p>`;
  afterRender();
}

/* ---- 正在游戏:公共骨架 + 每卡带一个台面渲染器(校正 #3) ---- */

function renderGame(v, mine, tokenLost) {
  setScreen("game", "正在游戏");
  powerLed.classList.add("busy");
  const ui = CART_UI[v.cartridge.id] || CART_UI._fallback;
  const talk = (v.public_events || v.recent_public_events || [])
    .map(eventLine).filter(Boolean).join("");
  const solo = ui.layout === "solo";
  app.innerHTML = `
    ${tokenLost ? '<p class="center warn-note">人类席令牌无效或已丢失,本局只能旁观。</p>' : ""}
    ${infoPanel()}
    <div class="table-top ${solo ? "solo-table" : ""}">
      ${solo ? "" : sideSeat(v, v.seats[0])}
      <div class="felt">${ui.felt(v, mine)}</div>
      ${solo ? "" : sideSeat(v, v.seats[1])}
    </div>
    ${mine ? ui.myPanel(v, mine) : ""}
    ${solo ? "" : `<div class="table-talk">${talk}</div>`}
    <p class="center"><button class="soft warn focusable" data-act="end">结束本局</button></p>
    <p class="dim center">局号 ${esc(v.session_id)}</p>`;
  afterRender();
}

function sideSeat(v, s) {
  const turn = (v.waiting_for || []).includes(s.seat_id);
  const sub = v.public_state.submitted && v.public_state.submitted[s.seat_id];
  const isMe = S.human && S.human.seatId === s.seat_id;
  return `<div class="side-seat ${turn ? "turn" : ""}">
    <div class="lamp"></div>
    <div class="who">${esc(s.display_name)}${isMe ? " (你)" : ""}</div>
    <div class="surf">${esc(s.surface)}</div>
    <div class="stat">${sub ? "已暗投 ▮" : turn ? "考虑中…" : ""}</div>
  </div>`;
}

const nameOf = (v, seatId) => {
  const s = v.seats.find((x) => x.seat_id === seatId);
  return (s && s.display_name) || seatId;
};

function eventLine(e) {
  if (e.kind === "table_line")
    return `<div class="talk-line"><span class="tt">${esc(hhmm(e.t))}</span>
      <span class="who">${esc(e.display_name)}</span>
      <span class="txt">${esc(e.text)}</span></div>`;
  if (e.kind === "introduce")
    return `<div class="sys-line">· ${esc(e.display_name)}(${esc(e.surface)})入座 ·</div>`;
  if (e.kind === "start") return `<div class="sys-line">· 牌局开始 ·</div>`;
  if (e.kind === "finish") return `<div class="sys-line">· 结算 ·</div>`;
  if (e.kind === "human_end") return `<div class="sys-line">· 人类收起了这局 ·</div>`;
  return "";
}

/* ---------------- CART_UI:唯一的卡带渲染映射 ---------------- */

const CART_UI = {
  "pocket-night-shop": {
    layout: "solo",
    felt(v) {
      const ps = v.public_state;
      const keeper = v.seats.find((s) => s.seat_id === "seat_a") || v.seats[0];
      const inventory = (ps.inventory || []).map((item) => `
        <div class="item-card night-item ${item.displayed ? "displayed" : ""}">
          <div class="it-name">${item.displayed ? "◇ " : ""}${esc(item.name)}</div>
          <div class="it-tags">
            <span class="chip">${esc(item.kind)}</span>
            <span class="chip">修复 ${item.condition}/3</span>
            <span class="chip">估值 ${item.value}</span>
          </div>
          <div class="dim">${esc(item.story)}</div>
          ${item.secret ? `<div class="night-secret">✦ ${esc(item.secret)}</div>` : ""}
        </div>`).join("");
      const active = S.night.active || (ps.recent_history || []).slice(-1)[0];
      const newest = (ps.recent_history || []).slice(-1)[0];
      const replaying = active && newest && nightEntryKey(active) !== nightEntryKey(newest);
      const delta = active ? `
        <div class="night-deltas">
          <span class="chip">硬币 ${active.coins_delta >= 0 ? "+" : ""}${active.coins_delta}</span>
          <span class="chip">声望 ${active.reputation_delta >= 0 ? "+" : ""}${active.reputation_delta}</span>
        </div>` : "";
      const logs = (ps.recent_history || []).slice(-5).reverse().map((entry) => `
        <div class="night-log ${active && nightEntryKey(entry) === nightEntryKey(active) ? "active" : ""}">
          <span>第${entry.day}日·${esc(entry.shift)}</span><span>${esc(entry.text)}</span>
        </div>`).join("");
      const doors = (ps.door_history || []).slice(-2).map((entry) => `
        <div>🚪 ${esc(entry.text)}</div>`).join("");
      const customer = ps.customer ? `
        <div class="night-customer">
          <div class="night-customer-name">今夜来客 · ${esc(ps.customer.name)}
            <span class="chip">第${ps.customer.visits}次来店</span></div>
          <div>${esc(ps.customer.request)}</div>
          <div class="dim">可观察到:${esc(ps.customer.clue)}</div>
          <div class="dim">耐心:${"●".repeat(ps.customer.patience)}${"○".repeat(2 - ps.customer.patience)}</div>
        </div>` : "";
      const relations = (ps.customer_book || []).map((row) => `
        <div class="night-log"><span>${esc(row.name)}</span>
          <span>来过${row.visits}次 · 成交${row.deals}次 · 信任${row.trust}</span></div>`).join("");
      const week = (ps.weekly || []).slice(-1)[0];
      return `
        <div class="night-owner">${esc(keeper.display_name || "AI 店主")} 的夜铺</div>
        <div class="night-dashboard">
          <div class="night-day">第 ${ps.day} 日 · ${esc(ps.shift)}</div>
          <div>硬币 <strong>${ps.coins}</strong> · 声望 <strong>${ps.reputation}</strong> ·
            店铺 ${ps.shop_level}级 · 库存 ${(ps.inventory || []).length}/${ps.capacity}</div>
        </div>
        ${week ? `<div class="night-week">第 ${week.week} 周账 · 经过第${week.through_day}日 ·
          成交${week.deals}次 · 硬币${week.coins} · 声望${week.reputation}</div>` : ""}
        <div class="night-goal">店主眼下想做:${esc(ps.current_goal)}</div>
        ${customer}
        ${active ? `<div class="night-spotlight">
          <div class="night-replay-label">${replaying ? "显示器正在回放" : "本班刚刚发生"} ·
            第${active.day}日 ${esc(active.shift)}
            ${S.night.queue.length ? ` · 后面还有 ${S.night.queue.length} 段` : ""}</div>
          <div class="night-action">${esc(active.text)}</div>
          <div class="night-ambient">${esc(active.ambient)}</div>${delta}
          ${active.reaction ? `<div class="night-reaction">
            ${active.reaction.mood ? `心情灯 · ${esc(active.reaction.mood)} ` : ""}
            ${active.reaction.text ? `“${esc(active.reaction.text)}”` : ""}</div>` : ""}
        </div>` : '<div class="night-spotlight dim">店主刚刚点亮招牌。</div>'}
        <div class="night-section-title">橱窗与货架</div>
        <div class="night-inventory">${inventory || '<div class="empty-hint">货架空了</div>'}</div>
        ${logs ? `<details class="night-history"><summary>最近五班经营记录</summary>${logs}</details>` : ""}
        ${relations ? `<details class="night-history"><summary>顾客簿</summary>${relations}</details>` : ""}
        ${doors ? `<div class="report night-door-result">${doors}</div>` : ""}
        ${ps.door_waiting ? '<div class="start-hint ready">门外似乎有什么动静……</div>' : ""}`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing" || !mine) return "";
      const knock = (mine.legal_actions || []).find((x) => x.action_id === "knock");
      if (knock) return `<div class="my-panel">
        <div class="dim center">你不知道门外是什么。夜铺不会等你，也不会因此停下。</div>
        <button class="soft focusable" data-act="night-knock">门外一响 · 叩一下</button>
      </div>`;
      return `<div class="my-panel"><div class="dim center">
        今晚由店主自己经营。偶尔门外会响一下。</div></div>`;
    },
    memorial(v) {
      const ps = v.public_state;
      const diary = (ps.diary || []).map((entry) => `
        <div class="mem-round"><span class="dim">第${entry.day}日</span>
          <span>${esc(entry.text)}</span></div>`).join("");
      return {
        rounds: diary,
        champ: `夜铺停在第 ${ps.day} 日 · 硬币 ${ps.coins} · 声望 ${ps.reputation}`,
        scoreLine: `店铺 ${ps.shop_level}级 · 库存 ${(ps.inventory || []).length}/${ps.capacity}`,
      };
    },
  },
  "pocket-circuit": {
    felt(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const rows = (ps.revealed || []).map((r) => `
        <div class="mem-round">
          <span class="dim">节点 ${r.node} · 电荷 ${r.stake}</span>
          <span class="pcard ${r.winner === a.seat_id ? "win" : ""}">${r.cards[a.seat_id]}</span>
          <span class="dim">vs</span>
          <span class="pcard ${r.winner === b.seat_id ? "win" : ""}">${r.cards[b.seat_id]}</span>
          <span class="w">${r.winner
            ? `${esc(nameOf(v, r.winner))} 接走 ${r.points}`
            : "平局 · 电荷滚存"}</span>
        </div>`).join("");
      return `
        <div class="score">${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
          <span class="colon">:</span>${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}</div>
        <div class="round-line">第 ${ps.round} / ${ps.total_rounds} 轮 ·
          当前节点 ${ps.current_node} · 可争电荷 ${ps.stake}</div>
        <div class="rounds-mini">${rows}</div>`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing" || !mine) return "";
      const pending = mine.private_state.my_pending;
      if (pending !== null && pending !== undefined) {
        return `<div class="my-panel"><div class="dim center">
          你已锁定电压 <strong>${pending}</strong>。牌面不会交给 AI，提醒它落子即可。</div></div>`;
      }
      const la = mine.legal_actions && mine.legal_actions[0];
      if (!la) return `<div class="my-panel"><div class="dim center">等待对面落子……</div></div>`;
      const cards = (mine.private_state.hand || []).map((card) => `
        <button class="pcard focusable" data-act="circuit-card" data-card="${card}">${card}</button>`).join("");
      return `<div class="my-panel">
        <div class="dim center">你先锁牌 · 对面只能看见“已提交”，不能看见数字</div>
        <div class="hand-row">${cards}</div>
        <input id="circuit-line" maxlength="60" placeholder="桌边话(可空，不要写自己的牌)">
      </div>`;
    },
    memorial(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const rounds = (ps.revealed || []).map((r) => `
        <div class="mem-round">
          <span class="dim">节点 ${r.node} · 电荷 ${r.stake}</span>
          <span class="pcard ${r.winner === a.seat_id ? "win" : ""}">${r.cards[a.seat_id]}</span>
          <span class="dim">vs</span>
          <span class="pcard ${r.winner === b.seat_id ? "win" : ""}">${r.cards[b.seat_id]}</span>
          <span class="w">${r.winner ? esc(nameOf(v, r.winner)) : "平局滚存"}</span>
        </div>`).join("");
      const champ = ps.phase === "finished" && ps.winner
        ? `胜者 · ${esc(nameOf(v, ps.winner))} 🏆`
        : ps.phase === "finished" ? "平局 · 电路未分胜负" : "本局由人类提前收起";
      return { rounds, champ,
               scoreLine: `${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
                 : ${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}` };
    },
  },

  "four-things-in-my-pocket": {
    felt(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const sit = ps.situation;
      const props = ((sit && sit.props) || []).map((p) =>
        `<span class="chip prop">◇ ${esc(p.name)}</span>`).join("");
      const sitHtml = sit ? `
        <div class="situation">
          <div class="sit-name">${esc(sit.name)}</div>
          <div class="sit-text">${esc(sit.text)}</div>
          <div class="sit-tags">
            ${sit.needs.map((n) => `<span class="chip need">${esc(n)}</span>`).join("")}
            <span class="chip risk">⚠ ${esc(sit.risk)}</span>${props}
          </div>
        </div>` : "";
      const field = ps.field || [];
      const fieldHtml = field.length ? `
        <div class="field-row"><span class="dim">桌面:</span>
          ${field.map((f) => `<span class="chip fielditem ${f.spent ? "spent" : ""}"
             title="${esc((f.tags || []).join("、"))}">${esc(f.name)}${f.spent ? "·耗尽" : ""}</span>`).join("")}
        </div>` : "";
      const judging = ps.step === "judge" && ps.pending_reveal ? `
        <div class="report">
          ${Object.entries(ps.pending_reveal.choices).map(([sid, c]) =>
            `<div><strong>${esc(nameOf(v, sid))}</strong> 掏出「${esc(c.name)}」:${esc(c.usage)}</div>`).join("")}
          <div class="dim center">· 有非常规组合,等待对面裁决 ·</div>
        </div>` : "";
      const lastReport = ps.revealed && ps.revealed.length ? `
        <div class="report">${ps.revealed[ps.revealed.length - 1].report
          .map((l) => `<div>${esc(l)}</div>`).join("")}</div>` : "";
      return `
        <div class="score">${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
          <span class="colon">:</span>${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}</div>
        <div class="round-line">第 ${ps.round} / ${ps.total_rounds} 轮 ·
          共同星 ${"★".repeat(ps.stars || 0) || "—"} ·
          背书章 ${ps.chips?.[a.seat_id] ?? "-"} / ${ps.chips?.[b.seat_id] ?? "-"}</div>
        ${sitHtml}${fieldHtml}${judging}${lastReport}`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing" || !mine) return "";
      const la = mine.legal_actions && mine.legal_actions[0];
      const pending = mine.private_state.my_pending;
      if (!la) {
        if (pending) {
          const p = (mine.private_state.hand || []).find(
            (c) => c.item_id === pending.item_id);
          return `<div class="my-panel"><div class="dim center">
            你已暗投「${esc(p ? p.name : pending.item_id)}」—— 等对面 / 等裁决</div></div>`;
        }
        return "";
      }
      if (la.action_id === "draw_pick") {
        const cards = (mine.private_state.draw_offers || []).map((c) => `
          <div class="item-card focusable" data-act="pick-draw" data-item="${esc(c.item_id)}">
            <div class="it-name">${esc(c.name)}</div>
            <div class="it-tags">${c.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
          </div>`).join("");
        return `<div class="my-panel">
          <div class="dim center">中场补牌:二选一(只有你看得见)</div>
          <div class="hand-row">${cards}</div></div>`;
      }
      if (la.action_id === "judge") {
        const pr = ((v.public_state.pending_reveal || {}).proposals || [])
          .find((p) => p.judge === S.human.seatId && !p.verdict);
        const needs = (v.public_state.situation || {}).needs || [];
        return `<div class="my-panel">
          <div class="dim center">对面的非常规解,由你裁决(你的章还剩 ${mine.private_state.chips_left}):</div>
          <div class="report">"${esc(pr ? pr.usage : "")}"</div>
          <div class="confirm-bar">
            <span class="dim">它真能覆盖哪个需求?</span>
            ${needs.map((n) => `<label class="chip need"><input type="checkbox"
               class="need-box" value="${esc(n)}"> ${esc(n)}</label>`).join("")}
            <button class="soft focusable" data-act="hu-endorse">背书(花 1 章)</button>
            <button class="soft warn focusable" data-act="hu-doubt">存疑</button>
          </div></div>`;
      }
      const hand = mine.private_state.hand || [];
      const cards = hand.map((c) => `
        <div class="item-card focusable ${S.picked === c.item_id ? "picked" : ""}"
             data-act="pick" data-item="${esc(c.item_id)}">
          <div class="it-name">${esc(c.name)}</div>
          <div class="it-tags">${c.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
        </div>`).join("");
      const sel = hand.find((c) => c.item_id === S.picked);
      const fieldOpts = ((v.public_state.field || []).filter((f) => !f.spent))
        .map((f) => `<option value="field:${esc(f.field_id)}">与桌面的「${esc(f.name)}」组合</option>`)
        .join("");
      return `<div class="my-panel">
        <div class="dim center">你的口袋(只有你看得见)——选一件、说用法、暗投:</div>
        <div class="hand-row">${cards}</div>
        ${sel ? `<div class="confirm-bar">
            <strong>${esc(sel.name)}</strong>
            <input id="usage-input" maxlength="80" placeholder="必填:一句具体用法(参与判定!)">
            <select id="combo-select">
              <option value="">不组合,单打</option>
              <option value="partner">赌对面这轮的牌能配上</option>
              ${fieldOpts}
            </select>
            <input id="tl-input" maxlength="120" placeholder="桌边话(可空)">
            <button class="soft focusable" data-act="hu-submit">确认暗投</button>
          </div>` : ""}
      </div>`;
    },
    memorial(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const rounds = (ps.revealed || []).map((r) => `
        <div class="mem-four">
          ${(r.report || [`第${r.round}轮 · ${r.situation.name}`])
            .map((l, i) => `<div class="${i === 0 ? "dim" : "mem-line"}">${esc(l)}</div>`)
            .join("")}
        </div>`).join("");
      const champ = ps.phase === "finished"
        ? `个人分 ${ps.scores?.[a.seat_id] ?? 0} : ${ps.scores?.[b.seat_id] ?? 0} · 共同星 ${"★".repeat(ps.stars || 0) || "无"}`
        : "本局由人类提前收起";
      return { rounds, champ,
               scoreLine: `${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
                 : ${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}` };
    },
  },

  "blind-companions": {
    felt(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const bar = (val, max, cls) => `
        <div class="bar-track"><div class="bar-fill ${cls}"
          style="width:${(val / max) * 100}%"></div></div>`;
      const omens = `
        <div class="dim center">🎋 抽签(每拍抽一支):已抽 ${(ps.omens_flipped || [])
          .map((o) => `<span class="chip risk">${esc(o)}</span>`).join("") || "无"}
          · 签筒里还剩 ${3 - (ps.omens_flipped || []).length} 支
          <span class="dim">(整筒是:顺势=好签 / 代价=坏签 / 回声=留念签)</span>
          ${ps.omen_peek ? `<span class="chip prop">👁 偷看到下一支:${esc(ps.omen_peek)}</span>` : ""}
        </div>`;
      const pinned = (ps.pinned || []).map((p) => `
        <div class="mem-line">📌 ${p.owner ? esc(nameOf(v, p.owner)) : "世界"}:
          ${esc(p.text)}<span class="dim">(兑现条件:${esc(bcRedeemLine(v, p.boost))})</span></div>`).join("");
      const lastLog = ps.beats_log && ps.beats_log.length ? `
        <div class="report">${ps.beats_log[ps.beats_log.length - 1].report
          .map((l) => `<div>${esc(l)}</div>`).join("")}</div>` : "";
      const endingHtml = ps.ending ? `
        <div class="situation"><div class="sit-name">${esc(ps.ending_text || "")}</div>
          ${ps.memory ? `<div class="sit-text">🕯 ${esc(ps.memory.text)}</div>` : ""}
        </div>` : "";
      return `
        <div class="sit-name center">${esc(ps.scene.name)} · 第 ${ps.beat}/${ps.total_beats} 拍</div>
        ${ps.beat === 1 && !(ps.beats_log || []).length
          ? `<div class="sit-text center">${esc(ps.scene.intro)}</div>` : ""}
        <div class="sit-text center">🎯 ${esc(ps.scene.goal)}</div>
        <div class="dim">进度 ${ps.progress}/5</div>${bar(ps.progress, 5, "ok")}
        <div class="dim">压力 ${ps.pressure}/4</div>${bar(ps.pressure, 4, "bad")}
        ${omens}
        <div class="dim center">${esc(nameOf(v, a.seat_id))} 持${esc(ps.packet_holders?.[a.seat_id] || "")}
          · ${esc(nameOf(v, b.seat_id))} 持${esc(ps.packet_holders?.[b.seat_id] || "")}</div>
        ${pinned ? `<div class="report">${pinned}</div>` : ""}
        ${lastLog}${endingHtml}`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing" || !mine) return "";
      const pending = mine.private_state.my_pending;
      if (pending) {
        return `<div class="my-panel"><div class="dim center">
          你已暗投【${esc(pending.stance)}】→「${esc(targetName(v, pending.target_id))}」
          ${pending.endorse ? "(已背书)" : ""} —— 等对面</div></div>`;
      }
      if (!mine.legal_actions.length) return "";
      const ps = v.public_state;
      const facts = mine.private_state.facts.map((f) => `
        <div class="item-card focusable ${S.bc.fact === f.id ? "picked" : ""}"
             data-act="bc-fact" data-id="${esc(f.id)}">
          <div class="it-tags">${esc(f.text)}</div>
          <div class="redeem">🎫 ${esc(bcRedeemLine(v, f.boost))}</div>
        </div>`).join("");
      const stances = (ps.stances_left[S.human.seatId] || []).map((st) => `
        <button class="soft focusable ${S.bc.stance === st ? "picked-btn" : ""}"
          data-act="bc-stance" data-id="${esc(st)}"
          title="${esc(BC_STANCE_GLOSS[st] || "")}">${esc(st)}<br>
          <span style="font-size:.68rem">${esc(BC_STANCE_GLOSS[st] || "")}</span></button>`).join(" ");
      const targets = (ps.objects || []).map((o) => `
        <button class="soft minor focusable ${S.bc.target === o.id ? "picked-btn" : ""}"
          data-act="bc-target" data-id="${esc(o.id)}">${esc(o.name)}</button>`).join(" ");
      const canEndorse = (ps.endorse_left[S.human.seatId] || 0) > 0;
      const ready = S.bc.fact && S.bc.stance && S.bc.target;
      return `<div class="my-panel">
        <div class="dim center">你的${esc(mine.private_state.packet)}(只有你看得见)。
          三步:亮一张情报券 → 选干活风格 → 点下手对象。
          券亮出来才能兑现;兑现条件印在券面上,谁踩中都算</div>
        <div class="hand-row">${facts}</div>
        <div class="center" style="margin-top:.5rem">${stances}</div>
        <div class="center" style="margin-top:.4rem">${targets}</div>
        <div class="confirm-bar">
          <input id="bc-line" maxlength="40" placeholder="一句公开台词(≤40字,可空)">
          ${canEndorse ? `<label class="chip need">
            <input type="checkbox" id="bc-endorse"> 背书本拍(仅1次)</label>` : ""}
          <button class="soft focusable" data-act="bc-submit"
            ${ready ? "" : "disabled"}>确认暗投</button>
        </div></div>`;
    },
    memorial(v) {
      const ps = v.public_state;
      const rounds = (ps.beats_log || []).map((bt) => `
        <div class="mem-four">${bt.report
          .map((l, i) => `<div class="${i === 0 ? "dim" : "mem-line"}">${esc(l)}</div>`)
          .join("")}</div>`).join("");
      const champ = ps.ending_text ? esc(ps.ending_text) : "本幕由人类提前收起";
      const memory = ps.memory ? `
        <div class="mem-sec"><div class="sec-t">世 界 记 忆</div>
          <div class="mem-line">🕯 ${esc(ps.memory.text)}</div></div>` : "";
      return { rounds: rounds + memory, champ,
               scoreLine: `进度 ${ps.progress}/5 · 压力 ${ps.pressure}/4` };
    },
  },

  "pocket-crossing": {
    felt(v) {
      const ps = v.public_state;
      const t = ps.tracks || {};
      const [a, b] = v.seats;
      const NARR_NAMES = { gen_world: "正在织一个新世界", gen_identities: "正在写身份卡",
                           gen_scene: "正在写下一幕", render_ending: "正在写结局" };
      const axesChips = ps.axes ? Object.values(ps.axes)
        .map((x) => `<span class="chip prop">${esc(x)}</span>`).join("") : "";
      const narr = ps.narration_pending ? `
        <div class="situation">
          <div class="sit-name">🖋 荷官执笔中 · ${esc(NARR_NAMES[ps.narration_pending] || ps.narration_pending)}</div>
          <div class="sit-tags">${axesChips}</div>
          <div class="center" style="margin-top:.4rem">
            <button class="soft focusable" data-act="pc-narrate">召荷官(可能要等半分钟)</button>
          </div></div>` : "";
      if (!ps.world) {
        return `<div class="sit-name center">世界正在成形…</div>
          <div class="dim center">种子:</div>
          <div class="center">${axesChips}</div>${narr}`;
      }
      const bar = (val, max, cls) => `
        <div class="bar-track"><div class="bar-fill ${cls}"
          style="width:${(val / max) * 100}%"></div></div>`;
      const hearts = (n) => "❤".repeat(n) + "🖤".repeat(Math.max(0, 3 - n));
      const idents = ps.identities || {};
      const identLine = (sid) => idents[sid]
        ? `${esc(nameOf(v, sid))}=${esc(idents[sid].name)}(擅${esc(idents[sid].specialty)})`
        : `${esc(nameOf(v, sid))} 暗选身份中…`;
      const sc = ps.scene;
      const sceneHtml = sc ? `
        <div class="situation">
          <div class="sit-name">第 ${ps.scene_index} 幕 · ${esc(sc.title)}</div>
          <div class="sit-text">${esc(sc.text)}</div>
          <div class="sit-text">⚡ ${esc(sc.crisis)}</div>
          <div class="sit-tags">${(sc.objects || []).map((o) =>
            `<span class="chip" title="${esc(o.hint)}">${esc(o.name)}</span>`).join("")}</div>
        </div>` : `<div class="sit-text center">${esc(ps.world.premise)}</div>`;
      const hooks = (ps.hooks || []).length
        ? `<div class="dim center">悬事:${ps.hooks.map(esc).join(" · ")}</div>` : "";
      const lastLog = ps.history && ps.history.length ? `
        <div class="report">${ps.history[ps.history.length - 1].report
          .map((l) => `<div>${esc(l)}</div>`).join("")}</div>` : "";
      const endProposed = ps.end_proposed_by
        ? `<div class="warn-note center">${esc(nameOf(v, ps.end_proposed_by))} 提议停笔</div>` : "";
      const endingHtml = ps.ending ? `
        <div class="situation"><div class="sit-name">【${esc(ps.ending.kind)}】${esc(ps.ending.reason_name || "")}</div>
          <div class="sit-text">${ps.ending.text ? esc(ps.ending.text) : "(结局成文中……)"}</div></div>` : "";
      return `
        ${narr}
        <div class="sit-name center">《${esc(ps.world.world_name)}》</div>
        <div class="sit-text center">🎯 ${esc(ps.world.public_goal)}</div>
        <div class="dim">进度 ${t.progress}/10</div>${bar(t.progress, 10, "ok")}
        <div class="dim">危险 ${t.danger}/10</div>${bar(t.danger, 10, "bad")}
        <div class="dim">时钟 ${t.clock}/8 · 默契 ${"★".repeat(t.synergy || 0) || "—"} ·
          ${esc(nameOf(v, a.seat_id))} ${hearts(t.vitality?.[a.seat_id] ?? 3)} /
          ${esc(nameOf(v, b.seat_id))} ${hearts(t.vitality?.[b.seat_id] ?? 3)}</div>
        <div class="dim center">${identLine(a.seat_id)} · ${identLine(b.seat_id)}</div>
        ${sceneHtml}${hooks}${endProposed}${lastLog}${endingHtml}`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing" || !mine) return "";
      const pending = mine.private_state.my_pending;
      if (pending) {
        return `<div class="my-panel"><div class="dim center">
          你已暗投【${esc(pending.intent)}】—— 等对面</div></div>`;
      }
      if (!mine.legal_actions.length) return "";
      const la = mine.legal_actions[0];
      if (la.action_id === "choose_identity") {
        const cards = (mine.private_state.identity_offers || []).map((it) => `
          <div class="item-card focusable" data-act="pc-ident" data-id="${esc(it.id)}">
            <div class="it-name">${esc(it.name)}</div>
            <div class="it-tags">${esc(it.origin)}</div>
            <div class="redeem">擅长:${esc(it.specialty)} · ${esc(it.gift.text)}<br>
              弱点:${esc(it.flaw.text)}<br>
              🤫 私密目标:${esc(it.secret_drive.text)}</div>
          </div>`).join("");
        return `<div class="my-panel">
          <div class="dim center">你抽到两张身份(只有你看得见,连私密目标也是)——暗选其一:</div>
          <div class="hand-row">${cards}</div></div>`;
      }
      const intents = [["advance", "推进"], ["explore", "探索"], ["support", "支援"],
                       ["confront", "对抗"], ["recover", "休整"], ["end", "停笔"]];
      const btns = intents.map(([k, n]) => `
        <button class="soft ${k === "end" ? "warn" : ""} focusable
          ${S.pc.intent === k ? "picked-btn" : ""}"
          data-act="pc-intent" data-id="${k}">${n}</button>`).join(" ");
      const items = [...(v.public_state.inventory?.[S.human.seatId] || []),
                     ...(v.public_state.inventory?.shared || [])];
      const itemOpts = items.map((i) =>
        `<option value="${esc(i.id)}">动用:${esc(i.name)}(利于${(i.use || []).join("/")})</option>`).join("");
      const ready = S.pc.intent && S.pc.intent !== "end";
      const prophecies = (mine.private_state.prophecies || []).map((p) =>
        `<div class="mem-line">📜 ${esc(p)}</div>`).join("");
      const npcOpt = la.params && la.params.target ? `
        <label class="dim"><input type="checkbox" id="pc-npc"> ${esc(la.params.target)}</label>` : "";
      return `<div class="my-panel">
        <div class="dim center">🤫 你的私密目标:${esc(mine.private_state.secret_drive || "")}</div>
        ${prophecies ? `<div class="report">${prophecies}
          <div class="dim">(先知情报,只有你看得见)</div></div>` : ""}
        <div class="center" style="margin-top:.4rem">${btns}</div>
        <div class="confirm-bar">
          <input id="pc-action" maxlength="120"
            placeholder="必填:这一步你具体怎么做(自由描述)">
          <select id="pc-item"><option value="">不动用物品</option>${itemOpts}</select>
          <input id="pc-line" maxlength="60" placeholder="桌边留言(可空)">
          ${npcOpt}
          <button class="soft focusable" data-act="pc-submit"
            ${S.pc.intent ? "" : "disabled"}>确认暗投</button>
        </div>
        ${!ready && S.pc.intent === "end"
          ? '<div class="dim center">停笔无需描述;双方同幕都选停笔才生效</div>' : ""}
      </div>`;
    },
    memorial(v) {
      const ps = v.public_state;
      const rounds = (ps.history || []).map((h) => `
        <div class="mem-four">${h.report
          .map((l, i) => `<div class="${i === 0 ? "dim" : "mem-line"}">${esc(l)}</div>`)
          .join("")}</div>`).join("");
      const e = ps.ending;
      const drives = e && e.secret_drives ? Object.entries(e.secret_drives)
        .map(([sid, d]) => `<div class="mem-line">${d.achieved ? "✅" : "❌"}
          ${esc(d.identity)}(${esc(nameOf(v, sid))})的私密目标:${esc(d.text)}</div>`)
        .join("") : "";
      const memory = e ? `
        <div class="mem-sec"><div class="sec-t">结 局 · ${esc(e.kind)}</div>
          <div class="mem-line">${esc(e.text)}</div>${drives}</div>` : "";
      const cr = ps.chronicle_reveal;
      const sqIcon = { resolved: "🔓", lost: "🗝️", open: "❔" };
      const sqHow = (q) => q.status === "resolved" ? "已解开"
        : q.unlock_kind === "npc"
          ? `错过了知情人${q.npc_name ? "「" + esc(q.npc_name) + "」" : ""}(登场于第${(q.windows || []).join("、")}幕)`
          : `数值考验未达成(${esc(JSON.stringify(q.stat || {}))})`;
      const sideQuests = cr && (cr.side_quests || []).length ? `
        <div class="mem-sec"><div class="sec-t">支 线 对 账 · 谜 底 摊 牌</div>
          ${cr.side_quests.map((q) => `<div class="mem-line">
            ${sqIcon[q.status] || "❔"} ${esc(q.question)}<br>
            <span class="dim">真相:${esc(q.truth)} —— ${sqHow(q)}</span></div>`).join("")}
        </div>` : "";
      const chronicle = cr ? `
        <div class="mem-sec"><div class="sec-t">原 典 揭 晓 · 本 该 发 生 的</div>
          ${(cr.chapters || []).map((c) => `<div class="mem-line">
            第${c.chapter}章《${esc(c.title)}》 ${esc(c.event)}</div>`).join("")}
          <div class="mem-line" style="margin-top:.4rem">📖 原典结局:${esc(cr.original_ending || "")}</div>
          <div class="dim">—— 而以上,是没有你们的版本。</div></div>` : "";
      return { rounds: rounds + memory + sideQuests + chronicle,
               champ: e ? `《${esc(e.world_name)}》· 世界种子 ${esc(String(e.seed))} · 孤本` : "本局提前收起",
               scoreLine: e ? `【${esc(e.kind)}】` : "未完" };
    },
  },

  _fallback: {
    felt(v) { return `<div class="dim center">未知卡带 ${esc(v.cartridge.id)}</div>`; },
    myPanel() { return ""; },
    memorial(v) { return { rounds: "", champ: "", scoreLine: "" }; },
  },
};

// 《口袋跑团》是《口袋穿越》分家出的经典骨架卡:对外状态与动作协议同构,直接共用界面
CART_UI["pocket-tabletop"] = CART_UI["pocket-crossing"];

/* ---------------- 纪念卡 ---------------- */

async function showMemorial(sid) {
  S.sid = sid;
  setScreen("memorial", "纪念卡");
  const v = await api(`/api/sessions/${sid}`);
  if (v.result !== "ok") {
    app.innerHTML = `<p class="center">读不到这局(${esc(v.result)})。按 B 回卡带架。</p>`;
    return;
  }
  const ui = CART_UI[v.cartridge.id] || CART_UI._fallback;
  const m = ui.memorial(v);
  const events = v.public_events || v.recent_public_events || [];
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
  app.innerHTML = `
    <div class="memcard">
      <h3>· ${esc(v.cartridge.name)} · 纪 念 卡 ·</h3>
      <div class="meta">局号 ${esc(v.session_id)} · ${esc((v.updated_at || "").replace("T", " ").slice(0, 16))}</div>
      <div class="big-score">${m.scoreLine}</div>
      <div class="champ">${m.champ}</div>
      ${m.rounds ? `<div class="mem-sec"><div class="sec-t">逐 轮 揭 示</div>${m.rounds}</div>` : ""}
      <div class="mem-sec"><div class="sec-t">座 签</div>${seatSec}</div>
      ${talks ? `<div class="mem-sec"><div class="sec-t">桌 边 话</div>${talks}</div>` : ""}
      <div class="mem-sec meta">此卡由 SQLite 里的原局面当场派生,可随时重新打开。</div>
    </div>
    <p class="center" style="margin-top:.8rem">
      <button class="soft focusable" data-act="back">回卡带架</button></p>`;
  afterRender();
}

/* ---------------- 人类席动作 ---------------- */

async function humanIntroduce() {
  const name = (document.getElementById("intro-name")?.value || "").trim();
  const now = (document.getElementById("intro-now")?.value || "").trim();
  if (!name) { alert("称呼不能为空"); return; }
  const o = await api(`/api/sessions/${S.sid}/observe`, "POST",
                      { seat_token: S.human.token });
  if (o.result !== "ok") { alert("读不到席位:" + o.result); return; }
  const r = await api(`/api/sessions/${S.sid}/act`, "POST", {
    seat_token: S.human.token,
    expected_revision: o.revision,
    action_id: "introduce",
    params: { display_name: name, surface: "掌机 UI", now },
  });
  if (r.result !== "ok") alert("入座失败:" + (r.reason || r.result));
  S.lastSnap = "";
}

async function humanAct(action_id, params, table_line = "") {
  const o = await api(`/api/sessions/${S.sid}/observe`, "POST",
                      { seat_token: S.human.token });
  if (o.result !== "ok") { alert("读不到席位:" + o.result); return null; }
  const r = await api(`/api/sessions/${S.sid}/act`, "POST", {
    seat_token: S.human.token,
    expected_revision: o.revision,
    action_id, params, table_line,
  });
  if (r.result !== "ok" && r.result !== "stale_revision")
    alert("动作失败:" + (r.reason || r.result));
  S.lastSnap = "";
  return r;
}

async function humanSubmit() {
  if (!S.picked) return;
  const usage = (document.getElementById("usage-input")?.value || "").trim();
  if (!usage) { alert("用法必填:说一句你打算怎么用它,这句话参与判定"); return; }
  const combo = document.getElementById("combo-select")?.value || "";
  const line = (document.getElementById("tl-input")?.value || "").trim();
  const params = { item_id: S.picked, usage };
  if (combo) params.combo_target = combo;
  const r = await humanAct("choose_item", params, line);
  if (r && r.result === "ok") S.picked = null;
}

async function humanJudge(verdict) {
  const needs = [...document.querySelectorAll(".need-box:checked")]
    .map((x) => x.value);
  if (verdict === "endorse" && (needs.length < 1 || needs.length > 2)) {
    alert("背书前先勾选它真正覆盖的需求(1-2 个)");
    return;
  }
  const params = { verdict };
  if (verdict === "endorse") params.needs = needs;
  await humanAct("judge", params);
}

async function humanDraw(itemId) {
  await humanAct("draw_pick", { item_id: itemId });
}

async function circuitPlay(card) {
  if (!confirm(`锁定电压 ${card}？本轮不能更改。`)) return;
  const line = (document.getElementById("circuit-line")?.value || "").trim();
  await humanAct("play_card", { card }, line);
}

async function nightKnock() {
  await humanAct("knock", {});
}

async function pcNarrate(btn) {
  btn.textContent = "荷官执笔中……";
  btn.disabled = true;
  const r = await api(`/api/sessions/${S.sid}/narrate`, "POST");
  if (r.result !== "ok") alert("荷官没接住:" + (r.message || r.reason || r.result));
  S.lastSnap = "";
}

async function pcSubmit() {
  if (!S.pc.intent) return;
  const action = (document.getElementById("pc-action")?.value || "").trim();
  if (S.pc.intent !== "end" && !action) {
    alert("行动描述必填:说清这一步你具体怎么做");
    return;
  }
  const params = { intent: S.pc.intent, action };
  const item = document.getElementById("pc-item")?.value || "";
  if (item) params.item_id = item;
  const line = (document.getElementById("pc-line")?.value || "").trim();
  if (line) params.line = line;
  if (document.getElementById("pc-npc")?.checked) params.target = "npc";
  const r = await humanAct("commit", params);
  if (r && r.result === "ok") S.pc = { intent: null };
}

async function bcSubmit() {
  if (!S.bc.fact || !S.bc.stance || !S.bc.target) return;
  const line = (document.getElementById("bc-line")?.value || "").trim();
  const endorse = !!document.getElementById("bc-endorse")?.checked;
  const r = await humanAct("commit", {
    fact_id: S.bc.fact, stance: S.bc.stance, target_id: S.bc.target,
    line, endorse,
  });
  if (r && r.result === "ok") S.bc = { fact: null, stance: null, target: null };
}

async function endSession() {
  if (!confirm("确定收起这局吗?局面会停在这里。")) return;
  await api(`/api/sessions/${S.sid}/end`, "POST");
  S.lastSnap = "";
}

async function copyConn(seatId, btn) {
  const tokens = JSON.parse(sessionStorage.getItem(aiTokensKey(S.sid)) || "[]");
  const t = tokens.find((x) => x.seat_id === seatId);
  if (!t) return;
  const text = isNightShop(S.currentCartridgeId)
    ? `你在 AI-Gameboy 的《口袋夜铺》里经营一间长期存档的夜铺(MCP 服务名 gameboy,入口 http://127.0.0.1:7777/mcp)。
session_id: ${S.sid}
seat_id: ${t.seat_id}
seat_token: ${t.seat_token}
请先调用 game_observe(session_id, seat_token) 看店铺,再按 legal_actions 用 game_act 经营。
你是唯一店主,可以连续执行许多个 work_shift,不必等待观看者;想停时直接停下,
下次凭同一连接继续。mood、goal、public_line 会显示在人类的掌机上。门铃不阻塞经营。`
    : `你在 AI-Gameboy 牌桌上有一个席位(MCP 服务名 gameboy,入口 http://127.0.0.1:7777/mcp)。
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

/* ---------------- 焦点与实体键 ---------------- */

function focusables() { return [...app.querySelectorAll("[data-act]")]; }

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
  if (a === "insert") {
    const cart = S.carts.find((c) => c.id === el.dataset.cart);
    if (cart && (cart.modes || []).includes("human_ai")) askMode(cart.id);
    else insertCartridge(el.dataset.cart, "ai_ai");
  } else if (a === "create") insertCartridge(S.chooseCart, el.dataset.mode);
  else if (a === "open-save") location.hash = `#/s/${el.dataset.sid}`;
  else if (a === "copy") copyConn(el.dataset.seat, el);
  else if (a === "end") endSession();
  else if (a === "back") location.hash = "#/";
  else if (a === "pick") { S.picked = el.dataset.item; S.lastSnap = ""; redrawSoon(); }
  else if (a === "hu-intro") humanIntroduce();
  else if (a === "hu-submit") humanSubmit();
  else if (a === "hu-endorse") humanJudge("endorse");
  else if (a === "hu-doubt") humanJudge("doubt");
  else if (a === "pick-draw") humanDraw(el.dataset.item);
  else if (a === "circuit-card") circuitPlay(Number(el.dataset.card));
  else if (a === "night-knock") nightKnock();
  else if (a === "bc-fact") { S.bc.fact = el.dataset.id; S.lastSnap = ""; redrawSoon(); }
  else if (a === "bc-stance") { S.bc.stance = el.dataset.id; S.lastSnap = ""; redrawSoon(); }
  else if (a === "bc-target") { S.bc.target = el.dataset.id; S.lastSnap = ""; redrawSoon(); }
  else if (a === "bc-submit") bcSubmit();
  else if (a === "pc-ident") humanAct("choose_identity", { identity_id: el.dataset.id });
  else if (a === "pc-intent") { S.pc.intent = el.dataset.id; S.lastSnap = ""; redrawSoon(); }
  else if (a === "pc-submit") pcSubmit();
  else if (a === "pc-narrate") pcNarrate(el);
}

let redrawTimer = null;
function redrawSoon() {
  // 点选物件后立即重绘一次(不等 3 秒轮询)
  if (redrawTimer) return;
  redrawTimer = setTimeout(() => { redrawTimer = null; }, 50);
  const ev = new HashChangeEvent("hashchange");
  // 直接触发当前视图重画:route 会重建轮询,简单可靠
  route();
}

function handleKey(key) {
  if (key === "up" || key === "left") moveFocus(-1);
  else if (key === "down" || key === "right") moveFocus(1);
  else if (key === "a") {
    const els = focusables();
    const el = els[Math.min(S.focusIdx, els.length - 1)];
    if (el) act(el);
  } else if (key === "b") {
    if (S.chooseCart) { S.chooseCart = null; showShelf(); }
    else if (S.view !== "shelf") location.hash = "#/";
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
    if (S.view === "shelf" && !S.chooseCart) showShelf();
  }
}

document.querySelectorAll("[data-key]").forEach((btn) => {
  btn.addEventListener("click", () => handleKey(btn.dataset.key));
  btn.addEventListener("pointerdown", () => btn.classList.add("pressed"));
  btn.addEventListener("pointerup", () => btn.classList.remove("pressed"));
  btn.addEventListener("pointerleave", () => btn.classList.remove("pressed"));
});

window.addEventListener("keydown", (e) => {
  // 输入框里正常打字,不当成手柄按键
  const tag = (e.target && e.target.tagName) || "";
  if (tag === "INPUT" || tag === "TEXTAREA") return;
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
