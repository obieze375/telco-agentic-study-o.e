FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTAPI_HOST=0.0.0.0 \
    FASTAPI_PORT=7860 \
    UVICORN_RELOAD=false \
    DATA_SOURCE=data/Phase_1 \
    DATA_SPLIT=test

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh

EXPOSE 7860

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:${FASTAPI_PORT}/health" || exit 1

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["server"]
