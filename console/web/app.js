/* AI-Gameboy 掌机主板。
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
  pc: { intent: null },                            // 口袋穿越的意图选择
  night: { sid: null, cursor: 0, known: [], journal: [], queue: [], active: null, holdUntil: 0, paused: false },
  bridge: { mode: "local", mcp_url: "http://127.0.0.1:7777/mcp" },  // /api/bridge:本地模式或开桥模式
};

const isNightShop = (id) => id === "pocket-night-shop";


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
  const history = ps.playback_entries || ps.recent_history || [];
  const now = Date.now();
  if (S.night.sid !== sid) {
    S.night = {
      sid, cursor: 0, known: [], journal: [], queue: [], active: null, holdUntil: 0, paused: false,
    };
  }
  for (const entry of history) {
    const key = nightEntryKey(entry);
    const fresh = ps.playback_entries ? entry.seq > S.night.cursor : !S.night.known.includes(key);
    if (fresh) {
      S.night.known.push(key);
      S.night.journal.push(entry);
      S.night.queue.push(entry);
      S.night.cursor = Math.max(S.night.cursor, entry.seq || 0);
    }
  }
  S.night.known = S.night.known.slice(-100);
  if (!S.night.paused && S.night.queue.length && (!S.night.active || now >= S.night.holdUntil)) {
    S.night.active = S.night.queue.shift();
    S.night.holdUntil = now + 5000;
  }
}

/* ---------------- 卡带架(真实清单) ---------------- */

async function showShelf() {
  setScreen("shelf", "卡带架");
  S.chooseCart = null;
  const [cartsData, sessData, bridge] = await Promise.all([
    api("/api/cartridges"), api("/api/sessions"), api("/api/bridge"),
  ]);
  S.bridge = bridge;
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
        <button class="soft focusable" data-act="create" data-mode="solo_ai">开一间夜铺</button>
      </div>
      <p class="center dim">店主自己经营、探索和应对事件。你可以翻图鉴、看每一班回放。</p>`;
    afterRender();
    return;
  }
  app.innerHTML = `
    <h2>· ${esc(cartName(cartId))} ·</h2>
    <p class="center dim">谁来玩?</p>
    <div class="mode-choices">${modeButtons(cartId)}</div>
    <p class="center dim">按 B 放回卡带</p>`;
  afterRender();
}

// 只列出卡带清单 modes 里真正支持的玩法
function modeButtons(cartId) {
  const modes = (S.carts.find((c) => c.id === cartId) || {}).modes || [];
  return [["human_ai", "human_ai", "我 × AI(我坐 B 席)"], ["multi_ai", "ai_ai", "AI × AI(我旁观)"],
          ["solo_ai", "solo_ai", "AI 单人玩(我旁观)"]]
    .filter(([cap]) => modes.includes(cap))
    .map(([, mode, label]) => `<button class="soft focusable" data-act="create" data-mode="${mode}">${label}</button>`)
    .join("");
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
  }
  location.hash = `#/s/${r.session_id}`;
}

/* ---------------- 牌局(席位 / 游戏) ---------------- */

async function showSession(sid) {
  if (S.sid !== sid) {
    S.picked = null;
    S.bc = { fact: null, stance: null, target: null };
    S.pc = { intent: null };
    S.night = { sid: null, cursor: 0, known: [], journal: [], queue: [], active: null, holdUntil: 0, paused: false };
  }
  S.sid = sid;
  const bridge = await api("/api/bridge");  // 直接打开局号链接时,卡带架没走过,这里补读一次模式
  if (bridge && bridge.mcp_url) S.bridge = bridge;
  // 人类身份只凭统一 observe 成功确认,不靠 localStorage 猜(校正 #1)
  const stored = localStorage.getItem(humanTokenKey(sid));
  let tokenLost = false;
  if (stored) {
    const o = await api(`/api/sessions/${sid}/observe`, "POST",
                        { seat_token: stored });
    if (o.result === "ok") S.human = { token: stored, seatId: o.you.seat_id };
    else tokenLost = true;
  }
  let drawing = false;
  const draw = async () => {
    if (drawing) return;
    drawing = true;
    try {
    const cursor = S.night.sid === sid ? S.night.cursor : 0;
    const v = await api(`/api/sessions/${sid}?after_seq=${cursor}`);
    if (v.result !== "ok") {
      setScreen("seats", "开局席位");
      app.innerHTML = `<p class="center">读不到这局(${esc(v.result)})。按 B 回卡带架。</p>`;
      return;
    }
    S.currentCartridgeId = v.cartridge.id;
    await ensureCartUi(v.cartridge.id);
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
                                 S.night.queue.length, S.night.paused]);
    if (snap === S.lastSnap) return;
    S.lastSnap = snap;
    const openDetails = [...app.querySelectorAll("details[open]")].map(x => x.dataset.panel).filter(Boolean);
    const scrollTop = app.scrollTop;
    const journalScroll = document.getElementById("night-journal-scroll")?.scrollTop || 0;
    if (v.status === "lobby") renderSeats(v, mine, tokenLost);
    else renderGame(v, mine, tokenLost);
    restoreDraft(draft);
    for (const panel of app.querySelectorAll("details[data-panel]"))
      panel.open = openDetails.includes(panel.dataset.panel);
    app.scrollTop = scrollTop;
    const journal = document.getElementById("night-journal-scroll");
    if (journal) journal.scrollTop = journalScroll;
    } finally { drawing = false; }
  };
  await draw();
  S.timer = setInterval(draw, 3000); // 人类自己的视图刷新,不触碰任何 AI 窗口
}

