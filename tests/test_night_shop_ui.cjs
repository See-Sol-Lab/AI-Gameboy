const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function page() {
  let now = 0;
  const element = {classList: {add() {}, remove() {}}, addEventListener() {}, querySelectorAll: () => []};
  const context = vm.createContext({
    document: {getElementById: () => element, querySelectorAll: () => []},
    window: {addEventListener() {}}, Date: {now: () => now},
  });
  const source = fs.readFileSync(path.join(__dirname, "../console/web/app.js"), "utf8")
    .replace(/\nroute\(\);\s*$/, "\n");
  vm.runInContext(source, context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,"../cartridges/pocket-tabletop/ui.js"),"utf8"),context);
  return {
    run(code) { return vm.runInContext(code, context); },
    time(value) { now = value; },
  };
}

test("batched journals queue every entry, deduplicate and advance in order", () => {
  const p = page();
  p.run(`updateNightPlayback("one", {playback_entries: Array.from({length:12}, (_, i) => ({seq:i+1}))})`);
  assert.equal(p.run("S.night.active.seq"), 1);
  assert.equal(p.run("S.night.queue.length"), 11);
  p.run(`updateNightPlayback("one", {playback_entries: [{seq:12},{seq:13},{seq:14}]})`);
  assert.equal(p.run("S.night.queue.length"), 13);
  p.time(4999);
  p.run(`updateNightPlayback("one", {playback_entries: []})`);
  assert.equal(p.run("S.night.active.seq"), 1);
  p.time(5000);
  p.run(`updateNightPlayback("one", {playback_entries: []})`);
  assert.equal(p.run("S.night.active.seq"), 2);
  assert.equal(p.run("S.night.cursor"), 14);
});

test("pause only holds the display, new journal entries still arrive", () => {
  const p = page();
  p.run(`updateNightPlayback("one", {playback_entries: [{seq:1}]}); S.night.paused = true;`);
  p.time(6000);
  p.run(`updateNightPlayback("one", {playback_entries: [{seq:2},{seq:3}]})`);
  assert.equal(p.run("S.night.active.seq"), 1);
  assert.equal(p.run("S.night.queue.length"), 2);
  p.run(`S.night.paused = false; updateNightPlayback("one", {playback_entries: []})`);
  assert.equal(p.run("S.night.active.seq"), 2);
});

test("catalogue escapes supplied text and never invents undiscovered entries", () => {
  const p = page();
  const html = p.run(`nightCollection({
    locations:[{id:"lane", name:"旧货巷", description:"街角", cost:1, unlocked:true, undiscovered:7}],
    collection:{found:1,total:16,revealed:0,entries:[{name:"<img onerror=x>", code:"one",
      rarity:"common", story:"test", first_day:1, first_location:"lane",count:1,revealed:null}]},
    encounters:{found:0,total:5,entries:[]}
  })`);
  assert.ok(html.includes("&lt;img onerror=x&gt;"));
  assert.ok(!html.includes("<img onerror"));
  assert.ok(html.includes("尚未修复揭秘"));
  assert.ok(html.includes("1/16"));
});

