# Единые команды разработки/деплоя Verdoc.
#
# Проект docker-first: Django-бэкенд и БД живут в контейнерах, поэтому команды
# manage.py / psql выполняются через `docker compose exec` в работающем стеке
# (сначала `make up`). Локально через uv ставятся только зависимости бэкенда и
# запускаются линтеры.
#
# Кроссплатформенно (Linux / Windows): рецепты — это только `cd` + вызов бинарника
# (uv / uvx / docker compose / npm). Файловые операции делает Python через
# `uv run --no-project`, поэтому grep/sed/find не нужны.
#
#   make init   — подготовить окружение с нуля
#   make up     — весь стек в docker
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

# Параметры БД для локальных команд (переопределяются: make db-dump PG_USER=…).
PG_USER ?= user
PG_DB   ?= database
DUMP    ?= backups/dump.sql
m       ?=

.DEFAULT_GOAL := help

.PHONY: help
help: ## Показать список целей
	@$(UV) run --no-project python -c "import re; [print(f'  {x[1]:<20} {x[2]}') for l in open('Makefile', encoding='utf-8') for x in [re.match(r'^([A-Za-z_-]+):.*?## (.*)', l)] if x]"

# --- Подготовка окружения ---------------------------------------------------

.PHONY: init
init: ## Подготовить окружение с нуля (deps → .env → install → pre-commit → up → migrate)
	$(MAKE) check-deps
	$(MAKE) env
	$(MAKE) install
	$(MAKE) pre-commit-install
	$(MAKE) up
	$(MAKE) migrate
	@echo "OK: окружение готово. Стек поднят: make ps"

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

# --- Локальная разработка (backend/frontend локально, postgres в docker) -----

.PHONY: dev-infra
dev-infra: ## Поднять dev-инфраструктуру (только postgres на localhost:5432)
	$(COMPOSE_DEV) up -d --build

.PHONY: dev-infra-down
dev-infra-down: ## Остановить dev-инфраструктуру
	$(COMPOSE_DEV) down

.PHONY: dev-migrate
dev-migrate: ## Миграции локальным backend в dev-БД
	$(MANAGE_DEV) migrate

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
db-restore: ## Восстановить БД из файла: make db-restore DUMP=backups/x.sql
	$(COMPOSE) exec -T postgres psql -U $(PG_USER) -d $(PG_DB) < $(DUMP)
	@echo "restored <- $(DUMP)"

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
clean: ## Удалить кэши (pycache, ruff)
	@$(UV) run --no-project python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for n in ('__pycache__','.ruff_cache') for p in pathlib.Path('.').rglob(n)]"
	@echo "OK: кэши очищены"
