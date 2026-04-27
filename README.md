# 🛒 Basket Debate

> **AI-система для умного формирования продуктовой корзины** на основе мульти-агентной архитектуры и LLM function calling.

**Basket Debate** принимает запрос на естественном языке («ужин на двоих за 1500 рублей без мяса») и формирует оптимальную продуктовую корзину с учётом бюджета, dietary-ограничений, количества людей и времени приготовления.

Внутри система строится на последовательном пайплайне агентов: LLM-парсер извлекает структурированные параметры из текста, `CompatibilityAgent` подбирает товары по совместимости и сценарию блюда, `BudgetAgent` оптимизирует корзину под бюджет через embedding-поиск дешёвых аналогов.

***

## Архитектура

```
User query (NL)
      │
      ▼
┌─────────────────────────────────────────┐
│  LLM Parser  (src/nlp/llm_parser.py)    │
│  openai SDK v2 + LM Studio              │
│  function calling → структурированный JSON
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────┐
│               AgentPipeline                      │
│          (src/backend/agent_pipeline.py)         │
│                                                  │
│  1. CompatibilityAgent                           │
│     ├── ScenarioMatcher   шаблоны блюд           │
│     ├── ProductSearcher   поиск в БД + embeddings│
│     └── Scorer            оценка корзины         │
│                                                  │
│  2. BudgetAgent                                  │
│     └── cosine_similarity (sklearn)              │
│         поиск дешёвых аналогов                   │
│                                                  │
│  3. ProfileAgent          ⏳ в разработке        │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
         ┌──────────────────────┐
         │    Flask Backend     │
         │  create_app(), :5000 │
         │  CORS: localhost:5173│
         └──────────────────────┘
                   │
                   ▼
            Web Interface
      (src/static + src/templates)
```

***

## Стек технологий

| Слой | Технологии |
|------|-----------|
| **NLP / LLM** | `openai` ≥ 2.16 · LM Studio · `gemma-2-9b-it-russian-function-calling` |
| **Embeddings** | `sentence-transformers` ≥ 5.2 · `intfloat/multilingual-e5-large` |
| **ML / DL** | `torch` ≥ 2.9 · `torchvision` ≥ 0.24 · `torchaudio` ≥ 2.9 · `torch-geometric` ≥ 2.7 · `scikit-learn` ≥ 1.8 · `numpy` ≥ 2.4 · `pandas` ≥ 2.3 |
| **RL / Agents** | `stable-baselines3` ≥ 2.7 · `sb3-contrib` ≥ 2.7 · `pettingzoo` ≥ 1.25 · `gymnasium` ≥ 1.2 |
| **Backend** | `flask` ≥ 3.1 · `flask-cors` ≥ 6.0 · `celery` ≥ 5.6 · `redis` ≥ 7.1 |
| **База данных** | SQLite (`data/processed/products.db`) · `sqlite3` (stdlib) |
| **Data** | `dvc` ≥ 3.66 · `dvc-s3` ≥ 3.3 · `kaggle` ≥ 1.8 |
| **Infra / Dev** | `pytest` ≥ 9.0 · `python-dotenv` ≥ 1.2 · `tensorboard` ≥ 2.20 · `tqdm` ≥ 4.67 · `uv` |

***

## Структура репозитория

```
basket-debate/
├── main.py                       # Точка входа: create_app() → Flask
├── pyproject.toml                # Зависимости (uv)
├── Makefile                      # Команды разработки
├── dvc.lock                      # DVC pipeline lock
│
├── src/
│   ├── agents/
│   │   ├── budget/
│   │   │   └── agent.py          # BudgetAgent: оптимизация корзины под бюджет
│   │   ├── compatibility/
│   │   │   ├── agent.py          # CompatibilityAgent: подбор и оценка корзины
│   │   │   ├── product_searcher.py  # Поиск по БД + embedding similarity
│   │   │   ├── scenario_matcher.py  # Шаблоны блюд и сценарии
│   │   │   └── scorer.py         # Оценка совместимости продуктов
│   │   └── profile/              # ProfileAgent (⏳ в разработке)
│   │
│   ├── nlp/
│   │   ├── llm_parser.py         # function calling → structured JSON
│   │   └── function_definitions.py  # JSON-схема parse_basket_query
│   │
│   ├── backend/
│   │   ├── app.py                # Flask: create_app(), маршруты API
│   │   └── agent_pipeline.py     # AgentPipeline: оркестрация этапов
│   │
│   ├── schemas/
│   │   └── basket_item.py        # Схема элемента корзины (dataclass)
│   │
│   ├── scripts/
│   │   ├── prepare_db.py         # Инициализация и наполнение SQLite
│   │   └── build_embeddings.py   # Генерация embeddings (multilingual-e5-large)
│   │
│   ├── utils/
│   │   ├── database.py           # get_connection(), init_db_for_flask()
│   │   ├── embeddings.py         # EmbeddingCache (singleton, in-memory)
│   │   └── queries.py            # SQL-утилиты
│   │
│   ├── static/                   # Статика фронтенда
│   └── templates/                # Jinja2 шаблоны (index.html)
│
├── data/                         # DVC-tracked данные
│   └── processed/
│       └── products.db           # SQLite с товарами и embeddings
│
└── tests/                        # pytest тесты
```

