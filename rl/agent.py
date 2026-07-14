from __future__ import annotations

try:
    from stable_baselines3 import PPO
except ImportError:  # pragma: no cover - fallback for missing optional deps
    PPO = None

from rl.environment import TradingEnv


class PPOAgent:
    """Thin wrapper around Stable-Baselines3 PPO."""

    def __init__(self) -> None:
        self.env = TradingEnv()
        if PPO is None:
            self.model = None
        else:
            self.model = PPO("MlpPolicy", self.env, verbose=0)

    def train(self, total_timesteps: int = 1000) -> None:
        if self.model is None:
            raise RuntimeError("stable-baselines3 is not installed")
        self.model.learn(total_timesteps=total_timesteps)

    def predict(self, observation):
        if self.model is None:
            return None, None
        return self.model.predict(observation)