test("current observer panel exposes no gameplay controls", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-night-shop"].myPanel(
    {status:"playing",cartridge:{version:"0.3.0"},public_state:{}},
    {legal_actions:[{action_id:"knock"}]})`);
  assert.equal(html, "");
});

test("tabletop display tracks act count and danger while keeping changes for the ending card", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-tabletop"].felt({seats:[],public_state:{ruleset:2,world:{world_name:"海港"},
    scene_index:9,tracks:{progress:1,progress_total:3,danger:2},main_complete:false,
    main_nodes:[{title:"取得钥匙",done:true,effort:2},{title:"修好海堤",done:false,effort:1}],
    npc:{available:false,location_name:"钟楼"},old_stories:[{owner:"npc",question:"谁留下钥匙",status:"open",clue_count:1,
    clues:[{source:"照片",text:"照片中出现见证人甲"}],truth:null}],
    scene:{title:"新的海港",text:"本幕的剧情",crisis:"眼前的危机"},
    world_changes:[{scene_index:1,seat:"seat_a",text:"修好了旧海堤"}],
    history:[{scene_index:1,title:"修堤",story_text:"过去的剧情",report:["检定成功", "世界已改变：修好了旧海堤"]}]}})`);
  for (const label of ["进度 9/10","证据1/2","见证人甲","危险 2/10","第9幕 · 新的海港"]) assert.ok(html.includes(label),label);
  assert.equal((html.match(/role="progressbar"/g) || []).length, 2);
  assert.ok(html.includes('aria-label="幕次进度" aria-valuemin="0" aria-valuemax="10" aria-valuenow="9"'));
  assert.ok(html.includes('style="width:90%"'));
  assert.ok(html.includes('aria-label="危险进度" aria-valuemin="0" aria-valuemax="10" aria-valuenow="2"'));
  assert.ok(!html.includes("NPC位置"));
  for (const label of ["主线完成", "主线阶段详情", "玩家改变的世界", "修好了旧海堤"]) assert.ok(!html.includes(label),label);
  const memorial = p.run(`CART_UI["pocket-tabletop"].memorial({public_state:{world:{world_name:"海港"},
    history:[{scene_index:1,title:"修堤",story_text:"过去的剧情",report:["检定成功", "世界已改变：修好了旧海堤"]}],
    ending:{kind:"HE",text:"新的生活开始了。"}}})`);
  assert.ok(memorial.rounds.includes("修好了旧海堤"));
  assert.ok(!html.includes("时钟"));
  assert.ok(!html.includes("null"));
});

test("both seats have escaped table bubbles on opposite sides", () => {
  const p = page();
  for (const [seat, side] of [["seat_a", "left"], ["seat_b", "right"]]) {
    const html = p.run(`eventLine({kind:"table_line",seat_id:${JSON.stringify(seat)},
      display_name:"<玩家>",text:"<script>留言</script>",t:"2026-01-01T16:00:00"})`);
    assert.ok(html.includes(`talk-${side}`));
    assert.ok(html.includes("&lt;玩家&gt;"));
    assert.ok(html.includes("&lt;script&gt;留言&lt;/script&gt;"));
  }
});

