# src/utils/queries.py
"""
SQL-запросы для работы с products.db.

Все функции используют единое подключение через get_connection().
"""

import sqlite3
from typing import List, Dict, Optional
from pathlib import Path


# ==================== КОНФИГУРАЦИЯ ====================

# Путь к БД (от корня проекта)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # basket-debate/
DB_PATH = PROJECT_ROOT / "data" / "processed" / "products.db"


# ==================== БАЗОВЫЕ ФУНКЦИИ ====================

def get_connection() -> sqlite3.Connection:
    """
    Создаёт подключение к БД с настройками.
    
    Returns:
        sqlite3.Connection: Подключение с row_factory=Row
    
    Usage:
        conn = get_connection()
        cursor = conn.execute("SELECT * FROM products WHERE ...")
        rows = cursor.fetchall()
        conn.close()
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"База данных не найдена: {DB_PATH}\n"
            f"Запустите: uv run python src/scripts/prepare_db.py"
        )
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Возвращаем dict вместо tuple
    return conn


# ==================== ЗАПРОСЫ ====================

def fetch_product_by_id(product_id: int) -> Optional[Dict]:
    """
    Получить товар по ID.
    
    Args:
        product_id: ID товара
    
    Returns:
        Dict или None: Данные товара
    
    Example:
        product = fetch_product_by_id(900101)
        print(product['product_name'])  # "Масло подсолнечное"
    """
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "id": row["id"],
        "product_name": row["product_name"],
        "product_category": row["product_category"],
        "brand": row["brand"],
        "package_size": row["package_size"],
        "unit": row["unit"],
        "price_per_unit": row["price_per_unit"],
        "tags": row["tags"].split("|") if row["tags"] else [],
        "meal_components": row["meal_components"].split("|") if row["meal_components"] else []
    }


def fetch_products_by_category(
    category: str,
    max_price: Optional[float] = None,
    limit: int = 10
) -> List[Dict]:
    """
    Получить товары по категории.
    
    Args:
        category: Категория (например, "Мясо", "Овощи")
        max_price: Максимальная цена (опционально)
        limit: Количество товаров
    
    Returns:
        List[Dict]: Список товаров
    
    Example:
        products = fetch_products_by_category("Мясо", max_price=500, limit=5)
    """
    query = """
        SELECT * FROM products
        WHERE product_category LIKE ?
    """
    params = [f"%{category}%"]
    
    if max_price is not None:
        query += " AND price_per_unit <= ?"
        params.append(max_price)
    
    query += " ORDER BY price_per_unit ASC LIMIT ?"
    params.append(limit)
    
    conn = get_connection()
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [_row_to_dict(row) for row in rows]


def fetch_candidate_products(
    constraints: Dict,
    limit: int = 100,
    max_price_ratio: float = 0.3,
    require_meal_components: bool = False
) -> List[Dict]:
    """
    Фильтрует товары из БД по constraints.
    
    Args:
        constraints: Ограничения {
            'budget_rub': 1500,
            'exclude_tags': ['dairy'],
            'include_tags': ['vegan'],
            'people': 2
        }
        limit: Максимальное количество товаров
        max_price_ratio: Макс. цена товара = budget * ratio
        require_meal_components: Исключить товары без meal_components
    
    Returns:
        List[Dict]: Список товаров-кандидатов
    
    Example:
        constraints = {'budget_rub': 1500, 'exclude_tags': ['dairy']}
        products = fetch_candidate_products(constraints, limit=50)
    """
    budget = constraints.get("budget_rub") or 5000
    exclude_tags = constraints.get("exclude_tags") or []
    include_tags = constraints.get("include_tags", [])
    people = constraints.get("people", 1)
    
    # Рассчитываем диапазон цен
    min_price = budget * 0.02   # Не берём слишком дешёвые (соль за 10₽)
    max_price = budget * max_price_ratio  # Не берём слишком дорогие
    
    query = """
        SELECT id, product_name, product_category, brand,
               package_size, unit, price_per_unit, tags, meal_components
        FROM products
        WHERE price_per_unit >= ?
        AND price_per_unit <= ?
    """
    params = [min_price, max_price]
    
    # Фильтр: только товары с meal_components
    if require_meal_components:
        query += """
            AND meal_components IS NOT NULL 
            AND meal_components != '' 
            AND meal_components != 'other'
        """
    
    # Фильтр: исключить теги (аллергены, непереносимость)
    for tag in exclude_tags:
        query += " AND (tags IS NULL OR tags NOT LIKE ?)"
        params.append(f"%{tag}%")
    
    # Фильтр: обязательные теги (веган, без глютена)
    if include_tags:
        for tag in include_tags:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")
    
    # Случайная выборка
    query += " ORDER BY RANDOM() LIMIT ?"
    params.append(limit)
    
    conn = get_connection()
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [_row_to_dict(row) for row in rows]


def count_products(filters: Optional[Dict] = None) -> int:
    """
    Подсчёт товаров в БД.
    
    Args:
        filters: Опциональные фильтры (category, max_price и т.д.)
    
    Returns:
        int: Количество товаров
    
    Example:
        total = count_products()
        mock_count = count_products({'id_min': 900000})
    """
    query = "SELECT COUNT(*) FROM products"
    params = []
    
    if filters:
        conditions = []
        
        if 'category' in filters:
            conditions.append("product_category LIKE ?")
            params.append(f"%{filters['category']}%")
        
        if 'max_price' in filters:
            conditions.append("price_per_unit <= ?")
            params.append(filters['max_price'])
        
        if 'id_min' in filters:
            conditions.append("id >= ?")
            params.append(filters['id_min'])
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
    
    conn = get_connection()
    cursor = conn.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    
    return count


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def _row_to_dict(row: sqlite3.Row) -> Dict:
    """
    Конвертирует SQLite Row в стандартный словарь.
    
    Обрабатывает split для tags и meal_components.
    """
    return {
        "id": row["id"],
        "product_name": row["product_name"],
        "product_category": row["product_category"],
        "brand": row["brand"],
        "package_size": row["package_size"],
        "unit": row["unit"],
        "price_per_unit": row["price_per_unit"],
        "tags": row["tags"].split("|") if row["tags"] else [],
        "meal_components": row["meal_components"].split("|") if row["meal_components"] else []
    }


# ==================== ТЕСТИРОВАНИЕ ====================

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ queries.py")
    print("=" * 60)
    
    # Тест 1: Подсчёт товаров
    print("\n1. Подсчёт товаров:")
    total = count_products()
    print(f"   Всего товаров: {total}")
    
    # Тест 2: Поиск по ID
    print("\n2. Поиск по ID (900101):")
    product = fetch_product_by_id(900101)
    if product:
        print(f"   ✅ {product['product_name']}: {product['price_per_unit']}₽")
    else:
        print("   ❌ Товар не найден")
    
    # Тест 3: Поиск по категории
    print("\n3. Поиск по категории 'Мясо' (до 500₽):")
    products = fetch_products_by_category("Мясо", max_price=500, limit=3)
    for p in products:
        print(f"   - {p['product_name']}: {p['price_per_unit']}₽")
    
    # Тест 4: Кандидаты с фильтрами
    print("\n4. Кандидаты (бюджет 1500₽, без dairy):")
    constraints = {
        "budget_rub": 1500,
        "exclude_tags": ["dairy"],
        "people": 2
    }
    candidates = fetch_candidate_products(constraints, limit=5)
    for p in candidates:
        print(f"   - {p['product_name']}: {p['price_per_unit']}₽, теги: {p['tags']}")
    
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено")
    print("=" * 60)
