# Единые команды разработки/деплоя Verdoc.
#
# Два независимых сценария (один не переходит в другой автоматически):
#
#   1) Полный стек в docker (прод-подобный, с nginx):
#        make up        — поднять весь стек (backend + postgres + frontend-nginx)
#        make migrate   — миграции ВНУТРИ контейнера backend
#      manage.py / psql выполняются через `docker compose exec` в этом стеке.
#
#   2) Локальная разработка (backend/frontend на хосте, только postgres в docker —
#      см. docker-compose.dev.yaml; нужен из-за rootless-podman и портов 80/443):
#        make init          — с нуля: deps → .env → install → pre-commit →
#                              dev-postgres → миграции (НЕ поднимает `up`!)
#        make dev-backend   — runserver на хосте (:8000)
#        make front-dev     — vite dev-сервер (:5173)
#
# Оба сценария используют один и тот же volume verdoc_postgres (общие данные,
# осознанно), но это РАЗНЫЕ контейнеры postgres — не поднимайте оба одновременно.
#
# Кроссплатформенно (Linux / Windows): рецепты — это только `cd` + вызов бинарника
# (uv / uvx / docker compose / npm). Файловые операции делает Python через
# `uv run --no-project`, поэтому grep/sed/find не нужны.
#
#   make init   — локальная разработка с нуля (сценарий 2)
#   make up     — весь стек в docker (сценарий 1)
#   make help   — полный список целей

COMPOSE     ?= docker compose
COMPOSE_DEV ?= docker compose -f docker-compose.dev.yaml
UV          ?= uv
RUFF        ?= uvx ruff@0.15.12
PRECOMMIT   ?= uvx pre-commit

# Пути для ruff (со своим [tool.ruff] в backend/pyproject.toml).
RUFF_PATHS ?= backend

# Django manage.py внутри контейнера backend.
MANAGE ?= $(COMPOSE) exec backend uv run python manage.py

# Django manage.py ЛОКАЛЬНО (backend вне контейнера): backend/.env + оверрайды dev.env.
# Требует поднятую dev-инфраструктуру (make dev-infra) и заполненный dev.env.
MANAGE_DEV ?= cd backend && $(UV) run --env-file .env --env-file dev.env python manage.py

# Параметры БД для локальных команд: по умолчанию берём POSTGRES_USER/POSTGRES_DB
# из postgres/.env (единый источник истины), переопределяются: make db-dump PG_USER=…
# Читаем через Python (splitlines корректно срезает CRLF), лениво — только когда переменная нужна.
PG_USER ?= $(shell $(UV) run --no-project python -c "import pathlib; p=pathlib.Path('postgres/.env'); vals=[l.split('=',1)[1].strip() for l in (p.read_text(encoding='utf-8').splitlines() if p.exists() else []) if l.startswith('POSTGRES_USER=')]; print(vals[0] if vals else 'user')")
PG_DB   ?= $(shell $(UV) run --no-project python -c "import pathlib; p=pathlib.Path('postgres/.env'); vals=[l.split('=',1)[1].strip() for l in (p.read_text(encoding='utf-8').splitlines() if p.exists() else []) if l.startswith('POSTGRES_DB=')]; print(vals[0] if vals else 'database')")
DUMP    ?= backups/dump.sql
m       ?=
FORCE   ?=
FRONT   ?=

.DEFAULT_GOAL := help

.PHONY: help
help: ## Показать список целей
	@$(UV) run --no-project python -c "import re; [print(f'  {x[1]:<20} {x[2]}') for l in open('Makefile', encoding='utf-8') for x in [re.match(r'^([A-Za-z_-]+):.*?## (.*)', l)] if x]"

# --- Подготовка окружения ---------------------------------------------------

.PHONY: init
init: ## Подготовить окружение с нуля (deps → .env → install → pre-commit → dev-infra → dev-migrate)
	$(MAKE) check-deps
	$(MAKE) env
	$(MAKE) install
	$(MAKE) pre-commit-install
	$(MAKE) dev-infra
	$(MAKE) dev-migrate
	@echo "OK: dev-postgres поднят, миграции применены. Дальше: make dev-backend (backend :8000) и make front-dev (frontend :5173). Статус dev-postgres: docker compose -f docker-compose.dev.yaml ps"

