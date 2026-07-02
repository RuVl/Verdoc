# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Verdoc is a digital-goods storefront: customers buy passport files, pay via **Plisio** (crypto invoices), and receive time-limited email download links. Vue 3 SPA frontend + Django REST Framework backend + PostgreSQL, all orchestrated with Docker Compose behind nginx. The whole app runs from two domains (a primary site and a "mirror") served by the same containers.

## Commands - use the Makefile

**Prefer `make` targets over hand-rolled commands.** The root `Makefile` wraps everything in a cross-platform way (recipes are just `cd` + `uv` / `uvx` / `docker compose` / `npm`; file ops go through `uv run --no-project python`). Run `make help` for the full list. The project is **docker-first**: `manage.py` and `psql` targets `exec` into the running stack (`docker-compose.yaml` builds `frontend-nginx` on 80/443, `backend` gunicorn on 8000, `postgres`), so bring it up first.

```bash
make init          # full bootstrap: check-deps → env → install → pre-commit → dev-infra → dev-migrate (NOT `up`)
make env           # create .env from *.dist (backend / frontend / postgres / backend/dev.env) where missing
make install       # backend venv (uv sync); make front-install for the frontend

make up            # full stack in docker (build + run)
make down          # stop; make ps / make logs[-backend|-db|-nginx]

# Local development - backend & frontend on the host, only postgres in docker
# (avoids the rootless-podman 80/443 problem; no nginx). See "Local development" below.
make dev-infra     # postgres only (docker-compose.dev.yaml), published to localhost:5432
make dev-migrate   # migrate with the host backend against the dev db
make dev-backend   # runserver 0.0.0.0:8000 on the host
make dev-superuser / make dev-shell / make dev-infra-down

# Django (run inside the backend container) - apps are: order, passport
make migrate
make makemigrations m="order passport"
make superuser
make update-rates  # fetch currency rates (djmoney); required before first orders
make expire        # release reservations on expired PENDING orders (also cron, 00:05 daily)

# Frontend
make front-dev     # vite dev server on 0.0.0.0:5173
make front-build   # production build to dist/

# DB
make db-dump [DUMP=backups/dump.sql] / make db-restore DUMP=… / make psql

# Quality
make lint          # ruff check + format --check (no edits)
make format        # ruff check --fix + ruff format
make pre-commit-install / make pre-commit
```

**Tooling:** dependencies and venvs are managed with **uv** - `backend/pyproject.toml` (+ `uv.lock`) is the source of truth (no `requirements.txt`), and the backend image installs via `uv sync`. Lint/format is **`uvx ruff@0.15.12`**; ruff config lives in `backend/pyproject.toml` - **line-length 120**, `target-version = "py313"`, rule set `E, F, I, UP, B, W, C4, SIM`. pre-commit lives at the **repo root** (`.pre-commit-config.yaml`, run via `uvx pre-commit`): ruff-check `--fix` + ruff-format; mypy is commented out. There are **no tests** (`tests.py` files are empty stubs). Target runtime is **Python 3.13**.

## Environment & configuration

