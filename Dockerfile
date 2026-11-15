# ---- Frontend build ----
FROM node:24-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/. .
RUN npm run build

# ---- Backend runtime, serving the compiled frontend as static files ----
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/. .
COPY --from=frontend-build /frontend/dist/frontend/browser ./static

RUN mkdir -p /data/files

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

# Migrationen beim Start ausführen, dann Server starten
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
