# src/backend/agent_pipeline.py
"""
Оркестрация агентов для генерации корзины.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import time

# Добавляем корень проекта в PYTHONPATH
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.compatibility.agent import CompatibilityAgent
from src.agents.budget.agent import BudgetAgent
from src.nlp.llm_parser import parse_query_with_function_calling
from src.schemas.basket_item import BasketItem  


# src/backend/agent_pipeline.py

import logging

logger = logging.getLogger(__name__)

class AgentPipeline:
    """Пайплайн для последовательной обработки запроса агентами."""
    
    def __init__(self):
        """Инициализирует агентов."""
        logger.info("🤖 Инициализация AgentPipeline...")
        
        try:
            self.compatibility_agent = CompatibilityAgent()
            logger.info("   ✅ CompatibilityAgent загружен")
        except Exception as e:
            logger.error(f"   ❌ Ошибка загрузки CompatibilityAgent: {e}")
            raise
        
        try:
            self.budget_agent = BudgetAgent()
            logger.info("   ✅ BudgetAgent загружен")
        except Exception as e:
            logger.error(f"   ❌ Ошибка загрузки BudgetAgent: {e}")
            raise
        
        self.profile_agent = None  # TODO
        logger.info("   ⏳ ProfileAgent (в разработке)")
    
    def process(self, user_query: str) -> Dict[str, Any]:
        """Обрабатывает запрос через весь пайплайн."""
        start_time = time.time()
        stages = []
        parsed_query = {}
        
        try:
            # ЭТАП 1: LLM PARSER
            logger.info(f"📝 Запрос пользователя: {user_query}")
            stage1_start = time.time()
            
            try:
                parsed_query = parse_query_with_function_calling(user_query)
                
                budget_rub = parsed_query.get('budget_rub') or 3000
                people = parsed_query.get('people') or 2
                meal_types = parsed_query.get('meal_type') or ['dinner']
                
                logger.info(f"✅ LLM Parser: budget={budget_rub}, people={people}, meals={meal_types}")
                
                stages.append({
                    'agent': 'llm_parser',
                    'name': '🧠 LLM Parser',
                    'status': 'completed',
                    'duration': round(time.time() - stage1_start, 2),
                    'result': {'parsed': parsed_query}
                })
            
            except Exception as e:
                logger.error(f"❌ Ошибка LLM Parser: {e}", exc_info=True)
                stages.append({
                    'agent': 'llm_parser',
                    'name': '🧠 LLM Parser',
                    'status': 'failed',
                    'error': str(e)
                })
                raise
            
            # ЭТАП 2: COMPATIBILITY AGENT
            logger.info("🔗 Запуск CompatibilityAgent...")
            stage2_start = time.time()
            
            try:
                compatibility_query = {
                    'meal_types': meal_types,
                    'people': people,
                    'budget_rub': budget_rub,
                    'exclude_tags': parsed_query.get('exclude_tags', []),
                    'include_tags': parsed_query.get('include_tags', [])
                }
                
                compatibility_result = self.compatibility_agent.generate_basket(
                    parsed_query=compatibility_query,
                    strategy='smart'
                )
                
                basket_v1 = compatibility_result.get('basket', [])
                
                logger.info(f"✅ CompatibilityAgent: {len(basket_v1)} товаров, {compatibility_result.get('total_price', 0):.2f}₽")
                
                stages.append({
                    'agent': 'compatibility',
                    'name': '🔗 Compatibility Agent',
                    'status': 'completed',
                    'duration': round(time.time() - stage2_start, 2),
                    'result': {
                        'basket': basket_v1,
                        'scenario': compatibility_result.get('scenario_used'),
                        'compatibility_score': compatibility_result.get('compatibility_score'),
                        'total_price': compatibility_result.get('total_price'),
                        'success': compatibility_result.get('success')
                    }
                })
                
                basket_current = basket_v1
            
            except Exception as e:
                logger.error(f"❌ Ошибка CompatibilityAgent: {e}", exc_info=True)
                stages.append({
                    'agent': 'compatibility',
                    'name': '🔗 Compatibility Agent',
                    'status': 'failed',
                    'error': str(e)
                })
                raise
            
            # ЭТАП 3: BUDGET AGENT
            logger.info("💰 Запуск BudgetAgent...")
            stage3_start = time.time()
            
            try:
                budget_result = self.budget_agent.optimize(
                    basket=basket_current,
                    budget_rub=budget_rub,
                    min_discount=0.2
                )
                
                basket_v2 = budget_result['basket']
                
                logger.info(f"✅ BudgetAgent: {len(budget_result['replacements'])} замен, экономия {budget_result['saved']:.2f}₽")
                
                stages.append({
                    'agent': 'budget',
                    'name': '💰 Budget Agent',
                    'status': 'completed',
                    'duration': round(time.time() - stage3_start, 2),
                    'result': {
                        'basket': basket_v2,
                        'saved': budget_result['saved'],
                        'replacements': budget_result['replacements'],
                        'within_budget': budget_result['within_budget'],
                        'optimized': len(budget_result['replacements']) > 0
                    }
                })
                
                basket_current = basket_v2
            
            except Exception as e:
                logger.error(f"❌ Ошибка BudgetAgent: {e}", exc_info=True)
                stages.append({
                    'agent': 'budget',
                    'name': '💰 Budget Agent',
                    'status': 'failed',
                    'error': str(e)
                })
                # НЕ падаем! Возвращаем корзину от CompatibilityAgent
                basket_current = basket_v1
                logger.warning("⚠️ Используем корзину без бюджетной оптимизации")
            
            # ЭТАП 4: PROFILE AGENT (заглушка)
            basket_v3 = basket_current
            
            stages.append({
                'agent': 'profile',
                'name': '👤 Profile Agent',
                'status': 'completed',
                'duration': 0.0,
                'result': {
                    'basket': basket_v3,
                    'personalized': False,
                    'message': 'В разработке'
                }
            })
            
            # ФОРМАТИРОВАНИЕ
            formatted_basket = []
            for item in basket_v3:
                formatted_item = {
                    **item,
                    'price_display': f"{item['price_per_unit']:.2f}₽/{item['unit']}",
                    'quantity_display': f"{item['quantity']:.2f}{item['unit']}",
                    'total_display': f"{item['total_price']:.2f}₽",
                    'breakdown': f"{item['quantity']:.2f}{item['unit']} × {item['price_per_unit']:.2f}₽ = {item['total_price']:.2f}₽"
                }
                formatted_basket.append(formatted_item)
            
            # ФИНАЛ
            total_price = sum(item['total_price'] for item in basket_v3)
            original_price = compatibility_result.get('total_price', total_price)
            savings = original_price - total_price
            
            execution_time = round(time.time() - start_time, 2)
            
            logger.info(f"🎉 Пайплайн завершён за {execution_time}с: {len(basket_v3)} товаров, {total_price:.2f}₽")
            
            return {
                'status': 'success',
                'parsed': parsed_query,
                'basket': formatted_basket,
                'summary': {
                    'items_count': len(basket_v3),
                    'total_price': round(total_price, 2),
                    'original_price': round(original_price, 2),
                    'savings': round(savings, 2),
                    'budget_rub': budget_rub,
                    'within_budget': total_price <= budget_rub,
                    'execution_time_sec': execution_time
                },
                'stages': stages,
                'metadata': {
                    'people': people,
                    'meal_types': meal_types,
                    'scenario_used': compatibility_result.get('scenario_used', {}).get('name'),
                    'strategy': 'smart'
                }
            }
        
        except Exception as e:
            logger.exception("❌ Критическая ошибка в пайплайне")
            
            return {
                'status': 'error',
                'message': str(e),
                'type': type(e).__name__,
                'parsed': parsed_query,
                'stages': stages
            }
