"""《口袋穿越》规则 v0.6(三维与随机事件版)。

v0.6 新增(莉莉丝定案,源自 10-09 菲博×Sol 联机局):
- 结局三档:危险满10当场 BE;进度满10当场锁定(不再回退,法则扣不动),之后可继续推各自目标,
  其余收场都是 TE;只有进度锁定+危险未满+两人都活着+双方目标都达成+支线了结才是 HE。
- 身份三维:选身份时引擎掷出 智慧/体力/幸运 各1-6,不影响行动骰。
- 随机事件:荷官在某幕写一件 event(只选难度 easy/normal/hard),两人各掷1骰,
  幸运≥5者多掷1骰;两人三维之和+所有骰 ≥ 目标值(24/28/31)则危险-2,否则危险+2。
  每局 2-5 次,引擎按幕数要求或禁止荷官写事件——给危险一条回落的路。
- 私密目标菜单只留引擎算得出的判定(删掉游戏里无从达成的"共享行囊≥3件")。


v0.5 新增·C期窗口B:世界三层拆分(world_background/global_canon/local_episode)。
worldgen 只写大世界与三个降落点,玩家选定落点后由 gen_episode 生成本局那一段
——同一颗世界种子能掉进三个完全不同的角落。global_canon.ticks 每两幕自走一行,
只作背景,除「天下大势」外禁止与本幕合流。

v0.4 新增:world_thread 仅作背景自走;两席自选 player_goal,荷官现场拆分逐席
里程碑;可花1时钟换目标;结局按目标成败 × 世界线走向成文。

v0.3.2 新增·B期 NPC响应协议(源自早期测试中的 NPC 回应问题):
- target 扩展:除 'npc'(暗典追查)外,可点名本幕任意在场对象正面交涉;
  判定不失败即挂"回应债",下一幕荷官必须交 npc_responses(六枚举+实质内容),
  校验器把关,没有"没有回应"这个选项;回应经引擎入账为既成事实。
- npc_book 台帐:对象登场记录;登场过的再进 objects 必须带 change(状态变化),
  否则废稿——治"糖人奶奶反复渲染同一个神秘姿势"式刷脸。
- 追问机制:commit 可带 about(逐字引用未解悬事)+target,判定成功=逼问一次,
  两次(卓越算两次)引擎当场揭谜底——问对了人、点对了悬事本身就是解谜成果,
  不许守门守到终局。
- 锁定收卷:主线锁定且支线全清时当场结算,不再发空转的余波幕。

v0.3 新增(源自早期测试反馈):
- 支线暗典:worldgen 时预写 2 条支线悬案(谜题+定死的谜底),谜底玩家不可见;
  一条绑剧情 NPC(在 1..10 幕中随机两个登场窗口,可错过、可翻盘),
  一条绑数值考验(默契/探索胜场/对抗胜场达标即自动揭示)。
- 悬事生命周期:hooks 由引擎全权管理 = 未解支线的谜题原句;荷官不得增殖同义悬事。
- 主线锁定即冻结:main_goal_locked 后进度与时钟不再变动(法则失效)。
- 提议停笔不再折算成休整:单方 end = 静候,不掷骰、不触发法则。
- 幕数走满由引擎强制结算,不再依赖双方同意。

与 v0.1 的机制完全相同(账本/骰子/法则/隐藏线/三类结局),区别只有一个:
世界、身份池、每一幕场景、结局文本改由叙事荷官(外部 API)按合同生成,
经宿主校验后以 apply_system() 写回。卡带仍是纯函数,永远碰不到网络与 key。

阶段机:worldgen → identities_gen → identity(玩家暗选) → goal(玩家选目标)
        → milestonegen → scenegen → scene(玩家暗投) → …… → endinggen → finished
narration_request 挂在状态里;宿主在事务外调荷官,回填 narration_result。
荷官不可用时停在原地,人类一键重召(蓝图 §14.3)。

天赋/弱点/私密目标采用**菜单制**:荷官只能从引擎支持的机制代码里选,
自由发挥的只有血肉文案——数值预算天然一致,DS 写不出超模身份。
与宿主的唯一结构约定:full_state["phase"]。
"""

import hashlib
from copy import deepcopy

ACTION_TEXT_MAX = 120
LINE_MAX = 60
MAX_SCENES = 10
INTENTS = ["advance", "explore", "support", "confront", "recover"]
INTENT_NAMES = {"advance": "推进", "explore": "探索", "support": "支援",
                "confront": "对抗", "recover": "休整", "end": "停笔",
                "wait": "静候"}
# NPC响应协议(B期):被玩家正面交涉的对象,下一幕必须给出六种回应之一,禁止空气
RESPONSE_KINDS = ["answered", "lied", "refused", "does_not_know",
                  "fled", "interrupted"]
RESPONSE_KIND_NAMES = {"answered": "如实作答", "lied": "撒了谎",
                       "refused": "拒绝回答", "does_not_know": "确实不知",
                       "fled": "脱身而去", "interrupted": "话被打断"}

# v0.3 词库重铸(起点男频/女频题材与标签,经人类作者审定):
# 每项 (词, 权重)。世界生成器 ≠ 任务生成器——题材决定世界,发动机决定这局的事,
# 倒计时毁灭只是发动机之一且权重压低(≈12%),大量对局应是中低烈度的世间事。
POOLS = {
    "genre": [  # 世界题材:这个世界是什么小说
        ("仙侠修真", 3), ("玄幻大陆", 3), ("武侠江湖", 2), ("西方奇幻", 2),
        ("现代都市", 3), ("都市异闻", 2), ("历史古代", 2), ("古代言情", 2),
        ("现代言情", 2), ("浪漫青春", 2), ("悬疑推理", 2), ("悬疑灵异", 2),
        ("科幻未来", 2), ("星际空间", 1), ("末世废土", 1), ("游戏电竞", 1),
        ("体育竞技", 1), ("军事谍战", 1), ("市井现实", 2), ("深海文明", 1),
        ("蒸汽时代", 1), ("梦境世界", 1), ("时间夹层", 1), ("封闭空间", 1),
        ("西游神话", 1), ("洪荒神话", 1), ("剑仙山门", 1), ("诸天无限", 1),
    ],
    "power": [("无超凡", 1), ("低武", 1), ("中武", 1), ("高武", 1), ("神话级", 1)],
    "engine": [  # 故事发动机:这局的剧情由什么牵引(≠世界末日)
        ("调查悬案", 3), ("寻人寻物", 3), ("经营生计", 3), ("市井日常", 3),
        ("护送同行", 2), ("夺宝竞逐", 2), ("拍卖风云", 2), ("大典选拔", 2),
        ("竞赛比武", 2), ("行商旅途", 2), ("社交风波", 2), ("奇遇机缘", 2),
        ("复仇雪冤", 2), ("营救脱困", 2), ("逃亡追捕", 2), ("潜入窃取", 1),
        ("谈判斡旋", 1), ("建设重建", 1), ("危机倒计时", 5),
    ],
    "element": [  # 特色元素:给世界加一味料(多数时候不加)
        ("(无特别元素)", 8),
        ("阵法符箓", 1), ("丹药炼制", 1), ("卡片御灵", 1), ("召唤契约", 1),
        ("亡灵鬼怪", 1), ("吸血鬼", 1), ("龙族", 1), ("魔兽异兽", 1),
        ("僵尸丧尸", 1), ("盗墓玄学", 1), ("鉴宝奇珍", 1), ("灵宠相伴", 1),
        ("系统面板", 1), ("随身空间", 1), ("位面穿梭", 1),
    ],
    "mood": [
        ("温暖", 2), ("轻快", 2), ("热血", 2), ("诡谲", 2), ("市井烟火", 2),
        ("压抑", 1), ("壮烈", 1), ("荒诞", 1), ("史诗", 1), ("孤独", 1),
        ("黑色幽默", 1), ("爆笑恶搞", 1), ("励志", 1), ("冷酷", 1),
    ],
    "entry": [  # 进入方式:两位玩家怎么来到这个世界
        ("穿越而来", 5), ("重生此世", 2), ("穿书成配角", 2),
        ("魂穿他人", 2), ("变身异类", 1), ("强者归来", 1),
    ],
    "variable": [
        ("身份存疑", 1), ("资源枯竭", 1), ("世界正在遗忘", 1),
        ("敌人会学习你们", 1), ("两人记忆不一致", 1), ("道路无法回头", 1),
        ("死亡会改变规则", 1), ("你们的到来早有预言", 1), ("原典主角就在附近", 1),
    ],
    "scope": [  # 剧情规模:本局镜头的大小(≠世界的大小;世界尽可宏大,镜头常常很小)
        ("鸡毛蒜皮", 3), ("一人之事", 3), ("街坊门户", 3),
        ("一城一地", 2), ("天下大势", 1),
    ],
}

