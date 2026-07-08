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

RESET         := $(COLOR_RESET)
BOLD          := $(COLOR_BOLD)

# Semantic Typology mappings (Meta-colorization)
STYLE_TITLE       ?= $(COLOR_CYAN)
STYLE_SECTION     ?= $(COLOR_MAGENTA)
STYLE_PHASE       ?= $(COLOR_CYAN)
STYLE_DISCREET    ?= $(COLOR_RESET)
STYLE_INSTRUCTION ?= $(COLOR_GREEN)
STYLE_RESULT      ?= $(COLOR_GREEN)
STYLE_WARNING     ?= $(COLOR_YELLOW)
STYLE_ERROR       ?= $(COLOR_RED)


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
	@printf "  $(STYLE_TITLE)┌───────────────────────────────────────────────────────────┐$(RESET)\n"
	@printf "  $(STYLE_TITLE)│$(RESET)     🏔️  $(BOLD)$(STYLE_TITLE)TRAIL$(RESET) $(STYLE_SECTION)🏔️ - TRAIL MAPPER stack COMMANDS$(RESET)           $(STYLE_TITLE)│$(RESET)\n"
	@printf "  $(STYLE_TITLE)└───────────────────────────────────────────────────────────┘$(RESET)\n"
	@printf "\n"
	@printf "  $(BOLD)$(STYLE_SECTION)❯ Configuration & Setup:$(RESET)\n"
	@printf "    $(STYLE_INSTRUCTION)make configure$(RESET)            $(STYLE_DISCREET)•$(RESET) Run system configuration and env setup\n"
	@printf "\n"
	@printf "  $(BOLD)$(STYLE_SECTION)❯ Local Development (Docker Container):$(RESET)\n"
	@printf "    $(STYLE_INSTRUCTION)make dev$(RESET)                  $(STYLE_DISCREET)•$(RESET) Start local dev containers (Port 3040)\n"
	@printf "    $(STYLE_INSTRUCTION)make up$(RESET)                   $(STYLE_DISCREET)•$(RESET) Start local dev Docker containers\n"
	@printf "    $(STYLE_INSTRUCTION)make down$(RESET)                 $(STYLE_DISCREET)•$(RESET) Stop local dev Docker containers\n"
	@printf "    $(STYLE_INSTRUCTION)make restart$(RESET)              $(STYLE_DISCREET)•$(RESET) Restart local dev Docker containers\n"
	@printf "\n"
	@printf "  $(BOLD)$(STYLE_SECTION)❯ Testing & Verification:$(RESET)\n"
	@printf "    $(STYLE_INSTRUCTION)make test$(RESET)                 $(STYLE_DISCREET)•$(RESET) Run test suite inside Docker container\n"
	@printf "    $(STYLE_INSTRUCTION)make setup-test$(RESET)           $(STYLE_DISCREET)•$(RESET) Create local Python venv for testing\n"
	@printf "    $(STYLE_INSTRUCTION)make test-local$(RESET)           $(STYLE_DISCREET)•$(RESET) Run test suite locally using virtual env\n"
	@printf "\n"
	@printf "  $(BOLD)$(STYLE_SECTION)❯ Production Deployment (VPS):$(RESET)\n"
	@printf "    $(STYLE_INSTRUCTION)make deploy$(RESET)               $(STYLE_DISCREET)•$(RESET) Push production compose & pull/recreate\n"
	@printf "    $(STYLE_INSTRUCTION)make deploy-delay$(RESET)         $(STYLE_DISCREET)•$(RESET) Wait 150s for GHA build and deploy\n"
	@printf "    $(STYLE_INSTRUCTION)make checklogs$(RESET)            $(STYLE_DISCREET)•$(RESET) Fetch real-time production logs from VPS\n"
	@printf "    $(STYLE_INSTRUCTION)make check-build$(RESET)          $(STYLE_DISCREET)•$(RESET) Query GHA build status (quiet on success)\n"
	@printf "    $(STYLE_INSTRUCTION)make check-build-full$(RESET)     $(STYLE_DISCREET)•$(RESET) Display verbose details of latest GHA run\n"
	@printf "  $(STYLE_DISCREET)────────────────────────────────────────────────────────────$(RESET)\n"