test("tabletop public background is readable before roles without revealing the original ending", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-tabletop"].felt({seats:[],public_state:{stage:"identity",scene_index:0,
    world:{world_name:"回音市",premise:"你们醒在末班电车。",lore:"市民的名字正从<档案>中消失。",
      public_goal:"抵达控制室，逆转遗忘波。",original_ending:"HIDDEN_TRAGEDY"},
    tracks:{progress:0,progress_total:3,danger:0},main_nodes:[],old_stories:[],history:[]}})`);
  for (const text of ["故事背景", "你们醒在末班电车", "名字正从&lt;档案&gt;中消失", "逆转遗忘波", "准备阶段"])
    assert.ok(html.includes(text), text);
  assert.ok(html.includes('data-panel="tt-background" open'));
  assert.ok(!html.includes("第0/10幕"));
  assert.ok(!html.includes("HIDDEN_TRAGEDY"));
  assert.ok(html.indexOf("</details>") < html.indexOf("共同目标："));
});

test("human adventure submission sends the message to both the card and public table", async () => {
  const p = page();
  p.run(`S.pc.intent="confront"; var submitted;
    document.getElementById=(id)=>({value:({"pc-action":"举起桨","pc-item":"oar","pc-line":"  我来！  "})[id] || "",checked:false});
    humanAct=async(action,params,line)=>{submitted={action,params,line};return {result:"ok"};};`);
  await p.run("pcSubmit()");
  assert.equal(p.run("submitted.line"), "我来！");
  assert.equal(p.run("submitted.params.line"), "我来！");
  assert.equal(p.run("submitted.params.intent"), "confront");
  assert.equal(p.run("submitted.action"), "commit");
});

test("adventure item uses and intent labels are Chinese while submitted codes stay intact", () => {
  const p = page();
  p.run('S.human={seatId:"seat_a"}; S.pc.intent="confront"');
  for (const id of ["pocket-crossing"]) {
    const html = p.run(`CART_UI[${JSON.stringify(id)}].myPanel({status:"playing",public_state:{inventory:{
      seat_a:[{id:"oar",name:"半刻之桨",use:["confront","recover"]}],
      shared:[{id:"map",name:"地图",use:["advance","explore","support"]}]}}},
      {private_state:{},legal_actions:[{action_id:"commit"}]})`);
    assert.ok(html.includes('value="oar">动用:半刻之桨(利于对抗／休整)'));
    assert.ok(html.includes("利于推进／探索／支援"));
    assert.ok(html.includes('data-id="confront">对抗'));
    assert.ok(!html.includes("confront/recover"));
    const pending = p.run(`CART_UI[${JSON.stringify(id)}].myPanel({status:"playing"},
      {private_state:{my_pending:{intent:"recover"}}})`);
    assert.ok(pending.includes("你已暗投【休整】"));
    const seat = p.run(`CART_UI[${JSON.stringify(id)}].seatExtra({public_state:{identities:{seat_a:{name:"旅人",specialty:"explore"}}}},"seat_a")`);
    assert.ok(seat.includes("擅探索"));
  }
});

test("tabletop player chooses a fixed target and sees Chinese item uses", () => {
  const p = page();
  p.run('S.human={seatId:"seat_a"}');
  const html = p.run(`CART_UI["pocket-tabletop"].myPanel({status:"playing",public_state:{ruleset:2,inventory:{seat_a:[{id:"tool",name:"铜剪",use:["confront","recover"]}]}}},
    {legal_actions:[{action_id:"commit"}],private_state:{targets:[{id:"main:m1",label:"取钥匙",intent:"advance",attribute:"wisdom",target:7}],old_stories:[]}})`);
  for (const label of ["智慧·目标7","利于对抗／休整",'value="main:m1"','data-act="tt-submit"']) assert.ok(html.includes(label),label);
  assert.ok(!html.includes("confront/recover"));
});

test("narrator failure explains retry and restores the summon button", async () => {
  const p = page();
  p.run(`var alerts=[], calls=0;
    var alert=(text)=>alerts.push(text);
    var fetch=async()=>{calls++; return {json:async()=>({result:"narrator_error",message:"gift.kind 不在菜单里"})};};
    var button={disabled:false,textContent:"召荷官"};`);
  await p.run("pcNarrate(button)");
  assert.ok(p.run("alerts[0]").includes("已有游戏进度保留"));
  assert.ok(p.run("alerts[0]").includes("重新点击「召荷官」"));
  assert.ok(p.run("alerts[0]").includes("gift.kind"));
  assert.equal(p.run("button.disabled"), false);
  assert.equal(p.run("button.textContent"), "召荷官");
  assert.equal(p.run("calls"), 1);
});

test("night shop offers a permanent close button after its display without changing gameplay controls", () => {
  const p = page();
  p.run(`renderGame({cartridge:{id:"pocket-night-shop"},session_id:"synthetic",seats:[{seat_id:"seat_a",display_name:"店主"}],
    public_state:{day:1,inventory:[],locations:[],collection:{entries:[]},encounters:{entries:[]}}},null,false)`);
  const html = p.run("app.innerHTML");
  assert.ok(html.includes('data-act="end">彻底关店'));
  assert.ok(html.indexOf("彻底关店") > html.indexOf("每次行动自动保存"));
  assert.ok(html.includes("关店后无法续玩"));
});

test("permanent close requires confirmation and uses the existing archive endpoint", async () => {
  const p = page();
  p.run(`S.currentCartridgeId="pocket-night-shop"; S.sid="synthetic";
    var promptText="", requests=[];
    var confirm=(message)=>{promptText=message; return false;};
    var fetch=async(path,options)=>{requests.push({path,method:options.method}); return {json:async()=>({result:"ok"})};};`);
  await p.run("endSession()");
  assert.equal(p.run("requests.length"), 0);
  assert.ok(p.run("promptText").includes("无法再续玩"));
  assert.ok(p.run("promptText").includes("图鉴会保留"));
  p.run("confirm=()=>true");
  await p.run("endSession()");
  assert.equal(p.run("requests.length"), 1);
  assert.equal(p.run("requests[0].path"), "/api/sessions/synthetic/end");
  assert.equal(p.run("requests[0].method"), "POST");
});

test("full journal keeps paged history beyond recent entries and resets between shops", () => {
  const p = page();
  for (let offset = 0; offset < 250; offset += 100) {
    p.run(`updateNightPlayback("one", {playback_entries: Array.from({length:${Math.min(100, 250-offset)}},
      (_, i) => ({seq:i+${offset+1}}))})`);
  }
  p.run(`updateNightPlayback("one", {playback_entries:[{seq:250}]})`);
  assert.equal(p.run("S.night.journal.length"), 250);
  assert.equal(p.run("S.night.journal[0].seq"), 1);
  assert.equal(p.run("S.night.journal[249].seq"), 250);
  p.run(`updateNightPlayback("two", {playback_entries:[{seq:1}]})`);
  assert.equal(p.run("S.night.journal.length"), 1);
});

test("journal renders public context and offers safely, without inventing old context", () => {
  const p = page();
  const html = p.run(`nightJournalEntry({seq:1,day:1,shift:"黄昏",focus:"sell",
    goal:"找新主人",customer:{name:"老师",visits:1,request:"留住声音",clue:"<script>"},
    offer:{item_name:"怀表",asking_price:5},text:"不合需要",coins_delta:0,reputation_delta:0})`);
  assert.ok(html.includes("找新主人"));
  assert.ok(html.includes("留住声音"));
  assert.ok(html.includes("怀表"));
  assert.ok(html.includes("报价5枚"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("<details class=\"night-journal-entry\" open"));
  const old = p.run(`nightJournalEntry({seq:2,day:1,shift:"深夜",focus:"tidy",text:"整理货架",
    coins_delta:3,reputation_delta:0})`);
  assert.ok(old.includes("早期记录未保存"));
  assert.ok(!old.includes("老师"));
});

test("full journal precedes inventory and catalogue and is collapsed initially", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-night-shop"].felt({seats:[{seat_id:"seat_a",display_name:"店主"}],
    public_state:{day:2,shift:"黄昏",coins:5,reputation:0,shop_level:1,capacity:6,current_goal:"经营",
      journal_total:0,inventory:[],locations:[],
      collection:{found:0,total:16,revealed:0,entries:[]},encounters:{found:0,total:5,entries:[]}}})`);
  assert.ok(html.indexOf("逐轮经营记录") < html.indexOf("橱窗与货架"));
  assert.ok(html.indexOf("逐轮经营记录") < html.indexOf("异物志"));
  assert.ok(!html.includes("data-panel=\"history\" open"));
  assert.ok(!html.includes("最近五班"));
});

