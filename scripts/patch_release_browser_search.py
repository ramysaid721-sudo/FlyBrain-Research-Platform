"""Apply a narrowly scoped CI compatibility fix to the extracted release tree.

The browser-search parser flushes its final result only from HTMLParser.close().
Calling close() after feed() ensures the final (and often only) search result is emitted.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_release_browser_search.py RELEASE_ROOT")

    release_root = Path(sys.argv[1]).resolve()
    target = release_root / "components" / "FlyBrain-NOS" / "flybrain_os" / "browser_use_adapter.py"
    if not target.is_file():
        raise SystemExit(f"Expected browser adapter was not found: {target}")

    source = target.read_text(encoding="utf-8")
    old = "    parser.feed(html)\n    results = []\n"
    new = "    parser.feed(html)\n    parser.close()\n    results = []\n"

    if new in source:
        print("Browser search parser finalization already present; no change needed.")
        return 0
    if source.count(old) != 1:
        raise SystemExit(
            "Refusing to patch: expected exactly one browser-search parser sequence; "
            f"found {source.count(old)}."
        )

    target.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("Applied browser-search parser finalization fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
