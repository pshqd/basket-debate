# Makefile
.PHONY: dev frontend db-init

# Запуск бэкенда
dev:
	uv run python -m flask --app src/backend/app.py run --debug --port 5000


prepare-db:
	uv run python -m src.scripts.prepare_db
	uv run python -m src.scripts.build_embeddings

prepare-db-no-mocks:
	uv run python -m src.scripts.prepare_db --no-mocks
	uv run python -m src.scripts.build_embeddings

# Embeddings
build-embeddings:
	uv run python -m src.scripts.build_embeddings

rebuild-embeddings:
	uv run python -m src.scripts.build_embeddings --rebuild

# Mock товары
add-mocks:
	uv run python -m src.scripts.prepare_db --step mocks
	uv run python -m src.scripts.build_embeddings --mocks-only

test-search:
	uv run python -m src.agents.compatibility.product_searcher

test-cmp:
	uv run python -m src.agents.compatibility.agent

test:
	uv run pytest -v