"""
Collection of game-playing strategies for flip_7 simulation.

Each strategy implements the BaseStrategy interface and provides
different decision-making logic for automated gameplay.
"""

from flip_7.simulation.strategies.random import RandomStrategy
from flip_7.simulation.strategies.threshold import ThresholdStrategy

__all__ = [
    "RandomStrategy",
    "ThresholdStrategy",
]
