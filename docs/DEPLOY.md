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
- **A domain name** (or a subdomain) whose DNS **A record points at the server's IP**, or a free
  `<your-ip>.sslip.io` address (see the free option below).
- **Ports 80 and 443 open** to the internet (Caddy needs 80 to prove it owns the domain).

## Free option: Oracle Cloud Always Free

Oracle's Always Free tier includes an Arm virtual machine big enough for the whole stack (as of
mid-2026: up to 2 OCPUs and 12 GB RAM, 200 GB of disk in total), with no time limit. All the images
CareerLens uses run on Arm. Other free tiers don't fit as well: Render's free web services sleep and
its free Postgres is deleted after 30 days; Google Cloud's free e2-micro has only 1 GB of RAM.

Limits change, so check Oracle's current Always Free page before you start. Things to know:

- **Sign-up needs a credit or debit card** for identity verification. Always Free resources aren't
  charged, but choose shapes marked "Always Free eligible" and stay within the limits.
- **Pick your home region carefully:** Always Free Arm capacity is only in your home region, and
  popular regions sometimes report "out of capacity". Retrying later or another availability domain
  usually works.
- **Idle instances can be reclaimed** on free-only accounts (very low CPU, network and memory use
  over 7 days). A small personal app can look idle. Oracle documents this for free-tier accounts;
  upgrading the account to pay-as-you-go keeps Always Free resources free while removing that risk.

### Step by step

1. **Create the account** at <https://www.oracle.com/cloud/free/> and choose a home region near you.

2. **Create the VM:** Compute → Instances → Create instance.
   - Image: **Ubuntu 24.04** (Canonical).
   - Shape: **VM.Standard.A1.Flex** (Ampere), 2 OCPUs and 12 GB memory (or less).
   - Networking: keep the default virtual cloud network and **assign a public IPv4 address**.
   - SSH keys: upload your public key (or let Oracle generate one and save it).

3. **Open ports 80 and 443 in Oracle's network:** open the instance's subnet → Security list →
   Add ingress rules: source `0.0.0.0/0`, TCP, destination ports `80` and `443`.

4. **Open them on the VM too.** Oracle's Ubuntu images ship with a firewall that only allows SSH, so
   this step is easy to miss. SSH in (`ssh ubuntu@YOUR_IP`) and run:

   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   ```

   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   ```

   ```bash
   sudo netfilter-persistent save
   ```

5. **Get a free address with HTTPS.** No domain needed: `sslip.io` turns your IP into a hostname.
   For the IP `203.0.113.10` the hostname is `203-0-113-10.sslip.io`. Caddy gets a real HTTPS
   certificate for it. (If you'd rather have a name, a free DuckDNS subdomain works the same way.)

6. **Install Docker and start CareerLens:** follow [First deployment](#first-deployment) below on the
   VM, with `DOMAIN=203-0-113-10.sslip.io` (your IP, dashes instead of dots) in `deploy/.env`.

7. **Open `https://203-0-113-10.sslip.io`**, create your account, then set
   `ALLOW_REGISTRATION=false` (step 6 of First deployment).

## Free option: Vercel + Supabase (no server to manage)

The frontend and the API run as two Vercel projects (Hobby plan, free for non-commercial use), and
Supabase provides the database and the storage for uploaded CVs (free plan). Things to know first:

- **A free Supabase project pauses after 7 days without database activity.** Your data is kept, but
  the site stops working until you click **Restore** in the Supabase dashboard.
- **CV uploads are limited to 4 MB** (Vercel accepts at most 4.5 MB per request).
- The first request after a quiet period is slower while the API starts up.
- Free plan sizes (500 MB database, 1 GB file storage on Supabase) are far more than CareerLens needs.

### 1. Supabase: database and storage

1. Create a project at <https://supabase.com> (pick a region near you; save the database password).
   `backend/vercel.json` and `frontend/vercel.json` run the app in Singapore (`sin1`). If your database
   is elsewhere, change `regions` in both files to the closest Vercel region: every page makes several
   database calls, so a distant database makes the whole app slow.
2. **Storage → New bucket** named `cv-files`. Keep it **private** (not public).
3. **Project Settings → API keys:** copy the **secret** key (`sb_secret_…`, or the legacy
   `service_role` key). It is a password for your whole project: it only ever goes into Vercel's
   environment variables, never into the frontend or a commit.
4. Click **Connect** (top of the dashboard) and copy two connection strings:
   - **Transaction pooler** (port `6543`): for the API on Vercel.
   - **Session pooler** (port `5432`): for running migrations from your computer.

   In both, change the start from `postgresql://` to `postgresql+psycopg://` and put your database
   password in place of `[YOUR-PASSWORD]`.

### 2. Create the tables

From `backend/` on your computer, run the migrations against Supabase using the **session pooler**
string (PowerShell shown; on macOS/Linux use `DATABASE_URL=... alembic upgrade head`):

```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres.YOUR-REF:YOUR-PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres"; .venv\Scripts\alembic.exe upgrade head
```

Run it again whenever a new version adds migrations, before deploying the new API.

### 3. Vercel: the API

1. At <https://vercel.com>, **Add New → Project**, import the GitHub repository, set **Root
   Directory** to `backend`. Vercel detects FastAPI from `app/main.py` and installs
   `requirements.txt` (Python 3.13 from `.python-version`).
2. Add these **Environment Variables**, then deploy:

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the **transaction pooler** string (port 6543), with `postgresql+psycopg://` |
   | `DB_SERVERLESS` | `true` |
   | `STORAGE_BACKEND` | `supabase` |
   | `SUPABASE_URL` | `https://YOUR-REF.supabase.co` |
   | `SUPABASE_SERVICE_ROLE_KEY` | the secret key from step 1.3 |
   | `COOKIE_SECURE` | `true` |
   | `APP_ENV` | `production` |
   | `GEMINI_API_KEY` | optional |

3. Check `https://YOUR-API.vercel.app/api/v1/health` shows `"database":"ok"`.

### 4. Vercel: the web app

1. **Add New → Project** again with the same repository, **Root Directory** `frontend`.
2. Add the environment variable `API_URL` = `https://YOUR-API.vercel.app` (no trailing slash).
   It's read at build time, so redeploy the frontend if you change it.
3. Deploy, open the frontend's address, create your account, then set `ALLOW_REGISTRATION=false`
   on the **API** project and redeploy it.

The browser only ever talks to the frontend's address; the frontend forwards `/api/*` to the API
project, so the login cookie works without any cross-site setup.

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
