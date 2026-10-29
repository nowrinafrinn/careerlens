# Deploying CareerLens

The whole app (web frontend, API and database) runs as one Docker Compose
stack on a single server: `docker-compose.prod.yml`. Caddy in front of it gets
and renews the HTTPS certificate on its own.

```
Internet ──443──► caddy ──► frontend (Next.js) ──/api/*──► backend (FastAPI) ──► db (PostgreSQL)
                                                               └─► cv-storage volume (uploaded CVs)
```

Only Caddy is reachable from outside. The database and the API are on the
stack's private network.

## What you need

- **A server** with Docker. A small VPS is enough: 2 GB RAM, 1–2 vCPUs, 20 GB disk, Ubuntu 24.04
  (for example Hetzner CX22, DigitalOcean Basic or similar, a few dollars a month). Building the
  frontend image needs most of the memory; with 1 GB add swap first.
- **A domain name** (or a subdomain) whose DNS **A record points at the server's IP**.
- **Ports 80 and 443 open** to the internet (Caddy needs 80 to prove it owns the domain).

## First deployment

1. **Install Docker** on the server (official convenience script):

   ```bash
   curl -fsSL https://get.docker.com | sh
   ```

2. **Get the code:**

   ```bash
   git clone https://github.com/nowrinafrinn/careerlens.git
   cd careerlens
   ```

3. **Configure:** copy the example and edit it.

   ```bash
   cp deploy/.env.example deploy/.env
   nano deploy/.env
   ```

   Set `DOMAIN` to your domain and `POSTGRES_PASSWORD` to a long random value
   (`openssl rand -base64 32`). Leave `GEMINI_API_KEY` empty unless you want the optional AI.

4. **Start everything:**

   ```bash
   docker compose -f docker-compose.prod.yml --env-file deploy/.env up -d --build
   ```

   The first build takes a few minutes. The backend applies database migrations each time it
   starts. Check progress with `docker compose -f docker-compose.prod.yml ps` (all services should
   become `healthy` or `running`).

5. **Open `https://your-domain`**, create your account, and check `https://your-domain/status`
   shows the API and database as available.

6. **Close sign-ups** unless others should be able to register: set `ALLOW_REGISTRATION=false` in
   `deploy/.env`, then apply it:

   ```bash
   docker compose -f docker-compose.prod.yml --env-file deploy/.env up -d backend
   ```

> Tip: create a shell alias so the long command is short:
> `alias clp='docker compose -f docker-compose.prod.yml --env-file deploy/.env'`, then `clp ps`,
> `clp logs -f backend`, and so on.

## Updating to a new version

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file deploy/.env up -d --build
```

Data lives in named volumes (`pgdata`, `cv-storage`), so rebuilding the containers keeps it.
New migrations run automatically when the backend starts.

## Backups

Two things hold your data: the database and the uploaded CV files.

```bash
# Database → a compressed SQL dump
docker compose -f docker-compose.prod.yml --env-file deploy/.env exec -T db \
  pg_dump -U careerlens careerlens | gzip > careerlens-db-$(date +%F).sql.gz

# Uploaded CVs → a tar archive
docker run --rm -v careerlens-prod_cv-storage:/data -v "$PWD":/backup alpine \
  tar czf /backup/careerlens-cvs-$(date +%F).tar.gz -C /data .
```

Copy the files off the server (they contain personal data, so store them somewhere private).
To restore the database into a fresh stack:

```bash
gunzip -c careerlens-db-YYYY-MM-DD.sql.gz | docker compose -f docker-compose.prod.yml --env-file deploy/.env exec -T db \
  psql -U careerlens careerlens
```

`docker compose down` keeps the volumes. **`docker compose down -v` deletes them, including all
data.**

## Optional AI (Google Gemini)

Add `GEMINI_API_KEY` to `deploy/.env` and restart the backend (`... up -d backend`). Users still have
to turn AI assistance on themselves, after a consent screen that says what is sent. On Google's free
tier, data sent may be used to improve Google's products; for real CVs use a paid (billing-enabled)
key or don't enable it. See the README's "Optional AI assistance" section.

## Troubleshooting

| Symptom | What to check |
|---|---|
| The site doesn't load / certificate errors | DNS A record points at this server; ports 80 and 443 open (`ufw status`); `... logs caddy`. |
| "Unavailable" on `/status`, or 500 errors | `... logs backend`: usually the database password in `deploy/.env` changed after the first start (the database keeps the original). |
| Can't sign in on the live site | The cookie is HTTPS-only (`COOKIE_SECURE=true`), so use `https://`. |
| Build killed on a 1 GB server | Add swap: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`. |

## Trying the production stack on your own computer

With Docker Desktop you can run the same stack locally, on plain HTTP:

```bash
cp deploy/.env.example deploy/.env
```

In `deploy/.env` set `DOMAIN=:80`, `HTTP_PORT=8080`, `HTTPS_PORT=8443`, `COOKIE_SECURE=false` and a
`POSTGRES_PASSWORD`, then run the `up -d --build` command above and open <http://localhost:8080>.
Stop it with `docker compose -f docker-compose.prod.yml --env-file deploy/.env down`.

## Other hosts

The stack is plain Docker Compose, so any server that runs Docker works. Platforms like Railway or
Render don't run a Compose file as-is: there you would create a PostgreSQL database, a service from
`backend/Dockerfile` (with `DATABASE_URL`, `COOKIE_SECURE=true` and a persistent disk mounted at
`/app/storage`) and a service from `frontend/Dockerfile` (with the build argument `API_URL` set to the
backend's internal address), and let the platform provide HTTPS instead of Caddy.
