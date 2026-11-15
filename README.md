# SecureTransfer

Web-App zum sicheren Up- und Download von beliebig großen Dateien (bis 10 GB+).
Verschlüsselung findet **ausschließlich im Client** statt — der Server sieht nie den Klartext.

**Algorithmus:** AES-256-GCM · PBKDF2-SHA256 · 100.000 Iterationen · 8 MB Blöcke

---

## Voraussetzungen

- Docker + Docker Compose

Für lokale Entwicklung zusätzlich:

- Python 3.14+
- Node.js 24 LTS (oder ≥ 22.22, nvm: `nvm install 24`)
- Angular CLI (`npm install -g @angular/cli`)

---

## Schnellstart mit Docker

```bash
# 1. Repository klonen und ins Verzeichnis wechseln
git clone <repo-url>
cd dap

# 2. .env anlegen und Werte setzen
cp .env.example .env
```

`.env` befüllen:

```env
POSTGRES_PASSWORD=sicheres-datenbankpasswort
ADMIN_TOKEN=langer-zufaelliger-admin-token
JWT_SECRET=langer-zufaelliger-jwt-secret
JWT_EXPIRE_HOURS=8
REFRESH_EXPIRE_DAYS=30
APP_PORT=8000
```

```bash
# 3. Starten
docker compose up --build

# App lauscht auf http://127.0.0.1:8000 – der eigene Reverse Proxy leitet dorthin weiter
# (siehe Abschnitt „Reverse Proxy / TLS“)
```

### Variante: fertiges Image aus GitHub

Statt lokal zu bauen, kann das von der GitHub Action gebaute Image
`ghcr.io/jowin202/dap/app:latest` verwendet werden. `docker-compose.github.yml` ist
eigenständig (braucht nur `.env` und `volumes/`), sonst aber identisch zu
`docker-compose.yml` — Änderungen an einer Datei auch in der anderen nachziehen.

```bash
docker compose -f docker-compose.github.yml pull
docker compose -f docker-compose.github.yml up -d
```

Aktualisieren: Action „Build & Push Docker Image" auf GitHub starten, danach dieselben
zwei Befehle erneut ausführen.

### Architektur

Ein `app`-Container enthält Frontend und Backend in einem Image: das Angular-Frontend
wird im Docker-Build kompiliert und landet als statischer Ordner (`backend/static`) im
FastAPI-Backend-Container. FastAPI liefert alles unter `/api/*` selbst aus, alle anderen
Pfade werden aus dem statischen Ordner bedient (SPA-Fallback auf `index.html`).

Der `app`-Container spricht nur HTTP und ist ausschließlich auf `127.0.0.1:8000` gebunden.
TLS und HTTP/2 übernimmt ein vorgeschalteter Reverse Proxy (siehe unten).

Bei jedem Start führt der App-Container automatisch `alembic upgrade head` aus.

---

## Erstes Admin-Setup: User anlegen

Upload ist nur für eingeloggte Nutzer möglich. User werden per API angelegt:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/create_user \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "sicher123"}'
```

Der `ADMIN_TOKEN` ist der Wert aus der `.env`.

---

## Lokale Entwicklung

### Backend

```bash
cd backend

# Abhängigkeiten installieren (einmalig)
pip install -r requirements.txt

# Umgebungsvariablen setzen
export DATABASE_URL="postgresql+asyncpg://dap:pw@localhost/dap"
export ADMIN_TOKEN="dev-admin-token"
export JWT_SECRET="dev-jwt-secret"

# Datenbank migrieren (einmalig bzw. nach neuen Migrations)
alembic upgrade head

# Server starten
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Abhängigkeiten installieren (einmalig)
npm install

# Dev-Server starten (Proxy auf Backend :8000 aktiv)
ng serve
```

App unter `http://localhost:4200` erreichbar.

Alternativ: VS Code Task **"dev: start all"** startet Backend und Frontend parallel
(`Terminal → Run Build Task` oder `Ctrl+Shift+B`).

### Datenbank (lokal)

Für lokale Entwicklung kann PostgreSQL per Docker gestartet werden:

```bash
docker run -d \
  --name dap-db \
  -e POSTGRES_USER=dap \
  -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=dap \
  -p 5432:5432 \
  postgres:17-alpine
```

---

## Nutzung

### Upload (Browser)

1. Unter `/upload` anmelden
2. Datei per Drag & Drop oder Dateiauswahl hinzufügen
3. Passwort eingeben und Ablaufzeit wählen
4. Upload starten — der Browser verschlüsselt die Datei blockweise vor dem Hochladen
5. Nach dem Upload: Download-URL und fertige Einzeiler für Browser, PowerShell und Shell kopieren

### Download (Browser)

URL aufrufen: `https://<host>/download/<token>`

oder unter `/download` den Token manuell eingeben, Passwort eingeben und herunterladen.
Die Entschlüsselung erfolgt komplett im Browser — die Datei wird direkt in den vom Nutzer
gewählten Speicherpfad geschrieben (via File System Access API).

> **Browserunterstützung:** nur Chromium-Browser (Chrome, Edge, Brave) auf dem Desktop.

### Download (Windows — PowerShell 7.4+)

```powershell
pwsh -Command "irm https://<host>/api/psdec/<token>/ | iex"
```

Lädt ein fertig konfiguriertes PowerShell-Script herunter und führt es aus.
Kein NuGet, keine externen Abhängigkeiten — nur Inline-C# via `Add-Type`.
Benötigt PowerShell 7.4 oder neuer (`winget install --id Microsoft.PowerShell -e`);
das vorinstallierte Windows PowerShell 5.1 kann kein AES-GCM.

