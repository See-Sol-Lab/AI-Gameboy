const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function page() {
  let now = 0;
  const element = {classList: {add() {}, remove() {}}, addEventListener() {}};
  const context = vm.createContext({
    document: {getElementById: () => element, querySelectorAll: () => []},
    window: {addEventListener() {}}, Date: {now: () => now},
  });
  const source = fs.readFileSync(path.join(__dirname, "../console/web/app.js"), "utf8")
    .replace(/\nroute\(\);\s*$/, "\n");
  vm.runInContext(source, context);
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
