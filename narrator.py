"""叙事荷官适配器(宿主侧):调用外部 API 按合同生成,校验后交回宿主。

- 配置:data/narrator.json {base_url, api_key, model, timeout}(gitignore);
- 协议:OpenAI 兼容 chat/completions,强制 JSON 输出;
- 荷官没有玩家席位、行动权、计分权与结局判定权(系统约束写死在提示里);
- 校验失败返回错误,由人类一键重召;本模块绝不重试、不换模型、不编造兜底。
"""

import json
import re
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
CONFIG_PATH = BASE / "data" / "narrator.json"

INTENTS = ["advance", "explore", "support", "confront", "recover"]
GIFT_KINDS = ["explore_crit_item", "support_synergy", "advance_crit_clock",
              "confront_no_law", "recover_heals_both", "ones_are_fours"]
FLAW_KINDS = ["advance_minus", "explore_minus", "support_minus",
              "confront_minus", "confront_minus_danger5", "six_feeds_danger"]
DRIVE_KINDS = ["shared_items>=3", "partner_full_vitality", "clock<=6",
               "hooks_resolved>=2", "both_alive", "hidden_triggered"]
POWERS = ["无超凡", "低武", "中武", "高武", "神话级"]
COST_KINDS = ["danger", "vitality", "progress", "clock", "flag"]

SYSTEM_PROMPT = (
    "你是双人文字冒险《口袋穿越》的叙事荷官。你负责把游戏引擎提供的世界事实与"
    "裁决结果写成玩家可读的剧情。你没有玩家席位,没有行动权、计分权和结局判定权。"
    "你不得替玩家说话、选择、补写心理或改变任何数值与既成事实。"
    "不得主动加入恋爱剧情;两名玩家是同行的旅伴,关系如何发展只来自他们的真实行动。"
    "输出必须是严格的 JSON,不带任何注释、前后缀或代码围栏。"
)


class NarratorError(Exception):
    pass


def _config():
    if not CONFIG_PATH.is_file():
        raise NarratorError("荷官未配置:请在 data/narrator.json 填入 base_url/api_key/model")
    return json.loads(CONFIG_PATH.read_text("utf-8"))


