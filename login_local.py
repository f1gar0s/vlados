"""
Разовый запуск ЛОКАЛЬНО (на своём компьютере, не на сервере), чтобы залогиниться
в Telegram как обычный аккаунт и получить строку сессии. Bot API не умеет читать
историю канала, поэтому индексатору и стримеру нужен user-аккаунт через MTProto —
и удобнее всего передавать его логин на сервер одной строкой, а не файлом сессии.

    pip install telethon
    export API_ID=...      # получить на https://my.telegram.org → API development tools
    export API_HASH=...
    python login_local.py

Спросит номер телефона и код из Telegram (и пароль облачного пароля, если он
у вас включён). После первого раза печатает строку сессии — её нужно положить
в переменную окружения STRING_SESSION на сервере (Fly.io/Railway secrets).

Считайте эту строку как пароль от аккаунта: тот, у кого она есть, может
писать и читать от вашего имени. Храните её только в секретах хостинга,
не в репозитории.
"""

import os

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]


def main() -> None:
    with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_string = client.session.save()
        print("\nГотово. Строка сессии (сохраните как секрет STRING_SESSION):\n")
        print(session_string)
        print("\nНикому не показывайте эту строку.")


if __name__ == "__main__":
    main()
