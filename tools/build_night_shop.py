"""Build the standalone blind edition from the canonical cartridge rules."""
import argparse
import base64
import json
from pathlib import Path
import textwrap
import zlib

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "口袋夜铺_单机盲玩版/pocket_night_shop.py"


def render():
    cart = ROOT / "cartridges/pocket-night-shop"
    version = json.loads((cart / "manifest.json").read_text("utf-8"))["version"]
    source = (cart / "rules.py").read_text("utf-8")
    blob = base64.b64encode(zlib.compress(source.encode("utf-8"), 9)).decode("ascii")
    template = Path(__file__).with_name("night_shop_standalone.py.in").read_text("utf-8")
    return (template.replace("@@VERSION@@", version)
            .replace("@@BLOB@@", "\n".join(f'    "{part}"' for part in textwrap.wrap(blob, 96)))
            .replace("@@LICENSE@@", (ROOT / "LICENSE").read_text("utf-8").rstrip()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check committed output is up to date")
    args = parser.parse_args()
    content = render()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text("utf-8") != content:
            parser.exit(1, "Blind edition is stale; run python tools/build_night_shop.py\n")
        print("Standalone file is current.")
    else:
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(content, encoding="utf-8", newline="\n")
        print("Built pocket_night_shop.py in the blind-edition folder.")