# NPC 人格池(B期):支线知情人的性格底色,seed 定死,荷官每次登场都得照此写人
NPC_PERSONAS = [
    ("腹黑藏锋", 1), ("阳光热心", 1), ("狡猾市侩", 1), ("铁血寡言", 1),
    ("胆小怕事", 1), ("傲慢毒舌", 1), ("疯癫痴语", 1), ("温吞慢热", 1),
    ("精明算计", 1), ("天真烂漫", 1), ("阴郁多疑", 1), ("豪爽仗义", 1),
]

# 硬茬人格:追查失败不再"消失在暗处",而是被逼进墙角——只能【对抗】摊牌。
# 胜则真相到手、其势力被打散、进度大涨;败则挂彩,但人还困在墙角,同伴可继续。
# (项目作者设计:治"反派瞬移",并给对抗一个真正的用途)
HARD_PERSONAS = {"腹黑藏锋", "狡猾市侩", "铁血寡言",
                 "傲慢毒舌", "精明算计", "阴郁多疑"}

# 剧情规模 → 烈度预算:荷官在此规模下最多写多大的事(注入 worldgen 提示)
SCOPE_INTENSITY = {
    "鸡毛蒜皮": "烈度1-2:一双鞋、一笔账、一场误会、一件丢失的小物",
    "一人之事": "烈度2-3:某个人的心愿、麻烦、心结或一段人情",
    "街坊门户": "烈度3-4:一条街、一家铺、一个小门派/学堂/商号的兴衰事",
    "一城一地": "烈度5-6:一座城、一个地区的风波,影响千百人的生计",
    "天下大势": "烈度7-9:国家、战争、王朝、世界级的大事,玩家身处漩涡",
}

# 菜单制:荷官只能从这里选机制代码
GIFT_KINDS = {
    "explore_crit_item": "探索骰达到8时额外寻获一件物品",
    "support_synergy": "支援成功时默契额外+1",
    "advance_crit_clock": "推进骰达到8时本幕时钟不前进",
    "confront_no_law": "他的对抗不触发『对抗类』世界法则",
    "recover_heals_both": "休整成功时两人都恢复生命",
    "ones_are_fours": "骰出1时按4计",
}
FLAW_KINDS = {
    "advance_minus": "推进-1", "explore_minus": "探索-1",
    "support_minus": "支援-1", "confront_minus": "对抗-1",
    "confront_minus_danger5": "危险≥5时对抗-1", "six_feeds_danger": "骰出6时危险+1",
}
DRIVE_KINDS = {
    "events_won>=2": "随机事件至少赢下2次",
    "crit>=1": "本人至少掷出1次卓越成功",
    "danger_peak<=6": "整局危险从未超过6",
    "partner_full_vitality": "结局时同伴生命满格",
    "clock<=6": "结局时时钟≤6",
    "hooks_resolved>=2": "全局了结悬事≥2件",
    "both_alive": "结局时两人都活着",
    "hidden_triggered": "任一暗线被触发",
}


ATTRS = {"wisdom": "智慧", "stamina": "体力", "luck": "幸运"}
LUCKY = 5                                           # 幸运≥5:随机事件多掷1骰
EVENT_TARGETS = {"easy": 24, "normal": 28, "hard": 31}
EVENT_NAMES = {"easy": "容易", "normal": "普通", "hard": "困难"}
EVENT_MIN, EVENT_MAX = 2, 5


def _roll_attrs(seed, seat):
    """身份三维:按种子与席位定死,与行动骰流互不干扰。"""
    return {k: int(hashlib.sha256(f"{seed}:attr:{seat}:{k}".encode()).hexdigest(), 16) % 6 + 1
            for k in ATTRS}


