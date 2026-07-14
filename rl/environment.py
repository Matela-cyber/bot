from __future__ import annotations

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError:  # pragma: no cover - fallback for missing optional deps
    class _DummyGym:
        pass

    gym = _DummyGym()
    spaces = None


class TradingEnv(getattr(gym, "Env", object)):
    """A simple Gym environment for trade action selection."""

    metadata = {"render_modes": ["human"]}

    def __init__(self) -> None:
        super().__init__()
        if spaces is None:
            self.action_space = None
            self.observation_space = None
        else:
            self.action_space = spaces.Discrete(5)
            self.observation_space = spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32)
        self.state = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if hasattr(super(), "reset"):
            super().reset(seed=seed)
        self.state = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        return self.state, {}

    def step(self, action: int):
        reward = 0.0 if action == 0 else 0.1
        self.state = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        terminated = False
        truncated = False
        return self.state, reward, terminated, truncated, {}
