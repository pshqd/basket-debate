"""
Оценка обученной политики: запускаем 10 эпизодов и смотрим на результаты.
"""

from stable_baselines3 import PPO
from src.rl.train_shared_ppo import make_env

def evaluate_policy(model_path: str, n_episodes: int = 10):
    """Запускает обученную политику и выводит статистику."""
    
    # Загружаем модель
    model = PPO.load(model_path)
    print(f"✅ Модель загружена: {model_path}")
    
    # Создаём окружение (то же, что для обучения)
    env = make_env(seed=42)
    
    total_rewards = []
    
    for episode in range(n_episodes):
        obs = env.reset()
        episode_reward = 0
        dones = [False]  # <-- Теперь список/массив
        
        while not all(dones):  # <-- Проверяем, что ВСЕ агенты завершили
            action, _states = model.predict(obs, deterministic=True)
            obs, rewards, dones, info = env.step(action)  # <-- rewards и dones во множ. числе
            
            # Суммируем награды от всех агентов (vectorized env возвращает массив)
            episode_reward += rewards.sum() if hasattr(rewards, 'sum') else sum(rewards)

        
        total_rewards.append(episode_reward)
        print(f"Эпизод {episode+1}: reward = {episode_reward:.2f}")
    
    avg_reward = sum(total_rewards) / len(total_rewards)
    print(f"\n📊 Средняя награда за {n_episodes} эпизодов: {avg_reward:.2f}")
    
    env.close()

if __name__ == "__main__":
    evaluate_policy("models/ppo_shared_v0.zip", n_episodes=10)
