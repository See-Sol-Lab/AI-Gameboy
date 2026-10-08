/* 《口袋电路》的界面——也是卡带界面的示例写法。

   卡带界面是可选的:cartridges/<卡带id>/ui.js 存在时,掌机会在显示这张卡带前加载它;
   没有就用通用显示(公开局面 + 可做的动作),也能玩。

   约定:往 CART_UI 里登记一个以卡带 id 为键的对象,掌机只调用这几项——
     felt(v, mine)      中间台面。v 是公开视图(/api/sessions/<id>),人人都能看,绝不含私牌
     myPanel(v, mine)   人类自己席位的操作区。mine 是人类这一席的 observe 结果(有私牌),没坐下时为 null
     memorial(v)        纪念卡,返回 { rounds, champ, scoreLine } 三段 HTML
     onAct(name, el)    可选。页面上 data-act="<name>" 的元素被点击 / 按 A 时调用

   能直接用的掌机小工具:esc(文本转义,拼 HTML 前一定要用)、nameOf(v, 席位id)、
   humanAct(action_id, params, 桌边话) 以人类席身份提交动作。 */

CART_UI["pocket-circuit"] = {
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

  onAct(name, el) {
    if (name === "circuit-card") circuitPlay(Number(el.dataset.card));
  },
};

async function circuitPlay(card) {
  if (!confirm(`锁定电压 ${card}？本轮不能更改。`)) return;
  const line = (document.getElementById("circuit-line")?.value || "").trim();
  await humanAct("play_card", { card }, line);
}
