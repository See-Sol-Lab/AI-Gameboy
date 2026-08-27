# C期·窗口A 施工交底：world_thread / player_goal 分家 + gen_milestones

依据：`docs/c-period-design.md` 第 2 节与第 6 节施工顺序。
基线：`cartridges/pocket-crossing` v0.3.4，`python -m unittest discover -s tests -q` 118 测全绿。

---

## 0. 本窗口的范围

**做这些：**
- 删除 `public_goal` 必成主线，拆成 `world_thread`（后台自走，不结算）+ `player_goal`（玩家自选）
- 新增 `gen_milestones` 荷官合同：玩家宣告目标后现场拆 2–3 步里程碑
- 新增 `switch_goal` 玩家动作（费 1 时钟）
- 结局 2×2 矩阵：玩家目标成败 × world_thread 走向

**不做这些（留给窗口 B/C，本窗口碰了算越界）：**
- `landing` 降落点、`world_background`/`global_canon`/`local_episode` 三层拆分、`canon_tick` → 窗口B
- `local_thread` 双线、`b_side`、`chronicle_reveal` 语义改造 → 窗口C
- 《口袋跑团》(`cartridges/pocket-tabletop`) 不跟进 C期，一行都不要改

---

## 1. 现状定位（照这个改，别自己找）

### `cartridges/pocket-crossing/rules.py`（1117 行）

| 行 | 符号 | 现在干什么 | 本窗口要动 |
|---|---|---|---|
| 165 | `new_game()` | 初始化 state，`stage="worldgen"`，发 `gen_world` 请求 | 加 `player_goals` 等新字段 |
| 255 | `apply_system()` | 处理 `narration_result`，按 `kind` 分支推进 stage 机 | 加 `gen_milestones` 分支 |
| 348 | `_world_brief()` | 汇总世界卡给荷官/玩家，**含 `public_goal`** | 改 `world_thread` |
| 357 | `_milestones()` | 读 `s["world"]["milestones"]` | 改读逐席目标 |
| 361 | `_current_milestone()` | 返回第一个未完成里程碑 | 改成按席位取 |
| 368 | `_scene_context()` | 拼荷官场景上下文（含 milestones/current_milestone/pacing） | 逐席目标入 ctx |
| 429 | `observe()` | 玩家视角快照 | 暴露自己的目标与进度 |
| 543 | `apply()` | 玩家动作分发 | 挂 `switch_goal` |
| 957–972 | `_resolve()` 里程碑段 | 任一玩家成功→当前里程碑达成、进度+2；全达成→`main_goal_locked` | 改逐席判定 |
| 1055 | `_finish()` | 组装 ending，发 `render_ending` | 加 2×2 矩阵字段 |

关键现状事实（别推翻）：
- 里程碑现在来自 `gen_world` 的 `d["milestones"]`（2–4 步），**校验器禁止措辞含「或」**（`narrator.py:395`），这条纪律要原样继承到 `gen_milestones`。
- `main_goal_locked` 是全局开关，牵动四处：法则失效（`_apply_law_cost` 1020）、余波幕 pacing（`_scene_context` 375）、收卷分支（`_resolve` 980–1011）、时钟冻结（711、905）。**改它要顺着这四处一起过。**
- `_finish()` 已有 `secret_drives` 逐席结算的成熟范式（1055–1078），逐席目标照抄这个形状。

### `narrator.py`（524 行）

| 行 | 符号 | 说明 |
|---|---|---|
| 112 | `call()` | `temp` 按 kind 分档；`VALIDATORS[kind](data, context)` 带 ctx 硬校验 |
| 357 | `PROMPTS` | kind → prompt 构造函数 |
| 368 | `_v_world()` | 世界卡校验，`milestones` 段在 381–397 |
| 523 | `VALIDATORS` | kind → 校验函数 |

新增 `gen_milestones` 要同时登记进 `PROMPTS` 和 `VALIDATORS` 两张表，并写 `_p_milestones` / `_v_milestones`。
`VALIDATORS` 签名统一是 `(d, ctx=None)`，新函数照此。

---

## 2. 改动清单

### 2.1 世界卡合同改造（`narrator.py:_v_world` + `_p_world`）

- `public_goal` 字段改名 `world_thread`：一句话，世界正在发生什么（例："正魔大战正向南方推进"）。
  **它没有里程碑，永不参与结算。**
- `milestones` 字段从 `gen_world` **移除**（校验器删掉 381–397 那段）。里程碑改由 `gen_milestones` 现场生成。
- prompt 里要写清：`world_thread` 是背景大事，**默认离玩家很远**，禁止写成"你们必须去阻止它"。

### 2.2 目标菜单与选择（新 stage）

现有 stage 机：`worldgen → identities_gen → identity → scenegen → scene → … → endinggen → finished`

本窗口插一段，改成：`… → identity → **goal** → milestonegen → scenegen → …`

- `gen_world` 数据里新增 `goal_menu`：2–4 个本地事件，每个 `{id, text}`，是玩家可选的目标菜单。
  校验：每条 `text` ≤ 40 字，可判定，规模不超过 `axes.scope`（沿用 `SCOPE_INTENSITY` 那套烈度预算）。
- 双方选完身份后进 `stage="goal"`，`narration_request=None`，等玩家动作。
- 新玩家动作 `choose_goal`，参数 `{goal_id}` 或 `{custom_text}`（自定义目标，≤40 字）。
- 双方都选定 → 引擎发 `gen_milestones` 请求，`stage="milestonegen"`。