***

## Быстрый старт

### Предварительные требования

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)
- Redis (для Celery)
- [LM Studio](https://lmstudio.ai/) с моделью `gemma-2-9b-it-russian-function-calling`

### Установка

```bash
git clone https://github.com/pshqd/basket-debate.git
cd basket-debate

uv sync

cp .env.example .env
# Отредактируй .env под свои параметры
```

### Подготовка базы данных

```bash
# Инициализация БД + генерация embeddings
make prepare-db

# Только embeddings (если БД уже есть)
make build-embeddings

# Пересоздать все embeddings с нуля
make rebuild-embeddings
```

> Embeddings генерируются моделью `intfloat/multilingual-e5-large` батчами по 1024.
> Устройство определяется автоматически: **MPS → CUDA → CPU**.

### Запуск

```bash
# LM Studio: запусти и загрузи gemma-2-9b-it-russian-function-calling
# Сервер должен быть доступен на http://localhost:1234/v1

make dev
# или
uv run python main.py
```

Приложение: **http://localhost:5000**

***

## API

### `POST /api/generate-basket`

```json
// Request
{ "query": "ужин на троих за 2000 без молока" }

// Response
{
  "status": "success",
  "parsed": {
    "budget_rub": 2000,
    "people": 3,
    "meal_type": ["dinner"],
    "exclude_tags": ["dairy"]
  },
  "basket": [
    {
      "product_name": "Куриное филе",
      "price_per_unit": 220.0,
      "quantity": 1.0,
      "total_price": 220.0,
      "price_display": "220.00₽/кг",
      "breakdown": "1.00кг × 220.00₽ = 220.00₽"
    }
  ],
  "summary": {
    "items_count": 8,
    "total_price": 1850.0,
    "original_price": 2100.0,
    "savings": 250.0,
    "within_budget": true,
    "execution_time_sec": 3.2
  }
}
```

### `GET /api/products`

| Параметр | Тип | Описание |
|----------|-----|----------|
| `category` | string | Фильтр по категории (LIKE) |
| `max_price` | float | Максимальная цена |
| `limit` | int | Количество записей (default: 20) |

### `GET /api/stats`

Статистика по БД: количество товаров, количество с embeddings, средняя цена, число категорий.

### `GET /health`

```json
{ "status": "ok", "pipeline_ready": true }
```

***

## NLP: Function Calling

`llm_parser.py` формирует промпт с JSON-схемой функции и парсит ответ модели через 4 regex-паттерна (под разные форматы ответа Gemma).

**Пример:**

```
Вход:  "Ужин на двоих за 1500 рублей без молочки, быстро"

Выход: {
  "budget_rub": 1500,
  "people": 2,
  "meal_type": ["dinner"],
  "exclude_tags": ["dairy"],
  "max_time_min": 30,
  "prefer_quick": true,
  "prefer_cheap": false
}
```

***

## Агенты

### CompatibilityAgent

Стратегии генерации: `smart` · `random` · `price_optimized`

1. **ScenarioMatcher** — выбирает шаблон блюда по типу еды, ограничениям и числу людей
2. **ProductSearcher** — ищет товары в SQLite по категориям сценария, фильтрует по тегам
3. **Scorer** — оценивает итоговую совместимость корзины

### BudgetAgent

Если корзина превышает бюджет — ищет аналоги для самых дорогих позиций через косинусное сходство embeddings (`sklearn`). Параметр `min_discount` (default: `0.2`) — аналог должен быть минимум на 20% дешевле.

Embeddings хранятся в SQLite как `BLOB` (float32) и кэшируются через `EmbeddingCache` (singleton, in-memory).

### ProfileAgent

⏳ В разработке. Заглушка в пайплайне.

***

## Команды Makefile

| Команда | Действие |
|---------|----------|
| `make dev` | Flask dev-сервер на порту 5000 |
| `make prepare-db` | Инициализация БД + генерация embeddings |
| `make prepare-db-no-mocks` | То же без mock-товаров |
| `make build-embeddings` | Только генерация embeddings |
| `make rebuild-embeddings` | Пересоздать все embeddings с нуля |
| `make add-mocks` | Добавить mock-товары и их embeddings |
| `make test-search` | Тест ProductSearcher |
| `make test-cmp` | Тест CompatibilityAgent |
| `make test` | Запуск pytest |

***

## Тесты

```bash
uv run pytest
# или
make test
```

Конфиг в `pyproject.toml`: `pythonpath = ["src"]`, `testpaths = ["tests"]`.

***

## Data Pipeline (DVC)

Данные версионируются через DVC с S3-хранилищем:

```bash
dvc pull    # Скачать данные
dvc repro   # Воспроизвести pipeline
```

***

## Roadmap

- [ ] Завершить **ProfileAgent** (история и предпочтения пользователя)
- [ ] Поддержка дополнительных LLM-провайдеров (OpenRouter, GigaChat)
- [ ] Telegram Bot интерфейс
- [ ] Docker Compose для полного развёртывания
- [ ] Интеграция с реальными API цен магазинов

***

## Автор

**Полина Царева** — ML Engineer / NLP Engineer  
GitHub: [@pshqd](https://github.com/pshqd) · Telegram: [@pshqd](https://t.me/pshqd)
