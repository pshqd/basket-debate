"""
BudgetAgent - оптимизация корзины под бюджет с embeddings.

Работает в отдельном потоке (thread-safe SQLite).
"""

import sqlite3
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from sklearn.metrics.pairwise import cosine_similarity
import sys

# ============================================
# УМНЫЙ ИМПОРТ: Работает и в тестах, и в Flask
# ============================================

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Теперь импортируем database utility
try:
    from src.utils.database import get_connection
    HAS_DB_UTILS = True
except ModuleNotFoundError:
    # Fallback: если не получилось - будем использовать прямой sqlite3.connect
    HAS_DB_UTILS = False
    print("⚠️ src.utils.database недоступен, используем fallback")

DB_PATH = Path("data/processed/products.db")


class BudgetAgent:
    """
    Агент для оптимизации корзины под бюджет.
    Ищет дешёвые аналоги дорогих товаров используя embeddings.
    """
    
    def __init__(self, db_path: Path = DB_PATH):
        """
        Инициализация агента.
        
        Args:
            db_path: Путь к БД с товарами
        """
        self.db_path = db_path
        print("💰 BudgetAgent инициализирован")
    
    def calculate_total(self, basket: list[dict]) -> float:
        """
        Подсчитать общую стоимость корзины.
        
        Поддерживает два формата:
        1. Упрощённый: {"price": 100, "quantity": 2}
        2. BasketItem: {"price_per_unit": 100, "quantity": 2, "total_price": 200}
        
        Args:
            basket: список товаров
        
        Returns:
            float: общая стоимость в рублях
        """
        total = 0.0
        
        for item in basket:
            # Вариант 1: уже есть total_price (BasketItem)
            if "total_price" in item:
                total += item["total_price"]
            
            # Вариант 2: есть price (упрощённый формат)
            elif "price" in item:
                price = item["price"]
                quantity = item.get("quantity", 1)
                total += price * quantity
            
            # Вариант 3: есть price_per_unit (BasketItem без total_price)
            elif "price_per_unit" in item:
                price_per_unit = item["price_per_unit"]
                quantity = item.get("quantity", 1)
                total += price_per_unit * quantity
            
            else:
                # Если вообще нет цены - пропускаем товар
                print(f"⚠️ Товар без цены: {item.get('name', 'unknown')}")
                continue
        
        return round(total, 2)
    def _search_in_db(
        self, 
        conn, 
        max_price, 
        meal_components, 
        original_embedding, 
        original_quantity, 
        original_item
    ):
        """
        Вынесенная логика поиска в БД (для переиспользования).
        """
        cursor = conn.cursor()
        
        query = """
            SELECT id, product_name, product_category, brand, price_per_unit, unit, 
                package_size, tags, meal_components, embedding
            FROM products
            WHERE embedding IS NOT NULL
            AND price_per_unit < ?
        """
        
        if meal_components:
            main_component = meal_components[0] if isinstance(meal_components, list) else meal_components
            query += f" AND meal_components LIKE '%{main_component}%'"
        
        cursor.execute(query, (max_price,))
        rows = cursor.fetchall()
        
        if not rows:
            return None
        
        # Similarity search (без изменений)
        candidates = []
        
        for row in rows:
            embedding_blob = row[9]
            if not embedding_blob:
                continue
            
            try:
                product_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                
                if len(product_embedding) == 0:
                    continue
                
                if not np.isfinite(product_embedding).all():
                    continue
                
                if not np.isfinite(original_embedding).all():
                    continue
                
                similarity = float(cosine_similarity(
                    original_embedding.reshape(1, -1),
                    product_embedding.reshape(1, -1)
                )[0, 0])
                
                if not np.isfinite(similarity):
                    continue
                
                price_per_unit = row[4]
                total_price = price_per_unit * original_quantity
                
                candidates.append({
                    'id': row[0],
                    'name': row[1],
                    'product_name': row[1],
                    'product_category': row[2],
                    'category': row[2],
                    'brand': row[3],
                    'price_per_unit': price_per_unit,
                    'price': price_per_unit,
                    'quantity': original_quantity,
                    'total_price': round(total_price, 2),
                    'unit': row[5],
                    'package_size': row[6],
                    'tags': row[7],
                    'meal_components': row[8],
                    'embedding': product_embedding,
                    'similarity': similarity
                })
                
            except Exception as e:
                continue
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x['similarity'], reverse=True)
        
        for candidate in candidates:
            if candidate['id'] != original_item.get('id'):
                return candidate
        
        return None
    def validate_basket(self, basket: List[Dict]) -> Dict:
        """
        Валидация корзины перед оптимизацией.
        
        Проверяет:
        1. Наличие embeddings у всех товаров
        2. Валидность цен и количеств
        3. Корректность данных
        
        Args:
            basket: Корзина для проверки
        
        Returns:
            Dict: {
                "valid": True/False,
                "errors": [...],
                "warnings": [...]
            }
        """
        errors = []
        warnings = []
        
        for i, item in enumerate(basket):
            item_name = item.get('name', item.get('product_name', f'item_{i}'))
            
            # 1. Проверка embedding (КРИТИЧНО!)
            if 'embedding' not in item or item['embedding'] is None:
                errors.append(f"❌ Товар '{item_name}' не имеет embedding (невалидный товар)")
                continue
            
            # Проверяем, что embedding валидный numpy array
            embedding = item['embedding']
            if isinstance(embedding, list):
                embedding = np.array(embedding, dtype=np.float32)
                item['embedding'] = embedding  # обновляем in-place, чтобы дальше работало
            if not isinstance(embedding, np.ndarray):
                errors.append(f"❌ Товар '{item_name}': embedding не является numpy array")
                continue
            
            if len(embedding) == 0:
                errors.append(f"❌ Товар '{item_name}': пустой embedding")
                continue
            
            if not np.isfinite(embedding).all():
                errors.append(f"❌ Товар '{item_name}': embedding содержит NaN/Inf")
                continue
            
            # 2. Проверка цены
            price = item.get('price') or item.get('price_per_unit') or item.get('total_price')
            if price is None or price <= 0:
                errors.append(f"❌ Товар '{item_name}': некорректная цена ({price})")
            
            # 3. Проверка quantity
            quantity = item.get('quantity', 1)
            if quantity <= 0:
                warnings.append(f"⚠️ Товар '{item_name}': quantity = {quantity} (должно быть > 0)")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    # >>>>>>> НОВОЕ: вспомогательный метод <<<<<<<<
    def check_budget(self, basket: list[dict], budget: float) -> dict:
        """
        Проверить, вписывается ли корзина в бюджет (без оптимизации).
        Это просто удобный helper для тестов и дебага.
        """
        total = self.calculate_total(basket)
        fits = total <= budget
        overspend = max(0, total - budget)
        
        return {
            "total": total,
            "budget": budget,
            "fits": fits,
            "overspend": round(overspend, 2),
        }
    
    def optimize(
        self,
        basket: List[Dict],
        budget_rub: Optional[float] = None,
        min_discount: float = 0.3
    ) -> Dict:
        """Оптимизирует корзину под бюджет."""
        
        # Валидация и early exits (БЕЗ ИЗМЕНЕНИЙ)
        validation = self.validate_basket(basket)
        if not validation["valid"]:
            return {
                "basket": [],
                "total_price": 0.0,
                "saved": 0.0,
                "replacements": [],
                "within_budget": False,
                "errors": validation["errors"],
                "message": "Невалидная корзина"
            }
        
        if not basket:
            return {
                "basket": [],
                "total_price": 0.0,
                "saved": 0.0,
                "replacements": [],
                "within_budget": True,
                "message": "Пустая корзина"
            }
        
        original_price = self.calculate_total(basket)
        
        if budget_rub is None or original_price <= budget_rub:
            return {
                "basket": basket,
                "total_price": original_price,
                "saved": 0.0,
                "replacements": [],
                "within_budget": True,
                "message": "В пределах бюджета"
            }
        
        print(f"\n💰 BudgetAgent: Бюджет превышен на {original_price - budget_rub:.2f}₽")
        print(f"   Ищу дешёвые аналоги...")
        
        # ============================================
        # ИЗМЕНЕНИЕ: Выбираем способ подключения
        # ============================================
        optimized_basket = basket.copy()
        replacements = []
        total_saved = 0.0
        
        sorted_indices = sorted(
            range(len(optimized_basket)),
            key=lambda i: optimized_basket[i].get('total_price', 0),
            reverse=True
        )
        
        # Если доступен get_connection - используем context manager
        if HAS_DB_UTILS:
            with get_connection() as conn:
                for idx in sorted_indices:
                    current_price = self.calculate_total(optimized_basket)
                    
                    if current_price <= budget_rub:
                        break
                    
                    item = optimized_basket[idx]
                    
                    alternative = self._find_cheaper_alternative(
                        item,
                        min_discount=min_discount,
                        conn=conn
                    )
                    
                    if alternative:
                        old_price = item.get('total_price') or (
                            item.get('price_per_unit', item.get('price', 0)) * item.get('quantity', 1)
                        )
                        new_price = alternative.get('total_price', 0)
                        saved = old_price - new_price
                        
                        optimized_basket[idx] = alternative
                        
                        replacements.append({
                            'from': item.get('name', item.get('product_name', '')),
                            'to': alternative.get('name', alternative.get('product_name', '')),
                            'saved': round(saved, 2),
                            'old_price': round(old_price, 2),
                            'new_price': round(new_price, 2),
                            'quantity': alternative.get('quantity', 1)
                        })
                        
                        total_saved += saved
                        
                        print(f"   ✅ {item.get('name', '')[:40]} ({old_price:.2f}₽)")
                        print(f"      → {alternative.get('name', '')[:40]} ({new_price:.2f}₽)")
                        print(f"      Экономия: {saved:.2f}₽")
        
        else:
            # Fallback: используем прямой sqlite3.connect (для тестов)
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            try:
                for idx in sorted_indices:
                    current_price = self.calculate_total(optimized_basket)
                    
                    if current_price <= budget_rub:
                        break
                    
                    item = optimized_basket[idx]
                    
                    alternative = self._find_cheaper_alternative(
                        item,
                        min_discount=min_discount,
                        conn=conn
                    )
                    
                    if alternative:
                        old_price = item.get('total_price') or (
                            item.get('price_per_unit', item.get('price', 0)) * item.get('quantity', 1)
                        )
                        new_price = alternative.get('total_price', 0)
                        saved = old_price - new_price
                        
                        optimized_basket[idx] = alternative
                        
                        replacements.append({
                            'from': item.get('name', item.get('product_name', '')),
                            'to': alternative.get('name', alternative.get('product_name', '')),
                            'saved': round(saved, 2),
                            'old_price': round(old_price, 2),
                            'new_price': round(new_price, 2),
                            'quantity': alternative.get('quantity', 1)
                        })
                        
                        total_saved += saved
                        
                        print(f"   ✅ {item.get('name', '')[:40]} ({old_price:.2f}₽)")
                        print(f"      → {alternative.get('name', '')[:40]} ({new_price:.2f}₽)")
                        print(f"      Экономия: {saved:.2f}₽")
            finally:
                conn.close()
    
        # Финальный результат
        final_price = self.calculate_total(optimized_basket)
        
        return {
            "basket": optimized_basket,
            "total_price": final_price,
            "saved": round(total_saved, 2),
            "replacements": replacements,
            "within_budget": final_price <= budget_rub,
            "optimized": len(replacements) > 0,
            "message": f"Заменено {len(replacements)} товаров, сэкономлено {total_saved:.2f}₽"
                if replacements else "В пределах бюджета"
        }

        
    def _find_cheaper_alternative(
            self,
            item: Dict,
            min_discount: float = 0.3,
            conn: Optional[sqlite3.Connection] = None
        ) -> Optional[Dict]:
            """
            Ищет дешёвый аналог.
            
            ИЗМЕНЕНИЕ: Теперь принимает connection извне (не создаёт свой).
            """
            # Получение цены (без изменений)
            if 'price_per_unit' in item:
                original_price = item['price_per_unit']
            elif 'price' in item:
                original_price = item['price']
            elif 'total_price' in item and 'quantity' in item:
                original_price = item['total_price'] / item['quantity']
            else:
                print(f"⚠️ Товар {item.get('name', 'unknown')}: не найдена цена")
                return None
            

            meal_components = item.get('meal_components', [])
            original_quantity = item.get('quantity', 1)
            
            original_embedding = item.get('embedding')
            if original_embedding is None:
                return None
            if isinstance(original_embedding, list):
                original_embedding = np.array(original_embedding, dtype=np.float32)
            
            max_price = original_price * (1 - min_discount)
            
            # ============================================
            # ИЗМЕНЕНИЕ: НЕ создаём connection, используем переданный
            # ============================================
            if conn is None:
                with get_connection() as temp_conn:
                    return self._search_in_db(
                        temp_conn, 
                        max_price, 
                        meal_components, 
                        original_embedding, 
                        original_quantity, 
                        item
                    )
            else:
                # Используем переданный connection
                return self._search_in_db(
                    conn, 
                    max_price, 
                    meal_components, 
                    original_embedding, 
                    original_quantity, 
                    item
                )


