# src/rl/compare_policies.py
"""
Сравнение обученной политики с random baseline.
"""

from stable_baselines3 import PPO
from src.rl.train_shared_ppo import make_env
import numpy as np

def test_random_policy(n_episodes: int = 10):
    """Тестируем случайные действия (baseline)."""
    env = make_env(seed=42)
    rewards = []
    
    for _ in range(n_episodes):
        obs = env.reset()
        episode_reward = 0
        dones = [False]
        
        while not all(dones):
            # Случайное действие (как раньше)
            action = [env.action_space.sample() for _ in range(env.num_envs)]
            obs, rew, dones, info = env.step(action)
            episode_reward += rew.sum() if hasattr(rew, 'sum') else sum(rew)
        
        rewards.append(episode_reward)
    
    env.close()
    return np.mean(rewards)

def test_trained_policy(model_path: str, n_episodes: int = 10):
    """Тестируем обученную политику."""
    model = PPO.load(model_path)
    env = make_env(seed=42)
    rewards = []
    
    for _ in range(n_episodes):
        obs = env.reset()
        episode_reward = 0
        dones = [False]
        
        while not all(dones):
            action, _ = model.predict(obs, deterministic=True)
            obs, rew, dones, info = env.step(action)
            episode_reward += rew.sum() if hasattr(rew, 'sum') else sum(rew)
        
        rewards.append(episode_reward)
    
    env.close()
    return np.mean(rewards)

if __name__ == "__main__":
    print("🔍 Сравнение политик:\n")
    
    print("1️⃣  Random baseline...")
    random_reward = test_random_policy(n_episodes=20)
    print(f"   → Средняя награда: {random_reward:.2f}\n")
    
    print("2️⃣  Обученная PPO...")
    trained_reward = test_trained_policy("models/ppo_shared_v0.zip", n_episodes=20)
    print(f"   → Средняя награда: {trained_reward:.2f}\n")
    
    improvement = ((trained_reward - random_reward) / abs(random_reward)) * 100
    
    print("=" * 60)
    print(f"📈 Улучшение: {improvement:+.1f}%")
    if improvement > 50:
        print("   ✅ Обучение работает отлично!")
    elif improvement > 20:
        print("   ⚠️  Обучение работает, но есть потенциал")
    else:
        print("   ❌ Обучение почти не помогло")
    print("=" * 60)
