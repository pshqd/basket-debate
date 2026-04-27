# 🛒 Basket Debate

> **AI-система для умного формирования продуктовой корзины** на основе мульти-агентной архитектуры, LLM function calling и обучения с подкреплением.

***

## О проекте

**Basket Debate** — сервис, который принимает пользовательский запрос на естественном языке («ужин на двоих за 1500 рублей без мяса») и формирует оптимальную продуктовую корзину с учётом бюджета, dietary-ограничений, количества людей и времени приготовления.

Внутри система строится на дебатах агентов: несколько специализированных агентов спорят между собой, предлагая варианты корзины, а финальный выбор делается на основе консенсуса.

***

## Архитектура

```
User query (NL)
      │
      ▼
┌─────────────────────┐
│   LLM Parser        │  Function Calling (Gemma-2-9b, LM Studio)
│   (NLP module)      │  Парсинг запроса → структурированный JSON
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│           Multi-Agent Debate System     │
│                                         │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ BudgetAgent │  │ CompatibilityAgt │  │
│  │  (бюджет)   │  │  (совместимость) │  │
│  └─────────────┘  └──────────────────┘  │
│        ┌────────────────┐               │
│        │  ProfileAgent  │               │
│        │  (профиль user)│               │
│        └────────────────┘               │
│         RL: Stable Baselines3 / SB3     │
│         Env: PettingZoo / Gymnasium     │
└──────────────────┬──────────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  Flask Backend   │  REST API + WebSocket (SocketIO)
         │  + Celery Tasks  │  Async task queue via Redis
         └──────────────────┘
                   │
                   ▼
              Web Interface
```

***

## Стек технологий

| Слой | Технологии |
|------|-----------|
| **NLP / LLM** | OpenAI API (совместимый), LM Studio, Gemma-2-9b, function calling |
| **RL / Agents** | Stable Baselines3, SB3-Contrib, PettingZoo, Gymnasium |
| **ML** | PyTorch, Sentence Transformers, scikit-learn, NumPy, pandas |
| **Backend** | Flask, Flask-SocketIO, Flask-CORS, Celery, Redis |
| **Data** | DVC, DVC-S3, Kaggle |
| **Infra / Dev** | pytest, python-dotenv, TensorBoard, uv |

***

## Структура репозитория

```
basket-debate/
├── src/
│   ├── agents/
│   │   ├── budget/          # Агент оптимизации бюджета
│   │   ├── compatibility/   # Агент проверки совместимости продуктов
│   │   └── profile/         # Агент профиля пользователя
│   ├── nlp/
│   │   ├── llm_parser.py    # LLM function calling: парсинг NL-запроса
│   │   └── function_definitions.py  # JSON-схемы функций для LLM
│   ├── backend/             # Flask API + WebSocket handlers
│   ├── schemas/             # Pydantic/dataclass схемы данных
│   ├── scripts/             # Вспомогательные скрипты
│   ├── utils/               # Общие утилиты
│   └── static/ + templates/ # Frontend
├── data/                    # DVC-tracked данные
├── tests/                   # pytest тесты
├── dvc.lock                 # DVC pipeline lock
├── Makefile                 # Команды для запуска и управления
└── pyproject.toml           # Зависимости (uv)
```

***

## Быстрый старт

### Предварительные требования

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) (менеджер пакетов)
- Redis (для Celery)
- [LM Studio](https://lmstudio.ai/) с загруженной моделью `gemma-2-9b-it-russian-function-calling` (или другой OpenAI-совместимый LLM сервер)

### Установка

```bash
git clone https://github.com/pshqd/basket-debate.git
cd basket-debate

# Установка зависимостей через uv
uv sync

# Настройка переменных окружения
cp .env.example .env
# Отредактируй .env под свои параметры
```

### Запуск

```bash
# Запуск Redis (если не запущен)
redis-server

# Запуск Celery worker
uv run celery -A src.backend.celery_app worker --loglevel=info

# Запуск Flask приложения
uv run python main.py
```

Или через Makefile:

```bash
make run
```

### Запуск LLM сервера

Запусти LM Studio и загрузи модель `gemma-2-9b-it-russian-function-calling`. Сервер должен быть доступен на `http://localhost:1234/v1`.

***

## NLP модуль: Function Calling

Парсер запросов использует LLM с явным function calling для извлечения структурированных параметров из естественного языка. 

**Входной запрос:**
```
"Ужин на двоих за 1500 рублей без молочки, быстро"
```

**Выходной JSON:**
```json
{
  "raw_text": "Ужин на двоих за 1500 рублей без молочки, быстро",
  "budget_rub": 1500,
  "people": 2,
  "horizon": null,
  "meal_type": ["dinner"],
  "exclude_tags": ["dairy"],
  "include_tags": [],
  "max_time_min": 30,
  "prefer_quick": true,
  "prefer_cheap": false
}
```

***

## Агенты

Система использует три специализированных агента в мульти-агентной среде PettingZoo:

- **BudgetAgent** — следит за бюджетными ограничениями, оптимизирует стоимость корзины
- **CompatibilityAgent** — проверяет совместимость продуктов, dietary-ограничения, теги
- **ProfileAgent** — учитывает предпочтения и историю пользователя

Агенты обучаются методами RL (Stable Baselines3 + SB3-Contrib) и «спорят» между собой за финальный состав корзины.

***

## Тесты

```bash
uv run pytest
# или
make test
```

***

## Data Pipeline (DVC)

Данные версионируются через DVC с S3-хранилищем:

```bash
dvc pull   # Скачать данные
dvc repro  # Воспроизвести pipeline
```

***

## Roadmap

- [ ] Добавить поддержку дополнительных LLM-провайдеров (OpenRouter, GigaChat)
- [ ] Telegram Bot интерфейс
- [ ] Улучшить систему оценки качества корзины (метрики дебатов)
- [ ] Добавить интеграцию с реальными магазинами / API цен
- [ ] Docker Compose для полного развёртывания

***

## Автор

**Полина Царева** — ML Engineer / NLP Engineer  
GitHub: [@pshqd](https://github.com/pshqd) · Telegram: [@pshqd](https://t.me/pshqd)