def test_budget_agent():
    """Тестирует работу BudgetAgent."""
    
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ BudgetAgent")
    print("=" * 70)
    
    agent = BudgetAgent()
    
    # Загружаем РЕАЛЬНЫЕ товары из БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, product_name, price_per_unit, embedding, meal_components
        FROM products
        WHERE embedding IS NOT NULL
        AND price_per_unit > 100
        ORDER BY price_per_unit DESC
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("❌ Нет товаров с embeddings в БД!")
        return
    
    # Создаём корзину из реальных товаров
    expensive_basket = []
    for row in rows[:2]:
        embedding = np.frombuffer(row[3], dtype=np.float32)
        
        expensive_basket.append({
            'id': row[0],
            'name': row[1],
            'product_name': row[1],
            'price': row[2],
            'meal_components': row[4].split('|') if row[4] else ['main_course'],
            'embedding': embedding
        })
    
    print(f"\n📝 Тест 1: Дорогая корзина (бюджет 200₽)")
    for item in expensive_basket:
        print(f"   - {item['name'][:50]}: {item['price']:.2f}₽")
    
    result = agent.optimize(
        basket=expensive_basket,
        budget_rub=200.0,
        min_discount=0.2
    )
    
    print(f"\n📊 Результат:")
    print(f"   Исходная цена: {sum(i['price'] for i in expensive_basket):.2f}₽")
    print(f"   Итоговая цена: {result['total_price']:.2f}₽")
    print(f"   Сэкономлено: {result['saved']:.2f}₽")
    print(f"   В бюджете: {'✅' if result['within_budget'] else '❌'}")
    print(f"   Замен: {len(result['replacements'])}")
    
    for rep in result['replacements']:
        print(f"      {rep['from'][:40]} → {rep['to'][:40]} (-{rep['saved']:.2f}₽)")
    
    # Тест 2: Корзина в бюджете
    print("\n\n📝 Тест 2: Корзина в бюджете (бюджет 5000₽)")
    
    result2 = agent.optimize(
        basket=expensive_basket,
        budget_rub=5000.0
    )
    
    print(f"\n📊 Результат:")
    print(f"   {result2['message']}")
    print(f"   Замен: {len(result2['replacements'])}")
    
    print("\n" + "=" * 70)
    print("✅ Тестирование завершено")
    print("=" * 70)


if __name__ == "__main__":
    test_budget_agent()