### 2.3 `gen_milestones` 合同（新）

**请求 context：**
```
{"world": _world_brief(s),
 "goals": [{"seat": 席位, "identity": 身份名, "text": 目标原文}, ...],
 "scope": s["axes"]["scope"],
 "scope_intensity": SCOPE_INTENSITY[...]}
```

**返回数据：**
```
{"tracks": [{"seat": 席位, "milestones": [{"id": "...", "text": "..."}, ...]}, ...]}
```

**校验（`_v_milestones`）：**
- 每席 2–3 步
- `id` 在本席内唯一
- `text` **禁止含「或」**（继承 v0.3.1 禁析取铁律，原因见 `pocket-crossing-roadmap`：早期测试中伪人感的根）
- 每步可判定，规模不超过 scope
- 两席目标相同时，里程碑允许相同——但仍各走各的轨

### 2.4 逐席里程碑判定（`rules.py:_resolve` 957–972）

现状是全局单轨：任一玩家成功 → 推进唯一的当前里程碑。

改成：**本幕哪个席位判定 success/critical_success，就推进哪个席位自己的轨。**
- 该席进度 +2（`progress` 保持全局单值，不拆——拆了账本和结局矩阵都要重写，超出本窗口范围）
- 某席全部里程碑达成 → 该席 `goal_locked`
- **所有在场席位的目标都锁定** → `main_goal_locked = True`（沿用现有全局开关，四处联动逻辑一行不用改）

### 2.5 `switch_goal`（新玩家动作）

- 参数同 `choose_goal`
- 费 1 时钟（`clock += 1`）
- 旧目标标记 `abandoned`，旧里程碑轨保留在 state 里备查，**不惩罚、不评价、不进结局措辞**
- 换完立刻发一次 `gen_milestones`（只为该席重拆），`stage="milestonegen"`
- 已 `main_goal_locked` 后禁止换（返回 `IllegalAction`）

### 2.6 结局 2×2 矩阵（`rules.py:_finish` 1055）

`render_ending` 的 context 新增：
```
"player_goals": [{"seat": ..., "identity": ..., "text": ...,
                  "achieved": bool, "abandoned": bool}, ...],
"world_thread": {"text": ..., "outcome": 原典自走结果一句}
```

四象限措辞（写进 `_p_ending` prompt，不写进引擎硬编码）：

| | world_thread 照原典走 | world_thread 被扰动 |
|---|---|---|
| **玩家目标达成** | 你们做成了自己的事，世界照旧转 | 你们做成了，且留下了痕迹 |
| **玩家目标未成** | 没做成，世界也没在意 | 没做成，但世界因你们歪了一点 |

**铁律：「目标失败但世界照旧」是一个完整结局，不是 BE。** `kind` 判定不因目标未达成而自动降级——现有 `_finish` 的 kind/reason 逻辑保持不动，矩阵只影响荷官的成文措辞。

---

## 3. 一处需要项目作者拍板的地方

设计稿第 2 节写"双方各选一个（可同可不同）"，第 5 节结局矩阵却写单数"玩家目标"。双人各持一个目标时，里程碑分不分轨、`main_goal_locked` 算谁的，稿子没定。

**本交底采用的默认方案（上面 2.4 已按此写）：**
> 按席位分轨，各走各的里程碑；全部席位目标锁定才触发 `main_goal_locked`；结局逐席报告成败，照抄 `secret_drives` 的形状。

选它的理由：`secret_drives` 已经是逐席结算的成熟范式，复用它对现有四处联动逻辑零冲击。

**如果项目作者要改成"全桌共用一个目标"**，改动点只有三处：2.2 的 `choose_goal` 改成需双方一致、2.3 的 `tracks` 塌成单轨、2.4 退回现在的全局判定。一句话推翻即可，别自己权衡。

---

## 4. 验收标准

1. `python -m unittest discover -s tests -q` **全绿**，且新测试补进 `tests/test_pocket_crossing.py`（现 740 行 / 118 测）。
2. 新测试至少覆盖：
   - `gen_milestones` 校验器拒掉含「或」的里程碑
   - 逐席里程碑各走各轨，A 席成功不推进 B 席
   - 全席锁定才置 `main_goal_locked`
   - `switch_goal` 扣 1 时钟、旧轨标 abandoned、锁定后拒绝
   - 结局 context 带全四个象限所需字段
   - `world_thread` 永不产生里程碑、永不触发锁定
3. `cartridges/pocket-tabletop` 的 57 个测试**一个不动、一个不红**（narrator 校验器按 ctx 条件生效，别写成无条件）。
4. `manifest.json` 版本 bump 到 **0.4.0**（v0.3 有过忘 bump 的前科）。
5. 旧存档不要求兼容——`data/` 下的历史局允许读不出来，但**不许崩**：`observe()` 遇到缺字段的旧 state 要能降级返回，不要抛异常。

---

## 5. 施工纪律

- **小步提交**：2.1 / 2.2+2.3 / 2.4 / 2.5 / 2.6 各自成一提交，每步测试全绿再进下一步。
- **禁止顺手重构**：看见旁边代码难看也不要动，本窗口只做清单上的事。
- **禁止扩大合同**：荷官该给什么字段清单里写死了，不要"顺便"多要一个字段。
- 反史诗补丁（scope 轴 / 烈度预算 / 三条叙事纪律）是 v0.3 的既有资产，**继承不覆盖**。
- 完工后更新 `docs/c-period-design.md` 第 6 节，把窗口A 标成已落地，并在 `README.md` 版本行同步。
