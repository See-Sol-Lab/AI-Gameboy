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
  human: null,          // {token, seatId} — 仅在 observe 成功后设置
  picked: null,         // 人类本轮点选中的 item_id(未提交)
  chooseCart: null,     // 插卡后待选模式的卡带
};

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
  S.lastSnap = ""; S.focusIdx = 0; S.human = null; S.picked = null;
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
    return `<div class="cart focusable" data-act="insert" data-cart="${esc(c.id)}">
      <div class="cart-face">
        <div class="t">${esc(c.name)}</div>
        <div class="a">${esc(c.author)} · 自研</div>
        <div class="m">${esc(c.players.min)}–${esc(c.players.max)} 人 · 约 ${esc(c.minutes)} 分钟${human ? " · 可亲自下场" : ""}</div>
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
  }
  location.hash = `#/s/${r.session_id}`;
}

/* ---------------- 牌局(席位 / 游戏) ---------------- */

async function showSession(sid) {
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
    if (v.status === "finished") { location.replace(`#/m/${sid}`); return; }
    let mine = null;
    if (S.human) {
      const o = await api(`/api/sessions/${sid}/observe`, "POST",
                          { seat_token: S.human.token });
      if (o.result === "ok") mine = o;
    }
    const draft = captureDraft();
    const snap = JSON.stringify([v, mine && mine.revision, mine && mine.public_state,
                                 mine && mine.private_state, S.infoOpen, S.picked,
                                 tokenLost]);
    if (snap === S.lastSnap) return;
    S.lastSnap = snap;
    if (v.status === "lobby") renderSeats(v, mine, tokenLost);
    else renderGame(v, mine, tokenLost);
    restoreDraft(draft);
  };
  await draw();
  S.timer = setInterval(draw, 3000); // 人类自己的视图刷新,不触碰任何 AI 窗口
}

function captureDraft() {
  const tl = document.getElementById("tl-input");
  const nm = document.getElementById("intro-name");
  const nw = document.getElementById("intro-now");
  return { tl: tl && tl.value, nm: nm && nm.value, nw: nw && nw.value };
}
function restoreDraft(d) {
  if (!d) return;
  const tl = document.getElementById("tl-input");
  const nm = document.getElementById("intro-name");
  const nw = document.getElementById("intro-now");
  if (tl && d.tl != null) tl.value = d.tl;
  if (nm && d.nm != null && d.nm !== "") nm.value = d.nm;
  if (nw && d.nw != null) nw.value = d.nw;
}

/* ---- 开局席位 ---- */

