"""
Собирает tracks.json из каталога Audius — бесплатного открытого музыкального
API (не нужен ключ, только имя приложения в заголовке app_name).

Примеры:
    # по плейлисту
    python audius_catalog.py --playlist <playlist_id> --app "MyPlayerApp"

    # по поисковому запросу (жанр, исполнитель, что угодно)
    python audius_catalog.py --search "lofi hip hop" --limit 200 --app "MyPlayerApp"

    # топ треков за неделю
    python audius_catalog.py --trending --limit 100 --app "MyPlayerApp"

Ссылки в tracks.json указывают прямо на эндпойнт /v1/tracks/{id}/stream —
он отдаёт mp3 и поддерживает Range, так что перемотка в плеере будет работать.
Официальная позиция Audius: API бесплатный, единственное условие — указывать
авторов. Полю "artist" оставляем имя автора трека.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import urllib.parse
import urllib.request

API = "https://discoveryprovider.audius.co/v1"


def call(path: str, app: str, **params) -> dict:
    params["app_name"] = app
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{API}{path}?{query}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def to_entry(t: dict, app: str) -> dict:
    return {
        "id": t["id"],
        "title": t.get("title") or "Без названия",
        "artist": (t.get("user") or {}).get("name", ""),
        "duration": int(t.get("duration") or 0),
        "src": f"{API}/tracks/{t['id']}/stream?app_name={urllib.parse.quote(app)}",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True, help="имя вашего приложения для заголовка Audius")
    ap.add_argument("--playlist", help="ID плейлиста Audius")
    ap.add_argument("--search", help="поисковый запрос по трекам")
    ap.add_argument("--trending", action="store_true", help="топ недели")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--out", type=Path, default=Path("tracks.json"))
    args = ap.parse_args()

    if args.playlist:
        data = call(f"/playlists/{args.playlist}/tracks", args.app)["data"]
    elif args.search:
        data = call("/tracks/search", args.app, query=args.search)["data"][: args.limit]
    elif args.trending:
        data = call("/tracks/trending", args.app)["data"][: args.limit]
    else:
        sys.exit("Укажите --playlist, --search или --trending")

    entries = [to_entry(t, args.app) for t in data]

    args.out.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Сохранено треков: {len(entries)} → {args.out}")


if __name__ == "__main__":
    main()
