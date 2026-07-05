# ---- Frontend build ----
FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/. .
RUN npm run build

# ---- Backend runtime, serving the compiled frontend as static files ----
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/. .
COPY --from=frontend-build /frontend/dist/frontend/browser ./static

RUN mkdir -p /data/files

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
