# src/rl/train_shared_ppo.py
"""
Простой учебный пайплайн: обучаем shared PPO политику для всех агентов.

Пайплайн:
1. Создаём среду с фиксированным K=100 кандидатов
2. Применяем обёртки SuperSuit (pad_action_space, pad_observations)
3. Конвертируем PettingZoo → VectorEnv
4. Обучаем PPO на 50k шагов
5. Сохраняем модель
"""

import supersuit as ss
from stable_baselines3 import PPO

from src.backend.db.queries import fetch_candidate_products
from src.agent.env import create_basket_env
from src.agent.utils import pad_products_to_k

# КОНСТАНТА: фиксированное количество кандидатов
K = 100


def make_env(seed: int = 0):
    """
    Создаёт окружение для обучения.
    
    Ключевая особенность: фиксируем K=100 товаров, чтобы action_space был стабильным.
    """
    # 1. Фиксированные constraints для обучения
    constraints = {
        "budget_rub": 1500,
        "exclude_tags": ["dairy"],
        "include_tags": [],
        "meal_type": ["dinner"],
        "people": 3,
    }
    
    # 2. Фильтруем товары из БД
    products = fetch_candidate_products(constraints, limit=K)
    print(f"[INFO] Fetched {len(products)} products from DB")
    
    # 3. ВАЖНО: Паддим до K (добавляем dummy items, если меньше)
    products = pad_products_to_k(products, k=K)
    print(f"[INFO] Padded to {len(products)} products (K={K})")
    
    # 4. Создаём окружение
    env = create_basket_env(
        products=products,
        constraints=constraints,
        max_steps=10,
        render_mode=None  # <-- ВАЖНО: передаём render_mode
    )
    
    # 5. Обёртки SuperSuit (паддинг пространств)
    # pad_action_space: приводит action space всех агентов к одному размеру
    env = ss.pad_action_space_v0(env)
    
    # pad_observations: приводит observation space к одному размеру
    env = ss.pad_observations_v0(env)
    
    # 6. Конвертируем PettingZoo ParallelEnv → VectorEnv для SB3
    env = ss.pettingzoo_env_to_vec_env_v1(env)
    
    # 7. Обёртка для совместимости с SB3
    env = ss.concat_vec_envs_v1(env, 1, num_cpus=0, base_class="stable_baselines3")
    
    return env


if __name__ == "__main__":
    print("=" * 60)
    print("Простой учебный пайплайн: Shared PPO для BasketEnv")
    print("=" * 60)
    
    # Создаём окружение
    print("\n[1/4] Создаём окружение...")
    env = make_env(seed=0)
    print(f"✅ Окружение создано: action_space={env.action_space}, obs_space={env.observation_space}")
    
    # Создаём модель PPO (shared policy для всех агентов)
    print("\n[2/4] Инициализируем PPO...")
    model = PPO(
        "MlpPolicy",  # Простая fully-connected сеть
        env,
        verbose=1,    # Логи в консоль
        n_steps=1024, # Сколько шагов собирать перед обновлением
        batch_size=256,
        learning_rate=3e-4,
        tensorboard_log="./logs/ppo_basket/"  # Логи для TensorBoard
    )
    print("✅ PPO создан")
    
    # Обучаем модель
    print("\n[3/4] Обучаем модель (50k шагов)...")
    model.learn(total_timesteps=50_000)
    print("✅ Обучение завершено")
    
    # Сохраняем модель
    print("\n[4/4] Сохраняем модель...")
    model.save("models/ppo_shared_v0")
    print("✅ Модель сохранена в models/ppo_shared_v0.zip")
    
    env.close()
    print("\n" + "=" * 60)
    print("🎉 Обучение завершено! Используй модель через model.load()")
    print("=" * 60)
