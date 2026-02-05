# src/agents/compatibility/agent.py
"""
Агент для подбора совместимых товаров на основе сценариев.
"""

from typing import Dict, List, Optional
from pathlib import Path

from src.agents.compatibility.scenario_matcher import ScenarioMatcher
from src.agents.compatibility.product_searcher import ProductSearcher
from src.agents.compatibility.scorer import CompatibilityScorer


# ==================== КОНФИГУРАЦИЯ ====================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCENARIOS_PATH = PROJECT_ROOT / "data" / "scenarios.json"


# ==================== КЛАСС CompatibilityAgent ====================

class CompatibilityAgent:
    """
    Агент для генерации корзины на основе совместимости продуктов.
    
    Алгоритм:
    1. Выбирает сценарий (ScenarioMatcher)
    2. Ищет товары для каждого ингредиента (ProductSearcher)
    3. Оценивает совместимость корзины (CompatibilityScorer)
    """
    
    def __init__(self, scenarios_path: Path = SCENARIOS_PATH):
        """
        Инициализация агента.
        
        Args:
            scenarios_path: Путь к scenarios.json
        """
        print("=" * 70)
        print("🤖 ИНИЦИАЛИЗАЦИЯ CompatibilityAgent")
        print("=" * 70)
        
        # Загружаем компоненты
        self.scenario_matcher = ScenarioMatcher(scenarios_path=scenarios_path)
        self.searcher = ProductSearcher()  # ✅ БЕЗ db_path
        self.scorer = CompatibilityScorer()
        
        print("✅ CompatibilityAgent готов")
        print("=" * 70)
    
    
    def generate_basket(
        self,
        parsed_query: Dict,
        strategy: str = "random"
    ) -> Dict:
        """
        Генерирует корзину товаров.
        
        Args:
            parsed_query: {
                'meal_types': ['dinner'],
                'people': 2,
                'budget_rub': 1500,
                'exclude_tags': [],
                'include_tags': []
            }
            strategy: Стратегия выбора сценария
        
        Returns:
            Dict: {
                'success': bool,
                'basket': [...],
                'total_price': float,
                'scenario_used': {...},
                'compatibility_score': float
            }
        """
        
        meal_types = parsed_query.get('meal_types', ['dinner'])
        people = parsed_query.get('people', 1)
        budget_rub = parsed_query.get('budget_rub')
        exclude_tags = parsed_query.get('exclude_tags', [])
        include_tags = parsed_query.get('include_tags', [])
        
        # ============================================
        # ШАГ 1: Выбираем сценарий
        # ============================================
        scenario = self.scenario_matcher.match(
            meal_types=meal_types,
            people=people,
            strategy=strategy
        )
        
        if not scenario:
            return {
                'success': False,
                'message': f'Не найдено сценариев для {meal_types}',
                'basket': [],
                'total_price': 0
            }
        
        print(f"\n✅ Выбран сценарий: {scenario['name']}")
        print(f"   Ингредиентов: {len(scenario['components'])}")
        
        # ============================================
        # ШАГ 2: Ищем товары для каждого ингредиента
        # ============================================
        basket = []
        total_price = 0.0
        
        for component in scenario['components']:
            ingredient = component['ingredient']
            search_query = component['search_query']
            quantity_needed = component.get('quantity_scaled', component['quantity_per_person'])
            unit = component['unit']
            required = component.get('required', True)
            
            print(f"\n🔍 Поиск: {ingredient} ({search_query})")
            
            # Поиск товаров
            candidates = self.searcher.search(
                query=search_query,
                limit=5,
                exclude_tags=exclude_tags,
                include_tags=include_tags
            )
            
            if not candidates and required:
                print(f"   ⚠️  Обязательный ингредиент не найден: {ingredient}")
                continue
            
            if not candidates:
                print(f"   ℹ️  Опциональный ингредиент пропущен: {ingredient}")
                continue
            
            # Берём лучший товар
            best_product = candidates[0]
            
            # Рассчитываем цену
            price_per_unit = best_product.get('price_per_unit', 0)
            
            # Простой расчёт: цена * количество (позже улучшим)
            item_total_price = round(price_per_unit * (quantity_needed / 1000), 2)  # г -> кг
            
            # Добавляем в корзину
            basket_item = {
                'id': best_product['id'],
                'product_name': best_product['product_name'],
                'product_category': best_product.get('product_category', ''),
                'brand': best_product.get('brand', ''),
                'price_per_unit': price_per_unit,
                'unit': best_product.get('unit', 'кг'),
                'quantity_needed': quantity_needed,
                'quantity_unit': unit,
                'total_price': item_total_price,
                'ingredient_role': ingredient,
                'required': required,
                'search_score': best_product.get('score', 0),
                'meal_components': best_product.get('meal_components', [])
            }
            
            basket.append(basket_item)
            total_price += item_total_price
            
            print(f"   ✅ {best_product['product_name']}: {item_total_price:.2f}₽")
        
        # ============================================
        # ШАГ 3: Оценка совместимости
        # ============================================
        compatibility_result = self.scorer.compute_score(basket)
        compatibility_score = compatibility_result['total_score']
        
        print(f"\n📊 Совместимость корзины: {compatibility_score:.2f}")
        print(f"💰 Итоговая цена: {total_price:.2f}₽")
        
        # Проверка бюджета
        within_budget = True
        if budget_rub and total_price > budget_rub:
            within_budget = False
            print(f"⚠️  Превышен бюджет: {total_price:.2f}₽ > {budget_rub}₽")
        
        return {
            'success': True,
            'basket': basket,
            'total_price': round(total_price, 2),
            'scenario_used': {
                'id': scenario.get('id'),
                'name': scenario.get('name'),
                'meal_type': scenario.get('meal_type'),
                'people': scenario.get('scaled_for_people')
            },
            'compatibility_score': round(compatibility_score, 4),
            'within_budget': within_budget,
            'compatibility_details': compatibility_result
        }


# ==================== ТЕСТИРОВАНИЕ ====================

def test_agent():
    """Тестирует работу CompatibilityAgent."""
    print("\n" + "=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ CompatibilityAgent")
    print("=" * 70)
    
    agent = CompatibilityAgent()
    
    # Тест 1: Ужин на двоих
    print("\n📝 Тест 1: Ужин на двоих за 1500₽")
    
    query = {
        'meal_types': ['dinner'],
        'people': 2,
        'budget_rub': 1500,
        'exclude_tags': [],
        'include_tags': []
    }
    
    result = agent.generate_basket(query)
    
    print(f"\n{'='*70}")
    print("РЕЗУЛЬТАТ:")
    print(f"{'='*70}")
    print(f"Успех: {result['success']}")
    print(f"Товаров: {len(result['basket'])}")
    print(f"Итого: {result['total_price']}₽")
    print(f"Совместимость: {result['compatibility_score']}")
    print(f"В рамках бюджета: {result['within_budget']}")
    
    print(f"\n📋 Корзина:")
    for item in result['basket']:
        print(f"   - {item['product_name']}: {item['total_price']:.2f}₽ "
              f"({item['quantity_needed']}{item['quantity_unit']})")


if __name__ == "__main__":
    test_agent()
