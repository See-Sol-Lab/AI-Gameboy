/* 跑团2.0：显示确定状态和已获证据，不读取隐藏答案。 */
const TT_ATTR_NAMES = {wisdom:"智慧",stamina:"体力",luck:"幸运"};
const TT_NARR_NAMES = {tt_world:"预写世界与节点",tt_identities:"写身份与旧事",tt_scene:"写第一幕",tt_turn:"核对推断并承接世界变化"};

function ttStories(stories) {
  return (stories || []).map((q) => `<details><summary>${q.status === "resolved" ? "✓" : "◇"} ${esc(q.question)} · 证据${q.clue_count}/2</summary>
    ${(q.clues || []).map((c) => `<p>🔎 ${esc(c.source)}：${esc(c.text)}</p>`).join("")}
    ${q.truth ? `<p>已确认旧事：${esc(q.truth)}</p>` : '<p class="dim">调查取得证据后，选择“推断”并写出结论。</p>'}</details>`).join("");
}

CART_UI["pocket-tabletop"] = {
  seatExtra(v, sid) {
    return CART_UI["pocket-crossing"].seatExtra(v, sid);
  },
  felt(v) {
    const ps = v.public_state;
    const narr = ps.narration_pending ? `<div class="situation"><div class="sit-name">🖋 ${esc(TT_NARR_NAMES[ps.narration_pending])}</div>
      <button class="soft focusable" data-act="pc-narrate">召荷官</button></div>` : "";
    if (!ps.world) return narr + '<p class="center">世界正在成形。</p>';
    const scene = ps.scene;
    const publicStories = (ps.old_stories || []).filter((q) => q.owner === "npc" || q.status === "resolved");
    const last = (ps.history || []).at(-1);
    const report = last ? last.report.filter(line => !line.startsWith("世界已改变：")) : [];
    const bar = (value, total, cls, label) => `<div class="bar-track" role="progressbar" aria-label="${label}" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${value}">
      <div class="bar-fill ${cls}" style="width:${value / total * 100}%"></div></div>`;
    return `${narr}<div class="sit-name center">《${esc(ps.world.world_name)}》</div>
      <details class="situation" data-panel="tt-background" ${ps.scene_index === 0 ? "open" : ""}>
        <summary>故事背景 · 展开重读</summary>
        <p>${esc(ps.world.premise)}</p><p>${esc(ps.world.lore)}</p>
      </details>
      <p class="center">🎯 共同目标：${esc(ps.world.public_goal)}</p>
      <div class="dim center">进度 ${ps.scene_index}/10</div>
      ${bar(ps.scene_index, 10, "ok", "幕次进度")}
      <div class="dim center">危险 ${ps.tracks.danger}/10</div>${bar(ps.tracks.danger, 10, "bad", "危险进度")}
      ${ps.scene_index === 0 ? '<p class="center">准备阶段 · 等待双方选择身份</p>' : ""}
      ${scene ? `<div class="situation"><div class="sit-name">第${ps.scene_index}幕 · ${esc(scene.title)}</div><p>${esc(scene.text)}</p>
        <p>⚡ ${esc(scene.crisis)}</p>${(scene.objects || []).map((o) => `<span class="chip" title="${esc(o.hint)}">${esc(o.name)}</span>`).join("")}</div>` : ""}
      <div class="info-panel">队伍已有物品：${(ps.inventory?.shared || []).map((i) => esc(i.name)).join("、") || "暂无"}</div>
      <details><summary>旧事揭示 ${(ps.old_stories || []).filter(q=>q.status === "resolved").length}/6 · 已知证据</summary>${ttStories(publicStories)}</details>
      ${report.length ? `<div class="report">${report.map((line) => `<p>${esc(line)}</p>`).join("")}</div>` : ""}`;
  },
  myPanel(v, mine) {
    if (!mine || v.status !== "playing") return "";
    if (mine.private_state.my_pending) return '<div class="my-panel">你已提交本幕行动，等待同伴。</div>';
    if (!mine.legal_actions.length) return "";
    if (mine.legal_actions[0].action_id === "choose_identity") {
      return `<div class="hand-row">${mine.private_state.identity_offers.map((c) => `<button class="item-card focusable" data-act="pc-ident" data-id="${esc(c.id)}">
        <div class="it-name">${esc(c.name)}</div><p>${esc(c.origin)}</p><p>擅长${esc(pcIntentName(c.specialty))}</p>
        <p>随身物品：${esc(c.starting_item.name)}</p><p>有两条待调查的身份旧事</p></button>`).join("")}</div>`;
    }
    const targets = mine.private_state.targets || [];
    const items = [...(v.public_state.inventory?.[S.human?.seatId] || []), ...(v.public_state.inventory?.shared || [])];
    const pending = mine.private_state.my_pending;
    if (pending) return '<div class="my-panel">你已提交本幕行动，等待同伴。</div>';
    return `<div class="my-panel"><details><summary>我的旧事与已获证据</summary>${ttStories(mine.private_state.old_stories)}</details>
      <p class="dim">选择本幕目标，然后写你的做法；推断需说明结论和证据，自动核对，不再掷骰。</p>
      <select id="tt-target" aria-label="本幕目标">${targets.map((t) => `<option value="${esc(t.id)}" data-intent="${esc(t.intent || "explore")}">
        ${esc(t.label)}${t.attribute ? `（${TT_ATTR_NAMES[t.attribute]}·目标${t.target}）` : ""}</option>`).join("")}</select>
      <select id="tt-intent" aria-label="自由事件的意图">${Object.entries(PC_INTENT_NAMES).filter(([k])=>k!=="end").map(([k,label])=>`<option value="${k}">${label}</option>`).join("")}</select>
      <textarea id="tt-action" style="width:100%;min-height:5em;box-sizing:border-box;background:rgba(243,236,216,.6);color:inherit;font:inherit" maxlength="240" aria-label="具体行动" placeholder="说明你怎样实现目标，或根据哪些证据推断出了什么"></textarea>
      <select id="tt-item"><option value="">不动用物品</option>${items.map((i)=>`<option value="${esc(i.id)}">${esc(i.name)}（利于${(i.use || []).map(pcIntentName).map(esc).join("／")}）</option>`).join("")}</select>
      <input id="tt-line" maxlength="60" placeholder="桌边话（可空）">
      <button class="soft focusable" data-act="tt-submit">提交本幕行动</button>
      <button class="soft warn focusable" data-act="tt-stop">提议停笔</button></div>`;
  },
  async onAct(action) {
    if (action === "tt-stop") {
      await humanAct("commit", {intent:"end",action:"",target_id:"free"});
      return;
    }
    if (action !== "tt-submit") return;
    const target = document.getElementById("tt-target");
    const selected = target.selectedOptions[0];
    const intent = selected.dataset.intent;
    const params = {target_id:target.value,intent:["free","event"].includes(target.value.split(":")[0]) ? document.getElementById("tt-intent").value : intent,
      action:document.getElementById("tt-action").value.trim()};
    const item = document.getElementById("tt-item").value;
    if (item) params.item_id = item;
    const line = document.getElementById("tt-line").value.trim();
    params.line = line;
    await humanAct("commit",params,line);
  },
  memorial(v) {
    const ps = v.public_state;
    const e = ps.ending;
    const rounds = (ps.history || []).map((h)=>`<div class="mem-sec"><div class="sec-t">第${h.scene_index}幕 · ${esc(h.title)}</div>
      <p>${esc(h.story_text)}</p>${h.report.map((line)=>`<p>${esc(line)}</p>`).join("")}</div>`).join("");
    const original = ps.chronicle_reveal;
    return {rounds:rounds + (e ? `<div class="mem-sec"><div class="sec-t">结局 · ${esc(e.kind)}</div><p>${esc(e.text)}</p></div>` : "")
      + (original ? `<details><summary>原剧本：没有玩家时会怎样</summary><p>${esc(original.original_ending)}</p></details>` : ""),
      champ:`《${esc(ps.world?.world_name)}》 · 玩家写出的新故事`,scoreLine:e ? `【${esc(e.kind)}】` : "未完"};
  },
};
