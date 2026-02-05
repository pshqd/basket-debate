"""
Кэш embeddings в памяти (ускорение поиска).
"""

import numpy as np
from typing import Dict, Optional
from .database import get_connection


class EmbeddingCache:
    """
    Singleton для кэширования векторов.
    
    Пример:
        cache = EmbeddingCache()
        emb = cache.get(product_id=123)  # Первый раз из БД (5ms)
        emb = cache.get(product_id=123)  # Второй раз из RAM (0.001ms)
    """
    
    _instance = None
    _cache: Dict[int, np.ndarray] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get(self, product_id: int) -> Optional[np.ndarray]:
        """Получить embedding с кэшированием."""
        
        # Проверяем кэш
        if product_id in self._cache:
            return self._cache[product_id]
        
        # Читаем из БД
        conn = get_connection()
        cursor = conn.execute(
            "SELECT embedding FROM products WHERE id = ?",
            (product_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row and row['embedding']:
            # Десериализуем
            emb = np.frombuffer(row['embedding'], dtype=np.float32)
            
            # Сохраняем в кэш
            self._cache[product_id] = emb
            return emb
        
        return None
    
    def clear(self):
        """Очистка кэша (для тестов)."""
        self._cache.clear()