- Each service reads its own `.env` (copy from the `.env.dist` next to it): `backend/`, `frontend/`, `postgres/`. The backend also loads `postgres/.env` for the DB connection.
- **Local development** overrides live in `backend/dev.env` (copy from `backend/dev.env.dist`). It's layered on top of `backend/.env` when running the host backend (`uv run --env-file .env --env-file dev.env`), because `settings.py` reads only `os.environ` (no `read_env()`). It points `DATABASE_URL` at `localhost:5432` and sets `EMAIL_URL=consolemail://`. Its DB user/password/name **must match `postgres/.env`**.
- Settings use `django-environ`. Key vars: `DATABASE_URL`, `EMAIL_URL`, `PLISIO_SECRET_KEY`, `MIRROR_PLISIO_SECRET_KEY`, `OPENEXCHANGERATES_APP_ID`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`.
- Frontend build injects `VITE_API_URL` as the compile-time constant `__API_URL__` (see `vite.config.js`); the axios client in `src/api/index.js` uses Django's CSRF cookie/header.
- After first deploy, update the `django_site` row's domain to match your host (used to build absolute download URLs). `SITE_SCHEME = "https"`.

## Architecture

### Order / fulfillment flow (the core domain)
Backend apps: `passport` (catalog + inventory) and `order` (checkout, payment, delivery).

1. **Catalog** - `Country` → `Passport` → `PassportFile`. Each `PassportFile` is one sellable file with a status: `IN_STOCK → RESERVED → SOLD`. A `Passport.quantity` is a **denormalized count of IN_STOCK files**, kept in sync by the `post_save`/`post_delete` signal in `passport/signals.py`. Do not set `quantity` manually.
2. **Checkout** - `POST /api/order/` (`OrderCreateView` + `OrderSerializer`). Validates stock, computes `total_price` by converting each passport price to USD via djmoney `convert_money`, creates the `Order` + `OrderItem`s, and **reserves** files (flips them to `RESERVED`, decrements quantity). Then requests a Plisio invoice and returns `redirect_url`. If the invoice call fails, the reservation is rolled back and the order deleted.
3. **Payment callback** - `POST /api/order/status` (`PlisioCallbackView`). Verifies Plisio's `verify_hash` (HMAC-SHA1) against **both** the primary and mirror secret keys. Maps Plisio status → `Order.OrderStatus`, upserts the `Transaction`. On PAID/OVERPAID it calls `order.sell()` (files → `SOLD`, creates `DownloadLink`s) and emails links; on EXPIRED/CANCELLED it resets the reservation.
4. **Delivery** - `DownloadLink` (uuid, valid 24h). `GET /api/order/file/<email>/<uuid>/` streams the file. `POST /api/send-links/` re-issues fresh links for a customer's paid orders (refreshes uuid + expiry) and re-emails them.
5. **Expiry** - `Order.is_expired()` (~1h). The `expire_transactions` management command runs via cron in the backend container and returns reserved files to stock for stale PENDING orders.

**Money/inventory invariants live on the models** (`Order`, `OrderItem`, `Passport`), and every state transition (`reserve`, `return2stock`, `sell`, `reset_reservation`) is wrapped in a DB transaction (`@atomic`). Change these methods rather than mutating `status`/`quantity` in views. `reserve`/`sell` raise `ValueError` on invariant violations, which views translate to 400s.

### Dual-domain (mirror) setup
The same deployment serves a primary domain and a "mirror" domain. This shows up in several places you must keep consistent:
- **nginx**: `frontend/nginx/site.conf.template` and `mirror.conf.template` are rendered by nginx's `envsubst` (only the `DOMAIN` var is substituted; the Dockerfile copies them as `verif-docs.conf.template` / `photo-scan.conf.template`).
- **Plisio**: the primary domain uses `PLISIO_SECRET_KEY`, everything else uses `MIRROR_PLISIO_SECRET_KEY` (`OrderCreateView` picks by `Site.objects.get_current().domain == ALLOWED_HOSTS[0]`). The callback validates against both keys.

### Email delivery
Download links are emailed via whatever `EMAIL_URL` points to. **In production that is SendPulse (SMTP)** - the active path. A **backup** DKIM-signing relay is available as the `mail` service in `docker-compose.yaml`, on the ready-made `boky/postfix` image, behind a compose **profile** so it does not start by default:
- Start it only when needed: `docker compose --profile mail up -d mail`, then set `EMAIL_URL=smtp://mail:587` in `backend/.env` and restart the backend. boky listens on **587** (submission); outbound to recipients' MX on 25 is handled by Postfix itself - no port needs publishing.
- DKIM: selector is `mail` (boky default, matches the published `mail._domainkey.photo-scan.store` DNS record). The existing **private key** is mounted read-only at `/etc/opendkim/keys/photo-scan.store.private` (boky's expected `<domain>.private` path) - copy it from the server into `secrets/opendkim/photo-scan.store.private` (gitignored). **Never regenerate the key** (do not set `DKIM_AUTOGENERATE`) - it would break DNS - and never commit or print it.

### i18n
Both ends are bilingual (en/ru). Backend uses **django-modeltranslation** - translated fields are declared in `passport/translation.py` (`Country.name`, `Passport.name`); the country list endpoint honors a `?lang=` query param. Frontend uses vue-i18n (`src/i18n/locales/`). Note: `order/utils.py` email copy is hard-coded Russian.

### Frontend
Vue 3 + Pinia (with `pinia-plugin-persistedstate` for the cart), Vue Router, axios. Stores in `src/stores/` (`cart`, `currencies`, `order`, `settings`, `languages`) hold client state; currency switching is client-side using rates from `GET /api/exchange-rates/`.

## Local development

For day-to-day work you don't need the full docker stack (and under rootless podman `frontend-nginx` can't bind 80/443). Instead run the app processes on the host and keep only postgres in docker:
- `docker-compose.dev.yaml` runs **postgres only**, publishing it to `localhost:5432`, using a volume named `verdoc_postgres`. **This only overlaps with real prod data when you run it directly on the production server itself** - prod (the full stack, including its DB) lives on a separate remote server, not on a developer's local machine, so a local checkout's `verdoc_postgres` volume is its own independent, empty volume with no prod data in it. The "don't run both at once" rule below only matters when both stacks are on the *same* host (e.g. you're doing this on the prod server) - two instances on one data dir corrupt the DB.
- `backend/dev.env` overrides `backend/.env` for the host backend (see Environment above): `DEBUG=True`, `DATABASE_URL` → `localhost:5432`, `EMAIL_URL=consolemail://` (dev mail prints to the backend console).
- Typical loop: `make dev-infra` → `make dev-migrate` → `make dev-backend` (host, :8000) + `make front-dev` (vite, :5173). No nginx locally.

## Conventions

- **Communicate with the user in Russian in this project.**
- **Never read `*.env` files** (they hold secrets) - use the matching `.env.dist` template instead, and never treat a commented-out line as active config.
- Keep code comments short and in English (self-documenting code); prefer a plain hyphen `-` over an em-dash in prose and comments. Exception: the `Makefile` descriptions are intentionally Russian.
- Some existing comments and docstrings are in Russian; match the surrounding language when editing such a file.
- Backend style is enforced by ruff (line-length 120, double quotes) - run `make format` (or let pre-commit run it) before committing.
- Work happens on `dev`; PRs target `main`.
- **After each action, end your reply with a one-line summary written as a Conventional-Commit message:** `type(scope): что сделал` in the imperative, matching this repo's history. Types: `feat`, `fix`, `refactor`, `style`, `docs`, `ci`, `test`, `chore`. Scopes: `order`, `passport`, `backend`, `frontend`, `mail`, `Makefile`, `deps`, etc. Example: `ci(Makefile): добавил dev-цели для локального запуска`. This is a recap of the work performed - **not** an instruction to create a git commit (only commit when the user explicitly asks).