configure:
	@printf "$(STYLE_TITLE)┌──────────────────────────────────────────────────────────────────────┐$(RESET)\n"
	@printf "$(STYLE_TITLE)│$(RESET) ⚙️  $(BOLD)Configuring Trail Mapper Development Environment$(RESET)                 $(STYLE_TITLE)│$(RESET)\n"
	@printf "$(STYLE_TITLE)└──────────────────────────────────────────────────────────────────────┘$(RESET)\n"
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		printf "$(STYLE_RESULT)✅ Doppler CLI is installed.$(RESET)\n"; \
		printf "$(STYLE_WARNING)👉 Log in to Doppler:$(RESET)\n"; \
		$(DOPPLER) login; \
		printf "$(STYLE_WARNING)👉 Setup project '$(DOPPLER_PROJECT)' for the local directory:$(RESET)\n"; \
		$(DOPPLER) setup --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_DEV); \
	else \
		printf "$(STYLE_ERROR)❌ Doppler CLI is not installed.$(RESET)\n"; \
		printf "$(STYLE_WARNING)💡 Doppler is used to securely sync development & production secrets.$(RESET)\n"; \
		printf "👉 Install it via: https://docs.doppler.com/docs/install-cli\n"; \
	fi
	@printf "$(STYLE_TITLE)──────────────────────────────────────────────────────────────────────$(RESET)\n"

dev: up

up:
	@printf "$(STYLE_TITLE)✨ Starting local development environment...$(RESET)\n"
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		printf "$(STYLE_PHASE)🔑 Syncing fresh development secrets from Doppler...$(RESET)\n"; \
		if $(DOPPLER) secrets download --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_DEV) --no-file --format env > .env.temp 2>/dev/null; then \
			sed 's/="true"/=true/g; s/="false"/=false/g; s/^DOCKER_NETWORK_NAME="\(.*\)"/DOCKER_NETWORK_NAME=\1/g' .env.temp > .env; \
			rm -f .env.temp; \
			printf "$(STYLE_RESULT)✅ Secrets successfully synced!$(RESET)\n"; \
		else \
			printf "$(STYLE_WARNING)⚠️ Doppler secrets sync failed. Falling back to existing .env.$(RESET)\n"; \
			rm -f .env.temp; \
			if [ ! -f .env ]; then \
				printf "$(STYLE_ERROR)⚠️ No local .env found. Copying .env.example fallback...$(RESET)\n"; \
				cp $(DOCKER_DIR)/.env.example .env 2>/dev/null || printf "No .env.example found, using empty env\n"; \
			fi; \
			printf "$(STYLE_WARNING)💡 Tip: Run 'make configure' to set up your Doppler credentials.$(RESET)\n"; \
		fi; \
	else \
		if [ ! -f .env ]; then \
			printf "$(STYLE_WARNING)⚠️ Doppler CLI not found. Copying .env.example fallback...$(RESET)\n"; \
			cp $(DOCKER_DIR)/.env.example .env 2>/dev/null || printf "No .env.example found, using empty env\n"; \
		else \
			printf "$(STYLE_RESULT)ℹ️ Using existing local .env file.$(RESET)\n"; \
		fi; \
			printf "$(STYLE_WARNING)💡 Tip: Install Doppler CLI (https://doppler.com) to automatically keep development secrets in sync.$(RESET)\n"; \
	fi
	@if [ -f .env ]; then \
		NETWORK_NAME=$$(grep '^DOCKER_NETWORK_NAME=' .env | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo ""); \
		if [ -n "$$NETWORK_NAME" ]; then \
			if docker network inspect $$NETWORK_NAME >/dev/null 2>&1; then \
				printf "$(STYLE_RESULT)🔌 Existing shared network '$$NETWORK_NAME' detected. Joining integrated eole.me stack...$(RESET)\n"; \
				DOCKER_NETWORK_EXTERNAL=true docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build; \
			else \
				printf "$(STYLE_WARNING)ℹ️ Shared network '$$NETWORK_NAME' not found. Running in FULL STANDALONE mode...$(RESET)\n"; \
				DOCKER_NETWORK_EXTERNAL=false docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build; \
			fi; \
		else \
			docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build; \
		fi; \
	else \
		docker compose -f $(COMPOSE_DEV) up -d --build; \
	fi
	@printf "$(STYLE_RESULT)🚀 $(PROJECT_NAME) is ready locally on http://localhost:3040/trail-mapper/ !$(RESET)\n"

