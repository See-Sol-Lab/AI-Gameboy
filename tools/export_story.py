"""Export a selected completed adventure as a private, clean MD/TXT story."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
ADVENTURES = {"pocket-crossing": "口袋穿越", "pocket-tabletop": "口袋跑团"}


def story_sections(cid, state):
    if cid not in ADVENTURES:
        raise ValueError("剧情收藏仅支持口袋穿越和口袋跑团")
    ending = state.get("ending") or {}
    if state.get("phase") != "finished" or not ending.get("text"):
        raise ValueError("请先完成游戏并让荷官写完结局，提前收桌的局不能当作通关剧情导出")
    world = state.get("world") or {}
    title = world.get("world_name") or ADVENTURES[cid]
    sections = []
    prologue = [world.get(key) for key in ("premise", "world_background", "lore")]
    prologue = [text for text in prologue if isinstance(text, str) and text.strip()]
    if prologue:
        sections.append(("序章", prologue))
    pool = {row["id"]: row for row in state.get("identity_pool", [])}
    names, people = {}, []
    for seat, identity in state.get("identities", {}).items():
        row = pool.get(identity)
        if row:
            names[seat] = row["name"]
            people.append(row["name"] + ("：" + row["origin"] if row.get("origin") else ""))
    if people:
        sections.append(("同行者", people))
    warnings = []
    for entry in state.get("history", []):
        paragraphs = []
        text = entry.get("story_text")
        if isinstance(text, str) and text.strip():
            paragraphs.append(text)
        else:
            warnings.append(f"第{entry['scene_index']}幕没有保存场景正文；本次只保留已有行动，不补写")
        paragraphs.extend(text for text in entry.get("story_responses", []) if isinstance(text, str) and text.strip())
        for seat, action in entry.get("commits", {}).items():
            if seat not in names:
                raise ValueError("存档缺少已选角色资料，不能准确署名，请人工核对")
            if action.get("action"):
                paragraphs.append(f"{names[seat]}尝试：{action['action']}")
            if action.get("line"):
                paragraphs.append(f"{names[seat]}：“{action['line']}”")
        for event in (state.get("events") or {}).get("log", []):
            if event.get("scene") == entry["scene_index"] and event.get("text"):
                paragraphs.append(event["text"])
                paragraphs.append("两人化解了这场变故。" if event["won"] else "两人没能挡住这场变故。")
        sections.append((f"第{entry['scene_index']}幕 · {entry['title']}", paragraphs))
    sections.append(("终章", [ending["text"]]))
    return title, sections, warnings


def render(cid, state, fmt):
    if fmt not in ("md", "txt"):
        raise ValueError("只支持md或txt")
    title, sections, warnings = story_sections(cid, state)
    parts = [("# " if fmt == "md" else "") + title]
    for heading, paragraphs in sections:
        parts.append(("## " if fmt == "md" else "") + heading)
        parts.extend(paragraphs)
    return "\n\n".join(parts).strip() + "\n", warnings


def export(db, sid, fmt, output):
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("剧情收藏是私人文件，请选择游戏仓库之外的保存位置")
    if output.suffix.lower() != "." + fmt:
        raise ValueError("文件后缀需与md/txt格式一致")
    with closing(sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        row = conn.execute("SELECT cartridge_id,status,engine_state_json FROM session WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise ValueError("没有这个局号，请让人类从结局页确认")
    cid, status, payload = row
    if status != "finished":
        raise ValueError("这局尚未结束")
    state = json.loads(payload).get("cartridge_state") or {}
    text, warnings = render(cid, state, fmt)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(text)
    return warnings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="selected session id from the ending page")
    parser.add_argument("--format", choices=("md", "txt"), required=True)
    parser.add_argument("--output", type=Path, required=True, help="private destination outside the repository")
    args = parser.parse_args()
    try:
        warnings = export(ROOT / "data/gameboy.db", args.session, args.format, args.output)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, str(error) + "\n")
    print("已导出：" + str(args.output.resolve()))
    for warning in warnings:
        print("注意：" + warning)
