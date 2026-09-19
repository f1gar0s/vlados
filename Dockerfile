FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# DB_PATH и CACHE_DIR по умолчанию смотрят в ./data — примонтируйте сюда volume,
# иначе каталог и кеш файлов будут пропадать при каждом передеплое
VOLUME ["/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
