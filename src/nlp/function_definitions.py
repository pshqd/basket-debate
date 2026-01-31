from typing import List, Optional, Literal

def parse_basket_query(
    budget_rub: Optional[int] = None,
    people: Optional[int] = None,
    horizon_value: Optional[int] = None,
    horizon_unit: Optional[Literal["day", "week", "month"]] = None,
    meal_types: Optional[List[Literal["breakfast", "lunch", "dinner", "snack"]]] = None,
    exclude_tags: Optional[List[str]] = None,
    include_tags: Optional[List[str]] = None,
):
    """
    Функция для парсинга запроса пользователя о продуктовой корзине.
    Извлекает ограничения: бюджет, количество людей, срок, тип приёма пищи, запрещённые и обязательные теги продуктов.
    
    Args:
        budget_rub: Бюджет в рублях. Если не указан, возвращается None.
        people: Количество человек. Если не указано, возвращается None.
        horizon_value: Числовое значение срока (например, 1, 7, 30). Если не указано, возвращается None.
        horizon_unit: Единица измерения срока: "day" (день), "week" (неделя), "month" (месяц). Если не указано, возвращается None.
        meal_types: Список типов приёма пищи. Варианты: "breakfast" (завтрак), "lunch" (обед), "dinner" (ужин), "snack" (перекус). Если не указано, возвращается пустой список.
        exclude_tags: Список тегов продуктов, которые НУЖНО ИСКЛЮЧИТЬ. Используй английские ключи: "dairy" (молочное), "meat" (мясо), "fish" (рыба), "gluten_free" (без глютена), "no_sugar" (без сахара), "alcohol" (алкоголь). Если не указано, возвращается пустой список.
        include_tags: Список тегов продуктов, которые ОБЯЗАТЕЛЬНО должны быть. Используй те же английские ключи: "vegan" (веган), "vegetarian" (вегетарианское), "halal" (халяль), "children_goods" (детское). Если не указано, возвращается пустой список.
    """
    # Эта функция никогда не выполняется реально, она нужна только для описания схемы
    pass
