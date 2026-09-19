"""Конфигурация и хранилище каталога треков."""

import os
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "catalog.db"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", BASE_DIR / "data" / "cache"))

API_ID = int(os.environ.get("API_ID", "0") or 0)   # my.telegram.org
API_HASH = os.environ.get("API_HASH", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")  # см. login_local.py
CHANNEL = os.environ.get("CHANNEL", "")            # @designersformusic или -100...

# Раз в сколько минут проверять канал на новые посты, пока сервер работает
POLL_MINUTES = int(os.getenv("POLL_MINUTES", "10"))
# Ограничиваем, кто может дёргать API — необязательно, но полезно для приватного канала
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    msg_id     INTEGER PRIMARY KEY,   -- id сообщения в канале
    title      TEXT NOT NULL,
    artist     TEXT NOT NULL DEFAULT '',
    duration   INTEGER NOT NULL DEFAULT 0,
    size       INTEGER NOT NULL DEFAULT 0,
    mime       TEXT NOT NULL DEFAULT 'audio/mpeg',
    ext        TEXT NOT NULL DEFAULT 'mp3',
    added_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_added ON tracks(added_at DESC);

CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def upsert(conn: sqlite3.Connection, **row) -> None:
    row.setdefault("added_at", int(time.time()))
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in row if c != "msg_id")
    conn.execute(
        f"INSERT INTO tracks ({cols}) VALUES ({marks}) "
        f"ON CONFLICT(msg_id) DO UPDATE SET {updates}",
        tuple(row.values()),
    )
    conn.commit()


def all_tracks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tracks ORDER BY added_at DESC, msg_id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_state(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def clean_name(name: str) -> tuple[str, str]:
    """Из «Артист - Название.mp3» делает пару (название, артист)."""
    stem = Path(name or "").stem.replace("_", " ").strip()
    for sep in (" — ", " – ", " - "):
        if sep in stem:
            left, right = stem.split(sep, 1)
            return right.strip(), left.strip()
    return stem or "Без названия", ""
