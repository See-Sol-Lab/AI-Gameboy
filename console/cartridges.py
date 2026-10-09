"""Local cartridge management: list, install, hide, show, and safe uninstall."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat

ROOT = Path(__file__).resolve().parent.parent


def is_link(path):
    return path.is_symlink() or (os.name == "nt" and path.exists()
                                and bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def validate_id(cid):
    if not isinstance(cid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", cid):
        raise ValueError("卡带id只能用小写字母、数字和连字符")
    return cid


def locate(cartridges_dir, cid):
    """Installed games plus the current development example; no retired runtime."""
    validate_id(cid)
    base = Path(cartridges_dir).parent
    for folder in (Path(cartridges_dir) / cid, base / "examples" / cid):
        if (folder / "manifest.json").is_file():
            return folder
    raise FileNotFoundError(f"缺少卡带 {cid}，请重新安装原版本；存档保持不变")


def read_hidden(data_dir):
    path = Path(data_dir) / "hidden_cartridges.json"
    if not path.exists():
        return set()
    ids = json.loads(path.read_text("utf-8"))
    if not isinstance(ids, list):
        raise ValueError("hidden_cartridges.json须为卡带id数组")
    return {validate_id(cid) for cid in ids}


def set_hidden(cid, hidden, root=ROOT):
    validate_id(cid)
    if not (root / "cartridges" / cid / "manifest.json").is_file():
        raise ValueError("这张卡带未安装，不能改变显示状态")
    folder = root / "data"
    ids = read_hidden(folder)
    if hidden:
        ids.add(cid)
    else:
        ids.discard(cid)
    folder.mkdir(exist_ok=True)
    path = folder / "hidden_cartridges.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(sorted(ids), ensure_ascii=False) + "\n", "utf-8")
    os.replace(temporary, path)


def installed(root=ROOT):
    hidden = read_hidden(root / "data")
    return [{"id": m["id"], "name": m["name"], "version": m["version"], "hidden": m["id"] in hidden}
            for path in sorted((root / "cartridges").glob("*/manifest.json"))
            for m in [json.loads(path.read_text("utf-8"))]]


def install(source, root=ROOT):
    hidden = read_hidden(root / "data")
    source = Path(source)
    if is_link(source):
        raise ValueError("卡带安装目录不能是符号链接或目录联接")
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text("utf-8"))
    cid = validate_id(manifest.get("id"))
    if not (source / "rules.py").is_file():
        raise ValueError("卡带须有manifest.json和rules.py")
    if any(is_link(path) for path in source.rglob("*")):
        raise ValueError("卡带安装目录不能含符号链接或目录联接")
    try:
        locate(root / "cartridges", cid)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("同id卡带已存在，不覆盖；更新时请先核对存档和旧规则版本")
    target = root / "cartridges" / cid
    if target.parent.resolve().parent != root.resolve():
        raise ValueError("安装目标必须位于本机cartridges目录内")
    target.parent.mkdir(exist_ok=True)
    shutil.copytree(source, target)
    if cid in hidden:
        set_hidden(cid, False, root)
    return cid


def uninstall(cid, root=ROOT, confirmed=False):
    validate_id(cid)
    parent = (root / "cartridges").resolve()
    target = root / "cartridges" / cid
    if (parent.parent != root.resolve() or is_link(target) or target.resolve().parent != parent
            or any(is_link(path) for path in target.rglob("*"))):
        raise ValueError("卸载目标必须位于本机cartridges目录内")
    if not (target / "manifest.json").is_file():
        raise ValueError("这张卡带未安装")
    db = root / "data" / "gameboy.db"
    if db.exists():
        with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM session WHERE cartridge_id=?", (cid,)).fetchone()[0]
        if count:
            raise ValueError(f"还有{count}局存档引用这张卡；请改用hide保留读档能力，不删除存档")
    if not confirmed:
        raise ValueError("卸载会删除整张卡带目录；确认人类同意后加--yes。存档不会删除")
    shutil.rmtree(target)
    return cid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    for name in ("hide", "show", "uninstall"):
        p = commands.add_parser(name)
        p.add_argument("id")
        if name == "uninstall":
            p.add_argument("--yes", action="store_true")
    commands.add_parser("install").add_argument("folder")
    args = parser.parse_args()
    try:
        if args.command == "list":
            print(json.dumps(installed(), ensure_ascii=False, indent=2))
        elif args.command in ("hide", "show"):
            set_hidden(args.id, args.command == "hide")
            print("已更新卡带架；刷新卡带架即可，已有局仍可继续。")
        elif args.command == "install":
            print("已安装：" + install(args.folder))
        else:
            print("已卸载：" + uninstall(args.id, confirmed=args.yes))
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
