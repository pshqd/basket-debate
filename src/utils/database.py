"""
Единый интерфейс для работы с SQLite.
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path("data/processed/products.db")


def get_connection():
    """Создаёт подключение к БД."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Чтобы получать dict вместо tuple
    return conn


def fetch_products_by_category(category: str, max_price: float = None) -> List[Dict]:
    """
    Получает товары по категории.
    
    Пример:
        products = fetch_products_by_category("Мясо", max_price=500)
    """
    conn = get_connection()
    
    query = "SELECT * FROM products WHERE product_category LIKE ?"
    params = [f"%{category}%"]
    
    if max_price:
        query += " AND price_per_unit <= ?"
        params.append(max_price)
    
    cursor = conn.execute(query, params)
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return products


def fetch_product_by_id(product_id: int) -> Optional[Dict]:
    """Получает товар по ID."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    
    return dict(row) if row else None