.PHONY: check-deps
check-deps: ## Проверить наличие uv и docker compose
	$(UV) --version
	$(COMPOSE) version

.PHONY: env
env: ## Создать .env из *.dist там, где их нет (backend / frontend / postgres)
	@$(UV) run --no-project python -c "import os, shutil; [(shutil.copyfile(t+'.dist', t), print('created', t)) for t in ('backend/.env','frontend/.env','postgres/.env','backend/dev.env') if os.path.isfile(t+'.dist') and not os.path.isfile(t)]"
	@echo "Заполните .env файлы (backend / frontend / postgres) и dev.env для локальной разработки!"

# --- Установка зависимостей -------------------------------------------------

.PHONY: install
install: ## venv бэкенда (uv sync)
	cd backend && $(UV) sync

.PHONY: front-install
front-install: ## Зависимости фронтенда (npm install)
	cd frontend && npm install

# --- Docker -----------------------------------------------------------------

.PHONY: up
up: ## Поднять весь стек (backend + postgres + frontend-nginx)
	$(COMPOSE) up -d --build

.PHONY: down
down: ## Остановить стек
	$(COMPOSE) down

.PHONY: build
build: ## Пересобрать образы
	$(COMPOSE) build

.PHONY: ps
ps: ## Статус контейнеров
	$(COMPOSE) ps

.PHONY: logs
logs: ## Логи всего стека (follow)
	$(COMPOSE) logs -f

.PHONY: logs-backend
logs-backend: ## Логи бэкенда
	$(COMPOSE) logs -f backend

.PHONY: logs-db
logs-db: ## Логи postgres
	$(COMPOSE) logs -f postgres

.PHONY: logs-nginx
logs-nginx: ## Логи frontend-nginx
	$(COMPOSE) logs -f frontend-nginx

# --- Резервный SMTP-релей с DKIM (boky/postfix, профиль mail) ----------------
# Нужен ключ secrets/opendkim/photo-scan.store.private и EMAIL_URL=smtp://mail:587

.PHONY: mail-up
mail-up: ## Поднять резервный mail-релей (профиль mail)
	$(COMPOSE) --profile mail up -d mail

.PHONY: mail-down
mail-down: ## Остановить mail-релей
	$(COMPOSE) --profile mail stop mail

.PHONY: logs-mail
logs-mail: ## Логи mail-релея
	$(COMPOSE) --profile mail logs -f mail

# --- Локальная разработка (backend/frontend локально, postgres в docker) -----

.PHONY: dev-infra
dev-infra: ## Поднять dev-инфраструктуру (только postgres на localhost:5432)
	$(COMPOSE_DEV) up -d --build

.PHONY: dev-infra-down
dev-infra-down: ## Остановить dev-инфраструктуру
	$(COMPOSE_DEV) down

.PHONY: dev-reset
dev-reset: ## Пересоздать контейнер dev-postgres (volume verdoc_postgres НЕ трогает - общий с прод)
	@echo "Пересоздаю контейнер dev-postgres (down + up). Данные в volume verdoc_postgres НЕ удаляются - он общий с прод-стеком."
	$(COMPOSE_DEV) down
	$(COMPOSE_DEV) up -d --build
	@echo "OK: dev-postgres пересоздан. Для полного удаления данных (ОПАСНО - общие данные с прод!) вручную: docker compose -f docker-compose.dev.yaml down -v"

.PHONY: dev-migrate
dev-migrate: ## Миграции локальным backend в dev-БД
	$(MANAGE_DEV) migrate

.PHONY: dev-showmigrations
dev-showmigrations: ## Статус миграций локальным backend (dev-БД) - проверить перед migrate
	$(MANAGE_DEV) showmigrations

.PHONY: dev-backend
dev-backend: ## Запустить backend локально (runserver 0.0.0.0:8000)
	$(MANAGE_DEV) runserver 0.0.0.0:8000

