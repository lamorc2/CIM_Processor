.PHONY: install dev backend frontend fixtures smoke build

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

fixtures:
	bash scripts/make_fixtures.sh

backend:
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload

frontend:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173

dev:
	@echo "Run 'make backend' and 'make frontend' in two terminals (or use scripts/dev.sh)"
	bash scripts/dev.sh

build:
	cd frontend && npm run build

smoke:
	bash scripts/smoke_test.sh
