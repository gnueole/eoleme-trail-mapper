# ──────────────────────────────────────────────────────────────────────────────
# 🏔️ EOLE.ME — TRAIL MAPPER & GPX POI MERGER PIPELINES
# ──────────────────────────────────────────────────────────────────────────────
# Description : Local development management and automated VPS deployment.
# Version     : 1.0.0
# Author      : Julien (Éole) Avarre <hi@eole.me>
# License     : MIT
# ──────────────────────────────────────────────────────────────────────────────

# Environment variables from .env are loaded by Docker Compose or other subprocesses directly.
# We do not use GNU Make's "include .env" here because it fails when values contain colons (e.g. JSON strings).

# 🎨 COLOR CODES (ANSI ESCAPE SEQUENCES)
COLOR_RESET   := \033[0m
COLOR_BOLD    := \033[1m
COLOR_CYAN    := \033[1;36m
COLOR_GREEN   := \033[1;32m
COLOR_YELLOW  := \033[1;33m
COLOR_RED     := \033[1;31m
COLOR_MAGENTA := \033[1;35m

# ⚙️ INFRASTRUCTURE VARIABLES (SECURED)
VPS_SSH              ?= eole.me
VPS_PROJECT_NAME     := $(shell git config --get remote.origin.url | sed 's/.*\///; s/\.git$$//')
VPS_PROJECT_TAG      := $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")
VPS_PATH             ?= ~/projects/$(VPS_PROJECT_NAME)

PROJECT_NAME         := Trail Mapper
VERSION              := $(shell grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+" public/js/version.js 2>/dev/null || echo "1.0.0")

# 🔑 SECRETS MANAGEMENT (DOPPLER)
DOPPLER_PROJECT     := eole-me
DOPPLER_CONFIG_DEV  := dev
DOPPLER_CONFIG_PROD := prd

# Find doppler binary (robust check for WSL non-interactive paths)
DOPPLER := $(shell which doppler 2>/dev/null || ( [ -f $(HOME)/bin/doppler ] && echo $(HOME)/bin/doppler ) || echo doppler)

# 🛠️ LOCAL DOCKER CONFIGURATION
DOCKER_DIR   := docker
COMPOSE_DEV  := $(DOCKER_DIR)/docker-compose.yml
COMPOSE_PROD := $(DOCKER_DIR)/docker-compose.prod.yml
DOCKER_SERVICES := trail-mapper

.PHONY: help configure dev up down restart test setup-test test-local deploy _deploy deploy-delay checklogs check-build check-build-full

# ──────────────────────────────────────────────────────────────────────────────
# ℹ️ HELP MENU
# ──────────────────────────────────────────────────────────────────────────────
help:
	@printf "$(COLOR_CYAN)┌──────────────────────────────────────────────────────────────────────┐$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)                 🏔️  $(COLOR_BOLD)$(PROJECT_NAME)$(COLOR_RESET) Project Makefile 🏔️                 $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)├──────────────────────────────────────────────────────────────────────┤$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET) $(COLOR_YELLOW)Configuration & Setup:$(COLOR_RESET)                                               $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make configure       - Run system configuration and env setup      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)                                                                      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET) 💻 $(COLOR_YELLOW)Local Development (Docker Container):$(COLOR_RESET)                             $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make dev             - Start local dev containers (Port 3040)      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make up              - Start local dev Docker containers.          $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make down            - Stop local dev Docker containers.           $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make restart         - Restart local dev Docker containers.        $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)                                                                      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET) 🧪 $(COLOR_YELLOW)Testing & Verification:$(COLOR_RESET)                                           $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make test            - Run test suite inside Docker container      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make setup-test      - Create local python venv for testing        $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make test-local      - Run test suite locally using virtual env    $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)                                                                      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET) 🚀 $(COLOR_YELLOW)Production Deployment (VPS):$(COLOR_RESET)                                      $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make deploy          - Push production compose & pull/recreate     $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make deploy-delay    - Wait 150s for GHA build and deploy          $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make checklogs       - Fetch real-time production logs from VPS.   $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make check-build     - Query GHA build status (quiet on success)   $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET)   make check-build-full- Display verbose details of latest GHA run   $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)└──────────────────────────────────────────────────────────────────────┘$(COLOR_RESET)\n"

configure:
	@printf "$(COLOR_CYAN)┌──────────────────────────────────────────────────────────────────────┐$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)│$(COLOR_RESET) ⚙️  $(COLOR_BOLD)Configuring Trail Mapper Development Environment$(COLOR_RESET)                 $(COLOR_CYAN)│$(COLOR_RESET)\n"
	@printf "$(COLOR_CYAN)└──────────────────────────────────────────────────────────────────────┘$(COLOR_RESET)\n"
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		printf "$(COLOR_GREEN)✅ Doppler CLI is installed.$(COLOR_RESET)\n"; \
		printf "$(COLOR_YELLOW)👉 Log in to Doppler:$(COLOR_RESET)\n"; \
		$(DOPPLER) login; \
		printf "$(COLOR_YELLOW)👉 Setup project '$(DOPPLER_PROJECT)' for the local directory:$(COLOR_RESET)\n"; \
		$(DOPPLER) setup --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_DEV); \
	else \
		printf "$(COLOR_RED)❌ Doppler CLI is not installed.$(COLOR_RESET)\n"; \
		printf "$(COLOR_YELLOW)💡 Doppler is used to securely sync development & production secrets.$(COLOR_RESET)\n"; \
		printf "👉 Install it via: https://docs.doppler.com/docs/install-cli\n"; \
	fi
	@printf "$(COLOR_CYAN)──────────────────────────────────────────────────────────────────────$(COLOR_RESET)\n"

dev: up

up:
	@printf "$(COLOR_CYAN)✨ Starting local development environment...$(COLOR_RESET)\n"
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		printf "$(COLOR_CYAN)🔑 Syncing fresh development secrets from Doppler...$(COLOR_RESET)\n"; \
		if $(DOPPLER) secrets download --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_DEV) --no-file --format env > .env.temp 2>/dev/null; then \
			sed 's/="true"/=true/g; s/="false"/=false/g; s/^DOCKER_NETWORK_NAME="\(.*\)"/DOCKER_NETWORK_NAME=\1/g' .env.temp > .env; \
			rm -f .env.temp; \
			printf "$(COLOR_GREEN)✅ Secrets successfully synced!$(COLOR_RESET)\n"; \
		else \
			printf "$(COLOR_YELLOW)⚠️ Doppler secrets sync failed. Falling back to existing .env.$(COLOR_RESET)\n"; \
			rm -f .env.temp; \
			if [ ! -f .env ]; then \
				printf "$(COLOR_RED)⚠️ No local .env found. Copying .env.example fallback...$(COLOR_RESET)\n"; \
				cp $(DOCKER_DIR)/.env.example .env 2>/dev/null || printf "No .env.example found, using empty env\n"; \
			fi; \
			printf "$(COLOR_YELLOW)💡 Tip: Run 'make configure' to set up your Doppler credentials.$(COLOR_RESET)\n"; \
		fi; \
	else \
		if [ ! -f .env ]; then \
			printf "$(COLOR_YELLOW)⚠️ Doppler CLI not found. Copying .env.example fallback...$(COLOR_RESET)\n"; \
			cp $(DOCKER_DIR)/.env.example .env 2>/dev/null || printf "No .env.example found, using empty env\n"; \
		else \
			printf "$(COLOR_GREEN)ℹ️ Using existing local .env file.$(COLOR_RESET)\n"; \
		fi; \
		printf "$(COLOR_YELLOW)💡 Tip: Install Doppler CLI (https://doppler.com) to automatically keep development secrets in sync.$(COLOR_RESET)\n"; \
	fi
	@if [ -f .env ]; then \
		NETWORK_NAME=$$(grep '^DOCKER_NETWORK_NAME=' .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo ""); \
		if [ -n "$$NETWORK_NAME" ]; then \
			if docker network inspect $$NETWORK_NAME >/dev/null 2>&1; then \
				printf "$(COLOR_GREEN)🔌 Existing shared network '$$NETWORK_NAME' detected. Joining integrated eole.me stack...$(COLOR_RESET)\n"; \
				DOCKER_NETWORK_EXTERNAL=true docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build; \
			else \
				printf "$(COLOR_YELLOW)ℹ️ Shared network '$$NETWORK_NAME' not found. Running in FULL STANDALONE mode...$(COLOR_RESET)\n"; \
				DOCKER_NETWORK_EXTERNAL=false docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build; \
			fi; \
		else \
			docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build; \
		fi; \
	else \
		docker compose -f $(COMPOSE_DEV) up -d --build; \
	fi
	@printf "$(COLOR_GREEN)🚀 $(PROJECT_NAME) is ready locally on http://localhost:3040/trail-mapper/ !$(COLOR_RESET)\n"

down:
	@printf "$(COLOR_YELLOW)🛑 Stopping local development container...$(COLOR_RESET)\n"
	@if [ -f .env ]; then \
		NETWORK_NAME=$$(grep '^DOCKER_NETWORK_NAME=' .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo ""); \
		if [ -n "$$NETWORK_NAME" ]; then \
			if docker network inspect $$NETWORK_NAME >/dev/null 2>&1; then \
				DOCKER_NETWORK_EXTERNAL=true docker compose -f $(COMPOSE_DEV) --env-file .env down; \
			else \
				DOCKER_NETWORK_EXTERNAL=false docker compose -f $(COMPOSE_DEV) --env-file .env down; \
			fi; \
		else \
			docker compose -f $(COMPOSE_DEV) --env-file .env down; \
		fi; \
	else \
		docker compose -f $(COMPOSE_DEV) down; \
	fi

restart: down up

# ──────────────────────────────────────────────────────────────────────────────
# 🚀 AUTOMATED DEPLOYMENT PIPELINE (VPS)
# ──────────────────────────────────────────────────────────────────────────────
deploy:
	@make --no-print-directory _deploy SERVICES="$(DOCKER_SERVICES)"

_deploy:
	@printf "$(COLOR_CYAN)🚀 [1/4]$(COLOR_RESET) Preparing deployment space on VPS $(COLOR_BOLD)$(VPS_SSH)$(COLOR_RESET)...\n"
	@ssh $(VPS_SSH) "mkdir -p $(VPS_PATH)" >/dev/null
	@printf "$(COLOR_CYAN)📦 [2/4]$(COLOR_RESET) Uploading static assets and configuration files...\n"
	@scp $(COMPOSE_PROD) $(VPS_SSH):$(VPS_PATH)/docker-compose.prod.yml >/dev/null
	@printf "$(COLOR_CYAN)🔑 [3/4]$(COLOR_RESET) Streaming production secrets from Doppler...$(COLOR_RESET)\n"
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		if $(DOPPLER) secrets download --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_PROD) --no-file --format env > .env.prod.temp 2>/dev/null; then \
			sed 's/="true"/=true/g; s/="false"/=false/g; s/^DOCKER_NETWORK_NAME="\(.*\)"/DOCKER_NETWORK_NAME=\1/g' .env.prod.temp > .env.prod.clean; \
			scp .env.prod.clean $(VPS_SSH):$(VPS_PATH)/.env >/dev/null; \
			rm -f .env.prod.temp .env.prod.clean; \
		else \
			printf "$(COLOR_RED)❌ Error: Doppler secrets download failed!$(COLOR_RESET)\n"; \
			rm -f .env.prod.temp; \
			exit 1; \
		fi; \
	else \
		printf "$(COLOR_RED)❌ Error: Doppler CLI is not installed or not found in PATH!$(COLOR_RESET)\n"; \
		exit 1; \
	fi
	@printf "$(COLOR_CYAN)🐳 [4/4]$(COLOR_RESET) Recreating and starting production containers...$(COLOR_RESET)\n"
	@ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml pull" >/dev/null
	@ssh $(VPS_SSH) "docker rm -f eole-me-trail-mapper-prod-container 2>/dev/null || true" >/dev/null
	@ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml up -d --remove-orphans" >/dev/null
	@printf "$(COLOR_GREEN)✅ Deployment of $(PROJECT_NAME) [$(VERSION) / $(VPS_PROJECT_TAG)] successfully completed on production server!$(COLOR_RESET)\n"

checklogs:
	@printf "$(COLOR_CYAN)📟 Fetching real-time production logs from VPS [$(VPS_SSH)]...$(COLOR_RESET)\n"
	@ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml logs -f"

check-build:
	@python3 toolkit/check_build.py

check-build-full:
	@python3 toolkit/check_build.py --full

deploy-delay:
	@printf "$(COLOR_YELLOW)⏳ Waiting 150 seconds for GitHub Actions build to complete...$(COLOR_RESET)\n"
	git push && sleep 150 && make --no-print-directory deploy

test:
	@printf "$(COLOR_CYAN)🧪 Running unit tests inside the development container...$(COLOR_RESET)\n"
	@if [ -f .env ]; then \
		NETWORK_NAME=$$(grep '^DOCKER_NETWORK_NAME=' .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo ""); \
		if [ -n "$$NETWORK_NAME" ]; then \
			if docker network inspect $$NETWORK_NAME >/dev/null 2>&1; then \
				DOCKER_NETWORK_EXTERNAL=true docker compose -f $(COMPOSE_DEV) --env-file .env run --rm trail-mapper python -m pytest; \
			else \
				DOCKER_NETWORK_EXTERNAL=false docker compose -f $(COMPOSE_DEV) --env-file .env run --rm trail-mapper python -m pytest; \
			fi; \
		else \
			docker compose -f $(COMPOSE_DEV) --env-file .env run --rm trail-mapper python -m pytest; \
		fi; \
	else \
		docker compose -f $(COMPOSE_DEV) run --rm trail-mapper python -m pytest; \
	fi

setup-test:
	@printf "$(COLOR_CYAN)📦 Setting up local Python virtual environment for testing...$(COLOR_RESET)\n"
	python -m venv .venv
	@if [ -f .venv/bin/activate ]; then \
		.venv/bin/pip install -r requirements.txt; \
	else \
		.venv/Scripts/pip install -r requirements.txt; \
	fi
	@printf "$(COLOR_GREEN)✅ Test environment set up successfully!$(COLOR_RESET)\n"
	@printf "👉 Run tests with: $(COLOR_YELLOW)make test-local$(COLOR_RESET)\n"

test-local:
	@if [ -d .venv ]; then \
		if [ -f .venv/bin/python ]; then \
			.venv/bin/python -m pytest -v; \
		else \
			.venv/Scripts/python -m pytest -v; \
		fi; \
	else \
		python -m pytest -v; \
	fi
