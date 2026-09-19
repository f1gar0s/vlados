# Мини-приложение «Плеер» для Telegram

Схема под ваш репозиторий `f1gar0s/vlados`: сам плеер и личные mp3 живут в
GitHub, основной каталог из тысяч треков подтягивается с [Audius](https://audius.org) —
открытого музыкального протокола с бесплатным API, файлы там не занимают
место в вашем репозитории и не упираются в лимиты GitHub Pages.

## Файлы

| Файл / папка | Что это |
|---|---|
| `index.html` | Всё мини-приложение: вёрстка, стили, логика. Зависимостей нет. |
| `tracks.json` | Итоговый плейлист — то, что реально грузит плеер. |
| `bot.py` | Бот на aiogram 3: кнопка запуска мини-приложения. |
| `софийка.mp3` (и любые другие ваши mp3) | Личные треки прямо в репозитории. |
| `tools/local_catalog.py` | Сканирует mp3 рядом с `index.html`, читает теги. |
| `tools/audius_catalog.py` | Тянет каталог/плейлист/поиск с Audius. |
| `tools/merge_catalogs.py` | Склеивает локальный и Audius-каталоги в `tracks.json`. |
| `tools/build_catalog.py` | Запасной путь: залить свои файлы в Cloudflare R2, если когда-нибудь понадобится свой большой каталог. Для текущей схемы не нужен. |

## Как собрать tracks.json

```bash
pip install mutagen

cd tools

# 1. Личные треки, которые лежат прямо в репозитории (софийка.mp3 и т.п.)
python local_catalog.py .. --out local.json

# 2. Каталог с Audius — три варианта на выбор:
python audius_catalog.py --search "lofi hip hop" --limit 300 --app "VladosPlayer"
python audius_catalog.py --trending --limit 100 --app "VladosPlayer"
python audius_catalog.py --playlist <playlist_id> --app "VladosPlayer"
# каждый вызов перезаписывает tracks.json — переименуйте в audius.json перед следующим шагом
mv tracks.json audius.json

# 3. Склеить всё в один плейлист (личные треки — первыми)
python merge_catalogs.py local.json audius.json --out ../tracks.json
```

`--app` — просто имя вашего приложения для заголовка запроса, Audius его
использует для статистики, ключ не нужен. Значение может быть любым, например
`"VladosPlayer"`.

Повторяйте `audius_catalog.py --search` с разными запросами (жанры, исполнители,
настроения) и объединяйте несколько `audius_*.json` через `merge_catalogs.py`,
если один запрос не даёт нужный охват — так наберёте каталог на тысячи треков
без единого файла в вашем репозитории.

## Обновление репозитория

Я не могу запушить изменения сам — сеть в моём контейнере отключена. Проще
всего через веб-интерфейс:

1. Откройте `github.com/f1gar0s/vlados`.
2. **Add file → Upload files**, перетащите обновлённые `index.html` и
   `tracks.json` (и `tools/*`, если ещё не загружали).
3. Commit changes.

Или через git, если работаете локально:

```bash
git clone https://github.com/f1gar0s/vlados.git
cd vlados
# скопируйте сюда обновлённые index.html, tracks.json, tools/
git add .
git commit -m "Каталог через Audius + личные треки"
git push
```

GitHub Pages передеплоится сам за минуту-две — Deployments в репозитории уже
настроен, вы это видели на скриншоте.

## Запуск бота

```bash
pip install "aiogram>=3.7"
export BOT_TOKEN="123456:ABC..."               # токен от @BotFather
export WEBAPP_URL="https://f1gar0s.github.io/vlados/"
python bot.py
```

Дальше в BotFather: `/newapp` → выбрать бота → указать тот же URL, чтобы
получить короткую ссылку вида `t.me/ваш_бот/player`.

## Про формат tracks.json

```json
[
  { "id": "local-sofiyka", "title": "Софийка", "artist": "", "duration": 0, "src": "софийка.mp3" },
  { "id": "audius-abc123", "title": "Название", "artist": "Исполнитель",
    "duration": 214, "src": "https://discoveryprovider.audius.co/v1/tracks/abc123/stream?app_name=VladosPlayer" }
]
```

`src` может быть и относительным путём (файл рядом с `index.html`), и прямой
ссылкой — плеер не различает источники.

## Что уже учтено в плеере

- Список очереди отрисовывается порциями по 50 треков и подгружает следующие
  при прокрутке — с 4 тысячами записей интерфейс не подвиснет.
- Тема, хаптик-отклик, `CloudStorage` для избранного и последнего трека —
  как в предыдущей версии.
- Перемотка работает и для файлов из репозитория, и для потока с Audius —
  оба источника отдают `Range`-запросы.

## Важно про Audius

- API бесплатный, но Audius просит указывать авторов — плеер и так показывает
  исполнителя из тегов, ничего дополнительно делать не нужно.
- Каталог полностью независимый (инди-сцена, ремиксы, электроника), крупных
  лейблов там нет — если нужен мейнстрим, легального пути без подписки
  слушателя на стриминг не существует (см. предыдущее обсуждение про Spotify/
  Apple Music).
- Ссылки на стрим — постоянные (не протухают как у Telegram `getFile`),
  можно один раз собрать `tracks.json` и не пересобирать его при каждом запуске.
