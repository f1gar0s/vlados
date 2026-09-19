"""
Бэкенд плеера: один процесс делает всё —

  1. при старте вычитывает всю историю канала (документы-аудио) в SQLite;
  2. дальше раз в POLL_MINUTES проверяет канал на новые посты;
  3. отдаёт GET /tracks.json — каталог в формате, который понимает index.html;
  4. отдаёт GET /stream/{msg_id}?ext=mp3 — сам файл, с кешем на диск и
     поддержкой Range (без него в плеере не работает перемотка).

Запуск:
    pip install -r requirements.txt
    export API_ID=... API_HASH=... STRING_SESSION=... CHANNEL="@designersformusic"
    uvicorn app:app --host 0.0.0.0 --port 8000
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeFilename

import catalog

log = logging.getLogger("uvicorn.error")

MIME_BY_EXT = {
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".ogg": "audio/ogg", ".opus": "audio/ogg", ".flac": "audio/flac", ".wav": "audio/wav",
}

client: TelegramClient | None = None
download_locks: dict[int, asyncio.Lock] = {}


def extract(message) -> dict | None:
    doc = getattr(message, "document", None)
    if doc is None:
        return None
    audio, file_name = None, ""
    for attr in doc.attributes:
        if isinstance(attr, DocumentAttributeAudio) and not attr.voice:
            audio = attr
        elif isinstance(attr, DocumentAttributeFilename):
            file_name = attr.file_name

    mime = (doc.mime_type or "").lower()
    if audio is None and not mime.startswith("audio/"):
        return None

    title = (getattr(audio, "title", None) or "").strip()
    artist = (getattr(audio, "performer", None) or "").strip()
    if not title:
        title, guessed = catalog.clean_name(file_name)
        artist = artist or guessed

    ext = (Path(file_name).suffix.lstrip(".").lower() or "mp3")
    return {
        "msg_id": message.id,
        "title": title[:200],
        "artist": artist[:200],
        "duration": int(getattr(audio, "duration", 0) or 0),
        "size": int(doc.size or 0),
        "mime": mime or "audio/mpeg",
        "ext": ext,
        "added_at": int(message.date.timestamp()),
    }


async def index_full() -> None:
    conn = catalog.connect()
    channel = await client.get_entity(catalog.CHANNEL)
    found, max_id = 0, 0
    async for message in client.iter_messages(channel):
        row = extract(message)
        if row:
            catalog.upsert(conn, **row)
            found += 1
            max_id = max(max_id, row["msg_id"])
    catalog.set_state(conn, "max_msg_id", str(max_id))
    log.info("Полная индексация: %s треков, последний id %s", found, max_id)


async def index_incremental() -> None:
    conn = catalog.connect()
    channel = await client.get_entity(catalog.CHANNEL)
    since = int(catalog.get_state(conn, "max_msg_id", "0"))
    found, max_id = 0, since
    async for message in client.iter_messages(channel, min_id=since):
        row = extract(message)
        if row:
            catalog.upsert(conn, **row)
            found += 1
            max_id = max(max_id, row["msg_id"])
    if max_id > since:
        catalog.set_state(conn, "max_msg_id", str(max_id))
    if found:
        log.info("Новых треков: %s", found)


async def poll_loop() -> None:
    while True:
        await asyncio.sleep(catalog.POLL_MINUTES * 60)
        try:
            await index_incremental()
        except Exception:
            log.exception("Ошибка при проверке новых постов")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global client
    if not (catalog.API_ID and catalog.API_HASH and catalog.STRING_SESSION and catalog.CHANNEL):
        raise RuntimeError(
            "Нужны переменные API_ID, API_HASH, STRING_SESSION (см. login_local.py) и CHANNEL"
        )
    client = TelegramClient(StringSession(catalog.STRING_SESSION), catalog.API_ID, catalog.API_HASH)
    await client.start()

    conn = catalog.connect()
    if catalog.get_state(conn, "max_msg_id") is None:
        await index_full()      # первый запуск — читаем всю историю канала
    else:
        await index_incremental()  # дальше — только то, что добавилось с прошлого раза

    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()
    await client.disconnect()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # только чтение каталога, сужать не обязательно
    allow_methods=["GET"],
    allow_headers=["*"],
)


def check_token(token: str | None) -> None:
    if catalog.ACCESS_TOKEN and token != catalog.ACCESS_TOKEN:
        raise HTTPException(401, "Неверный токен")


@app.get("/tracks.json")
async def tracks_json(request: Request, x_token: str | None = Header(default=None)):
    token = x_token or request.query_params.get("token")
    check_token(token)
    conn = catalog.connect()
    base = str(request.base_url).rstrip("/")
    suffix = f"&token={token}" if catalog.ACCESS_TOKEN else ""
    items = [
        {
            "id": str(row["msg_id"]),
            "title": row["title"],
            "artist": row["artist"],
            "duration": row["duration"],
            "src": f"{base}/stream/{row['msg_id']}?ext={row['ext']}{suffix}",
        }
        for row in catalog.all_tracks(conn)
    ]
    return JSONResponse(items)


async def ensure_cached(msg_id: int, ext: str) -> Path:
    path = catalog.CACHE_DIR / f"{msg_id}.{ext}"
    if path.exists():
        return path
    lock = download_locks.setdefault(msg_id, asyncio.Lock())
    async with lock:
        if path.exists():
            return path
        channel = await client.get_entity(catalog.CHANNEL)
        message = await client.get_messages(channel, ids=msg_id)
        if not message or not message.document:
            raise HTTPException(404, "Трек не найден в канале")
        tmp = path.with_suffix(path.suffix + ".part")
        await client.download_media(message, file=str(tmp))
        tmp.rename(path)
    return path


def _read_range(path: Path, start: int, end: int, chunk: int = 256 * 1024):
    def gen():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = f.read(min(chunk, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
    return gen()


@app.get("/stream/{msg_id}")
async def stream(msg_id: int, request: Request, ext: str = "mp3", token: str | None = None):
    check_token(token)
    path = await ensure_cached(msg_id, ext)
    size = path.stat().st_size
    mime = MIME_BY_EXT.get(f".{ext}", "audio/mpeg")

    range_header = request.headers.get("range")
    if not range_header:
        return StreamingResponse(
            _read_range(path, 0, size - 1), media_type=mime,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(size)},
        )

    try:
        start_s, end_s = range_header.split("=")[1].split("-")
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
    except (ValueError, IndexError):
        raise HTTPException(416, "Некорректный Range")
    end = min(end, size - 1)
    if start > end:
        raise HTTPException(416, "Некорректный Range")

    headers = {
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(_read_range(path, start, end), status_code=206, media_type=mime, headers=headers)


@app.get("/health")
async def health():
    return {"ok": True}
