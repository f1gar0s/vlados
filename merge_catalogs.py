"""
Склеивает несколько частичных каталогов (local.json, audius.json, ...) в
один tracks.json для плеера. Личные треки — первыми, чтобы попадались
в начале очереди.

    python merge_catalogs.py local.json audius.json --out ../tracks.json
"""

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", type=Path, nargs="+", help="файлы в порядке приоритета")
    ap.add_argument("--out", type=Path, default=Path("../tracks.json"))
    args = ap.parse_args()

    merged, seen = [], set()
    for src in args.sources:
        items = json.loads(src.read_text(encoding="utf-8"))
        added = 0
        for item in items:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            merged.append(item)
            added += 1
        print(f"{src}: {added} треков добавлено")

    args.out.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Итого: {len(merged)} треков → {args.out}")


if __name__ == "__main__":
    main()