test("five rarity titles and tier gate are visible without revealing unknown items", () => {
  const p = page();
  const html = p.run(`nightCollection({shop_level:2,locations:[],
    rarities:[{label:"上古",found:0,total:9,min_level:3},{label:"遗世",found:0,total:5,min_level:3}],
    collection:{found:0,total:72,revealed:0,entries:[]},encounters:{found:0,total:18,entries:[]}})`);
  assert.ok(html.includes("上古 0/9"));
  assert.ok(html.includes("遗世 0/5"));
  assert.ok(html.includes("3级开放"));
  assert.ok(!html.includes("undefined"));
});

test("earned endings are readable with progress and safely escaped text", () => {
  const p = page();
  assert.equal(p.run(`nightEndings({endings:[]})`), "");
  const html = p.run(`nightEndings({endings:[{id:"collection",title:"第七面墙",day:291,
    reward:"铭牌",paragraphs:["<script>秘密</script>"]}],
    completion:{discoveries:72,items_total:72,secrets:12,guests:35,guests_total:86,true_ending:false}})`);
  assert.ok(html.includes("第291日"));
  assert.ok(html.includes("秘密 12/72"));
  assert.ok(html.includes("来客 35/86"));
  assert.ok(html.includes("&lt;script&gt;"));
  assert.ok(!html.includes("<script>"));
  assert.ok(!html.includes("莉莉丝"));
  const ending = p.run(`nightEndings({endings:[{id:"true_ending",title:"夜铺之外",day:400,
    reward:"钥匙",paragraphs:["门开了"]}], completion:{true_ending:true}})`);
  assert.ok(ending.includes("真正通关"));
  assert.ok(ending.includes("仍可继续经营"));
  assert.ok(ending.includes("night-ending-tunnel"));
});

