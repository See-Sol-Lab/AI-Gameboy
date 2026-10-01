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
  const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8")
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

test("v0.2 observer panel exposes no gameplay controls", () => {
  const p = page();
  const html = p.run(`CART_UI["pocket-night-shop"].myPanel(
    {status:"playing",cartridge:{version:"0.2.0"},public_state:{}},
    {legal_actions:[{action_id:"knock"}]})`);
  assert.equal(html, "");
});
