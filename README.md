# SecureTransfer

Web-App zum sicheren Up- und Download von beliebig großen Dateien (bis 10 GB+).
Verschlüsselung findet **ausschließlich im Client** statt — der Server sieht nie den Klartext.

**Algorithmus:** AES-256-GCM · PBKDF2-SHA256 · 100.000 Iterationen · 8 MB Blöcke

---

## Voraussetzungen

- Docker + Docker Compose

Für lokale Entwicklung zusätzlich:

- Python 3.12+
- Node.js 20+ (`n 20` oder nvm)
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
HTTP_PORT=80
HTTPS_PORT=443
```

```bash
# 3. Starten
docker compose up --build

# App ist erreichbar unter https://dap.jowin.at (oder https://localhost)
```

### Architektur

Ein `app`-Container enthält Frontend und Backend in einem Image: das Angular-Frontend
wird im Docker-Build kompiliert und landet als statischer Ordner (`backend/static`) im
FastAPI-Backend-Container. FastAPI liefert alles unter `/api/*` selbst aus, alle anderen
Pfade werden aus dem statischen Ordner bedient (SPA-Fallback auf `index.html`).

Ein separater `proxy`-Container (nginx) terminiert TLS für die Domain `dap.jowin.at` und
leitet alles an `app:8000` weiter. Der `app`-Container selbst ist nicht am Host exponiert.

> **Zertifikat:** `nginx/certs/cert.pem` + `nginx/certs/key.pem` sind selbstsignierte
> Platzhalter-Dateien. Der Browser zeigt deshalb beim ersten Aufruf eine
> Sicherheitswarnung — einmalig mit „Trotzdem fortfahren" / „Advanced → Proceed" bestätigen.
> Für ein echtes Deployment beide Dateien durch ein gültiges Zertifikat (z. B. Let's Encrypt)
> für `dap.jowin.at` ersetzen (gleiche Dateinamen, dann reicht `docker compose restart proxy`).
> Der Upload-Streaming-Mechanismus (Chrome ReadableStream) setzt HTTP/2 voraus — HTTP/2 erfordert HTTPS.

Beim ersten Start führt der App-Container automatisch `alembic upgrade head` aus.

---

## Erstes Admin-Setup: User anlegen

Upload ist nur für eingeloggte Nutzer möglich. User werden per API angelegt:

```bash
curl -k -X POST https://localhost/api/auth/create_user \
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

### Download (Windows 11 — PowerShell)

```powershell
powershell -Command "irm https://<host>/api/psdec/<token>/ | iex"
```

Lädt ein fertig konfiguriertes PowerShell-Script herunter und führt es aus.
Kein NuGet, keine externen Abhängigkeiten — nur Inline-C# via `Add-Type`.

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

Der `proxy`-Service (`nginx/nginx.conf`) ist bereits fertig konfiguriert und übernimmt
TLS-Terminierung für `dap.jowin.at`, HTTP→HTTPS-Redirect sowie die für große Uploads
nötigen Timeouts/Buffering-Einstellungen. Der `app`-Container selbst spricht nur HTTP
und ist nicht am Host exponiert.

**Echtes Zertifikat einspielen:**

```bash
cp /pfad/zu/deinem/fullchain.pem nginx/certs/cert.pem
cp /pfad/zu/deinem/privkey.pem   nginx/certs/key.pem
docker compose restart proxy
```

### Eigener Reverse Proxy (Server, auf dem schon einer läuft)

Läuft auf dem Zielserver bereits ein eigener nginx (z. B. weil dort mehrere Domains
gehostet werden), kann `docker-compose.server.yml` verwendet werden — die enthält
nur `db` + `app` und published `app` auf `${APP_PORT:-8000}` am Host, ohne eigenen
`proxy`-Container. Der externe nginx muss dann selbst auf diesen Port proxyen.

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
                proxy_pass http://127.0.0.1:8000/;
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

## Umgebungsvariablen

| Variable | Beschreibung | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL Connection String | — (Pflicht) |
| `ADMIN_TOKEN` | Token für `POST /api/auth/create_user` | — (Pflicht) |
| `JWT_SECRET` | Signing-Secret für JWTs | — (Pflicht) |
| `JWT_EXPIRE_HOURS` | Gültigkeit des Access Tokens | `8` |
| `REFRESH_EXPIRE_DAYS` | Gültigkeit des Refresh-Token Cookies | `30` |
| `FILES_DIR` | Verzeichnis für verschlüsselte Uploads | `/data/files` |
| `HTTP_PORT` | (nur Docker Compose) Host-Port für HTTP→HTTPS-Redirect | `80` |
| `HTTPS_PORT` | (nur Docker Compose) Host-Port für HTTPS | `443` |
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
| `GET` | `/download/{token}` | — | Angular SPA-Route (Download-Seite im Browser) |

Alles außer `/api/*` wird vom `app`-Container aus dem kompilierten Angular-Build
(`backend/static`) ausgeliefert (SPA-Fallback auf `index.html`).
