# Tarefas comuns. `make help` lista tudo. Nada aqui instala coisas globais:
# o Python fica em backend/.venv.
SHELL := /bin/bash
VENV  := backend/.venv
PY    := $(abspath $(VENV))/bin/python
BASE  ?= http://localhost:8000

.DEFAULT_GOAL := help
.PHONY: help venv db migrate backend worker seed test test-todo lint fmt up down logs doctor smoke stress

help: ## lista as tarefas
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

$(VENV)/.ok: backend/requirements.txt backend/requirements-dev.txt
	python3 -m venv $(VENV)
	@# AUTOBAHN_USE_NVX=0: o autobahn (dep. do daphne) não compila a extensão nativa no Python 3.15
	AUTOBAHN_USE_NVX=0 $(PY) -m pip install -q -r backend/requirements-dev.txt
	@touch $@

venv: $(VENV)/.ok ## cria backend/.venv e instala as dependências

db: ## sobe PostgreSQL e Redis (docker)
	docker compose up -d --wait db redis

migrate: venv ## aplica as migrações
	cd backend && $(PY) manage.py migrate

backend: venv ## servidor ASGI de desenvolvimento na porta 8000
	cd backend && $(PY) manage.py runserver 8000

worker: venv ## worker que abre e fecha leilões
	cd backend && $(PY) manage.py run_auction_worker

seed: venv ## dados de demonstração (RNF04)
	cd backend && $(PY) manage.py seed_demo

test: venv ## testes que DEVEM estar verdes
	cd backend && $(PY) -m pytest tests --ignore=tests/todo -q

test-todo: venv ## lista de trabalho: garantias RF10–RF18 ainda vermelhas
	cd backend && $(PY) -m pytest tests/todo -q --tb=line -p no:cacheprovider

lint: venv ## ruff (erros e formatação)
	cd backend && $(PY) -m ruff check . ../scripts && $(PY) -m ruff format --check . ../scripts

fmt: venv ## formata com ruff
	cd backend && $(PY) -m ruff check --fix . ../scripts && $(PY) -m ruff format . ../scripts

up: ## sobe tudo (igual à VM)
	docker compose up -d --build

down: ## para tudo (os volumes ficam)
	docker compose down

logs: ## logs de todos os serviços
	docker compose logs -f --tail=100

doctor: ## confere se o ambiente está ok (local ou VM)
	@BASE=$(BASE) bash scripts/doctor.sh

smoke: ## fluxo completo pela API: cadastro, leilão, lance, fechamento
	python3 scripts/smoke_test.py --base $(BASE)

stress: ## 50 lances paralelos no mesmo leilão + conferência das invariantes
	python3 scripts/stress_bids.py --base $(BASE)
