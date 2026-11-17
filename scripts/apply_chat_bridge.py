"""Apply the repository-level ChatGPT bridge overlay to the release ZIP tree."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PATCHES = {
    ROOT / "bridge" / "chat_api.py": Path("components/FlyBrain-NOS/flybrain_os/chat_api.py"),
    ROOT / "bridge" / "test_chat_api.py": Path("components/FlyBrain-NOS/tests/test_chat_api.py"),
}

def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"expected version marker not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="extracted release root")
    args = parser.parse_args()
    source = args.source.resolve()
    if not (source / "components/FlyBrain-NOS/pyproject.toml").is_file():
        raise SystemExit(f"not a FlyBrain release source tree: {source}")
    for origin, relative in PATCHES.items():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
    replace_once(source / "components/URCAL/urcal/__init__.py", '__version__="0.3.0"', '__version__="0.3.1"')
    replace_once(source / "components/FlyBrain-NOS/flybrain_os/__init__.py", '__version__ = "0.9.0"', '__version__ = "0.13.3"')
    replace_once(source / "components/FlyBrain-NOS/docs/NEURAL_RUNTIME_STATUS.md", "Release: FlyBrain-NOS 0.13.2.", "Release: FlyBrain-NOS 0.13.3.")
    print("CHATGPT_BRIDGE_OVERLAY_APPLIED")

if __name__ == "__main__":
    main()
