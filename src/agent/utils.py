from typing import List, Dict

def pad_products_to_k(products: List[Dict], k: int = 100) -> List[Dict]:
    """
    Паддит список товаров до фиксированного размера K.
    
    Зачем: SB3 требует фиксированный action_space для обучения нейросети.
    Если БД вернула меньше K товаров → дополняем "пустышками" (dummy items).
    
    Args:
        products: список товаров из БД
        k: целевое количество товаров
    
    Returns:
        список из ровно K товаров (реальные + dummy)
    """
    if len(products) >= k:
        return products[:k]  # Обрезаем до K, если больше
    
    # Дополняем пустышками (dummy items)
    dummy_item = {
        "id": -1,
        "product_name": "DUMMY",
        "product_category": "DUMMY",
        "brand": "DUMMY",
        "package_size": 0.0,
        "unit": "шт",
        "price_per_unit": 0.0,  # Цена 0 → агенты не выберут
        "tags": []
    }
    
    padded = products.copy()
    for i in range(k - len(products)):
        padded.append(dummy_item)
    
    return padded