### Download (Linux / macOS — Shell)

```bash
curl -sfL "https://<host>/api/shdec/<token>/" | sh
```

Erfordert Python 3 mit der `cryptography`-Library:

```bash
pip install cryptography
```

---

## Reverse Proxy / TLS

Das Projekt bringt keinen eigenen Proxy mit. Der `app`-Container lauscht nur per HTTP auf
`127.0.0.1:${APP_PORT:-8000}`; ein vorgeschalteter Reverse Proxy muss TLS terminieren und
HTTP/2 sprechen. Beides ist Pflicht:

- **HTTPS:** Die WebCrypto-API (`crypto.subtle`) ist im Browser nur in einem Secure Context
  (HTTPS oder `localhost`) verfügbar — ohne TLS funktioniert die Verschlüsselung nicht.
- **HTTP/2:** uvicorn spricht kein HTTP/2, der Streaming-Upload braucht es aber (siehe unten).

> **Wichtigster Punkt: `http2 on;` nicht vergessen.**
> Der Upload-Mechanismus (`fetch` mit `duplex: 'half'`, siehe
> [transfer.service.ts](frontend/src/app/services/transfer.service.ts)) braucht HTTP/2
> zwischen Browser und erstem Hop. Fehlt `http2`, wirkt das im Browser wie ein reiner
> TLS/ALPN-Fehler (`ERR_ALPN_NEGOTIATION_FAILED` in Chrome) und ist von der eigentlichen
> Ursache — fehlendes HTTP/2 — leicht zu verwechseln.

Vollständiges Beispiel für einen externen Server-Block:

```nginx
server {
        listen 443 ssl;
        listen [::]:443 ssl;
        http2 on;
        server_name dap.jowin.at;

        ssl_certificate     /etc/nginx/certs/fullchain.pem;
        ssl_certificate_key /etc/nginx/certs/privkey.pem;

        client_max_body_size    0;
        proxy_request_buffering off;
        proxy_buffering         off;
        proxy_read_timeout      3600s;
        proxy_send_timeout      3600s;

        location / {
                proxy_pass http://127.0.0.1:8000;
                proxy_set_header Host              $host;
                proxy_set_header X-Real-IP         $remote_addr;
                proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
                proxy_set_header X-Forwarded-Host  $host;
        }
}
```

Ohne `client_max_body_size 0;` bricht nginx jeden Upload über der Default-Grenze von
1 MB mit 413 ab — kleine Testdateien fallen darunter nicht auf, echte Dateien schon.
Ohne `proxy_request_buffering off;` / `proxy_buffering off;` puffert nginx den
kompletten Request/Response, statt ihn zu streamen (Speicherproblem bei großen Dateien).
`proxy_read/send_timeout` verhindert, dass lange Transfers am nginx-Default (60s) abreißen.

---

## Kubernetes

Manifeste und Anleitung liegen in [k8s/](k8s/README.md). Das Image
`ghcr.io/jowin202/dap/app` wird per GitHub Action (manuell auslösbar) gebaut.

---

## Umgebungsvariablen

| Variable | Beschreibung | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL Connection String | — (Pflicht) |
| `ADMIN_TOKEN` | Token für `POST /api/auth/create_user` | — (Pflicht) |
| `JWT_SECRET` | Signing-Secret für JWTs | — (Pflicht) |
| `JWT_EXPIRE_HOURS` | Gültigkeit des Access Tokens | `8` |
| `REFRESH_EXPIRE_DAYS` | Gültigkeit des Refresh-Token Cookies | `30` |
| `FILES_DIR` | Verzeichnis für verschlüsselte Uploads | `/data/files` |
| `APP_PORT` | (nur Docker Compose) Host-Port auf `127.0.0.1`, auf den der Reverse Proxy weiterleitet | `8000` |
| `POSTGRES_PASSWORD` | (nur Docker Compose) Datenbankpasswort | — (Pflicht) |

---

## Volumes

Zwei persistente Volumes — beide müssen gesichert werden:

| Volume | Inhalt |
|---|---|
| `postgres-data` | PostgreSQL-Datenbankdateien |
| `file-storage` | Verschlüsselte Upload-Dateien |

---

## API-Übersicht

| Method | Pfad | Auth | Beschreibung |
|---|---|---|---|
| `POST` | `/api/auth/create_user` | Admin-Token | Nutzer anlegen |
| `POST` | `/api/auth/login` | — | Login, gibt JWT zurück |
| `POST` | `/api/auth/refresh` | Cookie | Neuen Access Token holen |
| `POST` | `/api/auth/logout` | Cookie | Refresh-Token invalidieren |
| `POST` | `/api/upload` | JWT | Datei verschlüsselt hochladen |
| `GET` | `/api/download/{token}` | — | Datei herunterladen (Rohdaten) |
| `GET` | `/api/info/{token}` | — | Dateiinfos (Name, Größe, Ablauf) |
| `GET` | `/api/psdec/{token}/` | — | PowerShell-Decode-Script |
| `GET` | `/api/shdec/{token}/` | — | Shell-Decode-Script |
| `GET` | `/api/health` | — | Health-Check (für Docker/Kubernetes) |
| `GET` | `/download/{token}` | — | Angular SPA-Route (Download-Seite im Browser) |

Alles außer `/api/*` wird vom `app`-Container aus dem kompilierten Angular-Build
(`backend/static`) ausgeliefert (SPA-Fallback auf `index.html`).
