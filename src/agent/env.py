# src/agent/env.py
import numpy as np
from gymnasium import spaces
from pettingzoo import ParallelEnv


class BasketEnv(ParallelEnv):
    """
    MAS для корзины: 3 агента оптимизируют по запросу.
    
    Агенты:
    - budget_agent: минимизирует отклонение от бюджета
    - compat_agent: проверяет совместимость товаров
    - profile_agent: учитывает предпочтения пользователя
    """
    metadata = {"render_modes": ["human"], "name": "basket_mas_v0"}
    
    def __init__(
        self, 
        products,  
        constraints,  
        max_steps=10,
        render_mode = None
    ):
        """
        Args:
            budget: Бюджет в рублях
            max_steps: Максимальное количество шагов симуляции
            exclude_tags: Список запрещённых тегов (например, ['dairy'])
            include_tags: Список обязательных тегов (например, ['vegan'])
            meal_type: Тип приёма пищи (['breakfast', 'lunch', 'dinner', 'snack'])
            people: Количество человек
        """
        super().__init__()
        self.render_mode = render_mode
        self.products = products  
        self.constraints = constraints  
        self._max_steps = int(max_steps)

        # Извлекаем параметры из constraints
        self._budget = float(constraints.get("budget_rub", 1500))
        self.exclude_tags = constraints.get("exclude_tags", [])
        self.include_tags = constraints.get("include_tags", [])
        self.meal_type = constraints.get("meal_type", [])
        self.people = constraints.get("people", 1)

        # Агенты
        self.possible_agents = ["budget_agent", "compat_agent", "profile_agent"]
        self.agents = self.possible_agents.copy()
        
        # Пространства наблюдений и действий
        self._observation_spaces = {
            agent: spaces.Box(low=0, high=2.0, shape=(12,), dtype=np.float32) 
            for agent in self.possible_agents
        }

        num_actions = len(products) + 1  # +1 для действия "skip"
        self._action_spaces = {
            agent: spaces.Discrete(num_actions)
            for agent in self.possible_agents
        }
        
        # Состояние корзины
        self.current_sum = 0.0
        self.cart = []
        self.steps = 0
        self._cumulative_rewards = {agent: 0.0 for agent in self.possible_agents}
        self.last_actions = []
        self._precompute_product_stats()

    def observation_space(self, agent):
        return self._observation_spaces[agent]
    
    def action_space(self, agent):
        return self._action_spaces[agent]
    
    def reset(self, seed=None, options=None):
        """Сброс окружения."""
        if seed is not None:
            np.random.seed(seed)
        
        self.agents = self.possible_agents.copy()
        self.current_sum = 0.0
        self.cart = []
        self.steps = 0
        self._cumulative_rewards = {agent: 0.0 for agent in self.agents}
        self.last_actions = []
        
        # Формируем начальные наблюдения для каждого агента
        obs_dict = {}
        for agent in self.agents:
            # Используем метод _get_observation() (определим его ниже)
            obs_dict[agent] = self._get_observation(agent)
        
        # Мета-информация (доступна агентам)
        infos = {
            agent: {
                "budget": self._budget,
                "exclude_tags": self.exclude_tags,
                "include_tags": self.include_tags,
                "meal_type": self.meal_type,
                "people": self.people
            } 
            for agent in self.agents
        }
        
        return obs_dict, infos
    
    def step(self, actions):
        """
        Шаг симуляции. Каждый агент выбирает действие (добавить товар или пропустить).
        
        Args:
            actions: dict {agent_name: action_id}
        
        Returns:
            observations, rewards, terminations, truncations, infos
        """
        # Обрабатываем действия агентов
        for agent, action in actions.items():
            if action > 0:  # 0 = skip, 1..N = выбрать товар
                product_idx = action - 1  # action=1 → индекс 0 (первый товар)
                
                # Проверяем, что индекс в пределах списка
                if product_idx < len(self.products):
                    product = self.products[product_idx]  # Словарь с товаром
                    price = product["price_per_unit"]  # Реальная цена из БД
                    
                    # Проверяем, не превысим ли бюджет (допускаем +10%)
                    if self.current_sum + price <= self._budget * 1.1:
                        # Добавляем в корзину ИНДЕКС товара (не цену!)
                        # Потом по индексу достанем полную информацию
                        self.cart.append(product_idx)
                        self.current_sum += price

        
        self.steps += 1

        # === РАСЧЁТ НАГРАД (НОРМАЛИЗОВАННАЯ ВЕРСИЯ) ===
        rewards = {agent: 0.0 for agent in self.agents}

        # Константы для нормализации (чтобы reward был в диапазоне [-5, +5])
        MAX_REWARD = 5.0
        MIN_REWARD = -5.0

        # 1. BUDGET AGENT
        budget_diff = abs(self.current_sum - self._budget)
        budget_ratio = self.current_sum / self._budget if self._budget > 0 else 0

        # Штраф за отклонение (нормализованный от -2 до 0)
        normalized_budget_penalty = -(budget_diff / self._budget) * 2.0
        rewards["budget_agent"] += normalized_budget_penalty

        # Бонус за близость к бюджету (от 0 до +2)
        if 0.85 <= budget_ratio <= 1.05:  # 85%-105% идеально
            rewards["budget_agent"] += 2.0
        elif 0.7 <= budget_ratio <= 1.2:  # 70%-120% приемлемо
            rewards["budget_agent"] += 1.0

        # Бонус за наличие товаров (от 0 до +1)
        # Нормализуем: 0 товаров = 0, 10 товаров = +1
        cart_bonus = min(len(self.cart) / 10.0, 1.0)
        rewards["budget_agent"] += cart_bonus

        # 2. COMPATIBILITY AGENT
        if len(self.cart) > 0:
            # Базовый бонус за наличие товаров (от 0 до +0.5)
            rewards["compat_agent"] += min(len(self.cart) / 20.0, 0.5)
            
            if len(self.cart) > 1:
                # Разнообразие категорий
                categories = [self.products[idx]["product_category"] for idx in self.cart]
                unique_categories = len(set(categories))
                diversity_ratio = unique_categories / len(self.cart)
                
                # Бонус за разнообразие (от 0 до +2)
                rewards["compat_agent"] += diversity_ratio * 2.0
                
                # Штраф за однообразие (если все товары из 1 категории)
                if unique_categories == 1 and len(self.cart) >= 3:
                    rewards["compat_agent"] -= 3.0
                
                # Штраф за дубликаты
                from collections import Counter
                product_counts = Counter(self.cart)
                duplicate_penalty = 0
                for product_idx, count in product_counts.items():
                    if count > 2:
                        duplicate_penalty += 0.5 * (count - 2)
                rewards["compat_agent"] -= duplicate_penalty
        # НОВОЕ: Штраф за повторяющиеся действия между агентами
        # Если все 3 агента выбрали ОДИНАКОВОЕ действие → штраф
        unique_actions = len(set(actions.values()))
        if unique_actions == 1 and list(actions.values())[0] > 0:  # Все выбрали один товар (не skip)
            for agent in self.agents:
                rewards[agent] -= 3.0  # Штраф -1.0 за "стадное поведение"

        # НОВОЕ: Штраф за повторение того же действия, что и на прошлом шаге
        if len(self.last_actions) > 0:
            for agent, action in actions.items():
                if action in self.last_actions and action > 0:
                    rewards[agent] -= 0.5  # -0.5 за повторение прошлого действия

        # Сохраняем текущие действия для следующего шага
        self.last_actions = list(actions.values())

        # 3. PROFILE AGENT
        # Базовый бонус за наличие товаров (от 0 до +0.5)
        if len(self.cart) > 0:
            rewards["profile_agent"] += min(len(self.cart) / 20.0, 0.5)

        # Проверка тегов
        violation_count = 0
        match_count = 0

        for idx in self.cart:
            product = self.products[idx]
            product_tags = set(product["tags"])
            
            # Штраф за нарушение exclude_tags
            if product_tags & set(self.exclude_tags):
                violation_count += 1
            
            # Бонус за соответствие include_tags
            if self.include_tags and product_tags & set(self.include_tags):
                match_count += 1

        # Нормализованные штрафы/бонусы
        rewards["profile_agent"] -= violation_count * 1.0  # -1 за каждое нарушение
        rewards["profile_agent"] += match_count * 0.5      # +0.5 за каждое совпадение
                        
        # Обновляем накопленные награды
        for agent, r in rewards.items():
            self._cumulative_rewards[agent] += r
        
        # === НОВЫЕ НАБЛЮДЕНИЯ ===
        obs = {}
        for agent in self.agents:
            obs[agent] = self._get_observation(agent)
        
        # === ПРОВЕРКА ЗАВЕРШЕНИЯ ===
        done = self.steps >= self._max_steps

        # НОВОЕ: Финальный штраф за недостаток разнообразия
        if done and len(self.cart) >= 3:
            categories = [self.products[idx]["product_category"] for idx in self.cart]
            unique_categories = len(set(categories))
            
            if unique_categories < 3:
                for agent in self.agents:
                    rewards[agent] -= 2.0

        # КЛИППИНГ В КОНЦЕ (после всех штрафов и бонусов)
        for agent in rewards:
            rewards[agent] = max(MIN_REWARD, min(MAX_REWARD, rewards[agent]))

        # Обновляем накопленные награды
        for agent, r in rewards.items():
            self._cumulative_rewards[agent] += r

        terms = {agent: done for agent in self.agents}
        truncs = {agent: False for agent in self.agents}

        
        infos = {
            agent: {
                "cart_sum": self.current_sum, 
                "cart_size": len(self.cart),
                "cumulative_reward": self._cumulative_rewards[agent]
            } 
            for agent in self.agents
        }
        
        # Если эпизод завершён, убираем агентов
        if done:
            self.agents = []
        
        return obs, rewards, terms, truncs, infos
    
    def render(self):
        if self.render_mode in (None, "human"):
            print(f"Step {self.steps}: Cart={self.cart}, Sum={self.current_sum:.2f}")
            return None
        if self.render_mode == "ansi":
            return f"Step {self.steps}: Cart={self.cart}, Sum={self.current_sum:.2f}"
        return None

    
    def close(self):
        """Очистка ресурсов."""
        pass

    def _get_observation(self, agent: str) -> np.ndarray:
        """
        Формирует observation для агента.
        
        Observation (12 чисел, все в диапазоне [0, ~2]):
        1. budget_remaining_ratio — остаток бюджета (1.0 = весь бюджет остался)
        2. spent_ratio — потрачено денег (0.5 = потрачено 50%)
        3. cart_size_ratio — заполненность корзины (0.3 = 3 товара из 10)
        4. avg_price_ratio — средняя цена товара (нормализованная)
        5. step_progress — прогресс эпизода (0.5 = шаг 5 из 10)
        6. unique_categories_ratio — разнообразие категорий
        7. violation_ratio — доля товаров с запрещёнными тегами
        8. match_ratio — доля товаров с нужными тегами
        9-12. резерв (пока нули, можно добавить GNN embeddings позже)
        """
        
        # 1. Остаток бюджета (0 = всё потрачено, 1 = ничего не потрачено)
        budget_remaining_ratio = (self._budget - self.current_sum) / self._budget if self._budget > 0 else 0
        budget_remaining_ratio = max(0, min(1, budget_remaining_ratio))  # клиппинг в [0, 1]
        
        # 2. Потрачено денег (0 = ничего, 1 = весь бюджет)
        spent_ratio = self.current_sum / self._budget if self._budget > 0 else 0
        spent_ratio = min(1.2, spent_ratio)  # допускаем перерасход до 120%
        
        # 3. Заполненность корзины (0 = пусто, 1 = max_steps товаров)
        cart_size_ratio = len(self.cart) / self._max_steps
        
        # 4. Средняя цена товара в корзине (нормализованная)
        if len(self.cart) > 0:
            avg_price = self.current_sum / len(self.cart)
            target_avg_price = self._budget / 10  # ожидаемая средняя цена
            avg_price_ratio = avg_price / target_avg_price if target_avg_price > 0 else 0
        else:
            avg_price_ratio = 0.0
        avg_price_ratio = min(2.0, avg_price_ratio)  # ограничиваем 200%
        
        # 5. Прогресс эпизода (0 = начало, 1 = конец)
        step_progress = self.steps / self._max_steps
        
        # 6. Разнообразие категорий
        if len(self.cart) > 1:
            categories = [self.products[idx]["product_category"] for idx in self.cart]
            unique_categories = len(set(categories))
            unique_categories_ratio = unique_categories / len(self.cart)
        else:
            unique_categories_ratio = 0.0
        
        # 7. Доля товаров с запрещёнными тегами (violations)
        violation_count = 0
        if len(self.cart) > 0:
            for idx in self.cart:
                product_tags = set(self.products[idx]["tags"])
                if product_tags & set(self.exclude_tags):
                    violation_count += 1
            violation_ratio = violation_count / len(self.cart)
        else:
            violation_ratio = 0.0
        
        # 8. Доля товаров с нужными тегами (matches)
        match_count = 0
        if len(self.cart) > 0 and self.include_tags:
            for idx in self.cart:
                product_tags = set(self.products[idx]["tags"])
                if product_tags & set(self.include_tags):
                    match_count += 1
            match_ratio = match_count / len(self.cart)
        else:
            match_ratio = 0.0
        
        # 9-12. Используем предвычисленные агрегаты (из __init__)
        avg_available_price_ratio = self.avg_available_price / (self._budget / 10) if self._budget > 0 else 0
        avg_available_price_ratio = min(2.0, avg_available_price_ratio)

        num_available_categories_ratio = self.num_available_categories / 10.0

        reserved = [
            avg_available_price_ratio,       # 9
            num_available_categories_ratio,  # 10
            self.valid_products_ratio,       # 11 (предвычислено)
            0.0                              # 12 (резерв)
        ]
        
        obs = np.array([
            budget_remaining_ratio,  # 1
            spent_ratio,             # 2
            cart_size_ratio,         # 3
            avg_price_ratio,         # 4
            step_progress,           # 5
            unique_categories_ratio, # 6
            violation_ratio,         # 7
            match_ratio,             # 8
            *reserved                # 9-12
        ], dtype=np.float32)
        
        return obs
    
    def _precompute_product_stats(self):
        """Предвычисляет статистику товаров (вызывается один раз в __init__)."""
        
        # Средняя цена доступных товаров
        available_prices = [p["price_per_unit"] for p in self.products if p["price_per_unit"] > 0]
        self.avg_available_price = np.mean(available_prices) if available_prices else 0
        
        # Количество уникальных категорий
        available_categories = set(p["product_category"] for p in self.products if p["price_per_unit"] > 0)
        self.num_available_categories = len(available_categories)
        
        # Доля валидных товаров (без запрещённых тегов)
        valid_count = 0
        total_count = len([p for p in self.products if p["price_per_unit"] > 0])
        for p in self.products:
            if p["price_per_unit"] > 0:
                p_tags = set(p["tags"])
                if not (p_tags & set(self.exclude_tags)):
                    valid_count += 1
        self.valid_products_ratio = valid_count / total_count if total_count > 0 else 0

def create_basket_env(products, constraints, max_steps=10,render_mode=None):
    """
    Factory-функция для создания окружения.
    
    Args:
        products: список товаров из БД (каждый = словарь)
        constraints: словарь с параметрами запроса (budget_rub, exclude_tags, ...)
        max_steps: количество шагов симуляции
    
    Returns:
        BasketEnv: окружение с реальными товарами
    """
    return BasketEnv(
        products=products,
        constraints=constraints,
        max_steps=int(max_steps),
        render_mode=render_mode
    )
