# ==============================================================================
# 🏔️ EOLE.ME — TRAIL MAPPER & GPX POI MERGER PIPELINES
# ==============================================================================
# Description : Local development management and automated VPS deployment.
# Version     : 1.0.0
# Author      : Julien (Éole) Avarre <hi@eole.me>
# License     : MIT
# ==============================================================================

# ⚙️ INFRASTRUCTURE VARIABLES (SECURED)
VPS_SSH              := eole.me
VPS_PROJECT_NAME     := $(shell git config --get remote.origin.url | sed 's/.*\///; s/\.git$$//')
VPS_PROJECT_TAG      := $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")
VPS_PATH             := /home/eole/projects/$(VPS_PROJECT_NAME)

PROJECT_NAME         := Trail Mapper
VERSION              := 1.0.0

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

.PHONY: help configure dev up down restart deploy _deploy deploy-delay checklogs

# ==============================================================================
# ℹ️ HELP MENU
# ==============================================================================
help:
	@echo "======================================================================"
	@echo "                   🏔️  $(PROJECT_NAME) Project Makefile 🏔️"
	@echo "======================================================================"
	@echo "Configuration & Setup:"
	@echo "  make configure        - Run system configuration and env setup"
	@echo ""
	@echo "💻 LOCAL DEVELOPMENT (DOCKER CONTAINER):"
	@echo "  make dev              - Start local dev Docker containers (Port 3040)"
	@echo "  make up               - Start local dev Docker containers"
	@echo "  make down             - Stop local dev Docker containers"
	@echo "  make restart          - Restart local dev Docker containers"
	@echo ""
	@echo "🚀 PRODUCTION DEPLOYMENT (VPS - $(PROJECT_NAME) on $(VPS_SSH)):"
	@echo "  make deploy           - Push production compose & pull/recreate containers"
	@echo "  make deploy-delay     - Wait 150s for GitHub Actions build and then deploy"
	@echo "  make checklogs        - Fetch real-time production logs from VPS"
	@echo "======================================================================"

configure:
	@echo "Configuring Trail Mapper..."

dev: up

up:
	@echo "✨ Starting local development environment..."
	@if [ ! -f .env ]; then \
		if $(DOPPLER) --version >/dev/null 2>&1; then \
			echo "🔑 Downloading development secrets from Doppler..."; \
			$(DOPPLER) secrets download --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_DEV) --no-file --format env > .env; \
		else \
			echo "⚠️ Doppler CLI not found. Copying .env.example fallback..."; \
			cp $(DOCKER_DIR)/.env.example .env 2>/dev/null || echo "No .env.example found, using empty env"; \
		fi \
	fi
	docker compose -f $(COMPOSE_DEV) --env-file .env up -d --build
	@echo "🚀 $(PROJECT_NAME) is ready locally on http://localhost:3040/trail-mapper/ !"

down:
	@echo "🛑 Stopping local development container..."
	@if [ -f .env ]; then \
		docker compose -f $(COMPOSE_DEV) --env-file .env down; \
	else \
		docker compose -f $(COMPOSE_DEV) down; \
	fi

restart: down up

# ==============================================================================
# 🚀 AUTOMATED DEPLOYMENT PIPELINE (VPS)
# ==============================================================================
deploy:
	@make --no-print-directory _deploy SERVICES="$(DOCKER_SERVICES)"

_deploy:
	@echo "🚀 Deploying $(PROJECT_NAME) stack [$(VERSION)/$(VPS_PROJECT_TAG)] to VPS '$(VPS_SSH)' on '$(VPS_PATH)'..."
	ssh $(VPS_SSH) "mkdir -p $(VPS_PATH)"
	scp $(COMPOSE_PROD) $(VPS_SSH):$(VPS_PATH)/docker-compose.prod.yml
	@if $(DOPPLER) --version >/dev/null 2>&1; then \
		echo "🔑 Sending Doppler production secrets to VPS..."; \
		if $(DOPPLER) secrets download --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG_PROD) --no-file --format env > .env.prod.temp; then \
			scp .env.prod.temp $(VPS_SSH):$(VPS_PATH)/.env; \
			rm -f .env.prod.temp; \
		else \
			echo "❌ Error: Doppler secrets download failed!"; \
			rm -f .env.prod.temp; \
			exit 1; \
		fi; \
	else \
		echo "❌ Error: Doppler CLI is not installed or not found in PATH!"; \
		exit 1; \
	fi
	@echo "📥 Pulling latest image from GHCR..."
	ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml pull"
	@echo "🔄 Recreating and starting containers (handling potential container name conflicts)..."
	@ssh $(VPS_SSH) "docker rm -f eole-me-trail-mapper-prod-container 2>/dev/null || true"
	ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml up -d --remove-orphans"
	@echo "✅ Deployment of $(PROJECT_NAME) [$(VERSION) / $(VPS_PROJECT_TAG)] successfully completed on production server!"

checklogs:
	@echo "📟 Fetching real-time production logs from VPS [$(VPS_SSH)]..."
	ssh $(VPS_SSH) "cd $(VPS_PATH) && docker compose -f docker-compose.prod.yml logs -f"

deploy-delay:
	@echo "⏳ Waiting 150 seconds for GitHub Actions build to complete..."
	git push && sleep 150 && make --no-print-directory deploy
