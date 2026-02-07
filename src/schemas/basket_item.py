# src/schemas/basket_item.py
"""
Единая схема данных для элемента корзины.
Используется всеми агентами для консистентности.
"""

from typing import TypedDict, Optional


class BasketItem(TypedDict, total=False):
    """
    Единый формат элемента корзины для всех агентов.
    
    Все цены в рублях, все количества в указанных единицах.
    """
    # Идентификация товара
    id: int
    name: str
    category: str
    brand: str
    
    # Цена и количество (КЛЮЧЕВОЕ!)
    price_per_unit: float    # Цена за 1 единицу (₽/кг, ₽/л, ₽/шт)
    unit: str                # Единица измерения: 'кг', 'л', 'шт', 'г', 'мл'
    quantity: float          # Количество в единицах unit
    total_price: float       # price_per_unit * quantity (итоговая стоимость)
    
    # Метаданные
    agent: str               # Кто добавил: 'compatibility', 'budget', 'profile'
    reason: str              # Почему выбран товар
    ingredient_role: str     # Роль в блюде: 'main_course', 'side_dish', 'salad', 'sauce', и т.д.
    
    # Scoring
    search_score: float      # Релевантность поиска [0-1]
    rating: Optional[float]  # Рейтинг товара [1-5]


def create_basket_item(
    product: dict,
    quantity: float,
    agent: str = 'compatibility',
    reason: str = '',
    ingredient_role: str = '',
    search_score: float = 0.0
) -> BasketItem:
    """
    Фабрика для создания BasketItem из продукта БД.
    
    Args:
        product: Товар из БД/поиска с полями {id, name, price, unit, ...}
        quantity: Нужное количество в единицах product['unit']
        agent: Кто добавил товар
        reason: Причина выбора
        ingredient_role: Роль ингредиента
        search_score: Скор поиска
        
    Returns:
        Валидный BasketItem
    """
    price_per_unit = product['price']
    total_price = price_per_unit * quantity
    
    return BasketItem(
        id=product['id'],
        name=product['name'],
        category=product.get('category', ''),
        brand=product.get('brand', ''),
        
        price_per_unit=round(price_per_unit, 2),
        unit=product['unit'],
        quantity=round(quantity, 3),
        total_price=round(total_price, 2),
        
        agent=agent,
        reason=reason,
        ingredient_role=ingredient_role,
        search_score=round(search_score, 2),
        rating=product.get('rating')
    )
