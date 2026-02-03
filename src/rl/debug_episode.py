# src/rl/debug_episode.py
"""
Детальное логирование одного эпизода для диагностики.
"""

from stable_baselines3 import PPO
from src.rl.train_shared_ppo import make_env

def debug_episode(model_path: str):
    """Запускает один эпизод и логирует каждый шаг."""
    
    model = PPO.load(model_path)
    env = make_env(seed=42)
    
    # ИСПРАВЛЕНО: Правильный способ добраться до базового окружения
    # ConcatVecEnv -> SB3VectorEnv -> MarkovVectorEnv -> PettingZooEnv -> BasketEnv
    try:
        # Попытка 1: через unwrapped
        base_env = env.unwrapped
        while hasattr(base_env, 'venv') or hasattr(base_env, 'par_env') or hasattr(base_env, 'env'):
            if hasattr(base_env, 'venv'):
                base_env = base_env.venv
            elif hasattr(base_env, 'par_env'):
                base_env = base_env.par_env
            elif hasattr(base_env, 'env'):
                base_env = base_env.env
            else:
                break
    except:
        # Попытка 2: если не получилось, просто используем env (будет меньше информации)
        base_env = None
        print("⚠️  Не удалось получить доступ к базовому окружению, логи будут ограничены\n")
    
    obs = env.reset()
    episode_reward = 0
    dones = [False]
    step = 0
    
    print("🔍 ДЕТАЛЬНЫЙ ЛОГ ЭПИЗОДА\n")
    print("=" * 70)
    
    while not all(dones) and step < 10:
        # Предсказываем действие
        action, _ = model.predict(obs, deterministic=True)
        
        print(f"\n📍 Шаг {step + 1}:")
        print(f"   Действия: {action}")
        
        # Выполняем шаг
        obs, rewards, dones, info = env.step(action)
        
        # Логируем rewards
        if hasattr(rewards, '__len__') and len(rewards) >= 3:
            step_reward = rewards.sum() if hasattr(rewards, 'sum') else sum(rewards)
            print(f"   Rewards: budget={rewards[0]:.2f}, compat={rewards[1]:.2f}, profile={rewards[2]:.2f} | Σ={step_reward:.2f}")
        else:
            step_reward = rewards if not hasattr(rewards, '__len__') else sum(rewards)
            print(f"   Total reward: {step_reward:.2f}")
        
        episode_reward += step_reward
        
        # Если удалось получить доступ к базовому env — показываем детали
        if base_env is not None and hasattr(base_env, 'cart'):
            print(f"   Корзина: {len(base_env.cart)} товаров, сумма={base_env.current_sum:.2f}₽")
            
            if len(base_env.cart) > 0:
                last_idx = base_env.cart[-1]
                product = base_env.products[last_idx]
                print(f"   └─ Последний: {product['product_name']} ({product['price_per_unit']:.2f}₽, {product['product_category']})")
            else:
                print(f"   └─ Корзина пустая (все агенты выбрали skip)")
        
        step += 1
    
    print("\n" + "=" * 70)
    print(f"📊 ИТОГО:")
    print(f"   Episode reward: {episode_reward:.2f}")
    
    # Детали корзины (если доступны)
    if base_env is not None and hasattr(base_env, 'cart'):
        print(f"   Товаров в корзине: {len(base_env.cart)}")
        print(f"   Потрачено: {base_env.current_sum:.2f}₽ / {base_env._budget:.2f}₽")
        
        if base_env.cart:
            print(f"\n🛒 Корзина:")
            categories = set()
            for idx in base_env.cart:
                p = base_env.products[idx]
                categories.add(p['product_category'])
                print(f"   • {p['product_name']} — {p['price_per_unit']:.2f}₽ [{p['product_category']}]")
            print(f"\n   Уникальных категорий: {len(categories)}")
        else:
            print(f"\n⚠️  Корзина пустая!")
    
    print("=" * 70)
    
    env.close()

if __name__ == "__main__":
    debug_episode("models/ppo_shared_v0.zip")
