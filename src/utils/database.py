"""
Единый интерфейс для работы с SQLite.
Поддерживает Flask g-context и standalone режим.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

DB_PATH = Path("data/processed/products.db")


# ============================================
# FLASK INTEGRATION (для API endpoints)
# ============================================

def get_db():
    """
    Получить connection для текущего Flask request.
    
    Использование:
        @app.route('/products')
        def get_products():
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM products LIMIT 10")
            return {'products': [dict(row) for row in cursor.fetchall()]}
    
    Connection автоматически закроется после request.
    """
    from flask import g
    
    if 'db' not in g:
        logger.debug(f"Создаю новый DB connection для request")
        g.db = sqlite3.connect(
            DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    
    return g.db


def close_db(e=None):
    """
    Закрыть connection после Flask request.
    Вызывается автоматически через teardown_appcontext.
    """
    from flask import g
    
    db = g.pop('db', None)
    
    if db is not None:
        logger.debug("Закрываю DB connection после request")
        db.close()


def init_db_for_flask(app):
    """
    Регистрирует database в Flask app.
    
    Использование в app.py:
        from src.utils.database import init_db_for_flask
        
        app = Flask(__name__)
        init_db_for_flask(app)
    """
    app.teardown_appcontext(close_db)
    logger.info("Flask DB integration инициализирована")


# ============================================
# STANDALONE CONTEXT MANAGER (для агентов, Celery)
# ============================================

@contextmanager
def get_connection():
    """
    Context manager для безопасной работы с БД вне Flask.
    
    Использование:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products")
            # Connection автоматически закроется
    
    Для агентов и скриптов.
    """
    conn = None
    try:
        logger.debug(f"Создаю standalone DB connection")
        conn = sqlite3.connect(
            DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()  # Автоматический commit
    except Exception as e:
        if conn:
            logger.error(f"Ошибка БД, откат транзакции: {e}")
            conn.rollback()
        raise
    finally:
        if conn:
            logger.debug("Закрываю standalone DB connection")
            conn.close()


# ============================================
# HELPER FUNCTIONS (используют context manager)
# ============================================

def fetch_products_by_category(
    category: str, 
    max_price: Optional[float] = None,
    limit: int = 100
) -> List[Dict]:
    """
    Получает товары по категории.
    
    Args:
        category: Категория товара (поиск через LIKE)
        max_price: Максимальная цена (опционально)
        limit: Максимум товаров (default 100)
    
    Returns:
        List[Dict]: Список товаров
    
    Example:
        products = fetch_products_by_category("Мясо", max_price=500)
    """
    with get_connection() as conn:
        query = """
            SELECT * FROM products 
            WHERE product_category LIKE ?
        """
        params = [f"%{category}%"]
        
        if max_price is not None:
            query += " AND price_per_unit <= ?"
            params.append(max_price)
        
        query += f" LIMIT ?"
        params.append(limit)
        
        logger.debug(f"Запрос товаров: category={category}, max_price={max_price}")
        
        cursor = conn.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Найдено товаров: {len(products)}")
        return products


def fetch_product_by_id(product_id: int) -> Optional[Dict]:
    """
    Получает товар по ID.
    
    Args:
        product_id: ID товара
    
    Returns:
        Dict или None если не найден
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM products WHERE id = ?", 
            (product_id,)
        )
        row = cursor.fetchone()
        
        if row:
            logger.debug(f"Товар {product_id} найден")
            return dict(row)
        else:
            logger.warning(f"Товар {product_id} НЕ найден")
            return None


def fetch_products_by_meal_component(
    meal_component: str,
    max_price: Optional[float] = None,
    limit: int = 50
) -> List[Dict]:
    """
    Получает товары по meal_component (main_course, side_dish, etc.).
    
    Args:
        meal_component: Компонент блюда
        max_price: Максимальная цена
        limit: Лимит результатов
    
    Returns:
        List[Dict]: Товары
    """
    with get_connection() as conn:
        query = """
            SELECT * FROM products
            WHERE meal_components LIKE ?
            AND embedding IS NOT NULL
        """
        params = [f"%{meal_component}%"]
        
        if max_price is not None:
            query += " AND price_per_unit <= ?"
            params.append(max_price)
        
        query += " LIMIT ?"
        params.append(limit)
        
        cursor = conn.execute(query, params)
        products = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"Найдено товаров для {meal_component}: {len(products)}")
        return products


def execute_query(
    query: str, 
    params: tuple = (), 
    fetch_one: bool = False
) -> Any:
    """
    Универсальный executor для кастомных запросов.
    
    Args:
        query: SQL-запрос
        params: Параметры (tuple)
        fetch_one: Вернуть одну строку или все
    
    Returns:
        Dict, List[Dict] или None
    
    Example:
        # Один товар
        product = execute_query(
            "SELECT * FROM products WHERE id = ?",
            (123,),
            fetch_one=True
        )
        
        # Много товаров
        products = execute_query(
            "SELECT * FROM products WHERE price_per_unit < ?",
            (100,)
        )
    """
    with get_connection() as conn:
        cursor = conn.execute(query, params)
        
        if fetch_one:
            row = cursor.fetchone()
            return dict(row) if row else None
        else:
            return [dict(row) for row in cursor.fetchall()]


# ============================================
# DATABASE INITIALIZATION
# ============================================

def init_database_schema():
    """
    Создаёт таблицы если их нет (для первого запуска).
    
    Использование:
        python -c "from src.utils.database import init_database_schema; init_database_schema()"
    """
    with get_connection() as conn:
        # Создать таблицу products если не существует
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                product_category TEXT,
                brand TEXT,
                package_size REAL,
                unit TEXT,
                price_per_unit REAL NOT NULL,
                tags TEXT,
                meal_components TEXT,
                embedding BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создать индексы для быстрого поиска
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_price 
            ON products(price_per_unit)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_category 
            ON products(product_category)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meal_components 
            ON products(meal_components)
        """)
        
        logger.info("✅ Database schema инициализирована")


def get_db_stats() -> Dict:
    """
    Получить статистику по БД.
    
    Returns:
        Dict: {
            'total_products': int,
            'products_with_embeddings': int,
            'avg_price': float,
            'categories_count': int
        }
    """
    with get_connection() as conn:
        stats = {}
        
        # Всего товаров
        cursor = conn.execute("SELECT COUNT(*) as count FROM products")
        stats['total_products'] = cursor.fetchone()['count']
        
        # С embeddings
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM products WHERE embedding IS NOT NULL"
        )
        stats['products_with_embeddings'] = cursor.fetchone()['count']
        
        # Средняя цена
        cursor = conn.execute("SELECT AVG(price_per_unit) as avg FROM products")
        stats['avg_price'] = round(cursor.fetchone()['avg'] or 0, 2)
        
        # Количество категорий
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT product_category) as count FROM products"
        )
        stats['categories_count'] = cursor.fetchone()['count']
        
        return stats
    