.PHONY: dev-superuser
dev-superuser: ## Создать суперпользователя в dev-БД
	$(MANAGE_DEV) createsuperuser

.PHONY: dev-shell
dev-shell: ## Django shell локально (dev-БД)
	$(MANAGE_DEV) shell

# --- Django (внутри контейнера backend) -------------------------------------

.PHONY: migrate
migrate: ## Применить миграции
	$(MANAGE) migrate

.PHONY: showmigrations
showmigrations: ## Статус миграций в контейнере backend - проверить перед migrate
	$(MANAGE) showmigrations

.PHONY: makemigrations
makemigrations: ## Создать миграции: make makemigrations m="order passport"
	$(MANAGE) makemigrations $(m)

.PHONY: collectstatic
collectstatic: ## Собрать статику
	$(MANAGE) collectstatic --no-input

.PHONY: superuser
superuser: ## Создать суперпользователя
	$(MANAGE) createsuperuser

.PHONY: shell
shell: ## Django shell
	$(MANAGE) shell

# --- Доменные команды -------------------------------------------------------

.PHONY: update-rates
update-rates: ## Обновить курсы валют (djmoney)
	$(MANAGE) update_rates

.PHONY: expire
expire: ## Снять резерв с просроченных заказов
	$(MANAGE) expire_transactions

# --- База данных: дамп / импорт ---------------------------------------------

.PHONY: db-dump
db-dump: ## Дамп БД в файл (DUMP=backups/dump.sql по умолчанию)
	$(COMPOSE) exec -T postgres pg_dump -U $(PG_USER) -d $(PG_DB) > $(DUMP)
	@echo "dumped -> $(DUMP)"

.PHONY: db-restore
db-restore: ## Восстановить БД из файла (требует FORCE=1): make db-restore DUMP=backups/x.sql FORCE=1
ifneq ($(FORCE),1)
	@echo "ОПАСНО: db-restore перезапишет данные в живой БД дампом $(DUMP)."
	@echo "Если уверены - повторите с FORCE=1: make db-restore DUMP=$(DUMP) FORCE=1"
	@exit 1
else
	$(COMPOSE) exec -T postgres psql -U $(PG_USER) -d $(PG_DB) < $(DUMP)
	@echo "restored <- $(DUMP)"
endif

.PHONY: psql
psql: ## Интерактивный psql в контейнере
	$(COMPOSE) exec postgres psql -U $(PG_USER) -d $(PG_DB)

# --- Фронтенд ---------------------------------------------------------------

.PHONY: front-dev
front-dev: ## Vite dev-сервер (0.0.0.0:5173)
	cd frontend && npm run dev

.PHONY: front-build
front-build: ## Production-сборка фронтенда
	cd frontend && npm run build

# --- Качество кода ----------------------------------------------------------

.PHONY: pre-commit-install
pre-commit-install: ## Установить git-хуки pre-commit
	$(PRECOMMIT) install

.PHONY: pre-commit
pre-commit: ## Прогнать pre-commit по всем файлам
	$(PRECOMMIT) run --all-files

.PHONY: lint
lint: ## ruff check + проверка форматирования (без правок)
	$(RUFF) check $(RUFF_PATHS)
	$(RUFF) format --check $(RUFF_PATHS)

.PHONY: format
format: ## ruff format + автофиксы
	$(RUFF) check --fix $(RUFF_PATHS)
	$(RUFF) format $(RUFF_PATHS)

# --- Очистка ----------------------------------------------------------------

.PHONY: clean
clean: ## Удалить кэши (pycache, ruff); FRONT=1 - также frontend/node_modules и frontend/dist
	@$(UV) run --no-project python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for n in ('__pycache__','.ruff_cache') for p in pathlib.Path('.').rglob(n)]"
ifeq ($(FRONT),1)
	@$(UV) run --no-project python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('frontend/node_modules', 'frontend/dist')]"
	@echo "OK: node_modules и dist фронтенда удалены"
endif
	@echo "OK: кэши очищены"