down:
	@printf "$(STYLE_WARNING)🛑 Stopping local development container...$(RESET)\n"
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
	@printf "$(STYLE_RESULT)🚀 [1/4]$(RESET) Preparing deployment space on VPS $(BOLD)$(VPS_SSH)$(RESET)...\n"
	@ssh $(VPS_SSH) "mkdir -p $(VPS_PATH)" >/dev/null
	@printf "$(STYLE_PHASE)📦 [2/4]$(RESET) Uploading static assets and configuration files...\n"
	@scp $(COMPOSE_PROD) $(VPS_SSH):$(VPS_PATH)/docker-compose.prod.yml >/dev/null
	@printf "$(STYLE_PHASE)🔑 [3/4]$(RESET) Streaming production secrets from Doppler...$(RESET)\n"
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		if $(DOPPLER) secrets download --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_PROD) --no-file --format env > .env.prod.temp 2>/dev/null; then \
			sed 's/="true"/=true/g; s/="false"/=false/g; s/^DOCKER_NETWORK_NAME="\(.*\)"/DOCKER_NETWORK_NAME=\1/g' .env.prod.temp > .env.prod.clean; \
			scp .env.prod.clean $(VPS_SSH):$(VPS_PATH)/.env >/dev/null; \
			rm -f .env.prod.temp .env.prod.clean; \
		else \
			printf "$(STYLE_ERROR)❌ Error: Doppler secrets download failed!$(RESET)\n"; \
			rm -f .env.prod.temp; \
			exit 1; \
		fi; \
	else \
		printf "$(STYLE_ERROR)❌ Error: Doppler CLI is not installed or not found in PATH!$(RESET)\n"; \
		exit 1; \
	fi
	@printf "$(STYLE_PHASE)🐳 [4/4]$(RESET) Recreating and starting production containers...$(RESET)\n"
	@ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml pull" >/dev/null
	@ssh $(VPS_SSH) "docker rm -f eole-me-trail-mapper-prod-container 2>/dev/null || true" >/dev/null
	@ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml up -d --remove-orphans" >/dev/null
	@printf "$(STYLE_RESULT)✅ Deployment of $(PROJECT_NAME) [$(VERSION) / $(VPS_PROJECT_TAG)] successfully completed on production server!$(RESET)\n"

checklogs:
	@printf "$(STYLE_PHASE)📟 Fetching real-time production logs from VPS [$(VPS_SSH)]...$(RESET)\n"
	@ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml logs -f"

check-build:
	@python3 toolkit/check_build.py

check-build-full:
	@python3 toolkit/check_build.py --full

deploy-delay:
	@printf "$(STYLE_WARNING)⏳ Waiting 150 seconds for GitHub Actions build to complete...$(RESET)\n"
	git push && sleep 150 && make --no-print-directory deploy

test:
	@printf "$(STYLE_PHASE)🧪 Running unit tests inside the development container...$(RESET)\n"
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
	@printf "$(STYLE_PHASE)📦 Setting up local Python virtual environment for testing...$(RESET)\n"
	python -m venv .venv
	@if [ -f .venv/bin/activate ]; then \
		.venv/bin/pip install -r requirements.txt; \
	else \
		.venv/Scripts/pip install -r requirements.txt; \
	fi
	@printf "$(STYLE_RESULT)✅ Test environment set up successfully!$(RESET)\n"
	@printf "👉 Run tests with: $(STYLE_WARNING)make test-local$(RESET)\n"

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
