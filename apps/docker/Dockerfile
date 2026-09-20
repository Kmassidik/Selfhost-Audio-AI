# The public half of the platform: the website and its API.
# The graphics-card worker is NOT in here — it needs CUDA, the 17 GB engine
# build and 27 GB of weights, and it runs on the box under systemd.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

RUN useradd -m -u 10001 studio && mkdir -p /data && chown -R studio /data /app
USER studio

ENV DATA_DIR=/data FRONTEND_DIR=/app/frontend APP_HOST=0.0.0.0 APP_PORT=8095 \
    SERVE_MEDIA=0 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend
EXPOSE 8095
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -fsS http://127.0.0.1:8095/healthz || exit 1

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8095", \
     "--app-dir", "/app/backend", "--workers", "2"]
