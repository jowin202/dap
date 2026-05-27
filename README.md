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
PORT=443
```

```bash
# 3. Starten
docker compose up --build

# App ist erreichbar unter https://localhost
```

> **Selbstsigniertes Zertifikat:** Der Browser zeigt beim ersten Aufruf eine Sicherheitswarnung.
> Einmalig mit „Trotzdem fortfahren" / „Advanced → Proceed" bestätigen.
> Der Upload-Streaming-Mechanismus (Chrome ReadableStream) setzt HTTP/2 voraus — HTTP/2 erfordert HTTPS.
> In einem echten Deployment wird das selbstsignierte Zertifikat durch ein gültiges (z. B. Let's Encrypt) ersetzt.

Beim ersten Start führt der Backend-Container automatisch `alembic upgrade head` aus.

---

## Erstes Admin-Setup: User anlegen

Upload ist nur für eingeloggte Nutzer möglich. User werden per API angelegt:

```bash
curl -X POST http://localhost/auth/create_user \
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

URL aufrufen: `http://<host>/download/<token>`

oder unter `/download` den Token manuell eingeben, Passwort eingeben und herunterladen.
Die Entschlüsselung erfolgt komplett im Browser — die Datei wird direkt in den vom Nutzer
gewählten Speicherpfad geschrieben (via File System Access API).

> **Browserunterstützung:** nur Chromium-Browser (Chrome, Edge, Brave) auf dem Desktop.

### Download (Windows 11 — PowerShell)

```powershell
powershell -Command "irm https://<host>/psdec/<token>/ | iex"
```

Lädt ein fertig konfiguriertes PowerShell-Script herunter und führt es aus.
Kein NuGet, keine externen Abhängigkeiten — nur Inline-C# via `Add-Type`.

### Download (Linux / macOS — Shell)

```bash
curl -sfL "https://<host>/shdec/<token>/" | sh
```

Erfordert Python 3 mit der `cryptography`-Library:

```bash
pip install cryptography
```

---

## Deployment hinter Reverse Proxy (nginx / k8s)

Der Backend-Container spricht nur HTTP. TLS wird vom Reverse Proxy übernommen.
Folgende Header müssen weitergeleitet werden:

```nginx
proxy_set_header Host              $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
```

Für große Uploads Buffering deaktivieren:

```nginx
client_max_body_size    0;
proxy_request_buffering off;
proxy_buffering         off;
proxy_read_timeout      3600s;
```

---

## Umgebungsvariablen

| Variable | Beschreibung | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL Connection String | — (Pflicht) |
| `ADMIN_TOKEN` | Token für `POST /auth/create_user` | — (Pflicht) |
| `JWT_SECRET` | Signing-Secret für JWTs | — (Pflicht) |
| `JWT_EXPIRE_HOURS` | Gültigkeit des Access Tokens | `8` |
| `REFRESH_EXPIRE_DAYS` | Gültigkeit des Refresh-Token Cookies | `30` |
| `FILES_DIR` | Verzeichnis für verschlüsselte Uploads | `/data/files` |
| `PORT` | Exposed Port des Frontend-Containers | `80` |
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
| `POST` | `/auth/create_user` | Admin-Token | Nutzer anlegen |
| `POST` | `/auth/login` | — | Login, gibt JWT zurück |
| `POST` | `/auth/refresh` | Cookie | Neuen Access Token holen |
| `POST` | `/auth/logout` | Cookie | Refresh-Token invalidieren |
| `POST` | `/upload` | JWT | Datei verschlüsselt hochladen |
| `GET` | `/download/{token}` | — | Datei herunterladen |
| `GET` | `/api/info/{token}` | — | Dateiinfos (Name, Größe, Ablauf) |
| `GET` | `/psdec/{token}/` | — | PowerShell-Decode-Script |
| `GET` | `/shdec/{token}/` | — | Shell-Decode-Script |