function renderSeats(v, mine, tokenLost) {
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

/* ---- 正在游戏:公共骨架 + 每卡带一个台面渲染器(校正 #3) ---- */

function renderGame(v, mine, tokenLost) {
  setScreen("game", "正在游戏");
  powerLed.classList.add("busy");
  const ui = CART_UI[v.cartridge.id] || CART_UI._fallback;
  const talk = (v.public_events || v.recent_public_events || [])
    .map(eventLine).filter(Boolean).join("");
  app.innerHTML = `
    ${tokenLost ? '<p class="center warn-note">人类席令牌无效或已丢失,本局只能旁观。</p>' : ""}
    ${infoPanel()}
    <div class="table-top">
      ${sideSeat(v, v.seats[0])}
      <div class="felt">${ui.felt(v, mine)}</div>
      ${sideSeat(v, v.seats[1])}
    </div>
    ${mine ? ui.myPanel(v, mine) : ""}
    <div class="table-talk">${talk}</div>
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
  "pocket-circuit": {
    felt(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const rows = (ps.revealed || []).map((r) => `
        <div class="mem-round">
          <span class="dim">第${r.round}轮</span>
          <span class="pcard ${r.winner === a.seat_id ? "win" : ""}">${r.cards[a.seat_id]}</span>
          <span class="dim">vs</span>
          <span class="pcard ${r.winner === b.seat_id ? "win" : ""}">${r.cards[b.seat_id]}</span>
          <span class="w">${esc(nameOf(v, r.winner))} 得分</span>
        </div>`).join("");
      return `
        <div class="score">${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
          <span class="colon">:</span>${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}</div>
        <div class="round-line">第 ${ps.round} / ${ps.total_rounds} 轮</div>
        <div class="rounds-mini">${rows}</div>`;
    },
    myPanel() { return ""; },   // 口袋电路暂无人类席模式
    memorial(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const rounds = (ps.revealed || []).map((r) => `
        <div class="mem-round">
          <span class="dim">第${r.round}轮</span>
          <span class="pcard ${r.winner === a.seat_id ? "win" : ""}">${r.cards[a.seat_id]}</span>
          <span class="dim">vs</span>
          <span class="pcard ${r.winner === b.seat_id ? "win" : ""}">${r.cards[b.seat_id]}</span>
          <span class="w">${esc(nameOf(v, r.winner))}</span>
        </div>`).join("");
      const champ = ps.phase === "finished" && ps.winner
        ? `胜者 · ${esc(nameOf(v, ps.winner))} 🏆` : "本局由人类提前收起";
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
      const sitHtml = sit ? `
        <div class="situation">
          <div class="sit-name">${esc(sit.name)}</div>
          <div class="sit-text">${esc(sit.text)}</div>
          <div class="sit-tags">
            ${sit.needs.map((n) => `<span class="chip need">${esc(n)}</span>`).join("")}
            <span class="chip risk">⚠ ${esc(sit.risk)}</span>
          </div>
        </div>` : "";
      const rows = (ps.revealed || []).map((r) => `
        <div class="four-round">
          <span class="dim">第${r.round}轮 · ${esc(r.situation.name)}</span>
          <span>${esc(nameOf(v, a.seat_id))}:${esc(r.choices[a.seat_id].name)}
            (${r.points[a.seat_id] >= 0 ? "+" : ""}${r.points[a.seat_id]})</span>
          <span>${esc(nameOf(v, b.seat_id))}:${esc(r.choices[b.seat_id].name)}
            (${r.points[b.seat_id] >= 0 ? "+" : ""}${r.points[b.seat_id]})</span>
          <span>${r.joint_star ? "★ 共同星" : ""}</span>
        </div>`).join("");
      return `
        <div class="score">${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
          <span class="colon">:</span>${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}</div>
        <div class="round-line">第 ${ps.round} / ${ps.total_rounds} 轮 · 共同星 ${"★".repeat(ps.stars || 0) || "—"}</div>
        ${sitHtml}
        <div class="rounds-mini">${rows}</div>`;
    },
    myPanel(v, mine) {
      if (v.status !== "playing") return "";
      const pending = mine.private_state.my_pending;
      const hand = mine.private_state.hand || [];
      if (pending) {
        const p = hand.find((c) => c.item_id === pending);
        return `<div class="my-panel">
          <div class="dim center">你已暗投:${esc(p ? p.name : pending)} —— 等对面翻牌</div>
        </div>`;
      }
      const myTurn = (mine.waiting_for || []).includes(S.human.seatId);
      if (!myTurn) return "";
      const cards = hand.map((c) => `
        <div class="item-card focusable ${S.picked === c.item_id ? "picked" : ""}"
             data-act="pick" data-item="${esc(c.item_id)}">
          <div class="it-name">${esc(c.name)}</div>
          <div class="it-tags">${c.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
        </div>`).join("");
      const sel = hand.find((c) => c.item_id === S.picked);
      return `<div class="my-panel">
        <div class="dim center">你的口袋(只有你看得见)——选一件暗投:</div>
        <div class="hand-row">${cards}</div>
        ${sel ? `<div class="confirm-bar">
            <span>暗投 <strong>${esc(sel.name)}</strong>?</span>
            <input id="tl-input" maxlength="120" placeholder="附一句桌边话(可空)">
            <button class="soft focusable" data-act="hu-submit">确认暗投</button>
          </div>` : ""}
      </div>`;
    },
    memorial(v) {
      const ps = v.public_state;
      const [a, b] = v.seats;
      const rounds = (ps.revealed || []).map((r) => `
        <div class="mem-four">
          <div class="dim">第${r.round}轮 · ${esc(r.situation.name)} ${r.joint_star ? "· ★" : ""}</div>
          <div>${esc(nameOf(v, a.seat_id))} 掏出「${esc(r.choices[a.seat_id].name)}」
            (${r.points[a.seat_id] >= 0 ? "+" : ""}${r.points[a.seat_id]}) ·
            ${esc(nameOf(v, b.seat_id))} 掏出「${esc(r.choices[b.seat_id].name)}」
            (${r.points[b.seat_id] >= 0 ? "+" : ""}${r.points[b.seat_id]})</div>
        </div>`).join("");
      const champ = ps.phase === "finished"
        ? `个人分 ${ps.scores?.[a.seat_id] ?? 0} : ${ps.scores?.[b.seat_id] ?? 0} · 共同星 ${"★".repeat(ps.stars || 0) || "无"}`
        : "本局由人类提前收起";
      return { rounds, champ,
               scoreLine: `${esc(nameOf(v, a.seat_id))} ${ps.scores?.[a.seat_id] ?? 0}
                 : ${ps.scores?.[b.seat_id] ?? 0} ${esc(nameOf(v, b.seat_id))}` };
    },
  },

  _fallback: {
    felt(v) { return `<div class="dim center">未知卡带 ${esc(v.cartridge.id)}</div>`; },
    myPanel() { return ""; },
    memorial(v) { return { rounds: "", champ: "", scoreLine: "" }; },
  },
};

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

async function humanSubmit() {
  if (!S.picked) return;
  const line = (document.getElementById("tl-input")?.value || "").trim();
  const o = await api(`/api/sessions/${S.sid}/observe`, "POST",
                      { seat_token: S.human.token });
  if (o.result !== "ok") { alert("读不到席位:" + o.result); return; }
  const r = await api(`/api/sessions/${S.sid}/act`, "POST", {
    seat_token: S.human.token,
    expected_revision: o.revision,
    action_id: "choose_item",
    params: { item_id: S.picked },
    table_line: line,
  });
  if (r.result === "ok") S.picked = null;
  else if (r.result === "stale_revision") { /* 下一轮刷新会带来新局面 */ }
  else alert("暗投失败:" + (r.reason || r.result));
  S.lastSnap = "";
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
