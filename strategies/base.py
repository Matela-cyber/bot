"""Base strategy class."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime

import pandas as pd

from core.data_models import Signal


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame, current_time: datetime) -> Optional[Signal]:
        pass

    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        pass

    def should_enter(self, data: pd.DataFrame, signal: Signal) -> bool:
        return True

    def should_exit(self, data: pd.DataFrame, trade: Trade) -> bool:
        return False
