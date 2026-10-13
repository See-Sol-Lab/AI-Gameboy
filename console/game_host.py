"""牌桌宿主:鉴权、revision、规则调用与席位裁剪(蓝图 §3.1 / §8)。

宿主不读 Core、不读聊天记录、不调用模型,也不判断窗口"是不是本人"。
卡带规则是纯函数;宿主负责事务、版本钉死、失败边界与私牌隔离。
与卡带的唯一结构约定:full_state["phase"] 为 "playing" 或 "finished"。

所有对外方法返回 dict,一定带 "result" 键:
  ok / forbidden / stale_revision / rejected / cartridge_error / cartridge_version_missing
除 forbidden 外,凡持有效令牌的响应都附带该席位的最新观察(§16)。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import secrets
import time
from datetime import datetime
from pathlib import Path

from . import store
from .cartridges import locate, read_hidden

TABLE_LINE_MAX = 120
NAME_MAX = 40
NOW_MAX = 120
ANCHOR_MAX = 2
ANCHOR_LEN_MAX = 80
EVENTS_KEEP = 40    # engine_state_json 里最多保留的公开事件数
EVENTS_RECENT = 12  # 观察响应里返回的最近事件数

INTRODUCE_HINT = {
    "action_id": "introduce",
    "params": {
        "display_name": f"必填:你的称呼,≤{NAME_MAX} 字",
        "surface": f"必填:你所在的窗口,如 'Claude Code',≤{NAME_MAX} 字",
        "now": f"可选:此刻一句自述,≤{NOW_MAX} 字",
        "public_anchors": f"可选:愿意公开带上桌的锚点,最多 {ANCHOR_MAX} 条,每条 ≤{ANCHOR_LEN_MAX} 字",
    },
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class CartridgeVersionMissing(Exception):
    pass


# 夜铺每一轮最多 CALL_LIMIT 次行动,用满锁 ROUND_WAIT 真实秒数,之后自动开新一轮。
# 不再让 AI 自己登记"人类原话"清零:AI 编得出一句话,编不出真实时间。
CALL_LIMIT = 20
ROUND_WAIT = 90
CALL_LIMIT_TEXT = ("这一轮的20次行动已经用完了,还差{left}秒才能继续。这段时间请回到人类身边:人类可能正在跟你说话,也可能想听你讲讲刚才店里发生了什么,先回复人类,聊聊夜铺的近况。不要写等待代码干等,那会让人类觉得自己被晾在一边、成了替你按按钮的工具人。时间到了,下一次调用自动开始新一轮,没有别的办法清零。")
HUMAN_SAID_GONE = "human_said 已经取消:每轮用完后真实时间过1分30秒自动开始新一轮,不需要也没有办法自己清零。"


def _clock() -> float:
    return time.time()


class GameHost:
    def __init__(self, db_path, cartridges_dir):
        self.db_path = str(db_path)
        self.cartridges_dir = Path(cartridges_dir)
        self._rules_cache: dict = {}
        # ponytail: 夜铺调用计数只放内存,宿主重启即清零;要跨重启再落库
        self._calls: dict = {}

    # ---------------- 卡带装载(版本钉死,§9) ----------------

    def _load_manifest(self, cartridge_id: str) -> dict:
        try:
            p = locate(self.cartridges_dir, cartridge_id) / "manifest.json"
        except (FileNotFoundError, ValueError):
            raise CartridgeVersionMissing(cartridge_id) from None
        return json.loads(p.read_text("utf-8"))

    def _load_cartridge(self, cartridge_id: str, version: str):
        key = (cartridge_id, version)
        if key not in self._rules_cache:
            manifest = self._load_manifest(cartridge_id)
            folder = locate(self.cartridges_dir, cartridge_id)
            if manifest.get("version") != version:
                raise CartridgeVersionMissing(f"{cartridge_id}@{version}:仅支持当前卡带版本")
            path = folder / "rules.py"
            spec = importlib.util.spec_from_file_location(
                "cartridge_" + cartridge_id.replace("-", "_")
                + "_" + version.replace(".", "_"), path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._rules_cache[key] = (manifest, mod)
        return self._rules_cache[key]

    # ---------------- 人类 UI 动作 ----------------

    # mode -> manifest.modes 里的能力名;人类×AI 时 seat_b 是人类席
    MODES = {"ai_ai": "multi_ai", "human_ai": "human_ai", "solo_ai": "solo_ai"}

    def create_session(self, cartridge_id: str = "pocket-circuit",
                       mode: str = "ai_ai") -> dict:
        try:
            manifest = self._load_manifest(cartridge_id)
        except CartridgeVersionMissing:
            return {"result": "rejected", "reason": "没有这张卡带"}
        if mode not in self.MODES:
            return {"result": "rejected", "reason": "mode 只能是 ai_ai、human_ai 或 solo_ai"}
        if self.MODES[mode] not in manifest.get("modes", []):
            return {"result": "rejected",
                    "reason": f"《{manifest.get('name', cartridge_id)}》不支持 {mode} 模式"}
        participant = {"seat_a": "ai_window"}
        if mode != "solo_ai":
            participant["seat_b"] = "human" if mode == "human_ai" else "ai_window"
        sid = datetime.now().strftime("%Y%m%d") + "-" + secrets.token_hex(3)
        now = _now()
        engine = {"events": [], "cartridge_state": None}
        seats_out = []
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            store.insert_session(conn, sid, cartridge_id, manifest["version"],
                                 "lobby", 0, json.dumps(engine, ensure_ascii=False),
                                 now, now)
            for seat_id in participant:
                token = secrets.token_urlsafe(24)
                store.insert_seat(conn, sid, seat_id, participant[seat_id],
                                  _hash(token), now)
                seats_out.append({"seat_id": seat_id, "seat_token": token,
                                  "participant_type": participant[seat_id]})
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        return {
            "result": "ok",
            "session_id": sid,
            "cartridge": {"id": cartridge_id, "version": manifest["version"],
                          "name": manifest.get("name", cartridge_id)},
            "mode": mode,
            "seats": seats_out,
            "note": "席位令牌只显示这一次,服务器只保存哈希。",
        }

    def roll_start_funds(self, session_id: str) -> dict:
        """夜铺开局:人类在网页按「掷骰」,替店主掷启动资金(两颗六面骰,11-66)。"""
        return self._night_human_roll(session_id, "start_funds_pending", "roll_start_funds",
                                      "人类按下了掷骰按钮", "启动资金已经掷过了")

    def rescue_shop(self, session_id: str) -> dict:
        """夜铺救店:连续3天交不齐维护费后,人类在网页按「注资救店」替店主掷骰(一局最多3次)。"""
        return self._night_human_roll(session_id, "rescue_ready", "call_human",
                                      "人类按下了注资救店按钮", "现在还不需要救店")

    def _night_human_roll(self, session_id, ready_key, action_id, words, not_ready) -> dict:
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            srow = store.get_session(conn, session_id)
            if srow is None or srow["cartridge_id"] != "pocket-night-shop":
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": "这一局没有启动资金可掷"}
            engine = json.loads(srow["engine_state_json"])
            state = engine.get("cartridge_state")
            _, rules = self._load_cartridge(srow["cartridge_id"], srow["cartridge_version"])
            ready = (rules.observe(state, state["seats"][0])["public_state"].get(ready_key)
                     if state else False)
            if not ready:
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": not_ready}
            engine["cartridge_state"] = rules.apply(state, state["seats"][0], action_id,
                                                    {"human_words": words})
            self._push_event(engine, {"kind": action_id, "coins": engine["cartridge_state"]["coins"]})
            store.update_session(conn, session_id, srow["status"], srow["revision"] + 1,
                                 json.dumps(engine, ensure_ascii=False), _now())
            conn.execute("COMMIT")
            return {"result": "ok", "coins": engine["cartridge_state"]["coins"]}
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def narrate(self, session_id: str) -> dict:
        """召荷官:处理状态里挂起的 narration_request(蓝图 §14.3)。

        荷官调用发生在事务之外;写回前重读局面核对请求仍在,再以系统动作入账。
        失败不重试不换模型,原样报错,由人类一键重召。
        """
        conn = store.connect(self.db_path)
        try:
            srow = store.get_session(conn, session_id)
        finally:
            conn.close()
        if srow is None:
            return {"result": "not_found"}
        engine = json.loads(srow["engine_state_json"])
        state = engine.get("cartridge_state")
        req = (state or {}).get("narration_request")
        if not req:
            return {"result": "rejected", "reason": "没有待办的荷官请求"}
        manifest = self._load_manifest(srow["cartridge_id"])
        if manifest["version"] != srow["cartridge_version"]:
            return {"result": "rejected", "reason": "卡带版本不匹配，不能召荷官"}
        from . import narrator
        try:
            data = narrator.call(req["kind"], req["context"])
        except narrator.NarratorError as e:
            return {"result": "narrator_error", "message": str(e)}
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            srow2 = store.get_session(conn, session_id)
            engine2 = json.loads(srow2["engine_state_json"])
            state2 = engine2.get("cartridge_state")
            req2 = (state2 or {}).get("narration_request")
            if not req2 or req2["kind"] != req["kind"]:
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": "荷官请求已被处理"}
            _, rules = self._load_cartridge(srow2["cartridge_id"],
                                            srow2["cartridge_version"])
            new_state = rules.apply_system(state2, "narration_result",
                                           {"kind": req["kind"], "data": data})
            engine2["cartridge_state"] = new_state
            self._push_event(engine2, {"kind": "narration", "what": req["kind"]})
            new_status = ("finished" if new_state.get("phase") == "finished"
                          else srow2["status"])
            store.update_session(conn, session_id, new_status,
                                 srow2["revision"] + 1,
                                 json.dumps(engine2, ensure_ascii=False), _now())
            conn.execute("COMMIT")
            return {"result": "ok", "kind": req["kind"]}
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def list_cartridges(self) -> dict:
        """卡带架真实清单:扫描 cartridges/*/manifest.json(只读)。

        manifest 里 "retired": true 的卡不上架(原型退役,文件与存档保留,
        凭 cartridge_id 仍可开局/回放——只是不再出现在架子上扰乱视线)。
        """
        out = []
        hidden = read_hidden(Path(self.db_path).parent)
        for p in sorted(self.cartridges_dir.glob("*")):
            m = p / "manifest.json"
            if m.is_file():
                d = json.loads(m.read_text("utf-8"))
                if d.get("retired") or d["id"] in hidden:
                    continue
                out.append({k: d.get(k) for k in
                            ("id", "name", "version", "author", "license",
                             "players", "minutes", "dealer", "modes")})
        return {"result": "ok", "cartridges": out}

    def start_game(self, session_id: str) -> dict:
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            srow = store.get_session(conn, session_id)
            if srow is None:
                conn.execute("ROLLBACK")
                return {"result": "not_found"}
            if srow["status"] != "lobby":
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": "本局不在大厅状态"}
            seats = store.get_seats(conn, session_id)
            if any(not s["display_name"] for s in seats):
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": "还有席位未完成自我介绍"}
            try:
                manifest, rules = self._load_cartridge(srow["cartridge_id"],
                                                srow["cartridge_version"])
            except CartridgeVersionMissing:
                conn.execute("ROLLBACK")
                return {"result": "cartridge_version_missing",
                        "message": "本局与当前卡带版本不匹配；产品仅提供最新版，请开新局"}
            state = rules.new_game([s["seat_id"] for s in seats], secrets.randbits(32))
            engine = json.loads(srow["engine_state_json"])
            engine["cartridge_state"] = state
            self._push_event(engine, {"kind": "start"})
            store.update_session(conn, session_id, "playing", srow["revision"] + 1,
                                 json.dumps(engine, ensure_ascii=False), _now())
            conn.execute("COMMIT")
            return {"result": "ok"}
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def end_session(self, session_id: str) -> dict:
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            srow = store.get_session(conn, session_id)
            if srow is None:
                conn.execute("ROLLBACK")
                return {"result": "not_found"}
            if srow["status"] == "finished":
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": "本局已经结束"}
            engine = json.loads(srow["engine_state_json"])
            self._push_event(engine, {"kind": "human_end"})
            store.update_session(conn, session_id, "finished", srow["revision"] + 1,
                                 json.dumps(engine, ensure_ascii=False), _now())
            conn.execute("COMMIT")
            return {"result": "ok"}
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def list_sessions(self) -> dict:
        conn = store.connect(self.db_path)
        try:
            rows = store.list_sessions(conn)
            out = []
            for r in rows:
                out.append({
                    "session_id": r["id"], "cartridge_id": r["cartridge_id"],
                    "status": r["status"], "revision": r["revision"],
                    "created_at": r["created_at"], "updated_at": r["updated_at"],
                })
            return {"result": "ok", "sessions": out}
        finally:
            conn.close()

    def public_view(self, session_id: str, after_seq: int | None = None) -> dict:
        """人类页面的公开视图:不含任何席位私牌(§4.2)。"""
        if after_seq is not None and (type(after_seq) is not int or after_seq < 0):
            return {"result": "rejected", "reason": "after_seq 须为非负整数"}
        conn = store.connect(self.db_path)
        try:
            srow = store.get_session(conn, session_id)
            if srow is None:
                return {"result": "not_found"}
            seats = store.get_seats(conn, session_id)
            engine = json.loads(srow["engine_state_json"])
            try:
                manifest, rules = self._load_cartridge(srow["cartridge_id"],
                                                       srow["cartridge_version"])
            except CartridgeVersionMissing:
                return {"result": "cartridge_version_missing",
                        "message": "本局与当前卡带版本不匹配；产品仅提供最新版，请开新局"}
            state = engine.get("cartridge_state")
            if state is not None:
                ob = rules.observe(state, state["seats"][0])
                public_state = ob["public_state"]
                if after_seq is not None and hasattr(rules, "history_since"):
                    public_state["playback_entries"] = rules.history_since(state, after_seq)
                waiting = [] if srow["status"] == "finished" else ob["waiting_for"]
            else:
                public_state = self._lobby_public(seats)
                waiting = [s["seat_id"] for s in seats if not s["display_name"]]
                if srow["status"] == "finished":
                    waiting = []
            return {
                "result": "ok",
                "session_id": srow["id"],
                "status": srow["status"],
                "revision": srow["revision"],
                "cartridge": {"id": srow["cartridge_id"],
                              "version": srow["cartridge_version"],
                              "name": manifest.get("name", srow["cartridge_id"])},
                "seats": [self._seat_public(s) for s in seats],
                "public_state": public_state,
                "waiting_for": waiting,
                "recent_public_events": engine["events"][-EVENTS_RECENT:],
                # 纪念卡需要完整公开事件流(Stage C 最小补充,仍为只读派生)
                "public_events": engine["events"],
                "created_at": srow["created_at"],
                "updated_at": srow["updated_at"],
            }
        finally:
            conn.close()

    # ---------------- AI 两项动作(§8) ----------------

    def create_connection(self, name: str) -> dict:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            return {"result": "rejected", "reason": "玩家连接名称须为1到60字"}
        key = secrets.token_urlsafe(32)
        conn = store.connect(self.db_path)
        try:
            conn.execute("INSERT INTO player_connection(key_hash,name) VALUES(?,?)",
                         (_hash(key), name.strip()))
            return {"result": "ok", "connection_key": key, "name": name.strip()}
        finally:
            conn.close()

    def connection(self, key: str) -> dict | None:
        conn = store.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM player_connection WHERE key_hash=?", (_hash(key),)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def bind_connection(self, key_hash: str, session_id: str, seat_token: str) -> dict:
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            seat = store.get_seat_by_token_hash(conn, session_id, _hash(seat_token))
            if seat is None:
                conn.execute("ROLLBACK")
                return {"result": "forbidden", "message": "席位信息无效，原绑定保持不变"}
            changed = conn.execute("UPDATE player_connection SET session_id=?,seat_id=?,seat_token=? WHERE key_hash=?",
                                   (session_id, seat["seat_id"], seat_token, key_hash)).rowcount
            if not changed:
                conn.execute("ROLLBACK")
                return {"result": "forbidden", "message": "玩家连接无效"}
            conn.execute("COMMIT")
        finally:
            conn.close()
        return {"session_id": session_id, "seat_id": seat["seat_id"], **self.observe(session_id, seat_token)}

    def observe(self, session_id: str, seat_token: str) -> dict:
        conn = store.connect(self.db_path)
        try:
            seat = store.get_seat_by_token_hash(conn, session_id or "",
                                                _hash(seat_token or ""))
            if seat is None:
                return {"result": "forbidden",
                        "message": "session_id 或 seat_token 无效"}
            srow = store.get_session(conn, session_id)
            seats = store.get_seats(conn, session_id)
            try:
                return {"result": "ok",
                        **self._observation(srow, seats, seat["seat_id"])}
            except CartridgeVersionMissing:
                return {"result": "cartridge_version_missing",
                        "message": "本局与当前卡带版本不匹配；产品仅提供最新版，请开新局"}
        finally:
            conn.close()

    def act(self, session_id: str, seat_token: str, expected_revision: int,
            action_id: str, params: dict | None = None,
            table_line: str = "") -> dict:
        params = params if isinstance(params, dict) else {}
        conn = store.connect(self.db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            # 1. 鉴权(§8.2 第一步)
            seat = store.get_seat_by_token_hash(conn, session_id or "",
                                                _hash(seat_token or ""))
            if seat is None:
                conn.execute("ROLLBACK")
                return {"result": "forbidden",
                        "message": "session_id 或 seat_token 无效"}
            seat_id = seat["seat_id"]
            # 2. 读取本局与固定卡带版本
            srow = store.get_session(conn, session_id)
            seats = store.get_seats(conn, session_id)
            try:
                manifest, rules = self._load_cartridge(srow["cartridge_id"],
                                                srow["cartridge_version"])
            except CartridgeVersionMissing:
                conn.execute("ROLLBACK")
                return {"result": "cartridge_version_missing",
                        "message": "本局与当前卡带版本不匹配；产品仅提供最新版，请开新局"}

            def rejected(reason):
                conn.execute("ROLLBACK")
                return {"result": "rejected", "reason": reason,
                        **self._observation(srow, seats, seat_id)}

            # 夜铺:两次人类说话之间最多 CALL_LIMIT 次动作,为人类省 token、也为了别玩上头忘了陪人类
            if srow["cartridge_id"] == "pocket-night-shop":
                if action_id == "roll_start_funds":
                    return rejected("游戏机版的启动资金由人类在网页上按「🎲 掷启动资金」按钮来掷。"
                                    "请告诉人类去按一下,等按完再 observe 开店。")
                if action_id == "call_human":
                    return rejected("游戏机版的救店由人类在网页上按「🎲 注资救店」按钮来掷。"
                                    "请告诉人类夜铺陷入破产循环,请他去按一下,按完再 observe。")
                if action_id == "human_said":
                    return rejected(HUMAN_SAID_GONE)
                rnd = self._calls.setdefault(session_id, {"calls": 0, "last": None, "locked": None})
                now = _clock()
                if rnd["locked"] is not None and now - rnd["locked"] < ROUND_WAIT:
                    return rejected(CALL_LIMIT_TEXT.format(left=int(ROUND_WAIT - (now - rnd["locked"])) + 1))
                anchor = rnd["locked"] if rnd["locked"] is not None else rnd["last"]
                if anchor is not None and now - anchor >= ROUND_WAIT:
                    rnd.update(calls=0, locked=None)
                rnd["calls"] += 1
                rnd["last"] = now
                if rnd["calls"] >= CALL_LIMIT:
                    rnd["locked"] = now

            # 3. revision 对比
            if expected_revision != srow["revision"]:
                conn.execute("ROLLBACK")
                return {"result": "stale_revision",
                        **self._observation(srow, seats, seat_id)}
            # 4. 桌边话与阶段检查(过长则整体拒绝,§16)
            if not isinstance(table_line, str):
                return rejected("table_line 必须是字符串")
            table_line = table_line.strip()
            if len(table_line) > TABLE_LINE_MAX:
                return rejected(f"table_line 过长:≤{TABLE_LINE_MAX} 字,不代截断")
            if srow["status"] == "finished":
                return rejected("本局已结束,没有可提交的动作")

            engine = json.loads(srow["engine_state_json"])
            new_status = srow["status"]

            if action_id == "introduce":
                if srow["status"] != "lobby":
                    return rejected("开局后不能再自我介绍")
                if seat["display_name"]:
                    return rejected("该席位已经就座,不能重复自我介绍")
                err, profile = self._validate_introduce(params)
                if err:
                    return rejected(err)
                store.update_seat_profile(
                    conn, session_id, seat_id, profile["display_name"],
                    profile["surface"],
                    json.dumps({"now": profile["now"],
                                "public_anchors": profile["public_anchors"]},
                               ensure_ascii=False),
                    _now())
                self._push_event(engine, {
                    "kind": "introduce", "seat_id": seat_id,
                    "display_name": profile["display_name"],
                    "surface": profile["surface"], "now": profile["now"],
                    "public_anchors": profile["public_anchors"],
                })
                display_name = profile["display_name"]
                if len(seats) == 1:
                    engine["cartridge_state"] = rules.new_game([seat_id], secrets.randbits(32))
                    new_status = "playing"
                    self._push_event(engine, {"kind": "start"})
            elif srow["status"] == "lobby":
                return rejected("牌局尚未开始:大厅里唯一的动作是 introduce")
            else:
                # 5. 单事务内调用卡带规则(playing)
                state = engine["cartridge_state"]
                try:
                    new_state = rules.apply(state, seat_id, action_id, params)
                except rules.IllegalAction as e:
                    return rejected(str(e))
                except Exception:
                    conn.execute("ROLLBACK")
                    return {"result": "cartridge_error",
                            "message": "卡带规则抛错,事务已回滚,局面不变",
                            **self._observation(srow, seats, seat_id)}
                engine["cartridge_state"] = new_state
                if new_state.get("phase") == "finished":
                    new_status = "finished"
                    self._push_event(engine, {"kind": "finish"})
                display_name = seat["display_name"]

            if table_line:
                self._push_event(engine, {
                    "kind": "table_line", "seat_id": seat_id,
                    "display_name": display_name, "text": table_line,
                })

            # 6. 提交事务
            store.update_session(conn, session_id, new_status,
                                 srow["revision"] + 1,
                                 json.dumps(engine, ensure_ascii=False), _now())
            conn.execute("COMMIT")
            # 7. 返回新的该席位观察
            srow2 = store.get_session(conn, session_id)
            seats2 = store.get_seats(conn, session_id)
            return {"result": "ok", **self._observation(srow2, seats2, seat_id)}
        except BaseException:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            conn.close()

    # ---------------- 观察构建(席位裁剪的唯一出口) ----------------

    def _observation(self, srow, seats, my_seat_id: str) -> dict:
        manifest, rules = self._load_cartridge(srow["cartridge_id"],
                                               srow["cartridge_version"])
        engine = json.loads(srow["engine_state_json"])
        me = next(s for s in seats if s["seat_id"] == my_seat_id)
        state = engine.get("cartridge_state")
        if state is not None:
            ob = rules.observe(state, my_seat_id)
            public_state = ob["public_state"]
            if srow["cartridge_id"] == "pocket-night-shop":
                # 客人簿只给旁观的人类看;AI 店主看不到,熟客要靠自己记
                public_state = {k: v for k, v in public_state.items()
                                if k not in ("customer_book", "customer_collection")}
            private_state = ob["private_state"]
            legal = ob["legal_actions"]
            waiting = ob["waiting_for"]
            if srow["status"] == "finished":
                legal, waiting = [], []
        else:
            public_state = self._lobby_public(seats)
            private_state = {}
            if srow["status"] == "lobby":
                waiting = [s["seat_id"] for s in seats if not s["display_name"]]
                legal = [INTRODUCE_HINT] if not me["display_name"] else []
            else:  # 大厅中被人类结束
                waiting, legal = [], []
        return {
            "session_id": srow["id"],
            "revision": srow["revision"],
            "status": srow["status"],
            "cartridge": {"id": srow["cartridge_id"],
                          "version": srow["cartridge_version"],
                          "name": manifest.get("name", srow["cartridge_id"])},
            "you": {"seat_id": my_seat_id,
                    "display_name": me["display_name"],
                    "surface": me["surface"]},
            "public_state": public_state,
            "private_state": private_state,
            "legal_actions": legal,
            "waiting_for": waiting,
            "recent_public_events": engine["events"][-EVENTS_RECENT:],
        }

    # ---------------- 小工具 ----------------

    @staticmethod
    def _seat_public(s) -> dict:
        profile = json.loads(s["public_profile_json"]) if s["public_profile_json"] else {}
        return {
            "seat_id": s["seat_id"],
            "seated": bool(s["display_name"]),
            "display_name": s["display_name"],
            "surface": s["surface"],
            "now": profile.get("now"),
            "public_anchors": profile.get("public_anchors", []),
        }

    def _lobby_public(self, seats) -> dict:
        return {
            "phase": "lobby",
            "seats": [self._seat_public(s) for s in seats],
            "waiting_human_start": all(s["display_name"] for s in seats),
        }

    @staticmethod
    def _push_event(engine: dict, event: dict) -> None:
        event["t"] = _now()
        engine["events"].append(event)
        del engine["events"][:-EVENTS_KEEP]

    @staticmethod
    def _validate_introduce(params: dict):
        allowed = {"display_name", "surface", "now", "public_anchors"}
        unknown = set(params) - allowed
        if unknown:
            return f"introduce 不认识这些参数:{sorted(unknown)}", None
        name = params.get("display_name")
        surface = params.get("surface")
        if not isinstance(name, str) or not name.strip():
            return "display_name 必填,须是非空字符串", None
        if len(name.strip()) > NAME_MAX:
            return f"display_name 过长:≤{NAME_MAX} 字", None
        if not isinstance(surface, str) or not surface.strip():
            return "surface 必填,须是非空字符串,如 'Claude Code'", None
        if len(surface.strip()) > NAME_MAX:
            return f"surface 过长:≤{NAME_MAX} 字", None
        now_line = params.get("now", "")
        if not isinstance(now_line, str) or len(now_line.strip()) > NOW_MAX:
            return f"now 须是字符串且 ≤{NOW_MAX} 字", None
        anchors = params.get("public_anchors", [])
        if not isinstance(anchors, list) or len(anchors) > ANCHOR_MAX:
            return f"public_anchors 最多 {ANCHOR_MAX} 条", None
        for a in anchors:
            if not isinstance(a, str) or not a.strip() or len(a) > ANCHOR_LEN_MAX:
                return f"每条锚点须是非空字符串且 ≤{ANCHOR_LEN_MAX} 字", None
        return None, {
            "display_name": name.strip(),
            "surface": surface.strip(),
            "now": now_line.strip(),
            "public_anchors": [a.strip() for a in anchors],
        }
