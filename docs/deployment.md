# Deploying MetalArm

Everything runs on one Linux server with Docker, behind Caddy, which obtains
HTTPS certificates automatically. The stack is defined in
`deploy/docker-compose.prod.yml`; nothing in this repo deploys on its own.

| URL | Serves |
|---|---|
| `https://DOMAIN` | Web app (Reflex), plus `/privacy` and `/support` |
| `https://api.DOMAIN` | API for the web app's server and the iOS app |

Only ports 80 and 443 are public. Postgres, Redis, the API and the web app are
reachable only on the stack's internal network.

## 1. What you need

- A Linux server with Docker Engine and the Compose plugin. 2 vCPU / 4 GB RAM
  is comfortable (the Reflex frontend build is the heaviest step).
- A domain. Create DNS records pointing **both** `DOMAIN` and `api.DOMAIN` at
  the server (A, and AAAA if it has IPv6) before the first start, or the
  certificate requests fail.
- Inbound TCP 80 and 443 (and UDP 443 for HTTP/3) open in the firewall.

## 2. First deploy

```bash
git clone <your repo> metalarm && cd metalarm
cp deploy/.env.production.example deploy/.env.production
# Fill every CHANGE_ME. Generate each secret separately:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production up -d --build
```

The `migrate` service applies all migrations and imports the exercise library
before the API starts. Then check it really came up:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production ps
curl -s https://api.DOMAIN/health        # "status": "ok", schema "ready": true
curl -sI https://api.DOMAIN/docs         # 404: API docs are off in production
```

Tip: `alias mprod='docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production'`.

## 3. Updating

```bash
git pull
mprod up -d --build        # rebuilds images; migrate runs again before the API restarts
```

Migrations run automatically and are idempotent. Take a backup first when an
update contains a migration (`deploy/backup.sh`).

**Rollback:** check out the previous commit and `mprod up -d --build`. If that
release's migration has to be undone, restore the backup taken before the
update rather than downgrading by hand.

## 4. Backups

- The `backup` service writes a `pg_dump` to `deploy/backups/` every 24 hours
  and deletes dumps older than `BACKUP_RETENTION_DAYS` (default 14).
- **Copy `deploy/backups/` off the server** (object storage, another machine).
  A backup on the same disk does not survive losing the disk.
- Manual backup: `deploy/backup.sh`
- Restore: `deploy/backup.sh restore deploy/backups/<file>.dump` (asks for
  confirmation, stops the API while restoring).

Test a restore on a scratch server before you need one.

## 5. Secrets

All secrets live only in `deploy/.env.production` (gitignored).

| Secret | Rotating it |
|---|---|
| `JWT_SECRET_KEY` | Signs every user out on all devices. Change it, `mprod up -d`. |
| `POSTGRES_PASSWORD` | Must also be changed inside Postgres (`ALTER ROLE ... PASSWORD`), then `mprod up -d`. |
| `REDIS_PASSWORD` | Change it, `mprod up -d` (Redis only holds caches and rate-limit counters). |

## 6. Security built in

- HTTPS everywhere, HSTS and standard security headers (Caddy).
- Login, signup and token refresh are rate limited per client address and per
  account (`backend/app/core/rate_limit.py`); clients get 429 with `Retry-After`.
- Access tokens last `ACCESS_TOKEN_EXPIRE_MINUTES`; refresh tokens
  `REFRESH_TOKEN_EXPIRE_DAYS`. `POST /api/v1/auth/logout` revokes every token a
  user holds; `DELETE /api/v1/auth/me` deletes the account and all its data.
- `/docs`, `/redoc` and `/openapi.json` are disabled (`ENVIRONMENT=production`).
- Containers run as non-root; the backend image contains no test tooling.

## 7. Monitoring

- `https://api.DOMAIN/health` returns 503 and names the failing dependency
  (Postgres, Redis, or an un-migrated schema). Point an uptime monitor at it.
- Logs: `mprod logs -f backend` (rotated at 10 MB × 5 per container).

## 8. iOS app release checklist

The app lives in `ios/`. Its Release build talks to `https://api.<METALARM_DOMAIN>`,
set in `ios/Config/Release.xcconfig`.

1. Enroll in the Apple Developer Program.
2. In `ios/Config/Release.xcconfig`, set `METALARM_DOMAIN` to your DOMAIN.
   In Xcode → target MetalARM → Signing & Capabilities, choose your Team
   (or set `DEVELOPMENT_TEAM` in the xcconfig).
3. Create the app in App Store Connect with bundle ID `com.SreeRam.MetalARM`
   (or change `PRODUCT_BUNDLE_IDENTIFIER` first; it must be unique).
4. Listing: screenshots are in `ios/AppStore/screenshots/`; privacy policy URL
   `https://DOMAIN/privacy`; support URL `https://DOMAIN/support`. The privacy
   "nutrition label" answers match `ios/MetalARM/PrivacyInfo.xcprivacy`
   (email, name, fitness data, user ID; linked to the user; no tracking).
5. Give App Review a demo account (create one on the production server).
6. Xcode → Product → Archive → Distribute App → TestFlight, then submit.