def _chat(prompt, temperature, kind=None):
    cfg = _config()
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": cfg["model"],
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "max_tokens": 3000,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['api_key']}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("timeout", 90)) as r:
            body = json.loads(r.read())
    except Exception as e:
        raise NarratorError(f"荷官呼叫失败:{type(e).__name__}: {e}") from e
    try:
        text = body["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            start = min(x for x in (text.find("{"), text.find("[")) if x >= 0)
            end = max(text.rfind("}"), text.rfind("]"))
            text = text[start:end + 1]
        # 宽容修复:尾逗号与字符串内裸换行是大模型高发笔误,机械容错不改语义
        text = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            # 二次自愈:行尾缺逗号(值结尾直接换行接下一个键/元素)
            healed = re.sub(r'([j"\]}0-9el])\s*\n(\s*["{\[])', r"\1,\n\2", text)
            try:
                return json.loads(healed, strict=False)
            except json.JSONDecodeError:
                # 结局合同只有一个 text 字段:JSON 碎了也能打捞正文
                if kind == "render_ending":
                    m = re.search(r'"text"\s*:\s*"(.*)', text, re.S)
                    if m:
                        salvage = m.group(1).rstrip()
                        salvage = re.sub(r'["\s}`]*$', "", salvage)
                        salvage = (salvage.replace('\\n', '\n')
                                   .replace('\\"', '"'))
                        if len(salvage) >= 20:
                            return {"text": salvage}
                raise
    except Exception as e:
        try:  # 失败原稿落盘,便于尸检
            (BASE / "data" / "narrator_last_error.txt").write_text(
                body["choices"][0]["message"]["content"], encoding="utf-8")
        except Exception:
            pass
        raise NarratorError(f"荷官回文不是合法 JSON:{e}") from e


# ---------------- 四张合同 ----------------

def call(kind, context):
    """按合同生成并校验。返回校验后的 data;失败抛 NarratorError。"""
    prompt = PROMPTS[kind](context)
    # 1.3 高温实测会烧坏 JSON 纪律;1.0 的中文创意已经够野了
    temp = 1.0 if kind in ("gen_world", "gen_identities") else 0.9
    data = _chat(prompt, temp, kind=kind)
    VALIDATORS[kind](data)
    return data


def _p_world(ctx):
    a = ctx["axes"]
    persona_hint = (f";此人性格底色已定死={ctx['npc_persona']},名字、做派、说话方式都要贴这个性格"
                    if ctx.get("npc_persona") else "")
    if "engine" in a:   # 《口袋穿越》新种子:世界生成器 ≠ 任务生成器
        scope = a.get("scope", "街坊门户")
        grand = scope in ("一城一地", "天下大势")
        scope_line = f"剧情规模={scope}" + (
            f"({ctx['scope_intensity']})" if ctx.get("scope_intensity") else "")
        scale_rules = "" if grand else """
- 规模纪律(违反即废稿):本局禁止生成——世界毁灭、全城覆灭、文明断绝、末日倒计时、
  "幕后大人物制造了一切"的总阴谋、十幕内推翻政权或打败终极反派、
  "所有小事其实都连着终极秘密"。房租、生意、婚丧嫁娶、邻里矛盾、丢东西、
  修房子、赶集、收徒、小骗局、某个NPC自己的小麻烦——这些本身就是完整剧情,
  不需要证明它们关系世界命运;"""
        seed_block = f"""世界种子(必须全部体现):
世界题材={a['genre']},力量等级={a['power']},故事发动机={a['engine']},特色元素={a['element']},
情绪基调={a['mood']},进入方式={a['entry']},核心变数={a['variable']},{scope_line}。

种子怎么读:
- 世界题材决定这个世界本身是部什么小说——它在玩家到来之前已经运转了很久,
  也将在玩家离开后继续运转;
- 剧情规模决定**本局镜头的大小**,不是世界的大小:世界尽可宏大(原典主角也许
  正在万里之外经历惊天动地的主线),但玩家掉进的只是其中一小段、一个角落——
  像随手翻开一部长篇小说的第437章,而不是从序章到终局的压缩版;
- 故事发动机决定**这一局**玩家被卷入的事:只有抽到「危机倒计时」才允许大限将至,
  且倒数的也只是本规模内的事(矿洞三日后塌方,不是宇宙毁灭);其余发动机都是
  世间常事,世界不需要摇摇欲坠,鸡毛蒜皮也能有好故事;{scale_rules}
- 特色元素为(无特别元素)时不要硬塞超凡设定;
- 进入方式决定两位玩家与这个世界的关系(穿书成配角=他们是原典里的路人)。"""
        goal_desc = "本局共同主目标:由故事发动机引出的一件具体可完成的事,规模不得超出剧情规模"
        clock_desc = ("时钟在这局代表什么、走满了会发生什么,一句"
                      "——不必是灾难,可以只是'商队出发了''大典落幕了'")
        chron_desc = ("恰好8章,**本局这段小章节**没有玩家时本该怎么走——只写玩家落点"
                      "附近的这段事,远处的天下大势最多露一句、不展开;按时间排序")
        orig_desc = "没人干预时**这段事**的自然了局(≤80字)——不必是世界的结局"
    else:               # 《口袋跑团》经典种子:危机跑团,直给
        seed_block = f"""世界种子(必须全部体现):
题材={a['form']},力量等级={a['power']},冒险类型={a['kind']},情绪基调={a['mood']},核心变数={a['variable']}。"""
        goal_desc = "本局共同主目标,一句,具体可完成"
        clock_desc = "时钟走满会发生什么,一句(危机跑团:通常是大祸临头)"
        chron_desc = ("恰好8章,这个世界**没有玩家时**本该上演的完整剧情,按时间排序")
        orig_desc = "原典结局一句:没有任何人干预时,这个世界最后怎么了(≤80字)"
    return f"""为一局新游戏生成世界卡。{seed_block}

只输出这个 JSON:
{{
 "world_name": "不超过12字",
 "premise": "一句话说明两位玩家来到了哪里",
 "lore": "不超过400字的世界背景,三段以内,必须埋入核心变数",
 "power_level": "{a['power']}",
 "public_goal": "{goal_desc}",
 "clock_text": "{clock_desc}",
 "milestones": [把主目标拆成2到3步,按先后排序,每步 {{"id":"m1这样的短名","text":"一句可判定的阶段目标,如『通过西境检查站』"}}——玩家每完成一步,引擎当场记账;全部完成即结算,你无权拖延],
 "laws": [2到3条,每条 {{"id":"law_英文短名","text":"玩家能读懂的世界法则",
   "trigger_kind":"只能严格写成以下形式之一(不要照抄占位符):intent:advance / intent:explore / intent:support / intent:confront / intent:recover / clock>=5 这种带具体数字的 / danger>=6 这种带具体数字的",
   "cost_kind":"danger|progress|clock|flag 之一"}}],
 "opening_facts": ["开局已成立的3到5条事实,短句"],
 "hidden_threads": [1到2条,每条 {{"id":"h-英文短名",
   "required": 必须逐字采用下面四种写法之一,键名一个字符都不能改:
     {{"flag": "found_the_key_truth"}} 或 {{"synergy>=": 4}} 或 {{"progress>=": 7}} 或 {{"danger>=": 6}},
   "effect_kind":"truth|ending_modifier",
   "brief":"暗线浮出时向玩家公布的一句话"}}],
 "side_quests": [恰好2条支线悬案。这是玩家会反复追问的谜题,谜底**现在就定死**,
   写在这里只有引擎能看到;此后你永远只许照抄,不许改写、不许另编:
   第1条 {{"id":"sq_npc","question":"一句悬而未决的谜题(玩家视角的问句)",
     "truth":"谜底,≤80字,必须直接回答谜题,且与lore、原典自洽",
     "unlock_kind":"npc",
     "npc":{{"name":"知晓此事的剧情人物称呼","desc":"他登场时的样子与来意暗示,一句{persona_hint}"}}}},
   第2条 {{"id":"sq_stat","question":"另一句谜题","truth":"谜底,≤80字,同上要求",
     "unlock_kind":"stat",
     "stat": 逐字采用其一:{{"synergy>=": 3}} 或 {{"explore_wins>=": 3}} 或 {{"confront_wins>=": 2}}}}],
 "chronicle": [{chron_desc},
   每章 {{"chapter":1,"title":"≤8字","event":"本章原典事件一句,≤60字"}}——
   这是只有你和引擎能看到的底本小说,玩家永远看不到,直到终局才揭晓],
 "original_ending": "{orig_desc}"
}}
要求:法则是给玩家的真实约束与权衡,不是装饰;隐藏线要值得期待;
原典要是一个自洽的完整故事(玩家不来它也成立);
支线谜底是本局唯一的真相来源——谜底答不上谜题即废稿;
言情类题材允许 NPC 之间的感情戏,但两位玩家之间仍禁止恋爱剧情。"""


def _p_identities(ctx):
    w = ctx["world"]
    return f"""为世界《{w['world_name']}》生成 6 张身份卡。世界背景:{w['premise']} {w['lore'][:200]}

只输出这个 JSON(顶层是数组,恰好6个元素):
[{{"id":"英文短名","name":"身份称呼","origin":"一句来历,贴合世界",
  "specialty":"advance|explore|support|confront|recover 之一(六张卡尽量分散)",
  "gift":{{"kind":"从 {GIFT_KINDS} 里选","text":"用这个世界的语言描述这项天赋"}},
  "flaw":{{"kind":"从 {FLAW_KINDS} 里选","text":"用这个世界的语言描述这个弱点"}},
  "secret_drive":{{"kind":"从 {DRIVE_KINDS} 里选","text":"该身份的私密执念,一句"}},
  "starting_item":{{"id":"英文短名","name":"开局物品名","use":["利于的意图,{INTENTS} 的子集,1到2个"]}}
}}]
注意:kind 字段只能从给定菜单里选,机制预算因此天然一致;你的发挥全在文案里。"""


def _p_scene(ctx):
    w = ctx["world"]
    last = "\n".join(ctx["last_report"]) if ctx.get("last_report") else "(这是第一幕)"
    ms = "".join(f"\n- [{'✓已达成' if m['done'] else '未达成'}] {m['text']}"
                 for m in ctx.get("milestones", []))
    cur = ctx.get("current_milestone")
    chron = ""
    if ctx.get("chronicle_now"):
        chron = f"""
【原典推演(玩家不可见的底本)】这个世界没有玩家时,此刻本该发生:
{ctx['chronicle_now']}
但两位穿越者已经造成了这些偏移(见既成事实)。你的任务不是编新故事,
而是**推演**:原典的这一章,被他们的行动扰动之后,现场变成了什么样。
原典中的人物、事件照常想登场,除非偏移已经改变了它们。"""
    npc = ""
    if ctx.get("npc_onstage"):
        n = ctx["npc_onstage"]
        persona = f"性格底色={n['persona']},言行必须贴此性格;" if n.get("persona") else ""
        npc = f"""
【剧情人物登场(必须执行)】{n['name']}:{n['desc']}
{persona}此人知晓「{n['question']}」的内情。把他写进 text 的现场,并放进 objects
(该条 id 必须恰好是 "npc")。他只现身、只露暗示,绝不主动全盘托出;
玩家是否追上去、能不能问出来,由引擎裁决,与你无关。"""
    oq = ctx.get("open_questions") or []
    return f"""为《{w['world_name']}》生成第 {ctx['scene_index']} 幕场景。
世界目标:{w['public_goal']}
里程碑账本(已达成的绝不能推翻或重考):{ms or "(无)"}
本幕危机必须服务于当前里程碑:{cur or "全部已达成,收束"}{chron}{npc}
世界法则:{'; '.join(w['laws'])}
时钟含义:{w.get('clock_text') or "时钟走满,这段故事就到站"}
当前账本:{json.dumps(ctx['tracks'], ensure_ascii=False)}
在场身份:{json.dumps(ctx['identities'], ensure_ascii=False)}
既成事实(不可推翻):{json.dumps(ctx['facts'], ensure_ascii=False)}
未解决悬事:{json.dumps(ctx['hooks'], ensure_ascii=False)}
上一幕结果:
{last}

{f"节奏指令(必须遵守):{ctx['pacing']}" if ctx.get("pacing") else ""}

只输出这个 JSON:
{{"title":"不超过10字","text":"不超过300字,只描写玩家行动前已经发生的事,承接上一幕结果与既成事实;危险值越高氛围越紧",
 "crisis":"本幕必须面对的问题,一句",
 "objects":[3到4个,每个 {{"id":"英文短名","name":"对象名","hint":"玩家此刻能观察到的一句线索"}}],
 "questions":[0到2条,**只能从这份清单里逐字挑选**:{json.dumps(oq, ensure_ascii=False)};
   清单为空或都不贴切就写 []。禁止自创新谜题,禁止改写措辞——悬事的生老病死归引擎管]}}
铁律(违反即废稿):
- 用第三人称写场景,绝不用"你/你们"直接称呼玩家,绝不与玩家对话;
- 上一幕玩家做了什么,以裁决记录为准——不得移动、囚禁、伤害玩家角色,
  不得替他们说话、做事或安排遭遇结果;
- NPC 可以有态度,但不得回应玩家角色没有说出口的话;
- 不替玩家迈步、不预告正确解法、不否认既成事实、不无视未解决悬事;
- 普通生活事件本身就有完整的叙事价值,不需要升级成更大的秘密、象征或危机——
  玩家没有主动追求升级时,禁止替他们升级:修一双鞋就让它是一双鞋,
  不许鞋底藏上古符号、不许店主女儿是隐世高人之后、不许一碗汤关系城市存亡。"""


def _p_ending(ctx):
    w = ctx["world"]
    sq = ""
    quests = ctx.get("side_quests") or []
    if quests:
        lines = []
        for q in quests:
            if q["status"] == "resolved":
                lines.append(f"- 已解开:「{q['question']}」→ 真相:{q['truth']}(可以入文回响)")
            else:
                how = f"知情人{q['npc_name']}未被问到" if q.get("npc_name") else "考验未达成"
                lines.append(f"- 未解开({how}):「{q['question']}」——玩家至终不知道答案。"
                             "结局里**禁止**揭示或暗示谜底,只可写这个谜随他们一同留在了那个世界")
        sq = "\n【支线对账(纪律)】过程中没挣到的答案,结局无权补发:\n" + "\n".join(lines)
    return f"""为《{w['world_name']}》写终局。结局类型:{ctx['kind']}({ctx['reason_name']})。{sq}
时钟含义:{w.get('clock_text') or "时钟走满,这段故事就到站"}
(若结局因"时钟走完"或"三辞而别"而来,按时钟含义与散伙的分量写,不必强行升级成灾难。)
最终账本:{json.dumps(ctx['tracks'], ensure_ascii=False)}
两位旅人:{json.dumps(ctx['identities'], ensure_ascii=False)}
走过的地方:{json.dumps(ctx['scene_titles'], ensure_ascii=False)}
既成事实:{json.dumps(ctx['facts'], ensure_ascii=False)}
已浮出的暗线:{json.dumps(ctx['hidden_fired'], ensure_ascii=False)}

{f'''【原典对照(必写)】这个世界原本的结局是:{ctx['original_ending']}
原典各章:{json.dumps(ctx.get('chronicle_titles', []), ensure_ascii=False)}
结局正文必须包含时间线对照:先用一两句写"本该发生的",再写"因为这两位
穿越者,实际发生的"——如果他们终究没能改变什么,也如实写,那同样有分量。'''
 if ctx.get("original_ending") else ""}

结局纪律(违反即废稿):
- 只能写既成事实里真实发生过的事及其**直接**后果,禁止补写没演出来的新事件——
  过程里没有当众揭穿的阴谋,结局里就没人揭穿;没打过的反派,结局里就没被打败;
  没解除的诅咒,结局里仍在。玩家只知道了A,你无权推导他们后来完成了B和C;
- 不强制升华:不要总结主题、不要上价值、不要把玩家坚持的小事重新吞回大主题——
  一双鞋不必成为"人类对抗遗忘的火种",它是一双补好的鞋就够了;
- 允许没有"意义"的具体结果,允许世界的大问题继续存在、大势照旧推进,
  允许玩家只解决了一个局部问题就停笔。"鞋匠第二天照常开门,女儿第一次独自
  接了单,远处战争还在打,他们没再去管"——这样就是完整的结局。

只输出这个 JSON:
{{"text":"不超过400字的结局正文。必须与结局类型相符:HE收束而不腻,BE庄重而不残忍,TE余韵悠长。
引用至少一件既成事实;若有暗线,让它在结局里回响;写世界如何继续,不评价玩家。"}}"""


PROMPTS = {"gen_world": _p_world, "gen_identities": _p_identities,
           "gen_scene": _p_scene, "render_ending": _p_ending}


# ---------------- 校验器 ----------------

def _req(cond, msg):
    if not cond:
        raise NarratorError(f"荷官交稿不合格:{msg}")


def _v_world(d):
    _req(isinstance(d, dict), "世界卡须是对象")
    for k in ("world_name", "premise", "lore", "public_goal",
              "laws", "opening_facts", "hidden_threads"):
        _req(k in d, f"缺字段 {k}")
    _req(len(d["world_name"]) <= 16, "world_name 过长")
    _req(len(d["lore"]) <= 600, "lore 过长")
    # power_level 由引擎按种子注入,荷官写不写都以引擎为准
    _req(isinstance(d["laws"], list) and 1 <= len(d["laws"]) <= 4, "laws 数量不对")
    for l in d["laws"]:
        _req(all(k in l for k in ("id", "text", "trigger_kind", "cost_kind")), "law 缺字段")
        tk = l["trigger_kind"]
        ok = (tk.startswith("intent:") and tk[7:] in INTENTS) or \
             (tk.startswith("clock>=") and tk[7:].isdigit()) or \
             (tk.startswith("danger>=") and tk[8:].isdigit())
        _req(ok, f"trigger_kind 非法:{tk}")
        _req(l["cost_kind"] in COST_KINDS, f"cost_kind 非法:{l['cost_kind']}")
    _req(isinstance(d["opening_facts"], list) and 2 <= len(d["opening_facts"]) <= 6,
         "opening_facts 数量不对")
    _req(isinstance(d.get("milestones"), list) and 2 <= len(d["milestones"]) <= 4,
         "milestones 须是2到4步")
    mids = set()
    for m in d["milestones"]:
        _req(isinstance(m, dict) and m.get("id") and m.get("text"), "milestone 缺字段")
        _req(m["id"] not in mids, "milestone id 重复")
        mids.add(m["id"])
    _req(isinstance(d.get("chronicle"), list) and 6 <= len(d["chronicle"]) <= 10,
         "chronicle 须是6到10章的原典")
    for c in d["chronicle"]:
        _req(isinstance(c, dict) and c.get("title") and c.get("event"),
             "chronicle 章节缺字段")
    _req(isinstance(d.get("original_ending"), str) and d["original_ending"],
         "缺 original_ending")
    if not isinstance(d.get("clock_text"), str) or not d["clock_text"].strip():
        d["clock_text"] = "时钟走满,这段故事就到站。"   # 宽容:漏写不废稿
    _req(isinstance(d["hidden_threads"], list) and 1 <= len(d["hidden_threads"]) <= 3,
         "hidden_threads 数量不对")
    for t in d["hidden_threads"]:
        _req(all(k in t for k in ("id", "required", "effect_kind", "brief")), "thread 缺字段")
        r = t["required"]
        _req(isinstance(r, dict) and r, "thread 触发条件非法")
        # 规范化常见变体:synergy/progress/danger 裸键名、flag 给成列表、数字给成字符串
        fixed = {}
        for k, v in r.items():
            key = k.strip()
            if key in ("synergy", "progress", "danger"):
                key += ">="
            if key in ("synergy>=", "progress>=", "danger>="):
                try:
                    fixed[key] = int(v)
                except (TypeError, ValueError):
                    pass
            elif key == "flag":
                if isinstance(v, list) and v:
                    v = v[0]
                if isinstance(v, str) and v:
                    fixed[key] = v
        _req(fixed, f"thread 触发条件非法:{r}")
        t["required"] = fixed
        _req(t["effect_kind"] in ("truth", "ending_modifier"), "effect_kind 非法")
    # 支线暗典:恰好2条,一条NPC一条数值,谜题谜底俱全——这是余波幕的命根子
    sq = d.get("side_quests")
    _req(isinstance(sq, list) and len(sq) == 2, "side_quests 须恰好2条")
    kinds = sorted(q.get("unlock_kind") for q in sq if isinstance(q, dict))
    _req(kinds == ["npc", "stat"], "side_quests 须一条 npc 一条 stat")
    for q in sq:
        for k in ("id", "question", "truth", "unlock_kind"):
            _req(isinstance(q.get(k), str) and q[k].strip(), f"side_quest 缺字段 {k}")
        _req(len(q["truth"]) <= 160, "side_quest truth 过长")
        if q["unlock_kind"] == "npc":
            n = q.get("npc")
            _req(isinstance(n, dict) and n.get("name") and n.get("desc"),
                 "npc 支线缺 name/desc")
        else:
            st = q.get("stat")
            _req(isinstance(st, dict) and st, "stat 支线缺触发条件")
            fixed = {}
            for k, v in st.items():
                key = k.strip()
                if key in ("synergy", "explore_wins", "confront_wins"):
                    key += ">="
                if key in ("synergy>=", "explore_wins>=", "confront_wins>="):
                    try:
                        fixed[key] = int(v)
                    except (TypeError, ValueError):
                        pass
            _req(len(fixed) == 1, f"stat 触发条件非法:{st}")
            q["stat"] = fixed


def _v_identities(d):
    _req(isinstance(d, list) and len(d) == 6, "身份卡须恰好6张")
    ids = set()
    for i in d:
        for k in ("id", "name", "origin", "specialty", "gift", "flaw",
                  "secret_drive", "starting_item"):
            _req(k in i, f"身份缺字段 {k}")
        _req(i["id"] not in ids, "身份 id 重复")
        ids.add(i["id"])
        _req(i["specialty"] in INTENTS, "specialty 非法")
        _req(i["gift"].get("kind") in GIFT_KINDS, "gift.kind 不在菜单里")
        _req(i["flaw"].get("kind") in FLAW_KINDS, "flaw.kind 不在菜单里")
        _req(i["secret_drive"].get("kind") in DRIVE_KINDS, "drive.kind 不在菜单里")
        item = i["starting_item"]
        _req(all(k in item for k in ("id", "name", "use")), "物品缺字段")
        _req(isinstance(item["use"], list) and
             all(u in INTENTS for u in item["use"]), "物品 use 非法")


def _v_scene(d):
    for k in ("title", "text", "crisis", "objects"):
        _req(k in d, f"场景缺字段 {k}")
    _req(len(d["title"]) <= 14, "title 过长")
    _req(len(d["text"]) <= 450, "text 过长")
    _req(isinstance(d["objects"], list) and 2 <= len(d["objects"]) <= 5, "objects 数量不对")
    for o in d["objects"]:
        _req(all(k in o for k in ("id", "name", "hint")), "object 缺字段")
    if "questions" in d:
        _req(isinstance(d["questions"], list) and len(d["questions"]) <= 3,
             "questions 过多")
    else:
        d["questions"] = []


def _v_ending(d):
    _req(isinstance(d, dict) and "text" in d, "结局缺 text")
    _req(isinstance(d["text"], str) and 20 <= len(d["text"]) <= 600, "结局长度不对")


VALIDATORS = {"gen_world": _v_world, "gen_identities": _v_identities,
              "gen_scene": _v_scene, "render_ending": _v_ending}