test("story collection hint is limited to completed adventures with a written ending", () => {
  const p = page();
  for (const id of ["pocket-crossing", "pocket-tabletop"]) {
    const html = p.run(`storyCollectionHint({cartridge:{id:${JSON.stringify(id)}},status:"finished",public_state:{ending:{text:"故事落幕"}}})`);
    assert.ok(html.includes("帮我收藏这一局的剧情"));
    assert.ok(html.includes(".md"));
    assert.ok(html.includes(".txt"));
  }
  assert.equal(p.run(`storyCollectionHint({cartridge:{id:"pocket-night-shop"},status:"finished",public_state:{ending:{text:"结束"}}})`), "");
  assert.equal(p.run(`storyCollectionHint({cartridge:{id:"pocket-crossing"},status:"finished",public_state:{ending:null}})`), "");
  assert.equal(p.run(`storyCollectionHint({cartridge:{id:"pocket-crossing"},status:"playing",public_state:{ending:{text:"结束"}}})`), "");
});

test("updated spectator screen shows five shifts, sand, scroll, witch and closed maps", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-night-shop"].felt({seats:[{seat_id:"seat_a",display_name:"店主"}],
    public_state:{day:20,shift:"下午",shift_number:2,shifts_per_day:5,coins:30,stardust:22,reputation:10,
      shop_level:3,capacity:12,current_goal:"补货",journal_total:0,inventory:[],
      door:"下午还没开门，客人傍晚才来",scroll:"第20天打烊前使用",summon_goods:"货物飞来：99古币指定召货",exchange_resources:"1星沙换2古币，1声望换1古币",customer:null,
      last_run:{completed:1,requested:6,stop_reason:"scroll",stop_text:"拿到卷轴"},
      witch:{can_sell:2,hint:"上古八折",stock:[{name:"<旧物>",rarity:"ancient",condition:0,price:12}]},
      locations:[{id:"lane",name:"旧货巷",description:"故事已讲完",cost:2,undiscovered:0,closed:true,unlocked:true}],
      collection:{found:10,total:72,revealed:5,entries:[]},encounters:{found:2,total:24,entries:[]}}})`);
  for (const text of ["第2/5班", "星沙", "22", "下午还没开门", "限时传送卷轴", "魔女莉莉丝的摊位",
                      "上古八折", "&lt;旧物&gt;", "已关闭", "下午半价", "拿到限时卷轴", "99古币指定召货", "1星沙换2古币"]) assert.ok(html.includes(text), text);
  assert.ok(!html.includes("<旧物>"));
  assert.ok(!html.includes("眼下没有可接待的新来客"));
  assert.ok(!html.includes("data-act=\"teleport\""));
});

test("earned waiting-item hints appear on guest and customer book with escaped names", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-night-shop"].felt({seats:[{seat_id:"seat_a",display_name:"店主"}],
    public_state:{day:20,shift:"傍晚",coins:30,reputation:10,shop_level:5,capacity:12,inventory:[],
      customer:{name:"客人",visits:2,patience:2,clue:"线索",waiting_item:{name:"<指定旧物>"}},
      customer_book:[{name:"客人",visits:2,clue:"线索",waiting_item:{name:"<指定旧物>"},bond:true}],
      locations:[],collection:{found:72,total:72,revealed:72,entries:[]},encounters:{found:0,total:48,entries:[]}}})`);
  assert.equal((html.match(/等待的旧物：/g) || []).length, 2);
  assert.ok(html.includes("修满后交付"));
  assert.ok(html.includes("（已完成）"));
  assert.ok(html.includes("&lt;指定旧物&gt;"));
  assert.ok(!html.includes("<指定旧物>"));
});

