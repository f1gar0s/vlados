"""
Каталогизирует mp3/m4a/ogg-файлы, которые лежат прямо рядом с index.html в
репозитории (как ваша софийка.mp3) — для личных треков, которых немного и
которые не жалко держать в git.

    pip install mutagen
    python local_catalog.py .. --out local.json

По умолчанию сканирует папку на один уровень выше tools/, то есть корень
репозитория. Файл README.md, bot.py и сам index.html пропускаются — берутся
только звуковые файлы. Пути в "src" получаются относительными к index.html,
так что плеер найдёт их что локально, что на GitHub Pages.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mutagen import File as MutagenFile

AUDIO_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".wav"}


def read_tags(path: Path) -> dict:
    title, artist, duration = "", "", 0
    try:
        meta = MutagenFile(path, easy=True)
        if meta is not None:
            title = (meta.get("title") or [""])[0].strip()
            artist = (meta.get("artist") or [""])[0].strip()
            duration = int(getattr(meta.info, "length", 0) or 0)
    except Exception as exc:
        print(f"  теги не прочитались: {path.name} ({exc})", file=sys.stderr)

    if not title:
        stem = path.stem.replace("_", " ").strip()
        for sep in (" — ", " – ", " - "):
            if sep in stem:
                left, right = stem.split(sep, 1)
                artist = artist or left.strip()
                title = right.strip()
                break
        else:
            title = stem
    return {"title": title or "Без названия", "artist": artist, "duration": duration}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, nargs="?", default=Path(__file__).resolve().parent.parent,
                     help="папка репозитория (по умолчанию — на уровень выше tools/)")
    ap.add_argument("--out", type=Path, default=Path("local.json"))
    args = ap.parse_args()

    items = []
    for path in sorted(args.root.iterdir()):
        if path.is_file() and path.suffix.lower() in AUDIO_EXT:
            tags = read_tags(path)
            items.append({
                "id": "local-" + path.stem.lower().replace(" ", "-"),
                "title": tags["title"],
                "artist": tags["artist"],
                "duration": tags["duration"],
                "src": path.name,  # относительный путь — файл лежит рядом с index.html
            })

    args.out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Найдено локальных треков: {len(items)} → {args.out}")
    for i in items:
        print(f"  {i['artist'] or '—'} · {i['title']}  ({i['src']})")


if __name__ == "__main__":
    main()
