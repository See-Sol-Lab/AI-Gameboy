"""合并前检查一张卡带:python tools/check_cartridge.py <卡带id> [...]

维护者审 PR 用,也在 GitHub 上对每个改到卡带的 PR 自动跑。只查机械合约,不评价好不好玩;
真实验收仍然是两个真实 AI 窗口打完一局。退出码 0 = 全过。
"""

from __future__ import annotations

import importlib.util
import json
import random
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE = "PolyForm-Noncommercial-1.0.0"
MODES = {"multi_ai", "human_ai", "solo_ai"}
SEEDS = range(20)
MAX_STEPS = 2000


def load_rules(folder: Path):
    spec = importlib.util.spec_from_file_location(f"cart_{folder.name.replace('-', '_')}", folder / "rules.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(cid: str) -> list[str]:
    folder = ROOT / "cartridges" / cid
    problems: list[str] = []
    bad = problems.append
    if not (folder / "manifest.json").is_file() or not (folder / "rules.py").is_file():
        return [f"cartridges/{cid}/ 里要有 manifest.json 和 rules.py"]

    m = json.loads((folder / "manifest.json").read_text("utf-8"))
    if m.get("id") != cid:
        bad(f"manifest.id 必须等于文件夹名 {cid}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", cid):
        bad("卡带 id 只能用小写字母、数字和连字符")
    for key in ("name", "version", "author"):
        if not isinstance(m.get(key), str) or not m[key].strip():
            bad(f"manifest.{key} 必填")
    if not re.fullmatch(r"\d+\.\d+\.\d+", str(m.get("version", ""))):
        bad("manifest.version 要写成 1.0.0 这样的三段数字")
    if m.get("license") != LICENSE:
        bad(f"manifest.license 必须是 {LICENSE}")
    if m.get("dealer", "none") != "none":
        bad("社区卡带暂不支持荷官(dealer 必须是 none)")
    players = m.get("players") or {}
    lo, hi = players.get("min"), players.get("max")
    if not (isinstance(lo, int) and isinstance(hi, int) and 1 <= lo <= hi <= 2):
        bad("manifest.players 要写 {min, max},目前掌机支持 1–2 人")
    modes = set(m.get("modes") or [])
    if not modes or not modes <= MODES:
        bad(f"manifest.modes 只能从 {sorted(MODES)} 里选")
    if problems:
        return problems

    rules = load_rules(folder)
    for name in ("new_game", "observe", "apply", "sample_actions", "IllegalAction"):
        if not hasattr(rules, name):
            bad(f"rules.py 缺少 {name}")
    if problems:
        return problems

    seat_counts = sorted({n for n in (1, 2) if lo <= n <= hi})
    for n in seat_counts:
        seats = ["seat_a", "seat_b"][:n]
        for seed in SEEDS:
            problems += play_through(rules, seats, seed)
            if problems:
                return problems

    ui = folder / "ui.js"
    if ui.exists() and shutil.which("node"):
        r = subprocess.run(["node", "--check", str(ui)], capture_output=True, text=True)
        if r.returncode:
            bad("ui.js 语法错误:" + r.stderr.strip())
    return problems


def play_through(rules, seats, seed) -> list[str]:
    where = f"[{len(seats)} 人 · seed {seed}]"
    a = rules.new_game(list(seats), seed)
    b = rules.new_game(list(seats), seed)
    if json.dumps(a, sort_keys=True, ensure_ascii=False) != json.dumps(b, sort_keys=True, ensure_ascii=False):
        return [f"{where} 同样的 seats 和 seed,new_game 结果不一样(随机数要从 seed 来)"]
    state = a
    pick = random.Random(seed)
    for step in range(MAX_STEPS):
        try:
            json.dumps(state)
        except TypeError:
            return [f"{where} 第 {step} 步:局面里有存不进 JSON 的东西"]
        if state.get("phase") not in ("playing", "finished"):
            return [f"{where} 第 {step} 步:phase 只能是 playing 或 finished"]
        views = {}
        for seat in seats:
            ob = rules.observe(deepcopy(state), seat)
            for key in ("public_state", "private_state", "legal_actions", "waiting_for"):
                if key not in ob:
                    return [f"{where} observe 缺少 {key}"]
            views[seat] = ob
        publics = {json.dumps(v["public_state"], sort_keys=True, ensure_ascii=False) for v in views.values()}
        if len(publics) > 1:
            return [f"{where} 第 {step} 步:不同席位看到的 public_state 不一样——公开局面里混进了某一席的私有信息"]
        if state["phase"] == "finished":
            return []

        before = json.dumps(state, sort_keys=True)
        try:
            rules.apply(state, seats[0], "__no_such_action__", {})
            return [f"{where} 不存在的动作没有被拒绝(应抛 IllegalAction)"]
        except rules.IllegalAction:
            pass
        if json.dumps(state, sort_keys=True) != before:
            return [f"{where} apply 改动了传进来的局面(要先 deepcopy 再改)"]

        movers = [s for s in seats if rules.sample_actions(deepcopy(state), s)]
        if not movers:
            return [f"{where} 第 {step} 步:还没结束,但没有任何一席能行动(卡死)"]
        seat = pick.choice(movers)
        if not views[seat]["legal_actions"]:
            return [f"{where} 第 {step} 步:sample_actions 说 {seat} 能动,observe 却没给 legal_actions"]
        action_id, params = pick.choice(rules.sample_actions(deepcopy(state), seat))
        try:
            state = rules.apply(state, seat, action_id, params)
        except rules.IllegalAction as e:
            return [f"{where} sample_actions 给出的 {action_id} {params} 被 apply 拒绝:{e}"]
        if json.dumps(state, sort_keys=True) == before:
            return [f"{where} 合法动作 {action_id} 没有改变局面"]
    return [f"{where} 走了 {MAX_STEPS} 步还没到 finished"]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    failed = False
    for cid in argv:
        problems = check(cid)
        print(("✓ " if not problems else "✗ ") + cid)
        for p in problems:
            print("   - " + p)
        failed |= bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
