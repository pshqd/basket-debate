# Makefile
.PHONY: dev frontend db-init

# Запуск бэкенда
dev:
	uv run flask run --reload

# Запуск фронтенда
frontend:
	cd src/frontend && npm run dev

# Запуск обоих одновременно (требует tmux или screen)
all:
	make dev & make frontend

# Инициализация БД
db-init:
	uv run python src/process_dataset.py