test("bankrupt ending does not claim collection success or a null reward", () => {
  const p = page();
  const html = p.run(`nightEndings({bankrupt:true,endings:[{id:"closed",title:"落叶封门",day:10,
    reward:null,paragraphs:["灯熄了"]}],completion:{true_ending:false}})`);
  assert.ok(html.includes("夜铺已关闭"));
  assert.ok(!html.includes("异物志收齐"));
  assert.ok(!html.includes("纪念奖励"));
  assert.ok(!html.includes("null"));
  const memorial = p.run(`CART_UI["pocket-night-shop"].memorial({public_state:{bankrupt:true,day:10,coins:0,
    reputation:0,shop_level:2,capacity:10,inventory:[],locations:[],diary:[],
    collection:{found:3,total:72,revealed:1,entries:[]},encounters:{found:2,total:24,entries:[]},
    endings:[{id:"closed",title:"落叶封门",day:10,reward:null,paragraphs:["灯熄了"]}]}})`);
  assert.ok(memorial.rounds.includes("灯熄了"));
  assert.ok(memorial.rounds.includes("异物志"));
});

test("local and cloud seat texts use the same seat but different explicit entries", () => {
  const p = page();
  p.run(`S.sid="synthetic-session"; S.currentCartridgeId="pocket-tabletop";
    S.bridge={local_mcp_url:"http://127.0.0.1:7777/mcp",remote_mcp_url:"https://example.invalid/mcp",remote_kind:"fixed"}`);
  const local = p.run(`seatConnectionText({seat_id:"seat_a",seat_token:"synthetic-seat-token"},"local")`);
  const cloud = p.run(`seatConnectionText({seat_id:"seat_a",seat_token:"synthetic-seat-token"},"cloud")`);
  assert.ok(local.includes("http://127.0.0.1:7777/mcp"));
  assert.ok(!local.includes("https://example.invalid"));
  assert.ok(cloud.includes("https://example.invalid/mcp"));
  assert.ok(!cloud.includes("http://127.0.0.1"));
  for (const text of [local,cloud]) {
    assert.ok(text.includes("session_id: synthetic-session"));
    assert.ok(text.includes("seat_token: synthetic-seat-token"));
  }
  assert.ok(cloud.includes("只有你使用人类已配置的私有续席连接时"));
  const buttons = p.run(`seatCopyButtons("seat_a")`);
  assert.ok(buttons.includes('class="seat-copy-actions"'));
  assert.ok(buttons.includes("给云端AI"));
  assert.equal((buttons.match(/<button /g) || []).length, 2);
  assert.ok(!buttons.includes("复制 seat_a"));
  const hint = p.run("playerEntryHint()");
  assert.ok(hint.includes("同一台游戏机"));
  assert.ok(hint.includes("<br>"));
  assert.ok(!hint.includes("502"));
  assert.ok(!hint.includes("本地模式"));
  p.run("S.bridge.remote_mcp_url=null");
  assert.equal(p.run(`seatConnectionText({seat_id:"seat_a",seat_token:"synthetic"},"cloud")`), null);
  assert.ok(!p.run(`seatCopyButtons("seat_a")`).includes("给云端AI"));
});

test("grand slam memorial is a closing card with three trophies and the last words", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-night-shop"].memorial({public_state: {
    endings: [{id: "grand_slam", title: "万灯送行", day: 300, paragraphs: ["风铃最后响了一次。", "此间夜铺已经结业。\\n店主带着所有故事"]}],
    closing_record: {title: "万灯送行", day: 300,
      trophies: [{title: "第七面墙", day: 200, reward: "铭牌"}, {title: "夜铺之外", day: 280, reward: "钥匙"},
                 {title: "万灯送行", day: 300, reward: "装着整间夜铺的一盏小灯"}],
      keepsakes: [{name: "停在四点的怀表", rarity: "寻常"}],
      notes: {days: 300, guests: 86, revealed: 72, farewells: 24, lines: 72},
      last_words: {name: "钟表匠", line: "都是一种钟。", item: "扁瓶", day: 300},
      epilogue: "此间夜铺已经结业。"}}})`);
  assert.equal(html.scoreLine, "🏆🏆🏆 大满贯");
  assert.equal((html.rounds.match(/class="night-trophy"/g) || []).length, 3);
  for (const piece of ["装着整间夜铺的一盏小灯", "说出口的话 72 句", "「都是一种钟。」", "停在四点的怀表", "今夜照常营业。", "店铺已收起"]) {
    assert.ok(html.rounds.includes(piece), piece);
  }
  assert.ok(html.rounds.includes("此间夜铺已经结业。<br>"));
  assert.ok(!html.rounds.includes("mem-round"));     // 不留流水账
});