const DRAFT_IDS = ["tl-input", "intro-name", "intro-now", "pc-action", "pc-item", "pc-line"];

function captureDraft() {
  const d = {};
  for (const id of DRAFT_IDS) {
    const el = document.getElementById(id);
    if (el) d[id] = el.value;
  }
  return d;
}
function restoreDraft(d) {
  if (!d) return;
  for (const id of DRAFT_IDS) {
    const el = document.getElementById(id);
    if (el && d[id] != null && d[id] !== "") el.value = d[id];
  }
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
          <input id="intro-name" maxlength="40" value="玩家" aria-label="称呼">
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
    <p class="dim center">${S.bridge.mode === "bridge"
      ? `开桥模式 · 不在这台电脑上的 AI 用这个 MCP 网址:${esc(S.bridge.mcp_url)}`
      : "本地模式 · 只有这台电脑上的 AI 能连;要和手机或网页上的 AI 玩,请用开桥模式启动"}</p>
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
        <span class="dim">你可以观看与翻阅图鉴。事件由店主自己处理。</span></div>
    </div>
    <div class="start-hint ${ready ? "ready" : ""}">${v.seats.length === 1
      ? "AI 完成自我介绍后自动开灯营业"
      : ready
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
      ${solo ? "" : sideSeat(v, v.seats[0], ui)}
      <div class="felt">${ui.felt(v, mine)}</div>
      ${solo ? "" : sideSeat(v, v.seats[1], ui)}
    </div>
    ${mine ? ui.myPanel(v, mine) : ""}
    ${solo ? "" : `<div class="table-talk">${talk}</div>`}
    ${solo ? '<p class="dim center">每次行动自动保存 · 关闭页面不影响店铺存档</p>'
      : '<p class="center"><button class="soft warn focusable" data-act="end">结束本局</button></p>'}
    <p class="dim center">局号 ${esc(v.session_id)}</p>`;
  afterRender();
}

function sideSeat(v, s, ui) {
  const turn = (v.waiting_for || []).includes(s.seat_id);
  const sub = v.public_state.submitted && v.public_state.submitted[s.seat_id];
  const isMe = S.human && S.human.seatId === s.seat_id;
  return `<div class="side-seat ${turn ? "turn" : ""}">
    <div class="lamp"></div>
    <div class="who">${esc(s.display_name)}${isMe ? " (你)" : ""}</div>
    <div class="surf">${esc(s.surface)}</div>
    <div class="stat">${sub ? "已暗投 ▮" : turn ? "考虑中…" : ""}</div>
    ${ui && ui.seatExtra ? ui.seatExtra(v, s.seat_id) : ""}
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

/* 穿越/跑团:随机事件的难度与目标值(与卡带规则 EVENT_TARGETS 一致) */
const PC_EVENT_NAMES = { easy: "容易", normal: "普通", hard: "困难" };
const PC_EVENT_TARGETS = { easy: 24, normal: 28, hard: 31 };

/* 穿越/跑团:每一步告诉旁边的人类现在在等什么、要不要按按钮 */
function pcGuide(v) {
  const ps = v.public_state;
  const names = (v.waiting_for || []).filter((x) => x !== "narrator").map((x) => nameOf(v, x));
  const NARR = { gen_world: "写世界", gen_episode: "写这一段故事", gen_identities: "写身份卡",
                 gen_milestones: "拆里程碑", gen_scene: "写下一幕", render_ending: "写结局" };
  let tip;
  if (ps.narration_pending) tip = `请按「召荷官」——荷官要${NARR[ps.narration_pending] || "动笔"}了`;
  else if (ps.stage === "landing") tip = `等两位玩家商量选降落点${names.length ? "(还在等 " + names.join("、") + ")" : ""}`;
  else if (ps.stage === "identity") tip = `等两位玩家暗选身份${names.length ? "(还在等 " + names.join("、") + ")" : ""}`;
  else if (ps.stage === "goal") tip = `等两位玩家选各自的目标${names.length ? "(还在等 " + names.join("、") + ")" : ""}`;
  else if (ps.stage === "scene") tip = names.length ? `等 ${names.join("、")} 暗投这一幕的行动` : "两人都已行动,马上结算";
  else if (ps.stage === "finished") tip = "本局结束,按 B 回卡带架可再看纪念卡";
  return tip ? `<div class="warn-note center">👉 现在:${esc(tip)}</div>` : "";
}

/* ---------------- CART_UI:卡带渲染映射 ----------------
   内置卡带的界面写在下面;其他卡带把界面放在 cartridges/<id>/ui.js,显示前按需加载一次,
   加载不到就用 _fallback 通用显示。 */

const uiTried = new Set();
function ensureCartUi(id) {
  if (CART_UI[id] || uiTried.has(id)) return Promise.resolve();
  uiTried.add(id);
  return new Promise((resolve) => {
    const tag = document.createElement("script");
    tag.src = `/cartridges/${encodeURIComponent(id)}/ui.js`;
    tag.onload = tag.onerror = () => resolve();
    document.head.appendChild(tag);
  });
}

function nightJournalEntry(entry) {
  const focus = {scavenge:"出门淘货",repair:"修理旧物",tidy:"整理与小修补",sell:"向客人报价",
    dismiss:"送客",recycle:"回收零件",curate:"布置橱窗",upgrade:"扩建铺子",
    choose_event:"处理街巷事件",unlock_location:"开辟淘货路线"}[entry.focus] || entry.focus;
  const customer = (c, label) => c ? `<p><strong>${label} · ${esc(c.name)}</strong>
    （第${esc(c.visits)}次来店）<br>想找：${esc(c.request)}<br>
    <span class="dim">可观察到：${esc(c.clue)}</span></p>` : "";
  return `<details class="night-journal-entry" data-panel="journal-${esc(nightEntryKey(entry))}">
    <summary>第${esc(entry.seq)}条 · 第${esc(entry.day)}日 ${esc(entry.shift)} · ${esc(focus)}</summary>
    ${entry.goal ? `<p>当时公开目标：${esc(entry.goal)}</p>` : ""}
    ${customer(entry.customer, "当时在店的客人")}
    ${!entry.customer && !entry.goal ? '<p class="dim">此条早期记录未保存当班顾客与目标。</p>' : ""}
    ${entry.offer ? `<p>店主拿出「${esc(entry.offer.item_name)}」，报价${esc(entry.offer.asking_price)}枚古币。</p>` : ""}
    ${entry.event_name ? `<p>遇见「${esc(entry.event_name)}」 · 店主选择：${esc(entry.choice)}</p>` : ""}
    <p class="night-action">经过与结果：${esc(entry.text)}</p>
    ${customer(entry.customer_arrived, "随后进门的客人")}
    ${entry.ambient ? `<p class="night-ambient">${esc(entry.ambient)}</p>` : ""}
    <div class="night-deltas"><span class="chip">古币 ${entry.coins_delta >= 0 ? "+" : ""}${esc(entry.coins_delta)}</span>
      <span class="chip">声望 ${entry.reputation_delta >= 0 ? "+" : ""}${esc(entry.reputation_delta)}</span></div>
    ${entry.reaction ? `<p class="night-reaction">店主留下的话：${esc(entry.reaction.mood)} ${esc(entry.reaction.text)}</p>` : ""}
  </details>`;
}

function nightCollection(ps) {
  const locations = Object.fromEntries(ps.locations.map(x => [x.id, x.name]));
  const rarities = {common: "寻常", uncommon: "少见", rare: "奇珍", ancient: "上古", heirloom: "遗世"};
  const entries = ps.collection.entries.map(row => `
    <article class="night-dex-entry">
      <strong>${esc(row.name)}</strong><span class="chip">${rarities[row.rarity]}</span>
      <div class="dim">首次：第${row.first_day}日 · ${esc(locations[row.first_location] || row.first_location)} · 共见${row.count}件</div>
      <p>${esc(row.story)}</p>
      <div class="night-secret">${row.revealed ? "✦ " + esc(row.revealed) : "尚未修复揭秘"}</div>
    </article>`).join("");
  const encounters = ps.encounters.entries.map(row => `
    <article class="night-dex-entry"><strong>${esc(row.name)}</strong>
      <span class="chip">遇见 ${row.count} 次</span><p>${esc(row.text)}</p>
      ${Object.values(row.outcomes).map(text => `<div class="night-secret">${esc(text)}</div>`).join("")}
    </article>`).join("");
  return `<div class="night-dex-summary">异物志 ${ps.collection.found}/${ps.collection.total}
      · 已揭秘 ${ps.collection.revealed} · 街巷见闻 ${ps.encounters.found}/${ps.encounters.total}</div>
    <details class="night-history" data-panel="collection"><summary>翻开异物志 · 卖掉的发现也留在这里</summary>
      ${(ps.rarities || []).map(row => `<span class="chip">${esc(row.label)} ${row.found}/${row.total}
        ${ps.shop_level < row.min_level ? `· ${row.min_level}级开放` : ""}</span>`).join("")}
      <div class="night-dex-grid">${entries}</div></details>
    <details class="night-history" data-panel="encounters"><summary>翻开街巷见闻</summary>
      <div class="night-dex-grid">${encounters || '<p class="dim">还没有遇见街巷事件。</p>'}</div></details>
    <details class="night-history" data-panel="locations"><summary>淘货地图 · 寻找下一页</summary>
      ${ps.locations.map(loc => `<div class="night-log"><strong>${esc(loc.name)}</strong>
        <span>${esc(loc.description)} 待发现 ${loc.undiscovered} 种 · 每次 ${loc.cost} 枚古币
        ${loc.available_undiscovered !== undefined ? `（当前等级可寻 ${loc.available_undiscovered} 种）` : ""}
        · ${loc.unlocked ? "已解锁" : "需发现" + loc.required_discoveries + "种、店铺" + (loc.required_level || 1) + "级及" + loc.unlock_cost + "枚"}</span></div>`).join("")}
    </details>`;
}

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
            ${item.rarity ? `<span class="chip">${esc({common:"寻常",uncommon:"少见",rare:"奇珍",ancient:"上古",heirloom:"遗世"}[item.rarity])}</span>` : ""}
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
          <span class="chip">古币 ${active.coins_delta >= 0 ? "+" : ""}${active.coins_delta}</span>
          <span class="chip">声望 ${active.reputation_delta >= 0 ? "+" : ""}${active.reputation_delta}</span>
        </div>` : "";
      const logs = S.night.journal.map(nightJournalEntry).join("");
      const customer = ps.customer ? `
        <div class="night-customer">
          <div class="night-customer-name">今夜来客 · ${esc(ps.customer.name)}
            <span class="chip">第${ps.customer.visits}次来店</span></div>
          ${ps.customer.max_visits ? `<div class="dim">累计到访上限 ${ps.customer.max_visits} 次${ps.customer.special ? " · 专属来客" : ""}</div>` : ""}
          <div>${esc(ps.customer.request)}</div>
          <div class="dim">可观察到:${esc(ps.customer.clue)}</div>
          <div class="dim">耐心:${"●".repeat(ps.customer.patience)}${"○".repeat(2 - ps.customer.patience)}</div>
        </div>` : (ps.customer_collection ? '<div class="night-customer dim">眼下没有可接待的新来客。仍可淘货、修理、回收或扩建；达到三级可开放特殊来客。</div>' : "");
      const relations = (ps.customer_book || []).map((row) => `
        <article class="night-dex-entry"><strong>${esc(row.name)}</strong>
          <div>来过${row.visits}${ps.customer_collection ? "/" + ps.customer_collection.visit_limit : ""}次
          · 成交${row.deals}次 · 信任${row.trust}
          ${ps.customer_collection && row.visits >= ps.customer_collection.visit_limit ? " · 此后不再到访" : ""}
          ${row.special ? " · 专属来客" : ""}</div>
          ${row.request ? `<p>${esc(row.request)}</p><div class="dim">${esc(row.clue)}</div>` : ""}</article>`).join("");
      const week = (ps.weekly || []).slice(-1)[0];
      return `
        <div class="night-owner">${esc(keeper.display_name || "AI 店主")} 的夜铺</div>
        <div class="night-dashboard">
          <div class="night-day">实时店况 · 第 ${ps.day} 日 · ${esc(ps.shift)}</div>
          <div>古币 <strong>${ps.coins}</strong> · 声望 <strong>${ps.reputation}</strong> ·
            店铺 ${ps.shop_level}级 · 库存 ${(ps.inventory || []).length}/${ps.capacity}</div>
        </div>
        ${ps.resting ? `<div class="night-resting">暂时歇业 · 存档安全<br>
          <span>店主下次回来会从第 ${ps.day} 日 ${esc(ps.shift)}重新开门。</span></div>` : ""}
        ${week ? `<div class="night-week">第 ${week.week} 周账 · 经过第${week.through_day}日 ·
          成交${week.deals}次 · 古币${week.coins} · 声望${week.reputation}</div>` : ""}
        <div class="night-goal">店主眼下想做:${esc(ps.current_goal)}</div>
        <details class="night-history night-journal" data-panel="history">
          <summary>逐轮经营记录 · ${S.night.journal.length}/${ps.journal_total || 0} 条 · 从开店看起</summary>
          <p class="dim">按发生顺序排列，展开每条查看来客、店主行动与结果。公开目标来自店主填写。</p>
          ${S.night.journal.length < ps.journal_total ? '<p class="dim">正在载入后续记录……</p>' : ""}
          <div id="night-journal-scroll" tabindex="0" aria-label="全部经营记录">${logs || '<p class="dim">招牌刚点亮，还没有经营记录。</p>'}</div>
        </details>
        ${ps.pending_event ? `<div class="night-customer">
          <strong>店主正在面对 · ${esc(ps.pending_event.name)}</strong>
          <p>${esc(ps.pending_event.text)}</p>
          <div class="dim">可选：${ps.pending_event.choices.map(c => esc(c.label) + (c.available ? "" : "（暂不可选）")).join(" / ")}</div>
          <div class="dim">由 AI 决定，观看者无需操作。</div></div>` : ""}
        ${customer}
        ${ps.last_run ? `<div class="night-week">本次连续行动：${ps.last_run.completed}/${ps.last_run.requested}班
          · 停于 ${esc({count:"计划完成",new:"新发现",rare:"奇珍",event:"街巷事件",decision:"等待店主选择",
             reserve:"现金保留线",inventory_full:"货架已满",repair_complete:"修复完成",
             insufficient_coins:"现金不足"}[ps.last_run.stop_reason] || ps.last_run.stop_reason)}</div>` : ""}
        <div class="night-play-controls">
          <button class="soft" data-act="night-pause">${S.night.paused ? "继续回放" : "暂停回放"}</button>
          <span class="dim">每段至少5秒 · 回放不影响店主经营</span>
        </div>
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
        ${nightCollection(ps)}
        ${relations ? `<details class="night-history" data-panel="customers"><summary>顾客簿
          ${ps.customer_collection ? `· 已遇见 ${ps.customer_collection.found}/${ps.customer_collection.total} 位 · 达到到访上限 ${ps.customer_collection.retired} 位` : ""}</summary>
          <div class="night-dex-grid">${relations}</div></details>` : ""}
        `;
    },
    myPanel() { return ""; },
    memorial(v) {
      const ps = v.public_state;
      const diary = (ps.diary || []).map((entry) => `
        <div class="mem-round"><span class="dim">第${entry.day}日</span>
          <span>${esc(entry.text)}</span></div>`).join("");
      return {
        rounds: diary,
        champ: `夜铺停在第 ${ps.day} 日 · 古币 ${ps.coins} · 声望 ${ps.reputation}`,
        scoreLine: `店铺 ${ps.shop_level}级 · 库存 ${(ps.inventory || []).length}/${ps.capacity}`,
      };
    },
  },


  "pocket-crossing": {
    seatExtra(v, sid) {
      const it = (v.public_state.identities || {})[sid];
      if (!it) return "";
      const at = it.attrs;
      return `<div class="surf">${esc(it.name)}</div>
        <div class="surf">擅${esc(it.specialty)}</div>
        ${at ? `<div class="surf">智${at.wisdom} 体${at.stamina} 运${at.luck}${at.luck >= 5 ? " 🍀" : ""}</div>` : ""}`;
    },
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
        return `${pcGuide(v)}<div class="sit-name center">世界正在成形…</div>
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
        : ps.stage === "identity" ? `${esc(nameOf(v, sid))} 暗选身份中…`
        : `${esc(nameOf(v, sid))} 等荷官写身份卡`;
      const sc = ps.scene;
      const sceneHtml = sc ? `
        <div class="situation">
          <div class="sit-name">第 ${ps.scene_index} 幕 · ${esc(sc.title)}</div>
          <div class="sit-text">${esc(sc.text)}</div>
          <div class="sit-text">⚡ ${esc(sc.crisis)}</div>
          <div class="sit-tags">${(sc.objects || []).map((o) =>
            `<span class="chip" title="${esc(o.hint)}">${esc(o.name)}</span>`).join("")}</div>
          ${sc.event ? `<div class="sit-text">🎲 随机事件【${esc(PC_EVENT_NAMES[sc.event.difficulty] || sc.event.difficulty)}·目标${PC_EVENT_TARGETS[sc.event.difficulty] || "?"}】${esc(sc.event.text)}
            <span class="dim">—— 两人三维加骰子,本幕结算时自动判定:过了危险-2,没过危险+2</span></div>` : ""}
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
        ${pcGuide(v)}
        <div class="sit-name center">《${esc(ps.world.world_name)}》</div>
        ${ps.world.public_goal ? `<div class="sit-text center">🎯 ${esc(ps.world.public_goal)}</div>` : ""}
        <div class="dim">进度 ${t.progress}/10${ps.main_goal_locked ? " · 🔒 主线已锁定,进度不再回退" : ""}</div>${bar(t.progress, 10, "ok")}
        <div class="dim">危险 ${t.danger}/10</div>${bar(t.danger, 10, "bad")}
        <div class="dim">时钟 ${t.clock}/8 · 默契 ${"★".repeat(t.synergy || 0) || "—"} ·
          ${esc(nameOf(v, a.seat_id))} ${hearts(t.vitality?.[a.seat_id] ?? 3)} /
          ${esc(nameOf(v, b.seat_id))} ${hearts(t.vitality?.[b.seat_id] ?? 3)}</div>
        <div class="dim center">${identLine(a.seat_id)} · ${identLine(b.seat_id)}</div>
        ${ps.events && ps.events.done ? `<div class="dim center">随机事件 ${ps.events.done} 次 · 化解 ${ps.events.won} 次</div>` : ""}
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

  // 没有自带界面的卡带:通用显示。公开局面照原样列出;人类席把 legal_actions 一项项变成按钮。
  _fallback: {
    felt(v) {
      const ps = v.public_state || {};
      const rows = Object.entries(ps).map(([k, val]) => `
        <div class="kv"><span class="dim">${esc(k)}</span>
          <span>${esc(typeof val === "object" ? JSON.stringify(val) : val)}</span></div>`).join("");
      const waiting = (v.waiting_for || []).map((id) => esc(nameOf(v, id))).join("、");
      return `<div class="generic-felt">${rows}
        ${waiting ? `<div class="round-line">轮到:${waiting}</div>` : ""}</div>`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing" || !mine) return "";
      const acts = mine.legal_actions || [];
      if (!acts.length) return `<div class="my-panel"><div class="dim center">等待对面……</div></div>`;
      return `<div class="my-panel">
        <div class="dim center">你的私有信息:${esc(JSON.stringify(mine.private_state))}</div>
        ${acts.map((a, i) => `<div class="generic-act">
          <button class="soft focusable" data-act="generic-act" data-i="${i}">${esc(a.action_id)}</button>
          <span class="dim">${esc(JSON.stringify(a.params || {}))}</span></div>`).join("")}
        <input id="tl-input" maxlength="120" placeholder="桌边话(可空)">
      </div>`;
    },
    memorial(v) {
      return { rounds: this.felt(v), champ: v.public_state?.phase === "finished" ? "已结算" : "本局提前收起",
               scoreLine: "" };
    },
    async onAct(name, el) {
      if (name !== "generic-act") return;
      const o = await api(`/api/sessions/${S.sid}/observe`, "POST", { seat_token: S.human.token });
      const a = o.result === "ok" && (o.legal_actions || [])[Number(el.dataset.i)];
      if (!a) return;
      const hint = JSON.stringify(a.params || {}, null, 1);
      const text = prompt(`${a.action_id} 的参数(JSON)。说明:
${hint}`, "{}");
      if (text === null) return;
      let params;
      try { params = JSON.parse(text || "{}"); } catch { alert("不是合法的 JSON"); return; }
      const line = (document.getElementById("tl-input")?.value || "").trim();
      await humanAct(a.action_id, params, line);
    },
  },
};

// 《口袋跑团》是《口袋穿越》分家出的经典骨架卡:对外状态与动作协议同构,直接共用界面
CART_UI["pocket-tabletop"] = CART_UI["pocket-crossing"];

/* ---------------- 纪念卡 ---------------- */

function storyCollectionHint(v) {
  if (!["pocket-crossing", "pocket-tabletop"].includes(v.cartridge.id)
      || v.status !== "finished" || !v.public_state?.ending?.text) return "";
  return `<div class="mem-sec"><div class="sec-t">收 藏 这 段 故 事</div>
    <p>想把这局剧情留作纪念或小说素材？请告诉帮你启动游戏机的 Agent：
    “帮我收藏这一局的剧情。”它会问你要 Markdown（.md）还是纯文本（.txt），
    再整理成只保留游戏剧情、角色行动与对白的本地文件。</p>
    <p class="dim">把上方局号告诉 Agent 即可。收藏文件属于你的私人资料，不会自动上传。</p></div>`;
}

async function showMemorial(sid) {
  S.sid = sid;
  setScreen("memorial", "纪念卡");
  const v = await api(`/api/sessions/${sid}`);
  if (v.result !== "ok") {
    app.innerHTML = `<p class="center">读不到这局(${esc(v.result)})。按 B 回卡带架。</p>`;
    return;
  }
  await ensureCartUi(v.cartridge.id);
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
      ${storyCollectionHint(v)}
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
    ? `你在 AI-Gameboy 的《口袋夜铺》里经营一间长期存档的夜铺(MCP 服务名 gameboy,入口 ${S.bridge.mcp_url})。
session_id: ${S.sid}
seat_id: ${t.seat_id}
seat_token: ${t.seat_token}
请先调用 game_observe(session_id, seat_token) 看店铺,再按 legal_actions 用 game_act 经营。
你是唯一店主,可以连续执行许多个 work_shift,不必等待观看者;想停时直接停下,
介绍后先请人类替你掷启动资金(11-66 的数，必须由人类掷)，用 set_start_funds 登记后开店。之后人类只观看，无需等待或按门铃。
run_shifts 可连续淘货、修理或整理（count最多6，reserve现金保留线，stop_on=new/rare/event）。
遇到 pending_event 用 choose_event 自行决定。图鉴保留已发现旧物和见闻，卖掉也不消失。
想停时 close_for_now，下次 reopen_shop；mood/public_line 完全可选。`
    : `你在 AI-Gameboy 牌桌上有一个席位(MCP 服务名 gameboy,入口 ${S.bridge.mcp_url})。
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
    const modes = (cart && cart.modes) || [];
    // 只有一种玩法就直接插卡;有得选(或是夜铺)才进选择页
    if (modes.length > 1 || isNightShop(el.dataset.cart)) askMode(el.dataset.cart);
    else insertCartridge(el.dataset.cart, modes[0] === "multi_ai" ? "ai_ai" : modes[0]);
  } else if (a === "create") insertCartridge(S.chooseCart, el.dataset.mode);
  else if (a === "open-save") location.hash = `#/s/${el.dataset.sid}`;
  else if (a === "copy") copyConn(el.dataset.seat, el);
  else if (a === "end") endSession();
  else if (a === "back") location.hash = "#/";
  else if (a === "pick") { S.picked = el.dataset.item; S.lastSnap = ""; redrawSoon(); }
  else if (a === "hu-intro") humanIntroduce();
  else if (a === "night-pause") { S.night.paused = !S.night.paused; S.lastSnap = ""; }
  else if (a === "pc-ident") humanAct("choose_identity", { identity_id: el.dataset.id });
  else if (a === "pc-intent") { S.pc.intent = el.dataset.id; S.lastSnap = ""; redrawSoon(); }
  else if (a === "pc-submit") pcSubmit();
  else if (a === "pc-narrate") pcNarrate(el);
  else (CART_UI[S.currentCartridgeId] || CART_UI._fallback).onAct?.(a, el);
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