def _event_quota(s):
    """下一幕荷官必须写 / 不许写 / 可写随机事件。保证每局 2-5 次。"""
    ev = s.get("events") or {"done": 0}
    done, nxt = ev["done"], s["scene_index"] + 1
    left = MAX_SCENES - nxt + 1                      # 含下一幕在内还剩几幕
    if done >= EVENT_MAX:
        return "forbidden"
    if done < min(EVENT_MIN, nxt // 3) or EVENT_MIN - done >= left:
        return "required"
    return "optional"


def _resolve_event(s, scene, slip, report):
    ev = scene.get("event")
    if not ev or not s.get("attrs") or not all(s["attrs"].get(x) for x in s["seats"]):
        return
    target = EVENT_TARGETS[ev["difficulty"]]
    base = sum(sum(s["attrs"][x].values()) for x in s["seats"])
    dice, parts = [], []
    for x in s["seats"]:
        n = 2 if s["attrs"][x]["luck"] >= LUCKY else 1
        rolled = [_die(s) for _ in range(n)]
        dice += rolled
        name = _identity(s, s["identities"][x])["name"]
        parts.append(f"{name}掷{'+'.join(map(str, rolled))}{'(幸运加掷)' if n == 2 else ''}")
    total = base + sum(dice)
    won = total >= target
    book = s.setdefault("events", {"done": 0, "won": 0, "log": []})
    book["done"] += 1
    book["won"] += int(won)
    book["log"].append({"scene": s["scene_index"], "text": ev["text"],
                        "difficulty": ev["difficulty"], "target": target,
                        "total": total, "won": won})
    slip["danger_delta"] += -2 if won else 2
    report.append(f"◆ 随机事件【{EVENT_NAMES[ev['difficulty']]}·目标{target}】{ev['text']}")
    report.append(f"  三维合计{base} + {'、'.join(parts)} = {total} → "
                  + ("化解了(危险-2)" if won else "没能挡住(危险+2)"))


def _ending_kind(s):
    """结局三档:BE=危险满或无人生还;HE=锁定+两人都在+危险未满+双方目标达成+支线了结;其余 TE。"""
    alive = [x for x in s["seats"] if s["vitality"][x] > 0]
    if not alive or s["danger"] >= 10:
        return "BE"
    goals = [_active_goal(s, x) for x in s["seats"]]
    if (s.get("main_goal_locked") and len(alive) == 2
            and all(g and g.get("goal_locked") for g in goals)
            and not any(q["status"] == "open" for q in s.get("side_quests") or [])):
        return "HE"
    return "TE"


def _finish_auto(s, reason):
    kind = _ending_kind(s)
    alive = [x for x in s["seats"] if s["vitality"][x] > 0]
    if kind == "HE":
        reason = "goal"
    elif kind == "TE" and len(alive) < 2:
        reason = "sacrifice"
    _finish(s, kind, reason)


class IllegalAction(Exception):
    """非法动作:宿主据此返回 rejected,局面不变。"""


# ---------------- 建局与种子 ----------------

def _pick(seed, salt, pool):
    """加权抽签:pool 是 (词, 权重) 列表,seed 定死,可复现。"""
    total = sum(w for _, w in pool)
    h = int(hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest(), 16) % total
    for v, w in pool:
        h -= w
        if h < 0:
            return v
    return pool[-1][0]


def new_game(seats, seed):
    if len(seats) != 2:
        raise ValueError("这张卡只支持两名玩家")
    axes = {k: _pick(seed, k, POOLS[k]) for k in POOLS}
    return {
        "phase": "playing",
        "stage": "worldgen",
        "seed": seed,
        "axes": axes,
        "seats": list(seats),
        "world": None,
        "episode": None,                # 本局小段:降落点选定后才生成
        "landings": [],                 # 三个降落点选项(worldgen 产出)
        "landing": None,                # 选定的降落点
        "landing_votes": {},            # 席位 -> 降落点 id;两席同选才落定
        "canon_index": 0,               # 远方大事推进到第几行
        "identity_pool": None,
        "identity_offers": {},
        "identities": {seats[0]: None, seats[1]: None},
        "player_goals": {seats[0]: [], seats[1]: []},
        "scene_index": 0,
        "current_scene": None,
        "clock": 0, "progress": 0, "danger": 0, "synergy": 0,
        "main_goal_locked": False, "goal_locked_at_scene": None,
        "vitality": {seats[0]: 3, seats[1]: 3},
        "inventory": {seats[0]: [], seats[1]: [], "shared": []},
        "facts": [], "flags": [], "hooks": [],
        "hooks_resolved": 0, "hidden_fired": [],
        "side_quests": [],
        "wins": {"advance": 0, "explore": 0, "support": 0,
                 "confront": 0, "recover": 0},
        "pending": {}, "history": [],
        "prophecies": {seats[0]: [], seats[1]: []},   # 先知情报:私密撕页
        "prophecy_i": 0,
        "pending_interactions": None,   # NPC响应协议:上一幕欠下的回应债
        "npc_book": {},                 # NPC台帐:登场记录与状态变化(治刷脸伪人)
        "attrs": {seats[0]: None, seats[1]: None},   # 身份三维,选身份时掷出
        "events": {"done": 0, "won": 0, "log": []},   # 随机事件账
        "danger_peak": 0, "crits": {seats[0]: 0, seats[1]: 0},
        "ending": None, "rolls_used": 0, "end_proposed_by": None,
        "end_streaks": {seats[0]: 0, seats[1]: 0},   # 连续三幕提停笔=强制结算
        "narration_request": {"kind": "gen_world", "context": {
            "axes": axes,
            "scope_intensity": SCOPE_INTENSITY.get(axes.get("scope"), ""),
            "npc_persona": _pick(seed, "npc_persona", NPC_PERSONAS),
        }},
    }


def _die(state):
    h = hashlib.sha256(f"{state['seed']}:d{state['rolls_used']}".encode())
    state["rolls_used"] += 1
    return int(h.hexdigest(), 16) % 6 + 1


def _identity(s, iid):
    return next(i for i in s["identity_pool"] if i["id"] == iid)


# ---------------- 支线暗典 ----------------

def _npc_windows(seed):
    """NPC 的两个登场窗口:1..MAX_SCENES 里随机两幕,seed 定死,可复现。"""
    w1 = int(hashlib.sha256(f"{seed}:npcw1".encode()).hexdigest(), 16) % MAX_SCENES + 1
    w2 = int(hashlib.sha256(f"{seed}:npcw2".encode()).hexdigest(), 16) % MAX_SCENES + 1
    if w2 == w1:
        w2 = w2 % MAX_SCENES + 1
    return sorted([w1, w2])


def _npc_due(s, scene_no):
    """本幕是否有剧情 NPC 登场(支线未解且撞上窗口)。"""
    for q in s.get("side_quests") or []:
        if q["unlock_kind"] == "npc" and q["status"] == "open" \
                and scene_no in q.get("windows", []):
            return q
    return None


def _extend_window(q, scene_index):
    """墙角僵局:NPC 窗口顺延一幕——被盯死的人不会凭空消失。"""
    if scene_index + 1 not in q["windows"]:
        q["windows"].append(scene_index + 1)


def _quest_resolve(s, q, report, how):
    """支线了结:谜底从暗典掏出,写成既成事实,悬事划掉。"""
    q["status"] = "resolved"
    q["resolved_at"] = s["scene_index"]
    s["hooks_resolved"] += 1
    s["facts"].append(f"真相大白:{q['truth']}")
    if q["question"] in s["hooks"]:
        s["hooks"].remove(q["question"])
    report.append(f"◆ 悬事了结({how}):{q['question']}")
    report.append(f"  真相:{q['truth']}")


# ---------------- 荷官回填(宿主专用入口,玩家动作到不了这里) ----------------

def apply_system(full_state, action_id, payload):
    s = deepcopy(full_state)
    if action_id != "narration_result":
        raise IllegalAction("未知系统动作")
    req = s.get("narration_request")
    if not req or payload.get("kind") != req["kind"]:
        raise IllegalAction("没有与之匹配的荷官请求")
    data = payload["data"]
    kind = req["kind"]
    if kind == "gen_world":
        data = dict(data)
        data["power_level"] = s["axes"]["power"]   # 常量由引擎注入,不劳荷官复读
        # 三层拆分:世界层只留大世界。本局那一段等降落点选定后另开合同生成,
        # 同一颗世界种子可以落在不同的角落。
        landings = deepcopy(data.pop("landings"))
        s["world"] = data
        s["landings"] = landings
        s["landing"] = None
        s["landing_votes"] = {}
        s["narration_request"] = None
        s["stage"] = "landing"
        return s
    if kind == "gen_episode":
        data = dict(data)
        s["episode"] = data
        # 落点那句是这局的第一条事实,开局事实接在它后面,不覆盖
        landed = list(s["facts"]) if s.get("landing") else []
        s["facts"] = landed + list(data["opening_facts"])
        # 支线暗典入库:谜底与登场窗口只有引擎知道,悬事 = 谜题原句
        quests = []
        for q in data.get("side_quests", []):
            q = dict(q)
            q["status"] = "open"
            q["pressed"] = 0   # 追问计数:玩家点对悬事逼问,两次谜底必出
            if q["unlock_kind"] == "npc":
                q["windows"] = _npc_windows(s["seed"])
                # 人格由引擎抽签定死,不信荷官复读;每次登场都按此写人
                q.setdefault("npc", {})["persona"] = _pick(
                    s["seed"], "npc_persona", NPC_PERSONAS)
            quests.append(q)
        s["side_quests"] = quests
        s["hooks"] = [q["question"] for q in quests]
        s["narration_request"] = {"kind": "gen_identities",
                                  "context": {"world": _world_brief(s)}}
        s["stage"] = "identities_gen"
    elif kind == "gen_identities":
        s["identity_pool"] = data
        order = sorted([i["id"] for i in data], key=lambda x: hashlib.sha256(
            f"{s['seed']}:{x}".encode()).hexdigest())
        s["identity_offers"] = {s["seats"][0]: order[:2],
                                s["seats"][1]: order[2:4]}
        s["narration_request"] = None
        s["stage"] = "identity"
    elif kind == "gen_milestones":
        for track in data["tracks"]:
            goal = _active_goal(s, track["seat"])
            goal["milestones"] = deepcopy(track["milestones"])
            goal["milestones_done"] = []
            goal["goal_locked"] = False
        if s["current_scene"] is None:
            s["stage"] = "scenegen"
            s["narration_request"] = {"kind": "gen_scene",
                                      "context": _scene_context(s, None)}
        else:
            s["stage"] = "scene"
            s["narration_request"] = None
    elif kind == "gen_scene":
        new_idx = s["scene_index"] + 1
        # NPC响应入账:荷官清偿的回应债成为既成事实,后续幕与结局都看得见
        pend = {p["object_id"]: p for p in s.get("pending_interactions") or []}
        for r in (data.get("npc_responses") or []):
            p = pend.get(r.get("object_id"))
            if not p:
                continue
            kn = RESPONSE_KIND_NAMES.get(r.get("kind"), r.get("kind", "?"))
            s["facts"].append(f"[第{new_idx}幕]{p['object_name']}对{p['by']}"
                              f"有了回应({kn}):{(r.get('detail') or '')[:60]}")
        s["pending_interactions"] = None
        # NPC台帐:记登场,收状态变化
        book = s.setdefault("npc_book", {})
        for o in data.get("objects", []):
            rec = book.get(o["name"])
            if rec:
                rec["count"] += 1
                rec["last_scene"] = new_idx
                if o.get("change"):
                    rec["notes"].append(f"第{new_idx}幕:{o['change']}")
            else:
                book[o["name"]] = {"first_scene": new_idx, "last_scene": new_idx,
                                   "count": 1, "notes": []}
        s["current_scene"] = data
        s["scene_index"] = new_idx
        s["narration_request"] = None
        s["stage"] = "scene"
    elif kind == "render_ending":
        s["ending"]["text"] = data["text"]
        s["narration_request"] = None
        s["phase"] = "finished"
        s["stage"] = "finished"
    return s


COST_GLOSS = {"danger": "危险+1", "progress": "进度-1",
              "clock": "时钟+1", "flag": "留下印记", "vitality": "生命受创"}


def _law_gloss(law):
    tk = law["trigger_kind"]
    if tk.startswith("intent:"):
        when = f"有人【{INTENT_NAMES.get(tk[7:], tk[7:])}】时"
    elif tk.startswith("clock>="):
        when = f"时钟≥{tk[7:]}后每幕"
    elif tk.startswith("danger>="):
        when = f"危险≥{tk[8:]}后每幕"
    else:
        when = tk
    return f"{law['text']}(判定:{when} {COST_GLOSS.get(law['cost_kind'], '')})"


def _ep(s):
    """本局小段仅来自当前规则的 episode。"""
    return s["episode"] or {}


def _world_brief(s):
    w = s["world"]
    ep = _ep(s)
    brief = {"world_name": w["world_name"], "premise": w["premise"],
             "lore": w["lore"], "power_level": w["power_level"],
             "world_thread": w["world_thread"],
             "goal_menu": deepcopy(ep.get("goal_menu", [])),
             "clock_text": w.get("clock_text"),
             "laws": [_law_gloss(l) for l in w["laws"]]}
    if w.get("world_background"):
        brief["world_background"] = w["world_background"]
    if ep.get("local_episode"):
        brief["local_episode"] = deepcopy(ep["local_episode"])
    if s.get("landing"):
        brief["landing"] = deepcopy(s["landing"])
    return brief


def _active_goal(s, seat_id):
    for goal in reversed(s["player_goals"][seat_id]):
        if not goal.get("abandoned"):
            return goal
    return None


def _milestones(s):
    milestones = []
    for seat in s["seats"]:
        goal = _active_goal(s, seat)
        if not goal:
            continue
        for milestone in goal.get("milestones", []):
            item = dict(milestone)
            item["seat"] = seat
            milestones.append(item)
    return milestones


def _current_milestone(s, seat_id=None):
    seats = [seat_id] if seat_id else s["seats"]
    for seat in seats:
        goal = _active_goal(s, seat)
        if not goal:
            continue
        for milestone in goal.get("milestones", []):
            if milestone["id"] not in goal.get("milestones_done", []):
                item = dict(milestone)
                item["seat"] = seat
                return item
    return None


def _request_milestones(s, seats):
    goals = []
    for seat in seats:
        goal = _active_goal(s, seat)
        goals.append({"seat": seat,
                      "identity": _identity(s, s["identities"][seat])["name"],
                      "text": goal["text"]})
    s["stage"] = "milestonegen"
    s["narration_request"] = {"kind": "gen_milestones", "context": {
        "world": _world_brief(s), "goals": goals,
        "scope": s["axes"]["scope"],
        "scope_intensity": SCOPE_INTENSITY[s["axes"]["scope"]],
    }}


CANON_TICK_EVERY = 2   # 每两幕推进一行远方大事


def _canon_now(s):
    """远方大事推进到哪一行。它只作背景自走,永远不拽玩家参与。

    scope=天下大势 时玩家本就身处大主线,此时才允许它与本幕合流。
    """
    ticks = ((s["world"] or {}).get("global_canon") or {}).get("ticks") or []
    if not ticks:
        return None
    idx = min(s["scene_index"] // CANON_TICK_EVERY, len(ticks) - 1)
    return {"line": ticks[idx],
            "index": idx + 1, "total": len(ticks),
            "may_converge": s["axes"].get("scope") == "天下大势"}


def _scene_context(s, last_report):
    # 桌边留言是玩家之间的真实闲聊,永远不进荷官的眼(§DS永远不能)
    if last_report:
        last_report = [l for l in last_report if "留言:「" not in l]
    cur = _current_milestone(s)
    ms = _milestones(s)
    pacing = None
    if s.get("main_goal_locked"):
        remaining = max(0, MAX_SCENES - s["scene_index"])
        pacing = (f"余波幕:公开目标已经达成,主线结局已锁定。还可行动{remaining}幕;"
                  "余下的戏全在支线:未解悬事的答案早已写在暗典里,由引擎按解锁条件揭示,"
                  "你不负责回答也不负责加谜——只推演现场。承认主线成果,不要再制造新的主线门槛。")
    elif s["progress"] >= 8 or (cur and ms and cur["seat"] == ms[-1]["seat"]
                                and cur["id"] == ms[-1]["id"]):
        pacing = "决胜幕:终点已在眼前,本幕危机必须是通往目标的最后一道阻碍,不得新增支线人物或新谜团。"
    elif s["clock"] >= 6:
        pacing = "收束幕:时间无多,收拢已有线索,不再展开新方向。"
    chron = _ep(s).get("chronicle") or []
    idx = min(s["scene_index"], len(chron) - 1) if chron else -1
    chronicle_now = (f"第{chron[idx].get('chapter', idx + 1)}章"
                     f"《{chron[idx]['title']}》:{chron[idx]['event']}"
                     if idx >= 0 else None)
    npc = _npc_due(s, s["scene_index"] + 1)
    return {
        "npc_onstage": ({"name": npc["npc"]["name"], "desc": npc["npc"]["desc"],
                         "persona": npc["npc"].get("persona", ""),
                         "cornered": bool(npc.get("cornered")),
                         "question": npc["question"]} if npc else None),
        "open_questions": [q["question"] for q in s.get("side_quests") or []
                           if q["status"] == "open"],
        "pacing": pacing,
        "player_goals": [
            {"seat": seat,
             "identity": _identity(s, s["identities"][seat])["name"],
             "text": goal["text"],
             "milestones": [
                 {"id": m["id"], "text": m["text"],
                  "done": m["id"] in goal.get("milestones_done", [])}
                 for m in goal.get("milestones", [])]}
            for seat in s["seats"] if (goal := _active_goal(s, seat))],
        "chronicle_now": chronicle_now,
        "canon_now": _canon_now(s),
        "world": _world_brief(s),
        "scene_index": s["scene_index"] + 1,
        "tracks": {"progress": s["progress"], "danger": s["danger"],
                   "synergy": s["synergy"], "clock": s["clock"],
                   "vitality": dict(s["vitality"])},
        "main_goal_locked": s.get("main_goal_locked", False),
        "turns_remaining": max(0, MAX_SCENES - s["scene_index"]),
        "event_quota": _event_quota(s),
        "identities": [
            {"name": _identity(s, s["identities"][x])["name"],
             "specialty": _identity(s, s["identities"][x])["specialty"]}
            for x in s["seats"] if s["identities"][x]],
        "facts": s["facts"][-8:],
        "hooks": list(s["hooks"]),
        "last_report": last_report,
        # NPC响应协议:欠下的回应债,下一幕合同必须逐笔清偿
        "pending_interactions": deepcopy(s.get("pending_interactions") or []),
        # NPC台帐:登场过的对象,再写必须带状态变化(治刷脸伪人)
        "recurring_npcs": [
            {"name": n, "appearances": r["count"], "last_scene": r["last_scene"],
             "last_note": (r["notes"][-1] if r["notes"] else None)}
            for n, r in list((s.get("npc_book") or {}).items())[-12:]],
    }


# ---------------- 观察 ----------------

def observe(full_state, seat_id):
    s = full_state
    if seat_id not in s["seats"]:
        raise ValueError("未知席位")
    idents_public = {}
    for x in s["seats"]:
        if s["identities"][x]:
            it = _identity(s, s["identities"][x])
            idents_public[x] = {"name": it["name"], "origin": it["origin"],
                                "specialty": INTENT_NAMES[it["specialty"]],
                                "gift": it["gift"]["text"],
                                "flaw": it["flaw"]["text"],
                                "attrs": deepcopy((s.get("attrs") or {}).get(x))}
        else:
            idents_public[x] = None
    req = s.get("narration_request")
    public = {
        "phase": s["phase"], "stage": s["stage"],
        "axes": s["axes"],
        "world": _world_brief(s) if s["world"] else None,
        "narration_pending": req["kind"] if req else None,
        "tracks": {"progress": s["progress"], "danger": s["danger"],
                   "synergy": s["synergy"], "clock": s["clock"],
                   "vitality": dict(s["vitality"])},
        "main_goal_locked": s.get("main_goal_locked", False),
        "goal_locked_at_scene": s.get("goal_locked_at_scene"),
        "scene_index": s["scene_index"],
        "scene": deepcopy(s["current_scene"]) if s["stage"] == "scene" else None,
        "identities": idents_public,
        "events": deepcopy(s.get("events")),
        "inventory": deepcopy(s["inventory"]),
        "facts": list(s["facts"]),
        "hooks": list(s["hooks"]),
        "submitted": {x: (x in s["pending"]) for x in s["seats"]},
        "end_proposed_by": s["end_proposed_by"],
        # 降落点:待选时摊开三个选项与当前票型,选定后只留落点本身
        "landings": (deepcopy(s.get("landings", []))
                     if s["stage"] == "landing" else None),
        "landing_votes": (deepcopy(s.get("landing_votes", {}))
                          if s["stage"] == "landing" else None),
        "landing": deepcopy(s.get("landing")),
        "history": [{"scene_index": h["scene_index"], "title": h["title"],
                     "report": h["report"]} for h in s["history"]],
        "ending": deepcopy(s["ending"]),
        # 原典只在全书终了时揭晓——这一刻是穿越者的对账时刻
        "chronicle_reveal": (
            {"chapters": deepcopy(_ep(s).get("chronicle", [])),
             "original_ending": _ep(s).get("original_ending"),
             # 支线对账:解开的、错过的,谜底与钥匙一并摊牌
             "side_quests": [
                 {"question": q["question"], "truth": q["truth"],
                  "status": q["status"], "unlock_kind": q["unlock_kind"],
                  "npc_name": (q.get("npc") or {}).get("name"),
                  "windows": q.get("windows"),
                  "stat": q.get("stat")}
                 for q in s.get("side_quests") or []]}
            if s["phase"] == "finished" and s["world"] else None),
    }
    my_ident = s["identities"][seat_id]
    my_drive = None
    if my_ident:
        d = _identity(s, my_ident)["secret_drive"]
        my_drive = f"{d['text']}(判定:{DRIVE_KINDS.get(d['kind'], d['kind'])})"
    offers = None
    if s["stage"] == "identity" and not my_ident:
        offers = []
        for i in s["identity_offers"].get(seat_id, []):
            card = deepcopy(_identity(s, i))
            card["secret_drive"]["text"] += \
                f"(判定:{DRIVE_KINDS.get(card['secret_drive']['kind'], '')})"
            offers.append(card)
    private = {
        "identity_offers": offers,
        "secret_drive": my_drive,
        "player_goals": deepcopy(s["player_goals"][seat_id]),
        "my_pending": deepcopy(s["pending"].get(seat_id)),
        "prophecies": deepcopy(s.get("prophecies", {}).get(seat_id, [])),
    }
    legal, waiting = [], []
    if s["phase"] == "playing":
        if req:
            waiting = ["narrator"]
        elif s["stage"] == "landing":
            # 降落点是全桌共同的一步:两席同选才落定,谈不拢就掷骰交给运气
            waiting = [x for x in s["seats"] if x not in s.get("landing_votes", {})]
            if seat_id in waiting:
                opts = [l["id"] for l in s.get("landings", [])]
                legal = [{"action_id": "choose_landing", "params": {
                    "landing_id": f"商量后选同一个才落定:{opts}"}},
                    {"action_id": "roll_landing", "params": {}}]
        elif s["stage"] == "identity":
            waiting = [x for x in s["seats"] if not s["identities"][x]]
            if seat_id in waiting:
                legal = [{"action_id": "choose_identity",
                          "params": {"identity_id":
                                     f"暗选其一:{s['identity_offers'][seat_id]}"}}]
        elif s["stage"] == "goal":
            waiting = [x for x in s["seats"] if not _active_goal(s, x)]
            if seat_id in waiting:
                menu = [g["id"] for g in _ep(s).get("goal_menu", [])]
                legal = [{"action_id": "choose_goal", "params": {
                    "goal_id": f"从菜单选一个:{menu}",
                    "custom_text": "或自定义一个可判定目标(≤40字)",
                }}]
        elif s["stage"] == "scene":
            waiting = [x for x in s["seats"] if x not in s["pending"]]
            if seat_id in waiting:
                my_items = [i["id"] for i in s["inventory"][seat_id]] + \
                           [i["id"] for i in s["inventory"]["shared"]]
                commit_params = {
                    "intent": f"必填:{INTENTS} 之一;或 'end'=提议停笔(双方同幕都选才生效)",
                    "action": f"必填:这一步你具体怎么做(≤{ACTION_TEXT_MAX}字)",
                    "item_id": f"可选:动用一件物品,标签匹配意图时骰+1,可用:{my_items}",
                    "line": f"可选:一句桌边留言(≤{LINE_MAX}字,不参与判定)",
                }
                obj_ids = [o["id"] for o in
                           (s["current_scene"] or {}).get("objects", [])]
                tgt = (f"可选:点名一位在场对象正面交涉(本幕之一:{obj_ids}),"
                       "判定不失败则对方下一幕必须给出回应")
                npc = _npc_due(s, s["scene_index"])
                if npc and npc.get("cornered"):
                    tgt += (f";或 'npc'=与被逼到墙角的「{npc['npc']['name']}」摊牌"
                            "(只能【对抗】:胜则真相到手+其势力瓦解+进度大涨,败则挂彩)")
                elif npc:
                    tgt += (f";或 'npc'=追查登场人物「{npc['npc']['name']}」"
                            "(成功即揭开其知晓的悬事;此人不会久留)")
                commit_params["target"] = tgt
                if s["hooks"]:
                    commit_params["about"] = (
                        "可选(须与 target 同用):逐字引用一条未解决悬事,表示这次交涉"
                        "直指此谜——判定成功即逼问一次,两次(卓越算两次)谜底必出:"
                        f"{s['hooks']}")
                legal = [{"action_id": "commit", "params": commit_params}]
                if not s.get("main_goal_locked") and not s["pending"]:
                    menu = [g["id"] for g in _ep(s).get("goal_menu", [])]
                    legal.append({"action_id": "switch_goal", "params": {
                        "goal_id": f"从菜单选一个:{menu}",
                        "custom_text": "或自定义一个可判定目标(≤40字)",
                    }})
    return {"public_state": public, "private_state": private,
            "legal_actions": legal, "waiting_for": waiting}


# ---------------- 玩家动作 ----------------

def apply(full_state, seat_id, action_id, params):
    s = deepcopy(full_state)
    if seat_id not in s["seats"]:
        raise IllegalAction("未知席位")
    if s["phase"] != "playing":
        raise IllegalAction("本局已结束")
    if s.get("narration_request"):
        raise IllegalAction("荷官执笔中,请稍候(人类界面可一键召荷官)")
    params = params if isinstance(params, dict) else {}
    if action_id == "choose_landing":
        _apply_landing(s, seat_id, params)
    elif action_id == "roll_landing":
        _apply_roll_landing(s, seat_id)
    elif action_id == "choose_identity":
        _apply_identity(s, seat_id, params)
    elif action_id == "choose_goal":
        _apply_goal(s, seat_id, params)
    elif action_id == "switch_goal":
        _apply_switch_goal(s, seat_id, params)
    elif action_id == "commit":
        _apply_commit(s, seat_id, params)
    else:
        raise IllegalAction(f"没有这个动作:{action_id}")
    return s


def _landing_by_id(s, lid):
    return next((l for l in s.get("landings", []) if l["id"] == lid), None)


def _settle_landing(s, landing, how):
    """降落点落定:记事实,再开本局合同——这一段世界由降落点决定怎么展开。"""
    s["landing"] = deepcopy(landing)
    s["facts"] = [f"你们落在{landing['place']}。{landing['happening']}"]
    s["narration_request"] = {"kind": "gen_episode", "context": {
        "world": _world_brief(s),
        "landing": deepcopy(landing),
        "scope": s["axes"]["scope"],
        "scope_intensity": SCOPE_INTENSITY.get(s["axes"].get("scope"), ""),
        "settled_by": how,
    }}
    s["stage"] = "episodegen"


def _apply_landing(s, seat_id, params):
    if s["stage"] != "landing":
        raise IllegalAction("现在不是挑降落点的时候")
    lid = params.get("landing_id")
    if not _landing_by_id(s, lid):
        raise IllegalAction(
            f"只能从这三个里选:{[l['id'] for l in s.get('landings', [])]}")
    votes = s.setdefault("landing_votes", {})
    votes[seat_id] = lid
    if len(votes) < len(s["seats"]):
        return
    if len(set(votes.values())) == 1:
        _settle_landing(s, _landing_by_id(s, lid), "agreed")
    else:   # 谈不拢不罚也不僵:清票重来,想省事就 roll_landing
        s["landing_votes"] = {}


def _apply_roll_landing(s, seat_id):
    if s["stage"] != "landing":
        raise IllegalAction("现在不是挑降落点的时候")
    if not s.get("landings"):
        raise IllegalAction("这局没有降落点可掷")
    idx = (_die(s) - 1) % len(s["landings"])
    _settle_landing(s, s["landings"][idx], "rolled")


def _apply_identity(s, seat_id, params):
    if s["stage"] != "identity":
        raise IllegalAction("现在不是选身份的时候")
    if s["identities"][seat_id]:
        raise IllegalAction("你已经选过身份了")
    iid = params.get("identity_id")
    if iid not in s["identity_offers"][seat_id]:
        raise IllegalAction(f"只能从你抽到的两张里选:{s['identity_offers'][seat_id]}")
    s["identities"][seat_id] = iid
    s.setdefault("attrs", {})[seat_id] = _roll_attrs(s["seed"], seat_id)
    s["inventory"][seat_id].append(deepcopy(_identity(s, iid)["starting_item"]))
    if all(s["identities"].values()):
        names = [_identity(s, s["identities"][x])["name"] for x in s["seats"]]
        s["facts"].append(f"{names[0]}与{names[1]}在这个陌生的世界里认出了彼此。")
        s["stage"] = "goal"


def _goal_record(s, seat_id, params):
    goal_id = params.get("goal_id")
    custom = params.get("custom_text")
    if bool(goal_id) == bool(custom):
        raise IllegalAction("goal_id 与 custom_text 须且只能填一个")
    if goal_id:
        picked = next((g for g in _ep(s).get("goal_menu", [])
                       if g["id"] == goal_id), None)
        if not picked:
            raise IllegalAction("goal_id 不在目标菜单里")
        text = picked["text"]
    else:
        if not isinstance(custom, str) or not custom.strip() or len(custom.strip()) > 40:
            raise IllegalAction("custom_text 须是1到40字")
        text = custom.strip()
        goal_id = f"custom_{len(s['player_goals'][seat_id]) + 1}"
    return {
        "id": goal_id, "text": text, "abandoned": False,
        "goal_locked": False, "milestones": [], "milestones_done": [],
    }


def _apply_goal(s, seat_id, params):
    if s["stage"] != "goal":
        raise IllegalAction("现在不是选择目标的时候")
    if _active_goal(s, seat_id):
        raise IllegalAction("你已经选过目标了")
    s["player_goals"][seat_id].append(_goal_record(s, seat_id, params))
    if all(_active_goal(s, seat) for seat in s["seats"]):
        _request_milestones(s, s["seats"])


def _apply_switch_goal(s, seat_id, params):
    if s["stage"] != "scene":
        raise IllegalAction("现在不能更换目标")
    if s.get("main_goal_locked"):
        raise IllegalAction("结局已经锁定,不能更换目标")
    if s["pending"]:
        raise IllegalAction("本幕已有行动提交,请在下一幕开始时更换目标")
    old = _active_goal(s, seat_id)
    if not old:
        raise IllegalAction("当前没有可更换的目标")
    new_goal = _goal_record(s, seat_id, params)
    old["abandoned"] = True
    s["player_goals"][seat_id].append(new_goal)
    s["clock"] += 1
    _request_milestones(s, [seat_id])


def _apply_commit(s, seat_id, params):
    if s["stage"] != "scene":
        raise IllegalAction("现在不是行动阶段")
    if seat_id in s["pending"]:
        raise IllegalAction("这一幕你已经提交过了")
    intent = params.get("intent")
    if intent != "end" and intent not in INTENTS:
        raise IllegalAction(f"intent 须是 {INTENTS} 之一或 'end'")
    action = params.get("action", "")
    if intent != "end":
        if not isinstance(action, str) or not action.strip():
            raise IllegalAction("action 必填:说清你具体怎么做")
        if len(action.strip()) > ACTION_TEXT_MAX:
            raise IllegalAction(f"action 过长:≤{ACTION_TEXT_MAX} 字")
    item_id = params.get("item_id")
    if item_id is not None:
        mine = [i["id"] for i in s["inventory"][seat_id]] + \
               [i["id"] for i in s["inventory"]["shared"]]
        if item_id not in mine:
            raise IllegalAction(f"这件东西不在你能拿到的行囊里:{mine}")
    line = params.get("line", "")
    if not isinstance(line, str) or len(line.strip()) > LINE_MAX:
        raise IllegalAction(f"line 须是字符串且 ≤{LINE_MAX} 字")
    target = params.get("target")
    if target is not None:
        if intent == "end":
            raise IllegalAction("提议停笔的同时不能点名对象")
        if target == "npc":
            due = _npc_due(s, s["scene_index"])
            if not due:
                raise IllegalAction("本幕没有可追查的剧情人物")
            if due.get("cornered") and intent != "confront":
                raise IllegalAction(
                    f"{due['npc']['name']}已被逼到墙角,退路已断——"
                    "追查他只能【对抗】摊牌:胜则真相与战果,败则挂彩")
        else:
            # NPC响应协议:点名本幕在场对象正面交涉,判定不失败则对方欠下回应
            ids = [o["id"] for o in (s["current_scene"] or {}).get("objects", [])]
            if target not in ids:
                raise IllegalAction(f"target 须是 'npc' 或本幕在场对象之一:{ids}")
    about = params.get("about")
    if about is not None:
        # 追问机制:问对了人、点对了悬事,就是解谜的关键——引擎按逼问次数放谜底
        if not target or target == "npc":
            raise IllegalAction("about 须与 target(在场对象)同用:先点名问谁,再声明问什么")
        if about not in s["hooks"]:
            raise IllegalAction(f"about 须逐字引用未解决悬事之一:{s['hooks']}")
    s["pending"][seat_id] = {"intent": intent, "action": (action or "").strip(),
                             "item_id": item_id, "line": line.strip(),
                             "target": target, "about": about}
    if len(s["pending"]) == 2:
        _resolve(s)


# ---------------- 裁决 ----------------

def _modifiers(s, seat_id, intent, item_id, other_intent):
    ident = _identity(s, s["identities"][seat_id])
    mods, notes = 0, []
    if ident["specialty"] == intent:
        mods += 1
        notes.append("身份擅长+1")
    if item_id:
        item = next((i for i in s["inventory"][seat_id] + s["inventory"]["shared"]
                     if i["id"] == item_id), None)
        if item and intent in item.get("use", []):
            mods += 1
            notes.append(f"{item['name']}+1")
        elif item:
            notes.append(f"{item['name']}帮不上这种忙")
    if other_intent == "support":
        mods += 1
        notes.append("同伴支援+1")
    fk = ident["flaw"]["kind"]
    if fk == f"{intent}_minus":
        mods -= 1
        notes.append("身份弱点-1")
    if fk == "confront_minus_danger5" and intent == "confront" and s["danger"] >= 5:
        mods -= 1
        notes.append("身份弱点-1")
    if s["danger"] >= 7:
        mods -= 1
        notes.append("高危环境-1")
    if "truth_known" in s["flags"] and intent == "advance":
        mods += 1
        notes.append("真相在手+1")
    return mods, notes


def _tier(total):
    if total <= 3:
        return "failure"
    if total <= 5:
        return "mixed_success"
    if total <= 7:
        return "success"
    return "critical_success"


TIER_NAMES = {"failure": "失败", "mixed_success": "勉强成功",
              "success": "成功", "critical_success": "卓越成功"}


def _resolve(s):
    a, b = s["seats"]
    pa, pb = s["pending"][a], s["pending"][b]
    scene = s["current_scene"]
    report = [f"—— 第 {s['scene_index']} 幕 · {scene['title']} ——"]

    if pa["intent"] == "end" and pb["intent"] == "end":
        report.append("两人对视一眼,把故事合上了。")
        _log(s, scene, {a: pa, b: pb}, {}, report)
        _finish_auto(s, "mutual_end")
        return
    streaks = s.setdefault("end_streaks", {a: 0, b: 0})
    for seat, p in ((a, pa), (b, pb)):
        if p["intent"] == "end":
            # 单方停笔=静候:不掷骰、不折算休整、不触发任何法则
            s["end_proposed_by"] = seat
            p["intent"] = "wait"
            streaks[seat] = streaks.get(seat, 0) + 1
            report.append(f"{seat} 提议就此停笔,静静等着——另一人还想再走一程。"
                          f"(连提三幕即强制收卷,已 {streaks[seat]}/3)")
        else:
            streaks[seat] = 0

    slip = {"outcome": {}, "progress_delta": 0, "danger_delta": 0,
            "clock_delta": 0 if s.get("main_goal_locked") else 1,
            "synergy_delta": 0,
            "vitality_delta": {a: 0, b: 0}, "facts_added": [],
            "flags_added": [], "hooks_added": [], "hooks_resolved": 0,
            "items_gained": []}
    tiers = {}
    for seat, p, other_p in ((a, pa, pb), (b, pb, pa)):
        if p["intent"] == "wait":
            tiers[seat] = "wait"
            slip["outcome"][seat] = "wait"
            continue
        ident = _identity(s, s["identities"][seat])
        die = _die(s)
        if ident["gift"]["kind"] == "ones_are_fours" and die == 1:
            die = 4
        if ident["flaw"]["kind"] == "six_feeds_danger" and die == 6:
            slip["danger_delta"] += 1
        mods, notes = _modifiers(s, seat, p["intent"], p["item_id"], other_p["intent"])
        total = die + mods
        tier = _tier(total)
        tiers[seat] = tier
        slip["outcome"][seat] = tier
        name = ident["name"]
        report.append(f"{name}【{INTENT_NAMES[p['intent']]}】:{p['action'] or '(静静停下)'}")
        report.append(f"  骰{die}{'+' if mods >= 0 else ''}{mods}={total}"
                      f"({'、'.join(notes) if notes else '无修正'}) → {TIER_NAMES[tier]}")
        if p["line"]:
            report.append(f"  {name}留言:「{p['line']}」")
        it = p["intent"]
        if tier == "failure":
            slip["danger_delta"] += 1
            if it == "confront":
                slip["vitality_delta"][seat] -= 1
                report.append(f"  代价:{name}挂了彩(生命-1),局势更险了")
            else:
                report.append("  代价:局势更险了(危险+1)")
        elif tier == "mixed_success":
            if it in ("advance", "explore"):
                slip["progress_delta"] += 1
            # v0.3:悬事由暗典管理,勉强成功不再增殖新问号
        else:
            s.setdefault("wins", {}).setdefault(it, 0)
            s["wins"][it] += 1
            if it == "advance":
                slip["progress_delta"] += 2 if tier == "success" else 3
            elif it == "explore":
                slip["progress_delta"] += 1
                if tier == "critical_success":
                    if "found_the_key_truth" not in s["flags"] and \
                            "found_the_key_truth" not in slip["flags_added"]:
                        slip["flags_added"].append("found_the_key_truth")
                        report.append("  在最不可能的地方,摸到了这世界藏起来的一角真相")
                    if ident["gift"]["kind"] == "explore_crit_item":
                        item = {"id": f"found-{s['rolls_used']}",
                                "name": "路上寻获的小物", "use": ["advance"]}
                        slip["items_gained"].append((seat, item))
                        report.append(f"  {name}顺手寻获:{item['name']}")
                    # 先知情报:撕一页原典,私密塞给探到的人
                    chron = _ep(s).get("chronicle") or []
                    if s["prophecy_i"] < len(chron):
                        page = chron[s["prophecy_i"]]
                        s["prophecy_i"] += 1
                        s["prophecies"][seat].append(
                            f"原典第{page.get('chapter', '?')}章《{page['title']}》:{page['event']}")
                        report.append(f"  ◆ {name}瞥见了这个世界原本的样子(私密情报,仅其本人可见)")
            elif it == "confront":
                slip["progress_delta"] += 1
                slip["danger_delta"] -= 1
                report.append("  挡路的东西退了半步(危险-1)")
            elif it == "recover":
                heal = [seat]
                if ident["gift"]["kind"] == "recover_heals_both":
                    heal = [a, b]
                    report.append("  一双稳当的手:两人都缓了过来")
                for hseat in heal:
                    slip["vitality_delta"][hseat] += 1
            if tier == "critical_success":
                crits = s.setdefault("crits", {})
                crits[seat] = crits.get(seat, 0) + 1
                if it == "advance" and ident["gift"]["kind"] == "advance_crit_clock":
                    slip["clock_delta"] = 0
                    report.append("  抄了近路:这一幕没有花掉时钟")

    # 剧情 NPC 窗口:追查者按本幕骰果裁决;最后一个窗口错过即永久埋没。
    # 硬茬人格例外:追查失败即入墙角,窗口顺延,直到开口或被打服——绝不瞬移。
    due = _npc_due(s, s["scene_index"])
    if due:
        npc_name = due["npc"]["name"]
        hard = due["npc"].get("persona", "") in HARD_PERSONAS
        pursuers = [(seat, p) for seat, p in ((a, pa), (b, pb))
                    if p.get("target") == "npc"]
        showdown = due.get("cornered") and any(
            p["intent"] == "confront" for _, p in pursuers)
        if showdown and any(tiers[seat] in ("success", "critical_success")
                            for seat, p in pursuers if p["intent"] == "confront"):
            # 摊牌得胜:真相到手,反派势力就地瓦解,进度大涨
            _quest_resolve(s, due, report, "刀口之下")
            s["facts"].append(f"{npc_name}被当面制服,他背后的势力就此散了。")
            slip["progress_delta"] += 2
            report.append(f"  ◆ {npc_name}的势力被打散——这条街出了口恶气(进度+2)")
        elif any(tiers[seat] in ("success", "critical_success")
                 for seat, _ in pursuers):
            _quest_resolve(s, due, report, f"从{npc_name}口中问出")
        elif any(tiers[seat] == "mixed_success" for seat, _ in pursuers):
            if due.get("cornered"):
                _extend_window(due, s["scene_index"])
                report.append(f"  与{npc_name}一伙拉锯不下——他仍被困在墙角,下一幕再见分晓。")
            else:
                report.append(f"  {npc_name}只留下半句话,便隐入人群——话没说完。")
        elif pursuers:
            if hard:
                _extend_window(due, s["scene_index"])
                if not due.get("cornered"):
                    due["cornered"] = True
                    report.append(f"  ◆ {npc_name}被逼到了墙角——他没走脱。"
                                  "下一幕要么他开口,要么刀兵说话(追查他只能【对抗】)。")
                else:
                    report.append(f"  {npc_name}的人手围了上来,你们没能撕开缺口"
                                  "——他还困在墙角。")
            else:
                report.append(f"  {npc_name}被惊动,消失在暗处。")
        else:
            if due.get("cornered"):
                _extend_window(due, s["scene_index"])
                report.append(f"  {npc_name}仍被困在墙角,虎视眈眈——没人上前,僵局又拖了一幕。")
            else:
                report.append(f"  {npc_name}在人群边缘停了停,无人上前,他转身离去。")
        if due["status"] == "open" and s["scene_index"] >= max(due["windows"]):
            due["status"] = "lost"
            report.append(f"◆ {npc_name}再也不会出现了——某段真相就此埋没。")

    # NPC响应协议(B期):点名在场对象且没骰砸,对方下一幕必须有所回应,禁止空气
    obj_by_id = {o["id"]: o for o in scene.get("objects", [])}
    interactions = []
    for seat, p in ((a, pa), (b, pb)):
        t = p.get("target")
        if not t or t == "npc" or t not in obj_by_id:
            continue
        ident = _identity(s, s["identities"][seat])
        if tiers[seat] in ("mixed_success", "success", "critical_success"):
            interactions.append({
                "object_id": t, "object_name": obj_by_id[t]["name"],
                "by": ident["name"], "action": p["action"][:80],
                "tier": tiers[seat], "about": p.get("about")})
            report.append(f"  ◆ {ident['name']}与{obj_by_id[t]['name']}正面交涉"
                          "——对方下一幕必须有所回应")
            # 追问机制:点对悬事且判定成功=逼问一次;两次(卓越算两次)谜底必出。
            # 能问对人、问对问题,本身就是解谜成果——不许守门守到终局。
            if p.get("about") and tiers[seat] in ("success", "critical_success"):
                q = next((x for x in s.get("side_quests") or []
                          if x["status"] == "open"
                          and x["question"] == p["about"]), None)
                if q:
                    q["pressed"] = q.get("pressed", 0) + \
                        (2 if tiers[seat] == "critical_success" else 1)
                    if q["pressed"] >= 2:
                        _quest_resolve(s, q, report, "追问到底")
                    else:
                        report.append(f"  ◆ 这一问问到了痛处——「{p['about']}」"
                                      "的口风已被撬松,再追问一次,真相必出。")
        elif tiers[seat] == "failure":
            # 对象可能是人也可能是物,措辞须两者通吃。
            report.append(f"  {ident['name']}在{obj_by_id[t]['name']}那里没问出什么来,"
                          "线头断在手里。")
    # 谜底本幕已出的,追问债随之销账——真相大白就是最好的回应(三测毛边①)
    interactions = [i for i in interactions
                    if not i.get("about") or i["about"] in s["hooks"]]
    s["pending_interactions"] = interactions or None

    ia, ib = pa["intent"], pb["intent"]
    both_ok = all(t != "failure" for t in tiers.values())
    if both_ok and (("support" in (ia, ib)) or {"advance", "explore"} == {ia, ib}
                    or ia == ib == "advance"):
        slip["synergy_delta"] += 1
    for seat, p in ((a, pa), (b, pb)):
        if p["intent"] == "support" and tiers[seat] in ("success", "critical_success") \
                and _identity(s, s["identities"][seat])["gift"]["kind"] == "support_synergy":
            slip["synergy_delta"] += 1

    _resolve_event(s, scene, slip, report)

    for law in s["world"]["laws"]:
        tk = law["trigger_kind"]
        if tk.startswith("intent:"):
            want = tk.split(":", 1)[1]
            for seat, p in ((a, pa), (b, pb)):
                if p["intent"] != want:
                    continue
                if want == "confront" and _identity(
                        s, s["identities"][seat])["gift"]["kind"] == "confront_no_law":
                    report.append("  这条法则认得他,没有应验")
                    continue
                _apply_law_cost(s, slip, law, report)
        elif tk.startswith("clock>=") and s["clock"] >= int(tk[7:]):
            _apply_law_cost(s, slip, law, report)
        elif tk.startswith("danger>=") and s["danger"] >= int(tk[8:]):
            _apply_law_cost(s, slip, law, report)

    if s.get("main_goal_locked"):
        # 主线锁定即冻结:进度与时钟是主线的账,余波幕不再改写
        slip["progress_delta"] = 0
        slip["clock_delta"] = 0
    s["progress"] = max(0, min(10, s["progress"] + slip["progress_delta"]))
    s["danger"] = max(0, min(10, s["danger"] + slip["danger_delta"]))
    s["synergy"] = max(0, min(5, s["synergy"] + slip["synergy_delta"]))
    s["clock"] = min(8, s["clock"] + slip["clock_delta"])
    s["danger_peak"] = max(s.get("danger_peak", 0), s["danger"])
    if s["progress"] >= 10 and not s.get("main_goal_locked"):
        # 进度满即锁定:主线成了,进度此后不再回退(余下回合推各自目标与支线)
        s["main_goal_locked"] = True
        s["goal_locked_at_scene"] = s["scene_index"]
        report.append("◆ 进度满格——主线已锁定,进度不再回退。余下回合可继续推各自目标与支线。")
    for seat in (a, b):
        s["vitality"][seat] = max(0, min(3, s["vitality"][seat]
                                          + slip["vitality_delta"][seat]))
    for f in slip["flags_added"]:
        if f not in s["flags"]:
            s["flags"].append(f)
    s["facts"].extend(slip["facts_added"])
    for h in slip["hooks_added"]:
        if h not in s["hooks"]:   # 悬事永不重复
            s["hooks"].append(h)

    # 数值考验支线:账本更新完毕后对表,条件一到,真相自动大白
    for q in s.get("side_quests") or []:
        if q["status"] == "open" and q["unlock_kind"] == "stat":
            (k, v), = list(q["stat"].items())
            cur = s["synergy"] if k == "synergy>=" \
                else s.get("wins", {}).get(k.split("_wins")[0], 0)
            if cur >= v:
                _quest_resolve(s, q, report, "数值考验通过")

    for seat, item in slip["items_gained"]:
        s["inventory"][seat].append(item)

    for th in s["world"].get("hidden_threads", []):
        if th["id"] in s["hidden_fired"]:
            continue
        req = th["required"]
        hit = ("flag" in req and req["flag"] in s["flags"]) or \
              ("synergy>=" in req and s["synergy"] >= req["synergy>="]) or \
              ("progress>=" in req and s["progress"] >= req["progress>="]) or \
              ("danger>=" in req and s["danger"] >= req["danger>="])
        if hit:
            s["hidden_fired"].append(th["id"])
            s["facts"].append(th["brief"])
            report.append(f"◆ 暗线浮出:{th['brief']}")
            if th.get("effect_kind") == "truth":
                if "truth_known" not in s["flags"]:
                    s["flags"].append("truth_known")

    # 战果入账:成功即既成事实,荷官不得否认(早期测试报告 §3)
    for seat, p in ((a, pa), (b, pb)):
        if tiers[seat] in ("success", "critical_success") and p["action"]:
            ident = _identity(s, s["identities"][seat])
            s["facts"].append(f"[第{s['scene_index']}幕]{ident['name']}已做到:{p['action'][:50]}")
    # 逐席目标:谁本幕成功,谁只推进自己的当前里程碑。
    for seat in s["seats"]:
        cur = _current_milestone(s, seat)
        if not cur or tiers[seat] not in ("success", "critical_success"):
            continue
        goal = _active_goal(s, seat)
        goal["milestones_done"].append(cur["id"])
        if len(goal["milestones_done"]) == len(goal["milestones"]):
            goal["goal_locked"] = True
        s["progress"] = min(10, s["progress"] + 2)
        ident = _identity(s, s["identities"][seat])["name"]
        s["facts"].append(f"{ident}的里程碑达成:{cur['text']}")
        report.append(f"◆ {ident}的里程碑达成:{cur['text']}(进度+2)")
    goals = [_active_goal(s, seat) for seat in s["seats"]]
    if goals and all(goal and goal.get("goal_locked") for goal in goals):
        s["progress"] = 10
        if not s.get("main_goal_locked"):
            s["main_goal_locked"] = True
            s["goal_locked_at_scene"] = s["scene_index"]
            if any(q["status"] == "open" for q in s.get("side_quests") or []):
                report.append("◆ 两位玩家的目标全部达成——结局已锁定,余下回合可自由探索支线!")
            else:
                report.append("◆ 两位玩家的目标全部达成,支线亦已尽数了结——尘埃落定。")

    report.append(f"账本:进度{s['progress']}/10 危险{s['danger']}/10 "
                  f"默契{s['synergy']}/5 时钟{s['clock']}/8 "
                  f"生命 {s['vitality'][a]}/{s['vitality'][b]}")
    _log(s, scene, {a: pa, b: pb}, slip, report)

    alive = [x for x in s["seats"] if s["vitality"][x] > 0]
    locked = s.get("main_goal_locked")
    goals_done = all((_active_goal(s, x) or {}).get("goal_locked") for x in s["seats"])
    if len(alive) == 0:
        _finish(s, "BE", "all_down")
    elif s["danger"] >= 10:
        # 危险满格:不论主线锁没锁,当场 BE
        _finish(s, "BE", "world_lost")
    elif locked and goals_done and not any(q["status"] == "open"
                                           for q in s.get("side_quests") or []):
        # 余账清空:主线已锁、双方目标都成、支线尽数了结——当场收卷
        _finish_auto(s, "goal")
    elif max(s.get("end_streaks", {}).values() or [0]) >= 3:
        # 三辞而别:一人连提三幕停笔,引擎替这段散伙收卷
        _finish_auto(s, "insist_end")
    elif s["scene_index"] >= MAX_SCENES:
        # 幕数走满,引擎强制收卷——不看任何人脸色
        _finish_auto(s, "out_of_time")
    elif s["clock"] >= 8 and not locked:
        _finish_auto(s, "out_of_time")
    else:
        s["stage"] = "scenegen"
        s["narration_request"] = {"kind": "gen_scene",
                                  "context": _scene_context(s, s["history"][-1]["report"])}


def _apply_law_cost(s, slip, law, report):
    ck = law["cost_kind"]
    if ck in ("progress", "clock") and s.get("main_goal_locked"):
        report.append(f"  法则失效(主线已锁定):{law['text']}")
        return
    if ck == "danger":
        slip["danger_delta"] += 1
        report.append(f"  法则应验:{law['text']}")
    elif ck == "vitality":
        pass  # 生命型法则代价由失败结算承担,MVP 不重复扣
    elif ck == "clock":
        slip["clock_delta"] += 1
        report.append(f"  法则应验:{law['text']}(时钟+1)")
    elif ck == "progress":
        slip["progress_delta"] -= 1
        report.append(f"  法则应验:{law['text']}(进度-1)")
    elif ck == "flag":
        tag = f"law_{law['id']}_{s['scene_index']}"
        if tag not in slip["flags_added"]:
            slip["flags_added"].append(tag)
            report.append(f"  法则应验:{law['text']}")


def _log(s, scene, commits, slip, report):
    s["history"].append({
        "scene_index": s["scene_index"], "title": scene["title"],
        "story_text": scene["text"],
        "story_responses": [r["detail"] for r in (scene.get("npc_responses") or []) if r.get("detail")],
        "commits": deepcopy(commits), "slip": deepcopy(slip),
        "report": report,
    })
    s["pending"] = {}


REASON_NAMES = {"goal": "目标达成", "all_down": "无人生还", "world_lost": "世界失守",
                "sacrifice": "有人没能回来", "out_of_time": "时钟走完",
                "mutual_end": "双双停笔", "insist_end": "三辞而别"}


def _finish(s, kind, reason):
    drives = {}
    for seat in s["seats"]:
        if not s["identities"][seat]:
            continue
        ident = _identity(s, s["identities"][seat])
        d = ident["secret_drive"]
        ok = False
        if d["kind"] == "events_won>=2":
            ok = (s.get("events") or {}).get("won", 0) >= 2
        elif d["kind"] == "crit>=1":
            ok = (s.get("crits") or {}).get(seat, 0) >= 1
        elif d["kind"] == "danger_peak<=6":
            ok = s.get("danger_peak", s["danger"]) <= 6
        elif d["kind"] == "partner_full_vitality":
            other = [x for x in s["seats"] if x != seat][0]
            ok = s["vitality"][other] >= 3
        elif d["kind"] == "clock<=6":
            ok = s["clock"] <= 6
        elif d["kind"] == "hooks_resolved>=2":
            ok = s["hooks_resolved"] >= 2
        elif d["kind"] == "both_alive":
            ok = all(s["vitality"][x] > 0 for x in s["seats"])
        elif d["kind"] == "hidden_triggered":
            ok = bool(s["hidden_fired"])
        drives[seat] = {"text": d["text"], "achieved": ok,
                        "identity": ident["name"]}
    goal_results = []
    for seat in s["seats"]:
        identity = (_identity(s, s["identities"][seat])["name"]
                    if s["identities"].get(seat) else None)
        for goal in s["player_goals"][seat]:
            goal_results.append({
                "seat": seat, "identity": identity, "text": goal["text"],
                "achieved": bool(goal.get("goal_locked")),
                "abandoned": bool(goal.get("abandoned")),
            })
    world_thread = {
        "text": (s["world"] or {}).get("world_thread", ""),
        "outcome": _ep(s).get("original_ending", ""),
    }
    # 大主线结算只露一行:保持神秘才是余味(C期设计稿 §5)
    canon = _canon_now(s)
    if canon:
        world_thread["canon_line"] = canon["line"]
    s["ending"] = {"kind": kind, "reason": reason,
                   "reason_name": REASON_NAMES[kind_reason_key(kind, reason)],
                   "text": None,   # 待荷官成文
                   "secret_drives": drives,
                   "world_name": s["world"]["world_name"] if s["world"] else "未名之地",
                   "seed": s["seed"], "axes": s["axes"]}
    s["stage"] = "endinggen"
    s["narration_request"] = {
        "kind": "render_ending",
        "context": {
            "world": _world_brief(s), "kind": kind, "reason": reason,
            "reason_name": REASON_NAMES[kind_reason_key(kind, reason)],
            "player_goals": goal_results, "world_thread": world_thread,
            "tracks": {"progress": s["progress"], "danger": s["danger"],
                       "synergy": s["synergy"], "clock": s["clock"],
                       "vitality": dict(s["vitality"])},
            "identities": [_identity(s, s["identities"][x])["name"]
                           for x in s["seats"] if s["identities"][x]],
            "facts": s["facts"][-10:],
            "main_goal_locked": s.get("main_goal_locked", False),
            "goal_locked_at_scene": s.get("goal_locked_at_scene"),
            "events": deepcopy((s.get("events") or {}).get("log", [])),
            "secret_drives": deepcopy(drives),
            "unresolved_hooks": list(s["hooks"]),
            # 支线对账单:解开的谜底可入文;未解开的谜底禁止入文
            "side_quests": [
                {"question": q["question"], "truth": q["truth"],
                 "status": q["status"],
                 "npc_name": (q.get("npc") or {}).get("name")}
                for q in s.get("side_quests") or []],
            "hidden_fired": [th["brief"] for th in
                             (s["world"].get("hidden_threads", []) if s["world"] else [])
                             if th["id"] in s["hidden_fired"]],
            "scene_titles": [h["title"] for h in s["history"]],
            "original_ending": _ep(s).get("original_ending"),
            "chronicle_titles": [c["title"] for c in
                                 _ep(s).get("chronicle", [])],
        },
    }


def kind_reason_key(kind, reason):
    return reason
